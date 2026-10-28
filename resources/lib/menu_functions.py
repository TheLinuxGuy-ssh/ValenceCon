from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import sys
import base64
import string

import xbmcplugin
import xbmcaddon
from six import ensure_binary, ensure_text
from six.moves.urllib.parse import quote

from .dir_functions import get_content
from .valence import api
from .kodi_utils import add_menu_directory_item, HomeWindow
from .lazylogger import LazyLogger
from .utils import (
    get_filtered_items_count_text, get_valence_url, translate_string, get_art_url,
    get_default_filters, get_current_profile_id
)
from .item_functions import get_art

log = LazyLogger(__name__)

__addon__ = xbmcaddon.Addon()
settings = xbmcaddon.Addon()


# Valence library kinds
LIBRARY_KINDS = {
    'movies': {'label': 30256, 'media_type': 'movies', 'valence_type': 'Movie'},
    'shows': {'label': 30261, 'media_type': 'tvshows', 'valence_type': 'Series'},
    'anime': {'label': 30261, 'media_type': 'tvshows', 'valence_type': 'Series'},
    'music': {'label': 30320, 'media_type': 'music', 'valence_type': 'MusicAlbum'},
    'books': {'label': 30320, 'media_type': 'books', 'valence_type': 'Book'},
}


def build_library_url(library_id, params=None):
    """Build a URL for browsing a library"""
    default_params = {
        'limit': 100,
        'fields': get_default_filters(),
    }
    if params:
        default_params.update(params)
    return get_valence_url('/libraries/{}/items'.format(library_id), default_params)


def build_library_shows_url(library_id, params=None):
    """Build a URL for browsing shows in a library"""
    default_params = {
        'limit': 100,
        'fields': get_default_filters(),
    }
    if params:
        default_params.update(params)
    return get_valence_url('/libraries/{}/shows'.format(library_id), default_params)


def add_library_menu_items(library, view_name, item_limit):
    """Add standard menu items for a library based on its kind"""
    handle = int(sys.argv[1])
    library_id = library.get('id')
    library_kind = library.get('kind', 'mixed')
    
    # Map library kind to display functions
    if library_kind in ['movies', 'shows', 'anime']:
        display_movies_or_shows_type(library, view_name, item_limit)
    elif library_kind == 'music':
        display_music_type(None, library)
    elif library_kind == 'books':
        display_books_type(None, library)
    elif library_kind == 'livetv':
        display_livetv_type(None, library)


