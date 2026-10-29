from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import sys
import re

import xbmcaddon
import xbmcplugin
import xbmcgui
from six.moves.urllib.parse import quote, unquote, parse_qsl

from .datamanager import DataManager
from .lazylogger import LazyLogger
from .item_functions import add_gui_item, ItemDetails
from .tracking import timer
from .utils import (
    send_event_notification, translate_string,
    load_user_details, get_default_filters
)
from .valence import api

log = LazyLogger(__name__)


@timer
def get_content(url, params):
    log.debug("== ENTER: getContent ==")

    default_sort = params.get("sort")
    media_type = params.get("media_type", None)
    if not media_type:
        xbmcgui.Dialog().ok(translate_string(30135), translate_string(30139))

    log.debug("URL: {0}".format(url))
    log.debug("MediaType: {0}".format(media_type))
    pluginhandle = int(sys.argv[1])

    settings = xbmcaddon.Addon()
    # determine view type, map it from media type to view type
    view_type = ""
    content_type = ""
    media_type = str(media_type).lower().strip()
    
    # Parse URL to get query params
    from six.moves.urllib.parse import urlparse, parse_qs
    parsed_url = urlparse(url)
    url_params = parse_qs(parsed_url.query)
    # Convert lists to single values
    url_params = {k: v[0] if v else '' for k, v in url_params.items()}
    
    if media_type.startswith("movie"):
        view_type = "Movies"
        content_type = 'movies'
    elif media_type == "musicalbums":
        view_type = "Albums"
        content_type = 'albums'
    elif media_type == "musicartists":
        view_type = "Artists"
        content_type = 'artists'
    elif media_type == "musicartist":
        view_type = "Albums"
        content_type = 'albums'
    elif media_type == "music" or media_type == "audio" or media_type == "musicalbum":
        view_type = "Music"
        content_type = 'songs'
    elif media_type.startswith("boxsets"):
        view_type = "Movies"
        content_type = 'sets'
    elif media_type.startswith("boxset"):
        view_type = "BoxSets"
        content_type = 'movies'
    elif media_type == "tvshows":
        view_type = "Series"
        content_type = 'tvshows'
    elif media_type == "series":
        view_type = "Seasons"
        content_type = 'seasons'
    elif media_type == "season" or media_type == "episodes":
        view_type = "Episodes"
        content_type = 'episodes'
    elif media_type == "playlists":
        view_type = "Playlists"
    elif media_type == "musicvideos":
        view_type = "Music Videos"
        content_type = 'musicvideos'
    elif media_type == "livetv":
        view_type = "Live TV"
        content_type = 'livetv'
    elif media_type == "books":
        view_type = "Books"
        content_type = 'books'
    elif media_type == "mixed":
        content_type = 'videos'

    log.debug("media_type:{0} content_type:{1} view_type:{2} ".format(media_type, content_type, view_type))

    # show a progress indicator if needed
    progress = None
    if settings.getSetting('showLoadProgress') == "true":
        progress = xbmcgui.DialogProgress()
        progress.create(translate_string(30112))
        progress.update(0, translate_string(30113))

    # update url for paging
    start_index = int(url_params.get("offset", url_params.get("startIndex", 0)))
    url_limit = url_params.get("limit", url_params.get("Limit"))
    movie_page_limit = int(settings.getSetting('moviePageSize'))
    show_page_limit = int(settings.getSetting('showPageSize'))
    url_prev = None
    url_next = None
    
    if not url_limit or start_index > 0:
        if movie_page_limit > 0 and media_type.startswith("movie"):
            log.debug("UPDATING NEXT URL: {0}".format(url))
            log.debug("current_start : {0}".format(start_index))
            if start_index > 0:
                prev_index = start_index - movie_page_limit
                if prev_index < 0:
                    prev_index = 0
                url_prev = update_url_param(url, 'offset', str(prev_index))
                url_next = update_url_param(url, 'offset', str(start_index + movie_page_limit))
                log.debug("UPDATING NEXT URL: {0}".format(url_next))
            else:
                log.debug("ADDING NEXT URL: {0}".format(url))
                url_next = update_url_param(url, 'offset', str(start_index + movie_page_limit))
                url = update_url_param(url, 'offset', str(start_index))
                log.debug("ADDING NEXT URL: {0}".format(url_next))

        if show_page_limit > 0 and media_type.startswith("tvshow"):
            log.debug("UPDATING NEXT URL: {0}".format(url))
            log.debug("current_start : {0}".format(start_index))
            if start_index > 0:
                prev_index = start_index - show_page_limit
                if prev_index < 0:
                    prev_index = 0
                url_prev = update_url_param(url, 'offset', str(prev_index))
                url_next = update_url_param(url, 'offset', str(start_index + show_page_limit))
                log.debug("UPDATING NEXT URL: {0}".format(url_next))
            else:
                log.debug("ADDING NEXT URL: {0}".format(url))
                url_next = update_url_param(url, 'offset', str(start_index + show_page_limit))
                url = update_url_param(url, 'offset', str(start_index))
                log.debug("ADDING NEXT URL: {0}".format(url_next))

    use_cache = params.get("use_cache", "true") == "true"

    dir_items, detected_type, total_records = process_directory(url, progress, params, use_cache)
    if dir_items is None:
        return

    log.debug("total_records: {0}".format(total_records))

    if not url_limit or start_index > 0:
        # add paging items
        if movie_page_limit > 0 and media_type.startswith("movie"):
            if url_prev:
                list_item = xbmcgui.ListItem("Prev Page (" + str(start_index - movie_page_limit + 1) + "-" + str(start_index) +
                                             " of " + str(total_records) + ")")
                u = sys.argv[0] + "?url=" + quote(url_prev) + "&mode=GET_CONTENT&media_type=movies"
                log.debug("ADDING PREV ListItem: {0} - {1}".format(u, list_item))
                dir_items.insert(0, (u, list_item, True))

            if start_index + movie_page_limit < total_records:
                upper_count = start_index + (movie_page_limit * 2)
                if upper_count > total_records:
                    upper_count = total_records
                list_item = xbmcgui.ListItem("Next Page (" + str(start_index + movie_page_limit + 1) + "-" +
                                             str(upper_count) + " of " + str(total_records) + ")")
                u = sys.argv[0] + "?url=" + quote(url_next) + "&mode=GET_CONTENT&media_type=movies"
                log.debug("ADDING NEXT ListItem: {0} - {1}".format(u, list_item))
                dir_items.append((u, list_item, True))
        # add paging items
        if show_page_limit > 0 and media_type.startswith("tvshow"):
            if url_prev:
                list_item = xbmcgui.ListItem("Prev Page (" + str(start_index - show_page_limit + 1) + "-" + str(start_index) +
                                             " of " + str(total_records) + ")")
                u = sys.argv[0] + "?url=" + quote(url_prev) + "&mode=GET_CONTENT&media_type=tvshows"
                log.debug("ADDING PREV ListItem: {0} - {1}".format(u, list_item))
                dir_items.insert(0, (u, list_item, True))

            if start_index + show_page_limit < total_records:
                upper_count = start_index + (show_page_limit * 2)
                if upper_count > total_records:
                    upper_count = total_records
                list_item = xbmcgui.ListItem("Next Page (" + str(start_index + show_page_limit + 1) + "-" +
                                             str(upper_count) + " of " + str(total_records) + ")")
                u = sys.argv[0] + "?url=" + quote(url_next) + "&mode=GET_CONTENT&media_type=tvshows"
                log.debug("ADDING NEXT ListItem: {0} - {1}".format(u, list_item))
                dir_items.append((u, list_item, True))

    # set the Kodi content type
    if content_type:
        xbmcplugin.setContent(pluginhandle, content_type)
    elif detected_type is not None:
        # if the media type is not set then try to use the detected type
        log.debug("Detected content type: {0}".format(detected_type))
        if detected_type == "Movie":
            view_type = "Movies"
            content_type = 'movies'
        if detected_type == "Episode":
            view_type = "Episodes"
            content_type = 'episodes'
        xbmcplugin.setContent(pluginhandle, content_type)

    # set the sort items
    if movie_page_limit > 0 and media_type.startswith("movie"):
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_UNSORTED)
    elif show_page_limit > 0 and media_type.startswith("tvshow"):
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_UNSORTED)
    else:
        set_sort(pluginhandle, view_type, default_sort)

    xbmcplugin.addDirectoryItems(pluginhandle, dir_items)
    xbmcplugin.endOfDirectory(pluginhandle, cacheToDisc=False)

    # set the view based on saved value
    view_key = "view-" + content_type
    view_id = settings.getSetting(view_key)
    if view_id:
        log.debug("Setting view for type:{0} to id:{1}".format(view_key, view_id))
        display_items_notification = {"view_id": view_id}
        send_event_notification("set_view", display_items_notification)
    else:
        log.debug("No view id for view type:{0}".format(view_key))

    if progress is not None:
        progress.update(100, translate_string(30125))
        progress.close()

    return


