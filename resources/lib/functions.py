from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import sys
import os
import time
import cProfile
import pstats

import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmc
from six import StringIO
from six.moves.urllib.parse import quote, unquote, parse_qsl, urlencode

from .valence import api
from .utils import (
    translate_string, get_version, load_user_details, get_art_url,
    get_default_filters, translate_path, kodi_version, get_valence_url
)
from .kodi_utils import HomeWindow, add_menu_directory_item
from .datamanager import clear_cached_server_data
from .server_detect import check_server, check_connection_speed
from .lazylogger import LazyLogger
from .menu_functions import (
    display_main_menu, display_menu, show_movie_alpha_list,
    show_tvshow_alpha_list, show_genre_list, show_search,
    show_movie_pages, show_artist_alpha_list, show_movie_years,
    show_movie_tags
)
from .server_sessions import show_server_sessions
from .action_menu import ActionMenu
from .dialogs import BitrateDialog
from .widgets import (
    get_widget_content, get_widget_content_cast, check_for_new_content
)
from .cache_images import CacheArtwork
from .item_functions import get_art
from .dir_functions import get_content, process_directory
from .tracking import timer
from .skin_cloner import clone_default_skin
from .play_utils import play_file

__addon__ = xbmcaddon.Addon()
__addondir__ = translate_path(__addon__.getAddonInfo('profile'))
__cwd__ = __addon__.getAddonInfo('path')
PLUGINPATH = translate_path(os.path.join(__cwd__))
addon_id = __addon__.getAddonInfo('id')

log = LazyLogger(__name__)

user_details = load_user_details()


@timer
def main_entry_point():
    log.debug("===== ValenceCon START =====")

    settings = xbmcaddon.Addon()
    profile_count = int(settings.getSetting('profile_count'))
    pr = None
    if profile_count > 0:
        profile_count = profile_count - 1
        settings.setSetting('profile_count', str(profile_count))
        pr = cProfile.Profile()
        pr.enable()

    log.debug("Running Python: {0}".format(sys.version_info))
    log.debug("Running ValenceCon: {0}".format(get_version()))
    log.debug("Kodi BuildVersion: {0}".format(
        xbmc.getInfoLabel("System.BuildVersion"))
    )
    log.debug("Kodi Version: {0}".format(kodi_version()))
    log.debug("Script argument data: {0}".format(sys.argv))

    params = get_params()
    log.debug("Script params: {0}".format(params))

    request_path = params.get("request_path", None)
    param_url = params.get('url', None)

    mode = params.get("mode", None)

    if (len(params) == 1 and request_path
            and request_path.find("/library/movies") > -1):

        check_server()
        new_params = {}
        new_params["item_type"] = "Movie"
        new_params["media_type"] = "movies"
        show_content(new_params)
    elif mode == "CHANGE_PROFILE":
        check_server(change_profile=True, notify=False)
    elif mode == "CACHE_ARTWORK":
        CacheArtwork().cache_artwork_interactive()
    elif mode == "DETECT_SERVER":
        check_server(force=True, notify=True)
    elif mode == "DETECT_CONNECTION_SPEED":
        check_connection_speed()
    elif mode == "playTrailer":
        item_id = params["id"]
        play_item_trailer(item_id)
    elif mode == "MOVIE_ALPHA":
        show_movie_alpha_list(params)
    elif mode == "TVSHOW_ALPHA":
        show_tvshow_alpha_list(params)
    elif mode == "ARTIST_ALPHA":
        show_artist_alpha_list(params)
    elif mode == "GENRES":
        show_genre_list(params)
    elif mode == "MOVIE_PAGES":
        show_movie_pages(params)
    elif mode == "TOGGLE_WATCHED":
        toggle_watched(params)
    elif mode == "SHOW_MENU":
        show_menu(params)
    elif mode == "CLONE_SKIN":
        clone_default_skin()
    elif mode == "SHOW_SETTINGS":
        __addon__.openSettings()
        window = xbmcgui.getCurrentWindowId()
        if window == 10000:
            log.debug(
                "Currently in home - refresh to allow new settings to be taken"
            )
            xbmc.executebuiltin("ActivateWindow(Home)")
    elif mode == "CLEAR_CACHE":
        clear_cached_server_data()
    elif mode == "WIDGET_CONTENT":
        get_widget_content(int(sys.argv[1]), params)
    elif mode == "WIDGET_CONTENT_CAST":
        get_widget_content_cast(int(sys.argv[1]), params)
    elif mode == "SHOW_CONTENT":
        check_server()
        show_content(params)
    elif mode == "SEARCH":
        xbmcplugin.setContent(int(sys.argv[1]), 'files')
        show_search()
    elif mode == "NEW_SEARCH":
        search_results(params)
    elif mode == "NEW_SEARCH_PERSON":
        search_results_person(params)
    elif mode == "SHOW_SERVER_SESSIONS":
        show_server_sessions()
    elif mode == "SHOW_ADDON_MENU":
        display_menu(params)
    else:
        log.debug("ValenceCon -> Mode: {0}".format(mode))
        log.debug("ValenceCon -> URL: {0}".format(param_url))

        if mode == "GET_CONTENT":
            get_content(param_url, params)
        elif mode == "PLAY":
            play_action(params)
        else:
            check_server()
            display_main_menu()

    if pr:
        pr.disable()

        file_time_stamp = time.strftime("%Y%m%d-%H%M%S")
        tab_file_name = "{}valencecon-profile({}).txt".format(
            __addondir__, file_time_stamp
        )
        s = StringIO()
        ps = pstats.Stats(pr, stream=s)
        ps = ps.sort_stats('cumulative')
        ps.print_stats()
        ps.strip_dirs()
        ps = ps.sort_stats('tottime')
        ps.print_stats()
        with open(tab_file_name, 'w') as f:
            f.write(s.getvalue())

    log.debug("===== ValenceCon FINISHED =====")


