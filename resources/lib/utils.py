from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import sys
import binascii
import string
import random
import json
import time
import math
import os
import hashlib
import re
from datetime import datetime
from uuid import uuid4

import requests
from dateutil import tz
import xbmcaddon
import xbmc
import xbmcvfs
from kodi_six.utils import py2_encode, py2_decode
from six import ensure_text, ensure_binary, text_type
from six.moves.urllib.parse import urlencode

from .lazylogger import LazyLogger
from .kodi_utils import HomeWindow

# hack to get datetime strptime loaded
throwaway = time.strptime('20110101', '%Y%m%d')

log = LazyLogger(__name__)


def kodi_version():
    # Kodistubs returns empty string, causing Python 3 tests to choke on int()
    # TODO: Make Kodistubs version configurable for testing purposes
    if sys.version_info.major == 2:
        default_versionstring = "18"
    else:
        default_versionstring = "19.1 (19.1.0) Git:20210509-85e05228b4"

    version_string = xbmc.getInfoLabel(
        'System.BuildVersion') or default_versionstring
    return int(version_string.split(' ', 1)[0].split('.', 1)[0])


def get_valence_url(path, params):
    """Build a Valence API URL with query parameters"""
    params["format"] = "json"
    url_params = urlencode(params)
    return '{}?{}'.format(path, url_params)


def get_checksum(item):
    """Generate checksum for cache validation"""
    userdata = item.get('UserData', {})
    checksum = "{}_{}_{}_{}_{}_{}_{}".format(
        item.get('Etag', ''),
        userdata.get('Played', False),
        userdata.get('IsFavorite', False),
        userdata.get('Likes', "-"),
        userdata.get('PlaybackPositionTicks', 0),
        userdata.get('UnplayedItemCount', "-"),
        userdata.get("PlayedPercentage", "-")
    )
    return checksum


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def single_urlencode(text):
    # urlencode needs a utf- string
    text = urlencode({'blahblahblah': text.encode('utf-8')})
    text = text[13:]
    return text.decode('utf-8')  # return the result again as unicode


def send_event_notification(method, data=None, hexlify=False):
    '''
    Send events through Kodi's notification system
    '''
    data = data or {}
    data_str = json.dumps(data)

    if hexlify:
        # Used exclusively for the upnext plugin
        data_str = ensure_text(binascii.hexlify(ensure_binary(data_str)))
        data = '["{}"]'.format(data_str)
    else:
        data = '"[{}]"'.format(data_str.replace('"', '\\"'))

    sender = 'plugin.video.valencecon'

    xbmc.executebuiltin('NotifyAll({}, {}, {})'.format(sender, method, data))


def datetime_from_string(time_string):

    # Builtin python library can't handle ISO-8601 well. Make it compatible
    if time_string.endswith("Z"):
        time_string = re.sub("[0-9]{1}Z", " UTC", time_string)
    elif time_string.endswith("+00:00"):
        time_string = re.sub(r"[0-9]{1}\+00:00", " UTC", time_string)

    try:
        dt = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%S.%f %Z")
    except TypeError:
        # https://bugs.python.org/issue27400
        dt = datetime(*(
            time.strptime(time_string, "%Y-%m-%dT%H:%M:%S.%f %Z")[0:6])
        )

    """
    Dates received from the server are in UTC, but parsing them results
    in naive objects
    """
    utc = tz.tzutc()
    utc_dt = dt.replace(tzinfo=utc)

    return utc_dt


def get_current_datetime():
    # Get current time in UTC
    now = datetime.utcnow()
    utc = tz.tzutc()
    now_dt = now.replace(tzinfo=utc)

    return now_dt


def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "{} {}".format(s, size_name[i])


def translate_string(string_id):
    try:
        addon = xbmcaddon.Addon()
        return py2_encode(addon.getLocalizedString(string_id))
    except Exception as e:
        log.error('Failed String Load: {0} ({1})', string_id, e)
        return str(string_id)