def update_url_param(url, param_name, param_value):
    """Update or add a query parameter to a URL"""
    from six.moves.urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    query_params[param_name] = [param_value]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def set_sort(pluginhandle, view_type, default_sort):
    log.debug("SETTING_SORT for media type: {0}".format(view_type))

    if default_sort == "none":
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_UNSORTED)

    sorting_order_mapping = {
        "1": xbmcplugin.SORT_METHOD_UNSORTED,
        "2": xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE,
        "3": xbmcplugin.SORT_METHOD_VIDEO_YEAR,
        "4": xbmcplugin.SORT_METHOD_DATEADDED,
        "5": xbmcplugin.SORT_METHOD_GENRE,
        "6": xbmcplugin.SORT_METHOD_LABEL,
        "7": xbmcplugin.SORT_METHOD_VIDEO_RATING
    }

    settings = xbmcaddon.Addon()
    preset_sort_order = settings.getSetting("sort-" + view_type)
    log.debug("SETTING_SORT preset_sort_order: {0}".format(preset_sort_order))
    if preset_sort_order in sorting_order_mapping:
        xbmcplugin.addSortMethod(pluginhandle, sorting_order_mapping[preset_sort_order])

    if view_type == "BoxSets":
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE)
    elif view_type == "Episodes":
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_EPISODE)
    elif view_type == "Music":
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_TRACKNUM)
    else:
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE)
        xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_YEAR)

    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_DATEADDED)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_GENRE)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
    xbmcplugin.addSortMethod(pluginhandle, xbmcplugin.SORT_METHOD_LABEL)