def toggle_watched(params):
    log.debug("toggle_watched: {0}".format(params))
    item_id = params.get("item_id", None)
    if item_id is None:
        return

    media = api.get_media(item_id)
    log.debug("toggle_watched item info: {0}".format(media))

    # Valence uses progress endpoint to mark watched
    if media and media.get("Type") == "Episode":
        # Mark as watched by reporting progress at end
        api.report_progress(item_id, media.get("durationSeconds", 0), media.get("durationSeconds", 0), True)
    elif media:
        api.report_progress(item_id, media.get("durationSeconds", 0), media.get("durationSeconds", 0), True)

    check_for_new_content()
    home_window = HomeWindow()
    last_url = home_window.get_property("last_content_url")
    if last_url:
        log.debug("markWatched_lastUrl: {0}".format(last_url))
        home_window.set_property("skip_cache_for_{}".format(last_url), "true")

    xbmc.executebuiltin("Container.Refresh")


def mark_item_watched(item_id):
    log.debug("Mark Item Watched: {0}".format(item_id))
    media = api.get_media(item_id)
    if media:
        api.report_progress(item_id, media.get("durationSeconds", 0), media.get("durationSeconds", 0), True)
    check_for_new_content()
    home_window = HomeWindow()
    last_url = home_window.get_property("last_content_url")
    if last_url:
        log.debug("markWatched_lastUrl: {0}".format(last_url))
        home_window.set_property("skip_cache_for_{}".format(last_url), "true")

    xbmc.executebuiltin("Container.Refresh")


def mark_item_unwatched(item_id):
    log.debug("Mark Item UnWatched: {0}".format(item_id))
    # For Valence, reset progress to 0
    api.report_progress(item_id, 0, 1, False)
    check_for_new_content()
    home_window = HomeWindow()
    last_url = home_window.get_property("last_content_url")
    if last_url:
        log.debug("markUnwatched_lastUrl: {0}".format(last_url))
        home_window.set_property("skip_cache_for_{}".format(last_url), "true")

    xbmc.executebuiltin("Container.Refresh")


