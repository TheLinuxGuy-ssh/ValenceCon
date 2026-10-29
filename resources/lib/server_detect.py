from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import json
import time

import xbmcaddon
import xbmcgui
import xbmc

from .kodi_utils import HomeWindow
from .valence import ValenceAPI
from .lazylogger import LazyLogger
from .utils import (
    translate_string, save_user_details,
    load_user_details, get_saved_users
)

log = LazyLogger(__name__)

__addon__ = xbmcaddon.Addon()
__addon_name__ = __addon__.getAddonInfo('name')


def check_connection_speed():
    """Test connection speed to Valence server"""
    log.debug("check_connection_speed")

    settings = xbmcaddon.Addon()
    speed_test_data_size = int(settings.getSetting("speed_test_data_size"))
    test_data_size = speed_test_data_size * 1000000
    user_details = load_user_details()

    api = ValenceAPI(
        settings.getSetting('server_address'),
        user_details.get('api_key') or settings.getSetting('api_key')
    )

    progress_dialog = xbmcgui.DialogProgress()
    message = 'Testing with {0} MB of data'.format(speed_test_data_size)
    progress_dialog.create("ValenceCon connection speed test", message)
    start_time = time.time()

    log.debug("Starting Connection Speed Test")
    # Use the about endpoint to measure server latency/throughput
    response = api.session.get(
        '{}/api/about'.format(api.server),
        stream=True,
        verify=api.verify_cert,
        timeout=(5, 30)
    )

    last_percentage_done = 0
    total_data_read = 0
    if response.status_code == 200:
        for data in response.iter_content(chunk_size=10240):
            total_data_read += len(data)
            percentage_done = int(float(total_data_read) / float(test_data_size) * 100.0)
            if last_percentage_done != percentage_done:
                progress_dialog.update(percentage_done)
                last_percentage_done = percentage_done
    else:
        log.error("HTTP response error: {0} {1}".format(response.status_code, response.content))
        error_message = "HTTP response error: %s\n%s" % (response.status_code, response.content)
        xbmcgui.Dialog().ok("Speed Test Error", error_message)
        return -1

    total_data_read_kbits = (total_data_read * 8) / 1000
    total_time = time.time() - start_time
    speed = int(total_data_read_kbits / total_time) if total_time > 0 else 0
    log.debug("Finished Connection Speed Test, speed: {0} total_data: {1}, total_time: {2}".format(speed, total_data_read, total_time))

    progress_dialog.close()
    del progress_dialog

    heading = "Speed Test Result : {0:,} Kbs".format(speed)
    message = "Do you want to set this speed as your max stream bitrate for playback?\n"
    message += "{0:,} MB over {1} sec".format(int((total_data_read / 1000000)), total_time)

    response = xbmcgui.Dialog().yesno(heading, message)
    if response:
        settings.setSetting("max_stream_bitrate", str(speed))

    return speed


