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
        user_details.get('api_key')
    )

    progress_dialog = xbmcgui.DialogProgress()
    message = 'Testing with {0} MB of data'.format(speed_test_data_size)
    progress_dialog.create("ValenceCon connection speed test", message)
    start_time = time.time()

    log.debug("Starting Connection Speed Test")
    # Use a test file from the server to measure speed
    # We'll use a simple GET request to measure latency/throughput
    response = api.session.get(
        '{}/api/health'.format(api.server),
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
    """Main server/profile detection and selection flow"""
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
                api.server = kb.getText()
            else:
                xbmc.executebuiltin("ActivateWindow(Home)")
                return

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

    # Check if we have API key
    user_details = load_user_details()
    api_key = user_details.get('api_key')
    current_profile = settings.getSetting('profile_name')
    
    home_window = HomeWindow()
    home_window.set_property('profile_name', current_profile)

    # if asked or we have no current profile then show profile selection screen
    if something_changed or change_profile or len(current_profile) == 0 or not api_key:
        
        # stop playback when switching profiles
        xbmc.Player().stop()

        # Get profiles from server
        profiles_result = api.get_profiles()
        profiles = profiles_result.get('profiles', []) if profiles_result else []
        
        if not profiles:
            xbmcgui.Dialog().ok(__addon_name__, 'No profiles found on server')
            return

        # Build profile selection dialog
        chosen_profile_id = profiles_result.get('chosenProfileId')
        users = []
        selected_id = -1

        for profile in profiles:
            profile_item = create_profile_listitem(profile)
            if profile_item:
                users.append(profile_item)
                if profile.get('id') == chosen_profile_id:
                    selected_id = len(users) - 1

        if not users:
            xbmcgui.Dialog().ok(__addon_name__, 'No accessible profiles found')
            return

        selection_title = translate_string(30180)  # "Select Profile"
        if current_profile:
            selection_title += " (" + current_profile + ")"

        user_selection = xbmcgui.Dialog().select(
            selection_title,
            users,
            preselect=selected_id,
            autoclose=60000,
            useDetails=True)

        if user_selection > -1:
            selected_profile = profiles[user_selection]
            profile_id = selected_profile.get('id')
            profile_name = selected_profile.get('name')
            has_pin = selected_profile.get('hasPin', False)

            pin = ''
            if has_pin:
                kb = xbmc.Keyboard()
                kb.setHeading(translate_string(30006))  # "Enter PIN"
                kb.setHiddenInput(True)
                kb.doModal()
                if kb.isConfirmed():
                    pin = kb.getText()
                else:
                    return

            # Choose the profile
            result = api.choose_profile(profile_id, pin if pin else None)
            
            if result and result.get('success'):
                # Save profile selection
                home_window.set_property('profile_name', profile_name)
                settings.setSetting('profile_name', profile_name)
                
                # Save user details (api_key and profile_id)
                # Note: Valence uses API key for auth, profile is chosen per session
                save_user_details(profile_name, profile_id, api_key)
                something_changed = True
                
                xbmcgui.Dialog().notification(__addon_name__, 
                    translate_string(30167).format(profile_name),
                    icon="special://home/addons/plugin.video.valencecon/icon.png")
            else:
                xbmcgui.Dialog().ok(__addon_name__, 'Failed to select profile')
                return

        if something_changed:
            home_window = HomeWindow()
            home_window.clear_property("valencecon_widget_reload")
            xbmc.executebuiltin("ActivateWindow(Home)")
            xbmc.executebuiltin("ReloadSkin()")


def create_profile_listitem(profile):
    '''Create a profile listitem for the profile selection screen'''
    name = profile.get("Name")
    
    profile_item = xbmcgui.ListItem(name)

    # Profile color/avatar
    colour = profile.get('colour', '#e8503a')
    avatar = profile.get('avatar', {})
    
    # Set profile color as label2
    sub_line = "Profile"
    if profile.get('isOwner'):
        sub_line += " (Owner)"
    
    # Set properties
    profile_item.setProperty("has_pin", "true" if profile.get('hasPin') else "false")
    profile_item.setProperty("profile_id", profile.get('id', ''))
    profile_item.setLabel2(sub_line)

    # Use colored square as thumbnail
    # Create a simple colored image or use default
    art = {"Thumb": "DefaultUser.png"}
    profile_item.setArt(art)

    return profile_item