def mark_item_favorite(item_id):
    log.debug("Add item to favourites: {0}".format(item_id))
    # Valence uses /api/media/{id}/favourite
    api.post('/media/{}/favourite'.format(item_id))
    check_for_new_content()
    home_window = HomeWindow()
    last_url = home_window.get_property("last_content_url")
    if last_url:
        home_window.set_property("skip_cache_for_{}".format(last_url), "true")

    xbmc.executebuiltin("Container.Refresh")


def unmark_item_favorite(item_id):
    log.debug("Remove item from favourites: {0}".format(item_id))
    api.delete('/media/{}/favourite'.format(item_id))
    check_for_new_content()
    home_window = HomeWindow()
    last_url = home_window.get_property("last_content_url")
    if last_url:
        home_window.set_property("skip_cache_for_{}".format(last_url), "true")

    xbmc.executebuiltin("Container.Refresh")


def delete(item_id):
    media = api.get_media(item_id)

    if not media:
        return

    item_name = media.get("title") or media.get("Name", "")
    series_name = media.get("seriesTitle") or media.get("SeriesName", "")
    ep_number = media.get("episodeNumber") or media.get("IndexNumber", -1)

    final_name_parts = []

    if series_name:
        final_name_parts.append(series_name)

    if ep_number != -1:
        final_name_parts.append("Episode {:02d}".format(ep_number))

    final_name_parts.append(item_name)
    final_name = " - ".join(final_name_parts)

    if not media.get("CanDelete", False):
        xbmcgui.Dialog().ok(
            translate_string(30135), translate_string(30417), final_name
        )
        return

    return_value = xbmcgui.Dialog().yesno(
        translate_string(30091), '{}\n{}'.format(
            final_name, translate_string(30092)
        )
    )
    if return_value:
        log.debug('Deleting Item: {0}'.format(item_id))
        url = '/media/{}'.format(item_id)
        progress = xbmcgui.DialogProgress()
        progress.create(translate_string(30052), translate_string(30053))
        api.delete(url)
        progress.close()
        check_for_new_content()
        home_window = HomeWindow()
        last_url = home_window.get_property("last_content_url")
        if last_url:
            home_window.set_property(
                "skip_cache_for_{}".format(last_url), "true"
            )

        xbmc.executebuiltin("Container.Refresh")


def get_params():
    '''
    Retrieve the request data from Kodi
    '''

    plugin_path = sys.argv[0]
    paramstring = sys.argv[2]

    log.debug("Parameter string: {0}".format(paramstring))
    log.debug("Plugin Path string: {0}".format(plugin_path))

    param = dict(parse_qsl(paramstring[1:]))

    # add plugin path
    request_path = plugin_path.replace("plugin://{}".format(addon_id), "")
    param["request_path"] = request_path

    log.debug("ValenceCon -> Detected parameters: {0}".format(param))
    return param


