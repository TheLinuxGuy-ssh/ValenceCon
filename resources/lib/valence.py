from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import json
import re
import time
import requests
import xbmcaddon
from kodi_six.utils import py2_decode
from six.moves.urllib.parse import quote, urlsplit

from .utils import get_device_id, get_version, load_user_details
from .lazylogger import LazyLogger

log = LazyLogger(__name__)


def _safe_api_path(path):
    """Return an API route suitable for logs without host, query, or item IDs."""
    parsed = urlsplit(path)
    route = parsed.path if parsed.scheme else path.split('?', 1)[0]
    parts = [part for part in route.split('/') if part]
    if parts and parts[0] == 'api':
        parts = parts[1:]

    safe_parts = []
    for part in parts:
        if re.match(r'^[0-9a-fA-F-]{16,}$', part) or part.isdigit():
            safe_parts.append('{id}')
        else:
            safe_parts.append(part)
    return '/' + '/'.join(safe_parts)


class ValenceAPI:
    user_id = None

    def __init__(self, server=None, api_key=None, profile_id=None):
        self.server = server
        self.api_key = api_key
        self.profile_id = profile_id
        self.settings = xbmcaddon.Addon()
        self._settings_server_address = self.settings.getSetting('server_address')
        self._settings_api_key = self.settings.getSetting('api_key')
        if self._settings_api_key:
            self.api_key = self._settings_api_key
        self.session = requests.Session()
        self.verify_cert = self.settings.getSetting('verify_cert') == 'true'
        self.last_error = None
        
        self._setup_session()

    def _setup_session(self):
        """Configure session with default headers"""
        device_name = self.settings.getSetting('deviceName')
        if len(device_name) == 0:
            device_name = "ValenceCon"
        device_name = py2_decode(device_name).replace('"', '_').replace(',', '_')
        device_id = get_device_id()
        version = get_version()

        self.session.headers.update({
            'User-Agent': 'ValenceCon/{} Kodi/{} ({})'.format(version, get_version(), device_name),
            'Accept': 'application/json',
            'X-Client-Name': 'ValenceCon',
            'X-Client-Version': version,
            'X-Device-Id': device_id,
            'X-Device-Name': device_name,
        })
        
        if self.api_key:
            self.session.headers['X-Api-Key'] = self.api_key

    def reconfigure(self, server=None, api_key=None):
        """Update the server and api key on the existing session"""
        if server:
            self.server = server
        if api_key:
            self.api_key = api_key
        if api_key:
            self.session.headers['X-Api-Key'] = self.api_key
        else:
            self.session.headers.pop('X-Api-Key', None)
        log.debug("ValenceAPI reconfigured (key present={0})".format(bool(api_key)))

    def refresh_settings(self):
        """Apply current Kodi settings before direct, non-JSON API requests."""
        try:
            current_settings = xbmcaddon.Addon()
            current_server = current_settings.getSetting('server_address')
            current_key = current_settings.getSetting('api_key')

            if current_server != self._settings_server_address:
                self.server = current_server or None
                self._settings_server_address = current_server
            elif not self.server and current_server:
                self.server = current_server

            if current_key != self._settings_api_key:
                self.api_key = current_key or None
                self._settings_api_key = current_key
                if self.api_key:
                    self.session.headers['X-Api-Key'] = self.api_key
                else:
                    self.session.headers.pop('X-Api-Key', None)
            elif current_key and not self.api_key:
                self.api_key = current_key
                self.session.headers['X-Api-Key'] = current_key

            self.verify_cert = current_settings.getSetting('verify_cert') == 'true'
            self.settings = current_settings
        except Exception:
            pass

    def _request(self, method, path, **kwargs):
        """Make a request to the Valence API"""
        self.last_error = None
        safe_path = _safe_api_path(path)
        request_started = time.time()
        log.info('Valence API request started: {} {}'.format(method, safe_path))
        # Kodi can keep this API client alive after the settings window closes.
        # Read through a fresh Addon object so edits made after service startup
        # reach the long-lived client as well.
        self.refresh_settings()

        if not self.server:
            log.error('Skipping Valence API request: server address is not configured')
            return {}

        parsed_server = urlsplit(self.server)
        if parsed_server.scheme not in ('http', 'https') or not parsed_server.netloc:
            log.error('Skipping Valence API request: server address is not a valid HTTP(S) URL')
            return {}

        url = '{}/api{}'.format(self.server.rstrip('/'), path)
        
        # Ensure verify_cert is set
        kwargs.setdefault('verify', self.verify_cert)
        # Keep Kodi directory loads responsive when the server stalls. The old
        # 60 second read timeout looked like a frozen browser and failures were
        # otherwise converted into an empty directory.
        kwargs.setdefault('timeout', (5, 20))
        
        try:
            resp = self.session.request(method, url, **kwargs)
            elapsed = time.time() - request_started
            log.info('Valence API request finished: {} {} status={} elapsed={:.1f}s'.format(
                method, safe_path, resp.status_code, elapsed))
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {}
        except requests.exceptions.HTTPError as e:
            self.last_error = 'HTTP {}'.format(e.response.status_code)
            log.error('Valence API HTTP error: {} {} status={} elapsed={:.1f}s'.format(
                method, safe_path, e.response.status_code, time.time() - request_started))
            if e.response.status_code == 401:
                # Token expired or invalid
                self._handle_auth_error()
            return {}
        except requests.exceptions.Timeout as e:
            self.last_error = 'request timed out'
            log.error('Valence API request timed out: {} {} elapsed={:.1f}s'.format(
                method, safe_path, time.time() - request_started))
            return {}
        except Exception as e:
            self.last_error = 'connection error ({})'.format(type(e).__name__)
            log.error('Valence API request failed: {} {} type={} elapsed={:.1f}s'.format(
                method, safe_path, type(e).__name__, time.time() - request_started))
            return {}

    def get(self, path, params=None):
        return self._request('GET', path, params=params)

    def post(self, path, json_data=None, data=None):
        return self._request('POST', path, json=json_data, data=data)

    def put(self, path, json_data=None):
        return self._request('PUT', path, json=json_data)

    def delete(self, path):
        return self._request('DELETE', path)

    def _handle_auth_error(self):
        """Handle authentication errors - clear stored credentials"""
        log.error('Authentication failed, clearing credentials')
        self.api_key = None
        self.profile_id = None
        self.session.headers.pop('X-Api-Key', None)

    def test_connection(self):
        """Test connection to Valence server"""
        result = self.get('/about')
        return bool(result and result.get('version'))

    def get_server_info(self):
        """Get server info from /api/about"""
        return self.get('/about')

    def get_libraries(self):
        """Get all libraries"""
        return self.get('/libraries')

    def get_library_items(self, library_id, params=None):
        """Get items from a library (movies or episodes)"""
        default_params = {'limit': 100}
        if params:
            default_params.update(params)
        return self.get('/libraries/{}/items'.format(library_id), params=default_params)

    def get_library_shows(self, library_id, params=None):
        """Get the series index for a library (Valence accepts no query params)."""
        return self.get('/libraries/{}/shows'.format(library_id))

    def get_media(self, media_id):
        """Get media details (works for movies, episodes, not for series)"""
        return self.get('/media/{}'.format(media_id))

    def get_media_artwork(self, media_id, kind='poster'):
        """
        Get media artwork URL.
        Note: Valence doesn't have /media/{id}/artwork endpoint on all versions.
        Use posterUrl/backdropUrl from item data directly.
        """
        # Return empty - artwork URLs come from item data (posterUrl, backdropUrl)
        return ""

    def get_profiles(self):
        """Get available profiles"""
        return self.get('/profiles')

    def choose_profile(self, profile_id, pin=None):
        """Select a profile"""
        payload = {'profileId': profile_id}
        if pin:
            payload['pin'] = pin
        result = self.post('/profiles/{}/choose'.format(profile_id), json_data=payload)
        if result and result.get('success'):
            self.profile_id = profile_id
            return result
        return {}

    def get_library_facets(self):
        """Get library facets (genres, decades, etc.)"""
        return self.get('/library-facets')

    def get_up_next(self):
        """Get continue watching / up next"""
        return self.get('/up-next')

    def get_progress(self):
        """Get playback progress for all items"""
        return self.get('/progress')

    def get_live_sources(self):
        """Get live TV sources"""
        return self.get('/live/sources')

    def get_live_guide(self, params=None):
        """Get live TV guide"""
        return self.get('/live/guide', params=params)

    def get_music_albums(self, params=None):
        """Get music albums"""
        default_params = {'limit': 100}
        if params:
            default_params.update(params)
        return self.get('/music/albums', params=default_params)

    def get_music_artists(self, params=None):
        """Get music artists"""
        default_params = {'limit': 100}
        if params:
            default_params.update(params)
        return self.get('/music/artists', params=default_params)

    def get_music_tracks(self, params=None):
        """Get music tracks"""
        default_params = {'limit': 100}
        if params:
            default_params.update(params)
        return self.get('/music/tracks', params=default_params)

    def get_books(self, params=None):
        """Get books"""
        default_params = {'limit': 100}
        if params:
            default_params.update(params)
        return self.get('/books', params=default_params)

    def get_collections(self, params=None):
        """Get collections"""
        default_params = {'limit': 100}
        if params:
            default_params.update(params)
        return self.get('/collections', params=default_params)

    # Playback methods
    def start_playback_session(self, media_id, device_profile):
        """Start a playback session - returns session with HLS manifest URL"""
        payload = {
            'mediaId': media_id,
            'deviceProfile': device_profile
        }
        return self.post('/playback/{}/session'.format(media_id), json_data=payload)

    def get_playback_file(self, media_id, params=None):
        """Get direct playback file URL (not used - session gives HLS manifest)"""
        return self.get('/playback/{}/file'.format(media_id), params=params)

    def get_playback_explain(self, media_id):
        """Get playback explanation"""
        return self.get('/playback/{}/explain'.format(media_id))

    def playback_session_heartbeat(self, session_id, is_playing):
        """Keep a Valence playback session alive and report its player state."""
        return self.post(
            '/playback/session/{}/heartbeat'.format(quote(str(session_id), safe='')),
            json_data={'isPlaying': bool(is_playing)},
        )

    def report_progress(self, media_id, position_seconds, duration_seconds, is_finished=False):
        """Report playback progress"""
        payload = {
            'positionSeconds': position_seconds,
            'durationSeconds': duration_seconds,
            'isFinished': is_finished
        }
        return self.put('/media/{}/progress'.format(quote(str(media_id), safe='')), json_data=payload)

    def search(self, query, params=None):
        """Search catalogue"""
        default_params = {'q': query, 'limit': 50}
        if params:
            default_params.update(params)
        return self.get('/admin/catalogue/search', params=default_params)


# Global API instance
settings = xbmcaddon.Addon()
user_details = load_user_details()
api = ValenceAPI(
    settings.getSetting('server_address'),
    user_details.get('api_key'),
    user_details.get('profile_id')
)