def display_movies_or_shows_type(library, view_name, item_limit):
    """Display menu for movies or shows library"""
    handle = int(sys.argv[1])
    library_id = library.get('id')
    library_kind = library.get('kind', 'movies')
    
    # Determine if movies or shows
    is_movies = library_kind == 'movies'
    valence_type = 'Movie' if is_movies else 'Series'
    media_type = 'movies' if is_movies else 'tvshows'
    view_label = translate_string(30256) if is_movies else translate_string(30261)
    
    if view_name:
        view_label = view_name
    
    # All items
    base_params = {
        'limit': item_limit,
        'fields': get_default_filters(),
    }
    path = build_library_url(library_id, base_params)
    
    if settings.getSetting("interface_mode") == "1":
        get_content(path, {"media_type": media_type})
        return

    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=" + media_type
    add_menu_directory_item('{}{}'.format(view_label, translate_string(30405)), url)
    
    if is_movies:
        # Favorite Movies
        fav_params = base_params.copy()
        fav_params['filters'] = 'favorite'
        path = build_library_url(library_id, fav_params)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies"
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30414)), url)
        
        # Unwatched Movies
        unwatched_params = base_params.copy()
        unwatched_params['filters'] = 'unplayed'
        path = build_library_url(library_id, unwatched_params)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies"
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30285)), url)
        
        # Recently Watched
        recent_watched = base_params.copy()
        recent_watched['filters'] = 'played'
        recent_watched['sort'] = 'datePlayed'
        recent_watched['sortOrder'] = 'desc'
        path = build_library_url(library_id, recent_watched)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies&sort=none"
        add_menu_directory_item('{}{}{}'.format(view_label, translate_string(30349), get_filtered_items_count_text()), url)
        
        # Resumable Movies
        resumable = base_params.copy()
        resumable['filters'] = 'resumable'
        resumable['sort'] = 'datePlayed'
        resumable['sortOrder'] = 'desc'
        path = build_library_url(library_id, resumable)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies&sort=none"
        add_menu_directory_item('{}{}{}'.format(view_label, translate_string(30267), get_filtered_items_count_text()), url)
        
        # Recently Added
        recent_added = base_params.copy()
        recent_added['sort'] = 'addedAt'
        recent_added['sortOrder'] = 'desc'
        path = build_library_url(library_id, recent_added)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies&sort=none"
        add_menu_directory_item('{}{}{}'.format(view_label, translate_string(30268), get_filtered_items_count_text()), url)
        
        # Genres
        path = "plugin://plugin.video.valencecon/?mode=GENRES&library_id={}&kind=movies".format(library_id)
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30325)), path)
        
        # Alpha Picker
        path = "plugin://plugin.video.valencecon/?mode=MOVIE_ALPHA&library_id={}".format(library_id)
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30404)), path)
        
        # Years/Decades
        path = "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=show_movie_years&library_id={}".format(library_id)
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30411)), path)
        
        path = "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=show_movie_years&group=true&library_id={}".format(library_id)
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30412)), path)
    else:
        # Shows/Anime
        # Favorite Shows
        fav_params = base_params.copy()
        fav_params['filters'] = 'favorite'
        path = build_library_shows_url(library_id, fav_params)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=tvshows"
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30414)), url)
        
        # Shows with unplayed
        unplayed_params = base_params.copy()
        unplayed_params['filters'] = 'unplayed'
        path = build_library_shows_url(library_id, unplayed_params)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=tvshows"
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30285)), url)
        
        # Totally unwatched
        totally_unwatched = base_params.copy()
        totally_unwatched['filters'] = 'unplayed'
        path = build_library_shows_url(library_id, totally_unwatched)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=tvshows&OnlyTotallyUnwatched=1"
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30454)), url)
        
        # In progress episodes
        in_progress = {
            'limit': item_limit,
            'sort': 'datePlayed',
            'sortOrder': 'desc',
            'filters': 'resumable',
            'type': 'episode',
            'fields': get_default_filters(),
        }
        path = build_library_url(library_id, in_progress)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=Episodes&sort=none"
        url += "&name_format=" + quote('Episode|episode_name_format')
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30267) + get_filtered_items_count_text()), url)
        
        # Latest Episodes
        latest_eps = {
            'limit': item_limit,
            'sort': 'addedAt',
            'sortOrder': 'desc',
            'type': 'episode',
            'fields': get_default_filters(),
        }
        path = build_library_url(library_id, latest_eps)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=Episodes&sort=none"
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30288) + get_filtered_items_count_text()), url)
        
        # Recently Added Episodes
        recent_eps = {
            'limit': item_limit,
            'sort': 'addedAt',
            'sortOrder': 'desc',
            'filters': 'notfolder',
            'type': 'episode',
            'fields': get_default_filters(),
        }
        path = build_library_url(library_id, recent_eps)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=Episodes&sort=none"
        url += "&name_format=" + quote('Episode|episode_name_format')
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30268) + get_filtered_items_count_text()), url)
        
        # Next Up Episodes
        next_up = {
            'limit': item_limit,
            'sort': 'datePlayed',
            'sortOrder': 'desc',
            'type': 'episode',
            'fields': get_default_filters(),
        }
        path = build_library_url(library_id, next_up)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=Episodes&sort=none"
        url += "&name_format=" + quote('Episode|episode_name_format')
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30278) + get_filtered_items_count_text()), url)
        
        # Genres
        path = "plugin://plugin.video.valencecon/?mode=GENRES&library_id={}&kind=shows".format(library_id)
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30325)), path)
        
        # Alpha picker
        path = "plugin://plugin.video.valencecon/?mode=TVSHOW_ALPHA&library_id={}".format(library_id)
        add_menu_directory_item('{}{}'.format(view_label, translate_string(30404)), path)