def show_menu(params):
    log.debug("showMenu(): {0}".format(params))

    home_window = HomeWindow()
    settings = xbmcaddon.Addon()
    item_id = params["item_id"]

    media = api.get_media(item_id)
    log.debug("Menu item info: {0}".format(media))

    if media is None:
        return

    action_items = []

    # Additional items to include in the context menu for different item types
    media_type = media.get("Type") or media.get("type", "")
    if media_type in ["Episode", "Movie", "Music", "Video", "Audio",
                      "LiveChannel", "Program", "MusicVideo", "MusicTrack", "Book"]:
        li = xbmcgui.ListItem(translate_string(30314), offscreen=True)
        li.setProperty('menu_id', 'play')
        action_items.append(li)

    if media_type in ["Season", "MusicArtist", "MusicAlbum", "Playlist",
                      "MusicGenre"]:
        li = xbmcgui.ListItem(translate_string(30317), offscreen=True)
        li.setProperty('menu_id', 'play_all')
        action_items.append(li)

    if media_type in ["MusicArtist", "MusicAlbum", "Playlist",
                      "Series", "Season", "MusicGenre"]:
        li = xbmcgui.ListItem(translate_string(30448), offscreen=True)
        li.setProperty('menu_id', 'shuffle')
        action_items.append(li)

    if media_type in ["MusicArtist", "MusicAlbum", "Audio", "MusicTrack"]:
        li = xbmcgui.ListItem(translate_string(30449), offscreen=True)
        li.setProperty('menu_id', 'instant_mix')
        action_items.append(li)

    if media_type in ["Episode", "Movie", "Video", "LiveChannel",
                      "Program", "MusicVideo"]:
        li = xbmcgui.ListItem(translate_string(30275), offscreen=True)
        li.setProperty('menu_id', 'transcode')
        action_items.append(li)

    if media_type in ["Episode", "Movie", "Music", "Video", "Audio",
                      "MusicArtist", "MusicAlbum", "MusicVideo",
                      "MusicGenre", "MusicTrack", "Book"]:
        li = xbmcgui.ListItem(translate_string(30402), offscreen=True)
        li.setProperty('menu_id', 'add_to_playlist')
        action_items.append(li)

    if media_type in ("Movie", "Series"):
        li = xbmcgui.ListItem(translate_string(30307), offscreen=True)
        li.setProperty('menu_id', 'play_trailer')
        action_items.append(li)

    if media_type == "Episode" and media.get("ParentId") or media.get("seriesId"):
        li = xbmcgui.ListItem(translate_string(30327), offscreen=True)
        li.setProperty('menu_id', 'view_season')
        action_items.append(li)

    if media_type in ("Series", "Season", "Episode"):
        li = xbmcgui.ListItem(translate_string(30354), offscreen=True)
        li.setProperty('menu_id', 'view_series')
        action_items.append(li)

    if media_type == "Movie":
        li = xbmcgui.ListItem("Show Extras", offscreen=True)
        li.setProperty('menu_id', 'show_extras')
        action_items.append(li)

    # User data from progress
    user_data = media.get("userProgress") or media.get("UserData") or {}
    if user_data:
        progress = user_data.get("positionSeconds", 0) != 0
        played = user_data.get("isFinished", False) or media.get("isPlayed", False)
        if not played or progress:
            li = xbmcgui.ListItem(translate_string(30270), offscreen=True)
            li.setProperty('menu_id', 'mark_watched')
            action_items.append(li)
        if played or progress:
            li = xbmcgui.ListItem(translate_string(30271), offscreen=True)
            li.setProperty('menu_id', 'mark_unwatched')
            action_items.append(li)

        if media.get("isFavorite", False) is False:
            li = xbmcgui.ListItem(translate_string(30272), offscreen=True)
            li.setProperty('menu_id', 'set_favorite')
            action_items.append(li)
        else:
            li = xbmcgui.ListItem(translate_string(30273), offscreen=True)
            li.setProperty('menu_id', 'unset_favorite')
            action_items.append(li)

    can_delete = media.get("CanDelete", False)
    if can_delete:
        li = xbmcgui.ListItem(translate_string(30274), offscreen=True)
        li.setProperty('menu_id', 'delete')
        action_items.append(li)

    li = xbmcgui.ListItem(translate_string(30398), offscreen=True)
    li.setProperty('menu_id', 'refresh_server')
    action_items.append(li)

    li = xbmcgui.ListItem(translate_string(30281), offscreen=True)
    li.setProperty('menu_id', 'refresh_images')
    action_items.append(li)

    if media_type in ["Movie", "Series"]:
        li = xbmcgui.ListItem(translate_string(30399), offscreen=True)
        li.setProperty('menu_id', 'hide')
        action_items.append(li)

    li = xbmcgui.ListItem(translate_string(30401), offscreen=True)
    li.setProperty('menu_id', 'info')
    action_items.append(li)

    window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
    container_view_id = str(window.getFocusId())
    container_content_type = xbmc.getInfoLabel("Container.Content")
    view_key = "view-{}".format(container_content_type)
    current_default_view = settings.getSetting(view_key)
    view_match = container_view_id == current_default_view
    log.debug("View ID:{0} Content type:{1}".format(
        container_view_id, container_content_type)
    )

    if container_content_type in ["movies", "tvshows", "seasons",
                                  "episodes", "sets"]:
        if view_match:
            li = xbmcgui.ListItem("Unset as default view", offscreen=True)
            li.setProperty('menu_id', 'unset_view')
            action_items.append(li)
        else:
            li = xbmcgui.ListItem("Set as default view", offscreen=True)
            li.setProperty('menu_id', 'set_view')
            action_items.append(li)

    action_menu = ActionMenu("ActionMenu.xml", PLUGINPATH, "default", "720p")
    action_menu.setActionItems(action_items)
    action_menu.doModal()
    selected_action_item = action_menu.getActionItem()
    selected_action = ""
    if selected_action_item is not None:
        selected_action = selected_action_item.getProperty('menu_id')
    log.debug("Menu Action Selected: {0}".format(selected_action))
    del action_menu

    if selected_action == "play":
        log.debug("Play Item")
        play_action(params)

    elif selected_action == "set_view":
        log.debug("Setting view type for {0} to {1}".format(
            view_key, container_view_id)
        )
        settings.setSetting(view_key, container_view_id)

    elif selected_action == "unset_view":
        log.debug("Un-Settign view type for {0} to {1}".format(
            view_key, container_view_id)
        )
        settings.setSetting(view_key, "")

    elif selected_action == "refresh_server":
        # Valence does not expose a dedicated refresh endpoint
        # This would need to be implemented via library scan
        xbmcgui.Dialog().ok(translate_string(30135), "Server refresh not implemented for Valence yet")

    elif selected_action == "hide":
        # Valence uses hidden endpoint
        api.post('/media/{}/hidden'.format(item_id))
        check_for_new_content()

        last_url = home_window.get_property("last_content_url")
        if last_url:
            log.debug("markUnwatched_lastUrl: {0}".format(last_url))
            home_window.set_property(
                "skip_cache_for_{}".format(last_url), "true"
            )

        xbmc.executebuiltin("Container.Refresh")

    elif selected_action == "play_all":
        play_action(params)

    elif selected_action == "shuffle":
        params["action"] = "shuffle"
        play_action(params)

    elif selected_action == "instant_mix":
        params["action"] = "instant_mix"
        play_action(params)

    elif selected_action == "play_trailer":
        play_item_trailer(item_id)

    elif selected_action == "transcode":
        params['force_transcode'] = 'true'

        max_bitrate = settings.getSetting("force_max_stream_bitrate")
        initial_bitrate_value = int(max_bitrate)
        bitrate_dialog = BitrateDialog(
            "BitrateDialog.xml", PLUGINPATH, "default", "720p"
        )
        bitrate_dialog.initial_bitrate_value = initial_bitrate_value
        bitrate_dialog.doModal()
        selected_transcode_value = bitrate_dialog.selected_transcode_value
        del bitrate_dialog
        log.debug("selected_transcode_value: {0}".format(
            selected_transcode_value)
        )

        if selected_transcode_value > 0:
            settings.setSetting(
                "force_max_stream_bitrate", str(selected_transcode_value))

            play_action(params)

    elif selected_action == "add_to_playlist":
        params["action"] = "add_to_playlist"
        play_action(params)

    elif selected_action == "set_favorite":
        mark_item_favorite(item_id)

    elif selected_action == "unset_favorite":
        unmark_item_favorite(item_id)

    elif selected_action == "mark_watched":
        mark_item_watched(item_id)

    elif selected_action == "mark_unwatched":
        mark_item_unwatched(item_id)

    elif selected_action == "delete":
        delete(item_id)

    elif selected_action == "show_extras":
        # Valence doesn't have special features endpoint yet
        xbmcgui.Dialog().ok(translate_string(30135), "Extras not available for Valence yet")

    elif selected_action == "view_season":
        xbmc.executebuiltin("Dialog.Close(all,true)")
        series_id = media.get("SeriesId") or media.get("seriesId")
        if series_id:
            # Get library for this series
            libraries = api.get_libraries()
            library_id = media.get("libraryId") or media.get("LibraryId")
            for lib in libraries:
                if library_id:
                    break
                if lib.get('kind') in ['shows', 'anime']:
                    library_id = lib.get('id')
                    break

            if library_id:
                season_number = media.get("seasonNumber")
                if season_number is None:
                    season_number = media.get("ParentIndexNumber")
                url = get_valence_url(
                    '/libraries/{}/shows/{}'.format(
                        quote(str(library_id), safe=''), quote(str(series_id), safe='')),
                    {})

                plugin_params = {
                    "url": url,
                    "mode": "GET_CONTENT",
                    "media_type": "Season",
                    "season_number": season_number if season_number is not None else -1,
                }
                action_params = urlencode(plugin_params)
                action_url = "plugin://{}/?{}".format(addon_id, action_params)
                built_in_command = 'ActivateWindow(Videos, {}, return)'.format(action_url)
                xbmc.executebuiltin(built_in_command)

    elif selected_action == "view_series":
        xbmc.executebuiltin("Dialog.Close(all,true)")

        series_id = media.get("SeriesId") or media.get("seriesId") or item_id

        libraries = api.get_libraries()
        library_id = media.get("libraryId") or media.get("LibraryId")
        for lib in libraries:
            if library_id:
                break
            if lib.get('kind') in ['shows', 'anime']:
                library_id = lib.get('id')
                break

        if library_id:
            url = get_valence_url(
                '/libraries/{}/shows/{}'.format(
                    quote(str(library_id), safe=''), quote(str(series_id), safe='')),
                {})

            plugin_params = {
                "url": url,
                "mode": "GET_CONTENT",
                "media_type": "Series"
            }
            action_params = urlencode(plugin_params)
            action_url = "plugin://{}/?{}".format(addon_id, action_params)

            if xbmc.getCondVisibility("Window.IsActive(home)"):
                built_in_command = 'ActivateWindow(Videos, {}, return'.format(action_url)
            else:
                built_in_command = 'Container.Update({})'.format(action_url)

            xbmc.executebuiltin(built_in_command)

    elif selected_action == "refresh_images":
        CacheArtwork().delete_cached_images(item_id)

    elif selected_action == "info":
        xbmc.executebuiltin("Dialog.Close(all,true)")
        xbmc.executebuiltin("Action(info)")


