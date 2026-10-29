from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import threading
import io
import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from random import shuffle
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import xbmcvfs
import xbmc
import xbmcaddon
import requests
from six.moves.urllib.parse import urljoin, urlparse, urlsplit
from six import ensure_text

from .valence import api
from .lazylogger import LazyLogger
from .item_functions import get_art
from .utils import translate_path, load_user_details

pil_loaded = False
try:
    from PIL import Image, ImageOps
    pil_loaded = True
except ImportError:
    pil_loaded = False

PORT_NUMBER = 24276
PORT_SCAN_LIMIT = 32
_stream_lock = threading.RLock()
_stream_sessions = {}
log = LazyLogger(__name__)


def _origin(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return None
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    return parts.scheme.lower(), parts.hostname.lower(), port


def register_stream(manifest_url, is_manifest=True):
    """Register a stream with Kodi's long-lived service proxy over loopback."""
    server_url = api.server or xbmcaddon.Addon().getSetting('server_address')
    if not server_url:
        log.error('Cannot register Valence playback without a server address')
        return None
    full_url = urljoin(server_url.rstrip('/') + '/', manifest_url)
    server_origin = _origin(server_url)
    if not server_origin or _origin(full_url) != server_origin:
        log.error('Cannot proxy Valence playback manifest from an unexpected origin')
        return None

    api_key = api.session.headers.get('X-Api-Key')
    if not api_key:
        log.error('Cannot register Valence playback without an API key')
        return None

    payload = json.dumps({
        'url': full_url,
        'is_manifest': bool(is_manifest),
    }).encode('utf-8')
    signature = hmac.new(
        api_key.encode('utf-8'), payload, hashlib.sha256).hexdigest()

    # The service runs in a different Kodi Python runtime, so its in-memory
    # stream registry cannot be reached directly from a plugin invocation.
    # Locate the service listener, then ask it to register the stream. The API
    # key is used only to sign the loopback request and is never sent or logged.
    registration_started = time.time()
    for attempt in range(3):
        for port in range(PORT_NUMBER, PORT_NUMBER + PORT_SCAN_LIMIT):
            base = 'http://127.0.0.1:{}'.format(port)
            try:
                ready = requests.get(
                    base + '/valence-stream/health',
                    timeout=(0.2, 0.5), allow_redirects=False)
                ready.close()
                if ready.status_code != 204:
                    continue
                response = requests.post(
                    base + '/valence-stream/register',
                    data=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'X-ValenceCon-Signature': signature,
                    },
                    timeout=(0.5, 2), allow_redirects=False,
                )
                try:
                    if response.status_code != 201:
                        log.error('Kodi service rejected Valence stream registration')
                        return None
                    result = response.json()
                finally:
                    response.close()
                path = result.get('path')
                if path:
                    log.info('Valence stream proxy registration completed in {:.2f}s'.format(
                        time.time() - registration_started))
                    return base + path
                log.error('Kodi service returned an invalid Valence stream registration')
                return None
            except requests.exceptions.RequestException:
                continue
            except Exception as error:
                log.warning('Valence stream registration failed: {}'.format(
                    type(error).__name__))
                return None
        if attempt < 2:
            time.sleep(0.25)

    log.error('Kodi service stream proxy is unavailable after {:.2f}s'.format(
        time.time() - registration_started))
    return None