@timer
def _filter_items_alpha(item_list, alpha_filter):
    """Filter a list of ItemDetails by initial letter. '#' matches non A-Z titles"""
    letter = alpha_filter.upper()

    def matches(name):
        if not name:
            return letter == '#'
        first = name[:1]
        if letter == '#':
            return not first.isalpha()
        return first.upper() == letter

    return [it for it in item_list if matches(getattr(it, 'name', None))]


def process_directory(url, progress, params, use_cache_data=False):
    log.debug("== ENTER: processDirectory ==")

    data_manager = DataManager()
    settings = xbmcaddon.Addon()
    server = settings.getSetting('server_address')
    user_details = load_user_details()

    name_format = params.get("name_format", None)
    name_format_type = None
    if name_format is not None:
        name_format = unquote(name_format)
        tokens = name_format.split("|")
        if len(tokens) == 2:
            name_format_type = tokens[0]
            name_format = settings.getSetting(tokens[1])
        else:
            name_format_type = None
            name_format = None

    gui_options = {}
    gui_options["server"] = server
    gui_options["name_format"] = name_format
    gui_options["name_format_type"] = name_format_type

    use_cache = settings.getSetting("use_cache") == "true" and use_cache_data
    default_filters = get_default_filters()

    # Fix skin shortcuts from pre-0.5.0
    item_limit = int(settings.getSetting("show_x_filtered_items"))
    
    # Update URL params for Valence
    # normalize per-url template tokens (url may be a single path or a list)
    def _normalize(u):
        u = u.replace('{server}', '')
        u = u.replace('{field_filters}', default_filters)
        u = u.replace('{ItemLimit}', str(item_limit))
        return u

    if isinstance(url, (list, tuple)):
        url = [_normalize(u) for u in url]
    else:
        url = _normalize(url)

    cache_file, item_list, total_records, cache_thread = data_manager.get_items(url, gui_options, use_cache)

    # optional client-side alpha filter (A-Z menus)
    alpha_filter = params.get("alpha")
    if alpha_filter:
        item_list = _filter_items_alpha(item_list, alpha_filter)

    # flatten single season
    flatten_single_season = settings.getSetting("flatten_single_season") == "true"
    if flatten_single_season and len(item_list) == 1 and item_list[0].item_type == "Season":
        season_id = item_list[0].id
        series_id = item_list[0].series_id
        # Build Valence URL for episodes in a season
        libraries = api.get_libraries()
        library_id = None
        for lib in libraries:
            if lib.get('kind') in ['shows', 'anime']:
                library_id = lib.get('id')
                break
        
        if library_id:
            season_url = get_valence_url('/libraries/{}/items'.format(library_id), {
                'seasonId': season_id,
                'seriesId': series_id,
                'limit': item_limit,
                'fields': default_filters,
                'type': 'episode',
            })
            if progress is not None:
                progress.close()
            params["media_type"] = "Episodes"
            get_content(season_url, params)
            return None, None, None

    hide_unwatched_details = settings.getSetting('hide_unwatched_details') == 'true'

    display_options = {}
    display_options["addCounts"] = settings.getSetting("addCounts") == 'true'
    display_options["addResumePercent"] = settings.getSetting("addResumePercent") == 'true'
    display_options["addSubtitleAvailable"] = settings.getSetting("addSubtitleAvailable") == 'true'
    display_options["addUserRatings"] = settings.getSetting("add_user_ratings") == 'true'

    show_empty_folders = settings.getSetting("show_empty_folders") == 'true'

    item_count = len(item_list)
    current_item = 1
    first_season_item = None
    total_unwatched = 0
    total_episodes = 0
    total_watched = 0

    detected_type = None
    dir_items = []
    OnlyTotallyUnwatchedTvShow = params.get("OnlyTotallyUnwatchedTvShow", None)
    
    for item_details in item_list:
        if OnlyTotallyUnwatchedTvShow == "1" and item_details.watched_episodes > 0:
            continue
        item_details.total_items = item_count

        if progress is not None:
            percent_done = (float(current_item) / float(item_count)) * 100
            progress.update(int(percent_done), translate_string(30126) + str(current_item))
            current_item = current_item + 1

        if detected_type is not None:
            if item_details.item_type != detected_type:
                detected_type = "mixed"
        else:
            detected_type = item_details.item_type

        if item_details.item_type == "Season" and first_season_item is None:
            log.debug("Setting First Season to : {0}".format(item_details.__dict__))
            first_season_item = item_details

        total_unwatched += item_details.unwatched_episodes
        total_episodes += item_details.total_episodes
        total_watched += item_details.watched_episodes

        # if set, for unwatched episodes dont show some of the info
        if hide_unwatched_details and item_details.item_type == "Episode" and item_details.play_count == 0:
            item_details.plot = "[Spoiler Alert]"
            item_details.art["poster"] = item_details.art["tvshow.poster"]
            item_details.art["thumb"] = item_details.art["tvshow.poster"]

        if item_details.is_folder is True:
            if item_details.item_type == "Series":
                # For Valence, navigate to seasons via library shows endpoint
                libraries = api.get_libraries()
                library_id = None
                for lib in libraries:
                    if lib.get('kind') in ['shows', 'anime']:
                        library_id = lib.get('id')
                        break
                
                if library_id:
                    u = get_valence_url('/libraries/{}/shows'.format(library_id), {
                        'seriesId': item_details.id,
                        'fields': default_filters,
                    })
                else:
                    u = item_details.id  # fallback

            elif item_details.item_type == "Season":
                # Navigate to episodes in season
                libraries = api.get_libraries()
                library_id = None
                for lib in libraries:
                    if lib.get('kind') in ['shows', 'anime']:
                        library_id = lib.get('id')
                        break
                
                if library_id:
                    u = get_valence_url('/libraries/{}/items'.format(library_id), {
                        'seasonId': item_details.id,
                        'seriesId': item_details.series_id,
                        'type': 'episode',
                        'limit': item_limit,
                        'fields': default_filters,
                    })
                else:
                    u = item_details.id

            else:
                # Generic folder - use items endpoint
                libraries = api.get_libraries()
                library_id = None
                for lib in libraries:
                    library_id = lib.get('id')
                    break
                
                if library_id:
                    u = get_valence_url('/libraries/{}/items'.format(library_id), {
                        'parentId': item_details.id,
                        'limit': item_limit,
                        'fields': default_filters,
                    })
                else:
                    u = item_details.id

            default_sort = item_details.item_type == "Playlist"

            if show_empty_folders or item_details.recursive_item_count != 0:
                gui_item = add_gui_item(u, item_details, display_options, default_sort=default_sort)
                if gui_item:
                    dir_items.append(gui_item)
            else:
                log.debug("Dropping empty folder item : {0}".format(item_details.__dict__))

        elif item_details.item_type == "MusicArtist":
            u = get_valence_url('/music/artists/{}/albums'.format(item_details.id), {
                'limit': item_limit,
                'fields': default_filters,
            })
            gui_item = add_gui_item(u, item_details, display_options)
            if gui_item:
                dir_items.append(gui_item)

        else:
            # Playable item
            u = item_details.id
            gui_item = add_gui_item(u, item_details, display_options, folder=False)
            if gui_item:
                dir_items.append(gui_item)

    # add the all episodes item
    show_all_episodes = settings.getSetting('show_all_episodes') == 'true'
    if (show_all_episodes
            and first_season_item is not None
            and len(dir_items) > 1
            and first_season_item.series_id is not None):
        
        libraries = api.get_libraries()
        library_id = None
        for lib in libraries:
            if lib.get('kind') in ['shows', 'anime']:
                library_id = lib.get('id')
                break
        
        if library_id:
            series_url = get_valence_url('/libraries/{}/items'.format(library_id), {
                'seriesId': first_season_item.series_id,
                'type': 'episode',
                'limit': item_limit,
                'fields': default_filters,
            })
            
            played = 0
            overlay = "7"
            if total_unwatched == 0:
                played = 1
                overlay = "6"

            item_details = ItemDetails()

            item_details.id = first_season_item.id
            item_details.name = translate_string(30290)
            item_details.art = first_season_item.art
            item_details.play_count = played
            item_details.overlay = overlay
            item_details.name_format = "Episode|episode_name_format"
            item_details.series_name = first_season_item.series_name
            item_details.item_type = "Season"
            item_details.unwatched_episodes = total_unwatched
            item_details.total_episodes = total_episodes
            item_details.watched_episodes = total_watched
            item_details.mode = "GET_CONTENT"

            gui_item = add_gui_item(series_url, item_details, display_options, folder=True)
            if gui_item:
                dir_items.append(gui_item)

    if cache_thread is not None:
        cache_thread.start()

    return dir_items, detected_type, total_records


def get_valence_url(path, params):
    """Helper to build Valence API URL"""
    from .utils import get_valence_url as _get_valence_url
    return _get_valence_url(path, params)