def show_content(params):
    log.debug("showContent Called: {0}".format(params))

    item_type = params.get("item_type")
    settings = xbmcaddon.Addon()
    library_id = params.get("library_id")

    # Get all libraries of the appropriate kind
    libraries = api.get_libraries()
    if not libraries:
        return

    target_kinds = {
        'Movie': ['movies'],
        'Series': ['shows', 'anime'],
        'MusicAlbum': ['music'],
        'MusicTrack': ['music'],
        'Book': ['books'],
    }

    kinds = target_kinds.get(item_type, ['movies'])
    lib_items = [l for l in libraries if l.get('kind') in kinds]

    if not lib_items:
        return

    # With per-library API routes, resolve to a single library.
    # If several, show a library chooser first.
    if not library_id and len(lib_items) > 1:
        handle = int(sys.argv[1])
        xbmcplugin.setContent(handle, 'files')
        server = settings.getSetting('server_address')
        for lib in lib_items:
            art = get_art(item=lib, server=server)
            url = (sys.argv[0] + "?mode=SHOW_CONTENT&item_type=" + item_type +
                   "&library_id=" + lib.get('id'))
            add_menu_directory_item(lib.get('name'), url, art=art)
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return

    if not library_id:
        library_id = lib_items[0].get('id')

    lib_ids = [library_id]

    if item_type and item_type.lower().find("movie") == -1:
        group_movies = False
    else:
        group_movies = settings.getSetting('group_movies') == "true"

    url_params = {
        "limit": 100,
        "fields": get_default_filters(),
    }

    if group_movies:
        url_params['collapseBoxSets'] = 'true'
        url_params['groupIntoCollections'] = 'true'

    if item_type == "Series":
        path = get_valence_url('/libraries/{}/shows'.format(lib_ids[0]), {})
        params["media_type"] = "tvshows"
    else:
        path = get_valence_url('/libraries/{}/items'.format(lib_ids[0]), url_params)

    log.debug("showContent Content Url: {0}".format(path))
    get_content(path, params)