def display_music_type(menu_params, view):
    handle = int(sys.argv[1])
    library = view if view else menu_params
    view_name = library.get("Name", translate_string(30320))
    library_id = library.get("Id")

    item_limit = settings.getSetting("show_x_filtered_items")

    # All albums
    params = {
        'limit': item_limit,
        'fields': get_default_filters(),
    }
    path = build_library_url(library_id, params)

    if settings.getSetting("interface_mode") == "1":
        get_content(path, {"media_type": "MusicAlbums"})
        return

    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=MusicAlbums"
    add_menu_directory_item(view_name + translate_string(30320), url)

    # Recently added
    recent_params = params.copy()
    recent_params['sort'] = 'addedAt'
    recent_params['sortOrder'] = 'desc'
    path = build_library_url(library_id, recent_params)
    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=MusicAlbums"
    add_menu_directory_item(view_name + translate_string(30268) + get_filtered_items_count_text(), url)

    # Artists
    artist_params = {
        'limit': item_limit,
        'fields': get_default_filters(),
    }
    path = get_valence_url('/music/artists', artist_params)
    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=MusicArtists"
    add_menu_directory_item(view_name + translate_string(30321), url)

    # Genres
    path = "plugin://plugin.video.valencecon/?mode=GENRES&library_id={}&kind=music".format(library_id)
    add_menu_directory_item(view_name + translate_string(30325), path)

    # Artist Alpha picker
    path = "plugin://plugin.video.valencecon/?mode=ARTIST_ALPHA&library_id={}".format(library_id)
    add_menu_directory_item('{} - {}{}'.format(
        view_name, translate_string(30323), translate_string(30404)), path)

    # Shuffle All
    path = "plugin://plugin.video.valencecon/?mode=PLAY&action=shuffle&library_id={}".format(library_id)
    add_menu_directory_item('{} - {}'.format(
        view_name, translate_string(30448)), path, False)

    xbmcplugin.endOfDirectory(handle)


def display_books_type(menu_params, view):
    handle = int(sys.argv[1])
    library = view if view else menu_params
    view_name = library.get("Name", translate_string(30320))
    library_id = library.get("Id")

    item_limit = settings.getSetting("show_x_filtered_items")

    # All books
    params = {
        'limit': item_limit,
        'fields': get_default_filters(),
    }
    path = build_library_url(library_id, params)

    if settings.getSetting("interface_mode") == "1":
        get_content(path, {"media_type": "books"})
        return

    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=books"
    add_menu_directory_item(view_name + translate_string(30320), url)

    xbmcplugin.endOfDirectory(handle)


def display_livetv_type(menu_params, view):
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'files')

    library = view if view else menu_params
    view_name = library.get("Name", "Live TV")
    library_id = library.get("Id")

    # Channels
    params = {
        'limit': 100,
        'fields': get_default_filters(),
    }
    path = get_valence_url('/live/channels', params)
    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=livetv"
    add_menu_directory_item(view_name + translate_string(30360), url)

    # Guide
    guide_params = params.copy()
    guide_params['now'] = 'true'
    path = get_valence_url('/live/guide', guide_params)
    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=livetv"
    add_menu_directory_item(view_name + translate_string(30361), url)

    xbmcplugin.endOfDirectory(handle)


def display_main_menu():
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'files')

    if settings.getSetting("interface_mode") == "1":
        display_library_views(None)
        return

    add_menu_directory_item(translate_string(30406),
                            "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=library")
    add_menu_directory_item(translate_string(30407),
                            "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=show_global_types")
    add_menu_directory_item(translate_string(30408),
                            "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=show_custom_widgets")
    add_menu_directory_item(translate_string(30409),
                            "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=addon_items")

    xbmcplugin.endOfDirectory(handle)


def display_menu(params):
    menu_type = params.get("type")
    if menu_type == "library":
        display_library_views(params)
    elif menu_type == "library_item":
        display_library_view(params)
    elif menu_type == "show_global_types":
        show_global_types(params)
    elif menu_type == "global_list_movies":
        display_global_movies(params)
    elif menu_type == "global_list_tvshows":
        display_global_tvshows(params)
    elif menu_type == "show_custom_widgets":
        show_widgets()
    elif menu_type == "addon_items":
        display_addon_menu(params)
    elif menu_type == "show_movie_years":
        show_movie_years(params)
    elif menu_type == "show_movie_tags":
        show_movie_tags(params)