def check_server(force=False, change_profile=False, notify=False):
    """Main server setup flow: server URL + API key, then verify profile binding"""
    log.debug("checkServer Called")

    settings = xbmcaddon.Addon()
    something_changed = False

    # Initialize API object
    api = ValenceAPI()

    if force is False:
        # if not forcing use server details from settings
        api.server = settings.getSetting('server_address')

    # if the server is not set then prompt for it
    if not api.server:
        return_index = xbmcgui.Dialog().yesno(__addon_name__,
            '{}\n{}'.format(translate_string(30282), translate_string(30370)))
        if not return_index:
            xbmc.executebuiltin("ActivateWindow(Home)")
            return

        while True:
            kb = xbmc.Keyboard()
            kb.setHeading(translate_string(30372))
            if api.server:
                kb.setDefault(api.server)
            else:
                kb.setDefault("https://")
            kb.doModal()
            if kb.isConfirmed():
                api.server = kb.getText().strip()
            else:
                xbmc.executebuiltin("ActivateWindow(Home)")
                return

            if not api.server:
                continue

            progress = xbmcgui.DialogProgress()
            progress.create('{} : {}'.format(__addon_name__, translate_string(30376)))
            progress.update(0, translate_string(30377))
            result = api.get_server_info()
            progress.close()

            if result:
                xbmcgui.Dialog().ok('{} : {}'.format(__addon_name__, translate_string(30167)),
                                    api.server)
                break
            else:
                return_index = xbmcgui.Dialog().yesno('{} : {}'.format(__addon_name__, translate_string(30135)),
                                                      api.server,
                                                      translate_string(30371))
                if not return_index:
                    xbmc.executebuiltin("ActivateWindow(Home)")
                    return

        log.debug("Selected server: {0}".format(api.server))
        settings.setSetting("server_address", api.server)
        something_changed = True

    # API key: required. The key is bound to a single Valence profile.
    api_key = settings.getSetting('api_key')
    if not api_key:
        user_details = load_user_details()
        api_key = user_details.get('api_key')

    if not api_key:
        # Prompt directly for the API key
        entered = _prompt_for_api_key(api.server)
        if not entered:
            xbmc.executebuiltin("ActivateWindow(Home)")
            return
        api_key = entered

    # Activate credentials on the shared session and validate them
    api.reconfigure(server=api.server, api_key=api_key)

    profiles_result = api.get_profiles()
    profiles = profiles_result.get('profiles', []) if profiles_result else []

    if not profiles:
        dialog = xbmcgui.Dialog()
        if not api_key:
            dialog.ok(__addon_name__, translate_string(30094),
                      translate_string(30371))
        else:
            # Server reachable but key rejected or no profiles visible
            dialog.ok(__addon_name__, translate_string(30389),
                      translate_string(30371))
            settings.setSetting('api_key', '')
        return

    # The API key acts for the profile that created it
    chosen_profile_id = profiles_result.get('chosenProfileId')
    chosen_profile = next(
        (p for p in profiles if p.get('id') == chosen_profile_id), None)
    if chosen_profile is None:
        chosen_profile = profiles[0]
    chosen_profile_id = chosen_profile.get('id')
    profile_name = chosen_profile.get('name') or chosen_profile.get('Name') or ''
    current_profile = settings.getSetting('profile_name')

    if not current_profile or current_profile != profile_name:
        settings.setSetting('profile_name', profile_name)

    home_window = HomeWindow()
    home_window.set_property('profile_name', profile_name)

    # Persist credentials (api_key and profile) for the next sessions
    save_user_details(profile_name, chosen_profile_id, api_key)
    something_changed = True

    if notify:
        xbmcgui.Dialog().notification(__addon_name__,
            profile_name,
            icon="special://home/addons/plugin.video.valencecon/icon.png")

    if something_changed:
        home_window = HomeWindow()
        home_window.clear_property("valencecon_widget_reload")
        xbmc.executebuiltin("ActivateWindow(Home)")
        xbmc.executebuiltin("ReloadSkin()")


def _prompt_for_api_key(server):
    """Prompt the user to enter the Valence API key, validating against the server"""
    settings = xbmcaddon.Addon()
    while True:
        kb = xbmc.Keyboard()
        kb.setHiddenInput(True)
        kb.setHeading("{}: {}".format(__addon_name__, translate_string(30025)))
        kb.doModal()
        if not kb.isConfirmed():
            return None
        candidate = kb.getText().strip()
        if not candidate:
            return None

        progress = xbmcgui.DialogProgress()
        progress.create('{} : {}'.format(__addon_name__, translate_string(30376)))
        progress.update(0, translate_string(30377))
        api = ValenceAPI(server, candidate)
        result = api.get_profiles()
        progress.close()

        if result and result.get('profiles'):
            settings.setSetting("api_key", candidate)
            xbmcgui.Dialog().ok(__addon_name__,
                                '{}: {}'.format(translate_string(30094), 'OK'))
            return candidate

        retry = xbmcgui.Dialog().yesno('{} : {}'.format(__addon_name__, translate_string(30135)),
                                       translate_string(30371))
        if not retry:
            return None


def create_profile_listitem(profile):
    '''Create a profile listitem for the profile selection screen'''
    name = profile.get("name") or profile.get("Name")
    if not name:
        return None

    profile_item = xbmcgui.ListItem(name)

    # Profile color/avatar
    sub_line = "Profile"
    if profile.get('isOwner'):
        sub_line += " (Owner)"

    profile_item.setProperty("has_pin", "true" if profile.get('hasPin') else "false")
    profile_item.setProperty("profile_id", profile.get('id', ''))
    profile_item.setLabel2(sub_line)

    art = {"Thumb": "DefaultUser.png"}
    profile_item.setArt(art)

    return profile_item