def get_device_id():

    window = HomeWindow()
    username = window.get_property('profile_name')
    client_id = window.get_property("client_id")
    hashed_name = hashlib.md5(username.encode()).hexdigest()

    if client_id and username:
        return '{}-{}'.format(client_id, hashed_name)
    elif client_id and not username:
        # No profile selected yet
        rand_id = uuid4().hex
        return '{}-{}'.format(client_id, rand_id)

    valence_guid_path = py2_decode(
        translate_path("special://temp/valencecon_guid")
    )
    log.debug("valencecon_guid_path: {0}".format(valence_guid_path))
    guid = xbmcvfs.File(valence_guid_path)
    client_id = guid.read()
    guid.close()

    if not client_id:
        client_id = uuid4().hex
        log.debug("Generating a new guid: {0}".format(client_id))
        guid = xbmcvfs.File(valence_guid_path, 'w')
        guid.write(client_id)
        guid.close()
        log.debug("valencecon_client_id (NEW): {0}".format(client_id))
    else:
        log.debug("valencecon_client_id: {0}".format(client_id))

    window.set_property("client_id", client_id)
    return '{}-{}'.format(client_id, hashed_name)


def get_version():
    addon = xbmcaddon.Addon()
    version = addon.getAddonInfo("version")
    return version


def save_user_details(profile_name, profile_id, api_key):
    """Save Valence authentication details"""
    settings = xbmcaddon.Addon()
    save_user_to_settings = settings.getSetting(
        'save_user_to_settings') == 'true'
    addon_data = translate_path(xbmcaddon.Addon().getAddonInfo('profile'))

    # Save to a config file for reference later if desired
    if save_user_to_settings:
        try:
            with open(os.path.join(addon_data, 'auth.json'), 'rb') as infile:
                auth_data = json.load(infile)
        except:  # noqa
            # File doesn't exist or is empty
            auth_data = {}

        auth_data[profile_name] = {
            'profile_id': profile_id,
            'api_key': api_key
        }

        with open(os.path.join(addon_data, 'auth.json'), 'wb') as outfile:
            data = json.dumps(
                auth_data, sort_keys=True, indent=4, ensure_ascii=False)
            if isinstance(data, text_type):
                data = data.encode('utf-8')
            outfile.write(data)

    # Make the profile name available for easy lookup
    window = HomeWindow()
    settings.setSetting('profile_name', profile_name)
    window.set_property('profile_name', profile_name)


def load_user_details():
    """Load Valence authentication details"""
    settings = xbmcaddon.Addon()
    window = HomeWindow()
    # Check current variables first, then check settings
    profile_name = window.get_property('profile_name')
    if not profile_name:
        profile_name = settings.getSetting('profile_name')
    save_user = settings.getSetting('save_user_to_settings') == 'true'
    addon_data = translate_path(xbmcaddon.Addon().getAddonInfo('profile'))

    if save_user:
        try:
            with open(os.path.join(addon_data, 'auth.json'), 'rb') as infile:
                auth_data = json.load(infile)
        except:  # noqa
            # File doesn't exist yet
            return {}

        user_data = auth_data.get(profile_name, {})
        # User doesn't exist yet
        if not user_data:
            return {}

        profile_id = user_data.get('profile_id')
        api_key = user_data.get('api_key')

        # Payload to return to calling function
        user_details = {}
        user_details['profile_name'] = profile_name
        user_details['profile_id'] = profile_id
        user_details['api_key'] = api_key
        return user_details

    else:
        return {}


def get_saved_users():
    """Get list of saved profiles"""
    settings = xbmcaddon.Addon()
    save_user = settings.getSetting('save_user_to_settings') == 'true'
    addon_data = translate_path(xbmcaddon.Addon().getAddonInfo('profile'))
    if not save_user:
        return []

    try:
        with open(os.path.join(addon_data, 'auth.json'), 'rb') as infile:
            auth_data = json.load(infile)
    except:  # noqa
        # File doesn't exist yet
        return []

    users = []
    for user, values in auth_data.items():
        users.append(
            {
                'Name': user,
                'Id': values.get('profile_id'),
                'Configuration': {'Dummy': True}
            }
        )

    return users