def show_global_types(params):
    handle = int(sys.argv[1])

    # Continue watching
    up_next = api.get_up_next()
    if up_next and up_next.get('episodes'):
        add_menu_directory_item(translate_string(30445),
                                "plugin://plugin.video.valencecon/?mode=GET_CONTENT&url=" + quote(api.server + "/api/up-next") +
                                "&media_type=Episodes" +
                                "&name_format=" + quote("Episode|episode_name_format"))

    add_menu_directory_item(translate_string(30256),
                            "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=global_list_movies")
    add_menu_directory_item(translate_string(30261),
                            "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=global_list_tvshows")

    xbmcplugin.endOfDirectory(handle)


def display_global_movies(params):
    """Display global movie lists across all movie libraries"""
    handle = int(sys.argv[1])
    item_limit = settings.getSetting("show_x_filtered_items")
    hide_watched = settings.getSetting("hide_watched") == "true"
    group_movies = settings.getSetting('group_movies') == "true"

    # Get all movie libraries
    libraries = api.get_libraries()
    movie_libs = [l for l in libraries if l.get('kind') == 'movies'] if libraries else []

    if not movie_libs:
        xbmcplugin.endOfDirectory(handle)
        return

    # Build combined URL for all movie libraries
    lib_ids = ','.join([l['id'] for l in movie_libs])
    
    base_params = {
        'limit': item_limit,
        'fields': get_default_filters(),
        'libraryIds': lib_ids,
    }

    # All Movies
    path = get_valence_url('/libraries/items', base_params)
    
    if settings.getSetting("interface_mode") == "1":
        get_content(path, {"media_type": "movies"})
        return

    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies"
    add_menu_directory_item(translate_string(30256) + translate_string(30405), url)

    # Favorite Movies
    fav_params = base_params.copy()
    fav_params['filters'] = 'favorite'
    path = get_valence_url('/libraries/items', fav_params)
    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies"
    add_menu_directory_item(translate_string(30414), url)

    # Unwatched Movies
    unwatched_params = base_params.copy()
    unwatched_params['filters'] = 'unplayed'
    path = get_valence_url('/libraries/items', unwatched_params)
    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies"
    add_menu_directory_item(translate_string(30285), url)

    # Recently Added
    recent_params = base_params.copy()
    if hide_watched:
        recent_params['filters'] = 'unplayed'
    recent_params['sort'] = 'addedAt'
    recent_params['sortOrder'] = 'desc'
    path = get_valence_url('/libraries/items', recent_params)
    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies&sort=none"
    add_menu_directory_item(translate_string(30268) + get_filtered_items_count_text(), url)

    # Genres
    path = "plugin://plugin.video.valencecon/?mode=GENRES&kind=movies"
    add_menu_directory_item(translate_string(30325), path)

    # Alpha Picker
    path = "plugin://plugin.video.valencecon/?mode=MOVIE_ALPHA"
    add_menu_directory_item(translate_string(30404), path)

    xbmcplugin.endOfDirectory(handle)


def display_global_tvshows(params):
    """Display global TV show lists across all show libraries"""
    handle = int(sys.argv[1])
    item_limit = settings.getSetting("show_x_filtered_items")

    libraries = api.get_libraries()
    show_libs = [l for l in libraries if l.get('kind') in ['shows', 'anime']] if libraries else []

    if not show_libs:
        xbmcplugin.endOfDirectory(handle)
        return

    lib_ids = ','.join([l['id'] for l in show_libs])
    
    base_params = {
        'limit': item_limit,
        'fields': get_default_filters(),
        'libraryIds': lib_ids,
    }

    # All TV Shows
    path = get_valence_url('/libraries/shows', base_params)
    
    if settings.getSetting("interface_mode") == "1":
        get_content(path, {"media_type": "tvshows"})
        return

    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=tvshows"
    add_menu_directory_item(translate_string(30261) + translate_string(30405), url)

    # Next Up Episodes
    next_up_params = {
        'limit': item_limit,
        'type': 'episode',
        'libraryIds': lib_ids,
        'sort': 'datePlayed',
        'sortOrder': 'desc',
        'fields': get_default_filters(),
    }
    path = get_valence_url('/libraries/items', next_up_params)
    url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=Episodes&sort=none"
    url += "&name_format=" + quote('Episode|episode_name_format')
    add_menu_directory_item(translate_string(30278) + get_filtered_items_count_text(), url)

    # Genres
    path = "plugin://plugin.video.valencecon/?mode=GENRES&kind=shows"
    add_menu_directory_item(translate_string(30325), path)

    # Alpha picker
    path = "plugin://plugin.video.valencecon/?mode=TVSHOW_ALPHA"
    add_menu_directory_item(translate_string(30404), path)

    xbmcplugin.endOfDirectory(handle)