def _register_service_stream(handler):
    """Validate an authenticated local registration and store it in service."""
    if not handler.client_address or handler.client_address[0] not in (
            '127.0.0.1', '::1'):
        handler.send_error(403)
        return

    try:
        content_length = int(handler.headers.get('Content-Length', '0'))
    except (TypeError, ValueError):
        handler.send_error(400)
        return
    if content_length <= 0 or content_length > 16384:
        handler.send_error(400)
        return

    payload = handler.rfile.read(content_length)
    settings = xbmcaddon.Addon()
    user_details = load_user_details()
    api_key = (settings.getSetting('api_key') or
               user_details.get('api_key') or
               api.session.headers.get('X-Api-Key'))
    signature = handler.headers.get('X-ValenceCon-Signature', '')
    expected = hmac.new(
        ensure_text(api_key).encode('utf-8'), payload, hashlib.sha256
    ).hexdigest() if api_key else ''
    if not expected or not hmac.compare_digest(signature, expected):
        handler.send_error(403)
        return

    try:
        data = json.loads(payload.decode('utf-8'))
        server_url = settings.getSetting('server_address') or api.server
        target_url = data.get('url')
        full_url = urljoin(server_url.rstrip('/') + '/', target_url)
        server_origin = _origin(server_url)
        if (not server_origin or _origin(full_url) != server_origin or
                not isinstance(data.get('is_manifest'), bool)):
            handler.send_error(400)
            return
    except Exception:
        handler.send_error(400)
        return

    stream_id = uuid.uuid4().hex
    with _stream_lock:
        now = time.time()
        for old_id in list(_stream_sessions):
            if now - _stream_sessions[old_id]['created'] > 12 * 60 * 60:
                del _stream_sessions[old_id]
        _stream_sessions[stream_id] = {
            'manifest_url': full_url,
            'origin': server_origin,
            'api_key': api_key,
            'user_agent': api.session.headers.get('User-Agent', 'ValenceCon'),
            'verify': settings.getSetting('verify_cert') == 'true',
            'created': now,
            'resources': {},
            'is_manifest': data['is_manifest'],
            'head_metadata': {},
        }
    resource_name = 'manifest.m3u8' if data['is_manifest'] else 'media'
    response = json.dumps({
        'path': '/valence-stream/{}/{}'.format(stream_id, resource_name),
    }).encode('utf-8')
    handler.send_response(201)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(response)))
    handler.end_headers()
    handler.wfile.write(response)


def _register_stream_resource(stream_id, upstream_url):
    alias = uuid.uuid4().hex
    with _stream_lock:
        stream = _stream_sessions.get(stream_id)
        if not stream:
            return None
        stream['resources'][alias] = upstream_url
    return '/valence-stream/{}/resource/{}'.format(stream_id, alias)


def get_image_links(url):

    settings = xbmcaddon.Addon()
    server = settings.getSetting('server_address')
    if server is None:
        return []

    # Valence image URLs use their own path and query format
    # Just ensure we have the right fields
    if 'fields=' not in url and 'limit=' not in url:
        # Add default fields if not present
        pass

    result = api.get(url)

    # Valence returns items in "items" array or directly
    items = result.get("items") or result.get("shows") or result.get("albums") or []
    if not items:
        return []

    art_urls = []
    for item in items:
        art = get_art(item=item, server=server)
        art_urls.append(art)

    shuffle(art_urls)

    return art_urls


def build_image(path):
    log.debug("build_image()")

    log.debug("Request Path : {0}".format(path))

    request_path = path[1:]

    if request_path == "favicon.ico":
        return []

    decoded_url = ensure_text(base64.b64decode(request_path))
    log.debug("decoded_url : {0}".format(decoded_url))

    image_urls = get_image_links(decoded_url)

    width, height = 500, 750
    collage = Image.new('RGB', (width, height), (5, 5, 5))

    cols = 2
    rows = 2
    thumbnail_width = int(width / cols)
    thumbnail_height = int(height / rows)
    size = (thumbnail_width, thumbnail_height)
    image_count = 0

    for art in image_urls:

        thumb_url = art.get("thumb")
        if thumb_url:
            url_bits = urlparse(thumb_url.strip())

            host_name = url_bits.hostname
            port = url_bits.port
            url_path = url_bits.path
            url_query = url_bits.query

            server = "%s:%s" % (host_name, port)
            url_full_path = url_path + "?" + url_query

            log.debug("Loading image from : {0} {1} {2}".format(image_count, server, url_full_path))

            try:
                image_response = requests.get(thumb_url)
                image_data = image_response.content

                loaded_image = Image.open(io.BytesIO(image_data))
                image = ImageOps.fit(loaded_image, size, method=Image.ANTIALIAS, bleed=0.0, centering=(0.5, 0.5))

                x = int(image_count % cols) * thumbnail_width
                y = int(image_count/cols) * thumbnail_height
                collage.paste(image, (x, y))

                del loaded_image
                del image
                del image_data

            except Exception as con_err:
                log.debug("Error loading image : {0}".format(con_err))

            image_count += 1

        if image_count == cols * rows:
            break

    del image_urls

    img_byte_arr = io.BytesIO()
    collage.save(img_byte_arr, format='JPEG')
    image_bytes = img_byte_arr.getvalue()

    return image_bytes


class HttpImageHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        if self.path.startswith('/valence-stream/'):
            # The URL contains an opaque playback-session handle. Keep it out
            # of Kodi's log, but retain the status code for playback diagnosis.
            status = args[1] if len(args) > 1 else 'unknown'
            log.debug('Valence stream proxy returned HTTP {}'.format(status))
            return
        log_line = format % args
        log.debug(log_line)
        return

    def do_GET(self):
        if urlparse(self.path).path == '/valence-stream/health':
            self.send_response(204)
            self.end_headers()
            return
        if self.path.startswith('/valence-stream/'):
            self.serve_stream()
            return
        log.debug("HttpImageHandler:do_GET()")
        self.serve_image()
        return

    def do_POST(self):
        if urlparse(self.path).path == '/valence-stream/register':
            _register_service_stream(self)
            return
        self.send_error(404)

    def do_HEAD(self):
        if self.path.startswith('/valence-stream/'):
            self.serve_stream(head_only=True)
            return
        log.debug("HttpImageHandler:do_HEAD()")
        self.send_response(200)
        self.end_headers()
        return

    def _stream_target(self):
        parts = [part for part in urlparse(self.path).path.split('/') if part]
        if len(parts) < 2 or parts[0] != 'valence-stream':
            return None, None
        stream_id = parts[1]
        with _stream_lock:
            stream = _stream_sessions.get(stream_id)
            if not stream:
                return None, None
            stream = dict(stream)
            if len(parts) == 3 and parts[2] == 'manifest.m3u8':
                target = stream['manifest_url']
            elif len(parts) == 3 and parts[2] == 'media':
                target = stream['manifest_url']
            elif len(parts) == 4 and parts[2] == 'resource':
                target = stream['resources'].get(parts[3])
            else:
                target = None
        return stream, target

    def _fetch_stream_response(self, stream, target):
        request_headers = {
            'User-Agent': stream['user_agent'],
            'Accept': '*/*',
            'Accept-Encoding': 'identity',
        }
        if self.headers.get('Range'):
            request_headers['Range'] = self.headers['Range']

        response = None
        for _ in range(6):
            # The API key is attached only to the configured Valence origin;
            # a redirect to a media host never receives the credential.
            if _origin(target) == stream['origin'] and stream.get('api_key'):
                request_headers['X-Api-Key'] = stream['api_key']
            else:
                request_headers.pop('X-Api-Key', None)
            response = requests.get(
                target,
                headers=request_headers,
                verify=stream['verify'],
                timeout=(5, 30),
                stream=True,
                allow_redirects=False,
            )
            if response.status_code not in (301, 302, 303, 307, 308):
                return response, target
            location = response.headers.get('Location')
            response.close()
            if not location:
                return None, None
            target = urljoin(target, location)
            if _origin(target) is None:
                return None, None
        return None, None

    def _cache_stream_head_metadata(self, stream, target, response):
        """Remember headers for a later local HEAD without forwarding it."""
        content_range = response.headers.get('Content-Range', '')
        total_match = re.match(r'^bytes\s+\d+-\d+/(\d+|\*)$', content_range,
                               re.IGNORECASE)
        content_length = None
        if total_match and total_match.group(1) != '*':
            content_length = total_match.group(1)
        elif response.status_code == 200:
            content_length = response.headers.get('Content-Length')

        with _stream_lock:
            metadata = stream.get('head_metadata')
            if metadata is None:
                return
            metadata = metadata.setdefault(target, {})
            content_type = response.headers.get('Content-Type')
            if content_type:
                metadata['content_type'] = content_type
            if content_length:
                metadata['content_length'] = content_length
            for header, key in (('Last-Modified', 'last_modified'),
                                ('ETag', 'etag')):
                value = response.headers.get(header)
                if value:
                    metadata[key] = value

    def _serve_stream_head(self, stream, target, manifest_request=False):
        """Answer Kodi's stat probe immediately from cached stream metadata."""
        with _stream_lock:
            all_metadata = stream.get('head_metadata') or {}
            metadata = dict(all_metadata.get(target) or {})

        self.send_response(200)
        content_type = metadata.get('content_type')
        if not content_type and manifest_request:
            content_type = 'application/vnd.apple.mpegurl'
        self.send_header('Content-Type', content_type or
                         'application/octet-stream')
        self.send_header('Accept-Ranges', 'bytes')
        content_length = metadata.get('content_length')
        if content_length and not manifest_request:
            self.send_header('Content-Length', content_length)
        for key, header in (('last_modified', 'Last-Modified'),
                            ('etag', 'ETag')):
            value = metadata.get(key)
            if value:
                self.send_header(header, value)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        log.debug('Valence stream HEAD answered from local metadata cached={}'.format(
            bool(metadata.get('content_type'))))

    def _rewrite_manifest(self, body, stream_id, base_url):
        text = body.decode('utf-8-sig', 'replace')

        def proxy_uri(uri):
            upstream = urljoin(base_url, uri.strip())
            if _origin(upstream) is None:
                return uri
            return _register_stream_resource(stream_id, upstream) or uri

        rewritten = []
        for line in text.splitlines():
            if line.startswith('#'):
                line = re.sub(
                    r'(?i)(\bURI=)(["\'])([^"\']+)(["\'])',
                    lambda match: match.group(1) + match.group(2) +
                    proxy_uri(match.group(3)) + match.group(4), line)
            elif line.strip():
                prefix = line[:len(line) - len(line.lstrip())]
                suffix = line[len(line.rstrip()):]
                line = prefix + proxy_uri(line.strip()) + suffix
            rewritten.append(line)
        return ('\n'.join(rewritten) + '\n').encode('utf-8')

    def serve_stream(self, head_only=False):
        stream, target = self._stream_target()
        if not stream or not target:
            self.send_error(404)
            return

        if head_only:
            manifest_request = (urlparse(self.path).path.endswith(
                '/manifest.m3u8'))
            self._serve_stream_head(stream, target, manifest_request)
            return

        stream_id = urlparse(self.path).path.split('/')[2]
        request_started = time.time()
        try:
            response, final_url = self._fetch_stream_response(stream, target)
            if response is None:
                self.send_error(502)
                return

            self._cache_stream_head_metadata(stream, target, response)

            status = response.status_code
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            log.info('Valence stream upstream returned HTTP {} type={} range={} headers_elapsed={:.2f}s'.format(
                status, content_type, bool(self.headers.get('Range')),
                time.time() - request_started))
            is_manifest = (
                not head_only and status == 200 and
                ('mpegurl' in content_type.lower() or
                 urlparse(final_url).path.lower().endswith('.m3u8'))
            )

            if is_manifest:
                body = response.content
                response.close()
                if len(body) > 4 * 1024 * 1024:
                    self.send_error(502)
                    return
                body = self._rewrite_manifest(body, stream_id, final_url)
                self.send_response(status)
                self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(status)
            for header in ('Content-Type', 'Content-Length', 'Content-Range',
                           'Accept-Ranges', 'Last-Modified', 'ETag'):
                value = response.headers.get(header)
                if value:
                    self.send_header(header, value)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if not head_only and status not in (204, 304):
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        self.wfile.write(chunk)
        except Exception as error:
            log.warning('Valence stream proxy failed: {}'.format(type(error).__name__))
            try:
                self.send_error(502)
            except Exception:
                pass
        finally:
            if 'response' in locals() and response is not None:
                response.close()

    def serve_image(self):

        if pil_loaded:

            image_bytes = build_image(self.path)
            self.send_response(200)
            self.send_header('Content-type', 'image/jpeg')
            self.send_header('Content-Length', str(len(image_bytes)))
            self.end_headers()
            self.wfile.write(image_bytes)

        else:

            image_path = translate_path("special://home/addons/plugin.video.valencecon/icon.png")
            self.send_response(200)
            self.send_header('Content-type', 'image/png')
            modified = xbmcvfs.Stat(image_path).st_mtime()
            self.send_header('Last-Modified', "%s" % modified)
            image = xbmcvfs.File(image_path)
            size = image.size()
            self.send_header('Content-Length', str(size))
            self.end_headers()
            self.wfile.write(image.readBytes())
            image.close()
            del image


class HttpImageServerThread(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.keep_running = True
        self.server = None

    def stop(self):
        log.debug("HttpImageServerThread:stop called")
        self.keep_running = False
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        with _stream_lock:
            _stream_sessions.clear()

    def run(self):
        log.debug("HttpImageServerThread:started")
        try:
            # Prefer the historical port, then find a free loopback port if a
            # second Kodi/add-on service instance is already using it.
            last_error = None
            for port in range(PORT_NUMBER, PORT_NUMBER + 32):
                try:
                    self.server = ThreadingHTTPServer(
                        ('127.0.0.1', port), HttpImageHandler)
                    self.server.daemon_threads = True
                    break
                except OSError as error:
                    last_error = error
                    self.server = None
            if self.server is None:
                log.error('Unable to start local image/stream server: {}'.format(
                    type(last_error).__name__ if last_error else 'unknown error'))
                return
            log.info('Local image/stream server started on loopback')
            self.server.serve_forever(poll_interval=0.5)
        finally:
            if self.server is not None:
                self.server.server_close()
            self.server = None
            log.debug("HttpImageServerThread:exiting")