def search_results_person(params):

    handle = int(sys.argv[1])

    person_id = params.get("person_id")

    # Valence server versions we target have no people endpoint,
    # so fall back to searching items by the person's name when available
    person_name = params.get("person_name")

    if person_name:
        params_new = dict(params)
        params_new["query"] = person_name
        params_new["item_type"] = "Movie"
        return search_results(params_new)

    xbmcgui.Dialog().ok(
        translate_string(30135),
        "Person details are not available on this Valence server version.")
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def search_results(params):

    item_type = params.get('item_type')
    query_string = params.get('query')
    if query_string:
        log.debug("query_string : {0}".format(query_string))
        query_string = unquote(query_string)
        log.debug("query_string : {0}".format(query_string))

    item_type = item_type.lower() if item_type else ''

    if item_type == 'movie':
        heading_type = translate_string(30231)
        content_type = 'movies'
    elif item_type == 'series':
        heading_type = translate_string(30229)
        content_type = 'tvshows'
    elif item_type == 'episode':
        heading_type = translate_string(30235)
        content_type = 'episodes'
        params["name_format"] = "Episode|episode_name_format"
    elif item_type in ["music", "audio", "musicalalbum"]:
        heading_type = 'Music'
        content_type = 'songs'
    elif item_type == "person":
        heading_type = 'Artists'
        content_type = 'artists'
    else:
        heading_type = item_type
        content_type = 'video'

    handle = int(sys.argv[1])

    if not query_string:
        home_window = HomeWindow()
        last_search = home_window.get_property("last_search")
        kb = xbmc.Keyboard()
        kb.setHeading("{} {}".format(
            heading_type.capitalize(), translate_string(30246).lower()
        ))
        kb.setDefault(last_search)
        kb.doModal()

        if kb.isConfirmed():
            user_input = kb.getText().strip()
        else:
            return

        home_window.set_property("last_search", user_input)
        log.debug('searchResults Called: {0}'.format(params))
        query = user_input

    else:
        query = query_string

    query = quote(query)
    log.debug("query : {0}".format(query))

    if (not item_type) or (not query):
        return

    # show a progress indicator if needed
    settings = xbmcaddon.Addon()
    progress = None
    if settings.getSetting('showLoadProgress') == "true":
        progress = xbmcgui.DialogProgress()
        progress.create(translate_string(30112))
        progress.update(0, translate_string(30113))

    # Valence 1.7 has no global search endpoint, so query each library
    libraries = api.get_libraries() or []

    query_libraries = []
    for lib in libraries:
        lib_kind = lib.get('kind')
        if lib_kind in ['movies', 'shows', 'anime', 'music']:
            query_libraries.append(lib)

    handle = int(sys.argv[1])
    content_types = set()
    all_dir_items = []

    for lib in query_libraries:
        lib_kind = lib.get('kind')
        lib_params = {
            'q': query,
            'limit': 20,
            'fields': get_default_filters(),
        }

        search_params = dict(params)
        if lib_kind in ['shows', 'anime']:
            # The Valence show index has no query-string search; match titles
            # locally after loading its series rows.
            search_params["title_query"] = query
            search_url = get_valence_url(
                '/libraries/{}/shows'.format(lib.get('id')), {})
        elif lib_kind == 'music':
            search_url = get_valence_url(
                '/music/artists', {'q': query, 'limit': 20})
        else:
            search_url = get_valence_url(
                '/libraries/{}/items'.format(lib.get('id')), lib_params)

        lib_dir_items, lib_detected, lib_total = process_directory(
            search_url, progress, search_params
        )
        log.debug("Search in library {0}: {1} results".format(
            lib.get('name'), len(lib_dir_items or [])))

        if lib_dir_items:
            all_dir_items.extend(lib_dir_items)
            if lib_detected:
                content_types.add(lib_detected)

    if not all_dir_items:
        if progress is not None:
            progress.close()
        xbmcgui.Dialog().ok(translate_string(30246),
                            translate_string(30305))
        return

    # set the dominant content type
    if 'Movie' in content_types:
        content_type = 'movies'
    elif 'Series' in content_types:
        content_type = 'tvshows'
    elif 'Episode' in content_types:
        content_type = 'episodes'
    elif content_types:
        content_type = 'video'
    else:
        content_type = 'video'

    xbmcplugin.setContent(handle, content_type)
    xbmcplugin.addDirectoryItems(handle, all_dir_items)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)

    if progress is not None:
        progress.update(100, translate_string(30125))
        progress.close()