def display_addon_menu(params):
    add_menu_directory_item(translate_string(30246), "plugin://plugin.video.valencecon/?mode=SEARCH")
    add_menu_directory_item(translate_string(30017), "plugin://plugin.video.valencecon/?mode=SHOW_SERVER_SESSIONS")
    add_menu_directory_item(translate_string(30012), "plugin://plugin.video.valencecon/?mode=CHANGE_PROFILE")
    add_menu_directory_item(translate_string(30011), "plugin://plugin.video.valencecon/?mode=DETECT_SERVER")
    add_menu_directory_item(translate_string(30435), "plugin://plugin.video.valencecon/?mode=DETECT_CONNECTION_SPEED")
    add_menu_directory_item(translate_string(30254), "plugin://plugin.video.valencecon/?mode=SHOW_SETTINGS")
    add_menu_directory_item(translate_string(30395), "plugin://plugin.video.valencecon/?mode=CLEAR_CACHE")
    add_menu_directory_item(translate_string(30293), "plugin://plugin.video.valencecon/?mode=CACHE_ARTWORK")
    add_menu_directory_item("Clone default skin", "plugin://plugin.video.valencecon/?mode=CLONE_SKIN")

    handle = int(sys.argv[1])
    xbmcplugin.endOfDirectory(handle)


def display_library_views(params):
    """Display Valence libraries as main menu items"""
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'files')

    server = settings.getSetting('server_address')
    if server is None:
        return

    libraries = api.get_libraries()
    if not libraries:
        return

    item_limit = settings.getSetting("show_x_filtered_items")

    for library in libraries:
        library_kind = library.get('kind', 'mixed')
        view_name = library.get("Name")
        art = get_art(item=library, server=server)
        art['landscape'] = get_art_url(library, "Primary", server=server)

        plugin_path = "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=library_item&library_id=" + library.get("Id")

        add_menu_directory_item(view_name, plugin_path, art=art)

    xbmcplugin.endOfDirectory(handle)


def display_library_view(params):
    """Display a specific library's content"""
    library_id = params.get("library_id")
    if not library_id:
        return

    libraries = api.get_libraries()
    library = next((l for l in libraries if l.get('id') == library_id), None)
    
    if not library:
        return

    library_kind = library.get('kind', 'mixed')
    view_name = library.get("Name")
    item_limit = settings.getSetting("show_x_filtered_items")

    if library_kind in ['movies', 'shows', 'anime']:
        display_movies_or_shows_type(library, view_name, item_limit)
    elif library_kind == 'music':
        display_music_type(params, library)
    elif library_kind == 'books':
        display_books_type(params, library)
    elif library_kind == 'livetv':
        display_livetv_type(params, library)