def get_current_profile_id():
    user_details = load_user_details()
    profile_id = user_details.get('profile_id')
    return profile_id


def get_art_url(data, art_type, parent=False, index=0, server=None):
    """
    Get artwork URL for Valence media items
    Valence uses /api/media/{id}/artwork/{kind} endpoint
    """
    item_id = data.get("id") or data.get("Id")
    
    if not item_id or not server:
        return ""

    # Map art types to Valence artwork kinds
    art_kind_map = {
        'Primary': 'poster',
        'Poster': 'poster',
        'Backdrop': 'backdrop',
        'Banner': 'banner',
        'Logo': 'logo',
        'Art': 'art',
        'Thumb': 'thumb',
        'Disc': 'disc',
    }
    
    valence_kind = art_kind_map.get(art_type, 'poster')
    
    # For episodes/seasons, use parent series artwork
    item_type = data.get("Type") or data.get("type")
    if item_type in ["Episode", "Season"] and art_type in ["Primary", "Backdrop", "Banner", "Logo", "Art"]:
        parent_id = data.get("seriesId") or data.get("SeriesId")
        if parent_id:
            item_id = parent_id

    artwork = "{}/api/media/{}/artwork/{}".format(server.rstrip('/'), item_id, valence_kind)
    return artwork


def image_url(item_id, art_type, index, width, height, image_tag, server):
    """Legacy function - kept for compatibility"""
    artwork = "{}/api/media/{}/artwork/{}".format(server.rstrip('/'), item_id, art_type)
    if int(width) > 0:
        artwork += '&maxWidth={}'.format(width)
    if int(height) > 0:
        artwork += '&maxHeight={}'.format(height)
    return artwork


def get_default_filters():
    """Get default fields to include in item requests"""
    addon_settings = xbmcaddon.Addon()
    include_media = addon_settings.getSetting("include_media") == "true"
    include_people = addon_settings.getSetting("include_people") == "true"
    include_overview = addon_settings.getSetting("include_overview") == "true"

    filter_list = [
        "overview",
        "genres",
        "rating",
        "year",
        "durationSeconds",
        "videoCodec",
        "videoRange",
        "audioStreams",
        "subtitleStreams",
        "addedAt",
        "sizeBytes",
        "width",
        "height",
        "hasPoster",
        "hasBackdrop",
        "hasLogo",
        "posterUrl",
        "externalId",
        "releaseDate",
        "tagline",
        "certification",
        "cast",
    ]

    return ','.join(filter_list)


def translate_path(path):
    '''
    Use new library location for translate path starting in Kodi 19
    '''
    version = kodi_version()

    if version > 18:
        return xbmcvfs.translatePath(path)
    else:
        return xbmc.translatePath(path)


def download_external_sub(language, codec, url, title):
    addon_settings = xbmcaddon.Addon()
    verify_cert = addon_settings.getSetting('verify_cert') == 'true'

    # Download the subtitle file
    r = requests.get(url, verify=verify_cert)
    r.raise_for_status()

    # Write the subtitle file to the local filesystem
    file_name = 'Stream.{}.{}.{}'.format(title, language, codec)
    file_path = py2_decode(
        translate_path('special://temp/{}'.format(file_name))
    )
    with open(file_path, 'wb') as f:
        f.write(r.content)

    return file_path


def get_bitrate(enum_value):
    ''' Get the video quality based on add-on settings.
    Max bit rate supported by server: 2147483 (max signed 32bit integer)
    '''
    bitrate = [500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000,
               7000, 8000, 9000, 10000, 12000, 14000, 16000, 18000,
               20000, 25000, 30000, 35000, 40000, 100000, 1000000, 2147483]
    return bitrate[int(enum_value) if enum_value else 24] * 1000


def get_filtered_items_count_text():
    settings = xbmcaddon.Addon()
    if settings.getSetting("hide_x_filtered_items_count") == 'true':
        return ""
    else:
        return " (" + settings.getSetting("show_x_filtered_items") + ")"
     
def seconds_to_ticks(seconds:float):
    return seconds * 10000000

def ticks_to_seconds(ticks:int):
    return round(ticks / 10000000, 1)