def play_action(params):
    log.debug("== ENTER: PLAY ==")

    log.debug("PLAY ACTION PARAMS: {0}".format(params))
    item_id = params.get("item_id")

    auto_resume = params.get("auto_resume", "-1")
    if auto_resume == 'None':
        auto_resume = '-1'
    if auto_resume:
        auto_resume = int(auto_resume)
    else:
        auto_resume = -1

    log.debug("AUTO_RESUME: {0}".format(auto_resume))

    force_transcode = params.get("force_transcode", None) is not None
    log.debug("FORCE_TRANSCODE: {0}".format(force_transcode))

    media_source_id = params.get("media_source_id", "")
    log.debug("media_source_id: {0}".format(media_source_id))

    subtitle_stream_index = params.get("subtitle_stream_index")
    log.debug("subtitle_stream_index: {0}".format(subtitle_stream_index))

    audio_stream_index = params.get("audio_stream_index")
    log.debug("audio_stream_index: {0}".format(audio_stream_index))

    action = params.get("action", "play")

    # set the current playing item id
    # set all the playback info, this will be picked up by the service
    # the service will then start the playback

    # Let Kodi replace the active item when the new item is resolved/played.
    # Calling Player.stop() here blocks the plugin action while Kodi closes
    # and stats the previous stream URL, which can leave the UI unresponsive
    # through Kodi's HTTP timeout retries. It also stops playback for the
    # add-to-playlist action, which should leave the current item running.

    play_info = {}
    play_info["action"] = action
    play_info["item_id"] = item_id
    play_info["media_type"] = params.get("media_type")
    for metadata_key in ("title", "artist", "album", "track_number", "duration", "codec"):
        if params.get(metadata_key) is not None:
            play_info[metadata_key] = params.get(metadata_key)
    play_info["auto_resume"] = str(auto_resume)
    play_info["force_transcode"] = force_transcode
    play_info["media_source_id"] = media_source_id
    play_info["subtitle_stream_index"] = subtitle_stream_index
    play_info["audio_stream_index"] = audio_stream_index
    log.info("Sending valencecon_play_action : {0}".format(play_info))
    play_file(play_info)


def play_item_trailer(item_id):
    log.debug("== ENTER: playTrailer ==")
    handle = int(sys.argv[1]) if sys.argv and len(sys.argv) > 1 else -1
    if handle != -1:
        xbmcplugin.endOfDirectory(handle, succeeded=False, updateListing=False, cacheToDisc=False)

    # Valence doesn't have local trailers endpoint yet
    xbmcgui.Dialog().ok(translate_string(30135), "Trailers not available for Valence yet")