def show_widgets():
    """Widget content for home screen"""
    add_menu_directory_item("All Movies",
                            'plugin://plugin.video.valencecon/library/movies')

    item_limit_text = get_filtered_items_count_text()

    add_menu_directory_item(translate_string(30257) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=recent_movies')
    add_menu_directory_item(translate_string(30258) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=inprogress_movies')
    add_menu_directory_item(translate_string(30269) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=random_movies')
    add_menu_directory_item(translate_string(30403) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=movie_recommendations')

    add_menu_directory_item(translate_string(30287) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=recent_tvshows')
    add_menu_directory_item(translate_string(30455) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=random_tvshows')
    add_menu_directory_item(translate_string(30263) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=recent_episodes')
    add_menu_directory_item(translate_string(30264) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=inprogress_episodes')
    add_menu_directory_item(translate_string(30265) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=nextup_episodes')
    add_menu_directory_item(translate_string(30457) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=recent_all')
    add_menu_directory_item(translate_string(30458),
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=favorites_all')
    add_menu_directory_item(translate_string(30456) + item_limit_text,
                            'plugin://plugin.video.valencecon/?mode=WIDGET_CONTENT&type=random_all')

    xbmcplugin.endOfDirectory(int(sys.argv[1]))


def show_search():
    add_menu_directory_item(translate_string(30231), 'plugin://plugin.video.valencecon/?mode=NEW_SEARCH&item_type=Movie')
    add_menu_directory_item(translate_string(30229), 'plugin://plugin.video.valencecon/?mode=NEW_SEARCH&item_type=Series')
    add_menu_directory_item(translate_string(30235), 'plugin://plugin.video.valencecon/?mode=NEW_SEARCH&item_type=Episode')
    add_menu_directory_item(translate_string(30337), 'plugin://plugin.video.valencecon/?mode=NEW_SEARCH&item_type=Audio')
    add_menu_directory_item(translate_string(30338), 'plugin://plugin.video.valencecon/?mode=NEW_SEARCH&item_type=MusicAlbum')
    add_menu_directory_item(translate_string(30339), 'plugin://plugin.video.valencecon/?mode=NEW_SEARCH&item_type=Person')

    xbmcplugin.endOfDirectory(int(sys.argv[1]))


# Placeholder functions for compatibility - will be implemented in Valence style
def show_movie_years(menu_params):
    """Show movie years - uses library-facets"""
    library_id = menu_params.get("library_id")
    log.debug("show_movie_years for library: {}".format(library_id))
    # For now, redirect to genres or use decades from facets
    facets = api.get_library_facets()
    decades = facets.get('decades', []) if facets else []
    
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'years')
    
    params = {
        'fields': get_default_filters(),
        'limit': settings.getSetting("show_x_filtered_items"),
    }
    if library_id:
        params['libraryIds'] = library_id

    for decade in decades:
        decade_name = str(decade) + "s"
        decade_params = params.copy()
        decade_params['decade'] = decade
        path = get_valence_url('/libraries/items', decade_params)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies"
        add_menu_directory_item(decade_name, url)

    xbmcplugin.endOfDirectory(handle)


def show_movie_tags(menu_params):
    """Show movie tags/genres - uses library-facets"""
    library_id = menu_params.get("library_id")
    log.debug("show_movie_tags for library: {}".format(library_id))
    
    facets = api.get_library_facets()
    genres = facets.get('genres', []) if facets else []
    
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'genres')
    
    params = {
        'fields': get_default_filters(),
        'limit': settings.getSetting("show_x_filtered_items"),
    }
    if library_id:
        params['libraryIds'] = library_id

    for genre in sorted(genres):
        genre_params = params.copy()
        genre_params['genre'] = genre
        path = get_valence_url('/libraries/items', genre_params)
        url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies"
        add_menu_directory_item(genre, url)

    xbmcplugin.endOfDirectory(handle)


def set_library_window_values(force=False):
    log.debug("set_library_window_values Called forced={0}".format(force))
    home_window = HomeWindow()

    already_set = home_window.get_property("view_item.0.name")
    if not force and already_set:
        return

    for index in range(0, 20):
        home_window.clear_property("view_item.%i.name" % index)
        home_window.clear_property("view_item.%i.id" % index)
        home_window.clear_property("view_item.%i.type" % index)
        home_window.clear_property("view_item.%i.thumb" % index)

    libraries = api.get_libraries()
    if not libraries:
        return

    server = settings.getSetting('server_address')

    index = 0
    for library in libraries:
        library_kind = library.get('kind', 'mixed')
        if library_kind in ["movies", "shows", "anime", "music", "books", "livetv"]:
            name = library.get("Name")
            library_id = library.get("Id")

            prop_name = "view_item.%i.name" % index
            home_window.set_property(prop_name, name)
            log.debug("set_library_window_values: plugin.video.valencecon-{0}={1}".format(prop_name, name))

            prop_name = "view_item.%i.id" % index
            home_window.set_property(prop_name, library_id)
            log.debug("set_library_window_values: plugin.video.valencecon-{0}={1}".format(prop_name, library_id))

            prop_name = "view_item.%i.type" % index
            home_window.set_property(prop_name, library_kind)
            log.debug("set_library_window_values: plugin.video.valencecon-{0}={1}".format(prop_name, library_kind))

            thumb = get_art_url(library, "Primary", server=server)
            prop_name = "view_item.%i.thumb" % index
            home_window.set_property(prop_name, thumb)
            log.debug("set_library_window_values: plugin.video.valencecon-{0}={1}".format(prop_name, thumb))

            index += 1
            if index >= 20:
                break