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
    view_name = library.get("name") or translate_string(30320)
    library_id = library.get("id")

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
    view_name = library.get("name") or translate_string(30320)
    library_id = library.get("id")

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
    library_id = library.get("id")

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
    """Display movie sections per movie library (per-library API routes)"""
    handle = int(sys.argv[1])
    item_limit = settings.getSetting("show_x_filtered_items")
    hide_watched = settings.getSetting("hide_watched") == "true"

    libraries = api.get_libraries() or []
    movie_libs = [l for l in libraries if l.get('kind') == 'movies']

    if not movie_libs:
        xbmcplugin.endOfDirectory(handle)
        return

    if len(movie_libs) > 1:
        # Offer each library explicitly since Valence queries are per-library
        for lib in movie_libs:
            art = get_art(item=lib, server=settings.getSetting('server_address'))
            path = "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=library_item&library_id=" + lib.get("id")
            add_menu_directory_item(lib.get('name'), path, art=art)
        xbmcplugin.endOfDirectory(handle)
        return

    library = movie_libs[0]
    display_library_view({"library_id": library.get("id")})


def display_global_tvshows(params):
    """Display TV show sections per show library (per-library API routes)"""
    handle = int(sys.argv[1])
    item_limit = settings.getSetting("show_x_filtered_items")

    libraries = api.get_libraries() or []
    show_libs = [l for l in libraries if l.get('kind') in ['shows', 'anime']]

    if not show_libs:
        xbmcplugin.endOfDirectory(handle)
        return

    if len(show_libs) > 1:
        for lib in show_libs:
            art = get_art(item=lib, server=settings.getSetting('server_address'))
            path = "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=library_item&library_id=" + lib.get("id")
            add_menu_directory_item(lib.get('name'), path, art=art)
        xbmcplugin.endOfDirectory(handle)
        return

    library = show_libs[0]
    display_library_view({"library_id": library.get("id")})


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
        view_name = library.get("name") or library.get("Name")
        art = get_art(item=library, server=server)
        art['landscape'] = get_art_url(library, "Primary", server=server)

        plugin_path = "plugin://plugin.video.valencecon/?mode=SHOW_ADDON_MENU&type=library_item&library_id=" + library.get("id")

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
    view_name = library.get("name") or library.get("Name")
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


def show_movie_years(menu_params):
    """Deprecated: Valence 1.7 has no year filter; keep menu mapping safe"""
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'files')
    f_year_tags = translate_string(30411)
    add_menu_directory_item(f_year_tags,
                            "plugin://plugin.video.valencecon/?mode=GET_CONTENT&nocontent=1")
    xbmcplugin.endOfDirectory(handle)


def show_movie_tags(menu_params):
    """Show movie genre menus based on library facets (per-library routes)"""
    library_id = menu_params.get("library_id")
    log.debug("show_movie_tags for library: {}".format(library_id))

    facets = api.get_library_facets()
    genres = facets.get('genres', []) if facets else []

    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'genres')

    libraries = _libraries_for_kind(['movies'])
    if not libraries:
        xbmcplugin.endOfDirectory(handle)
        return

    if library_id:
        libraries = [l for l in libraries if l.get('id') == library_id] or libraries[:1]

    params = {
        'fields': get_default_filters(),
        'limit': settings.getSetting("show_x_filtered_items"),
    }

    for genre in sorted(genres):
        for library in libraries:
            lib_params = params.copy()
            lib_params['genres'] = quote(genre)
            path = get_valence_url('/libraries/{}/items'.format(library.get('id')), lib_params)
            url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies"
            title = genre if len(libraries) == 1 else "{} ({})".format(genre, library.get('name') or '')
            add_menu_directory_item(title, url)

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
            name = library.get("name") or library.get("Name")
            library_id = library.get("id")

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

def _libraries_for_kind(kinds):
    """Return libraries whose kind is in kinds, tolerating failed requests"""
    libraries = api.get_libraries()
    if not libraries:
        return []
    return [l for l in libraries if l.get('kind') in kinds]


def _library_finder_url(library_id):
    """GET_CONTENT URL listing all items of a library with client-side alpha filter"""
    params = {
        'limit': 500,
        'sort': 'title',
        'fields': get_default_filters(),
    }
    path = get_valence_url('/libraries/{}/items'.format(library_id), params)
    return path


def show_movie_alpha_list(menu_params):
    """Movies A-Z: per-letter GET_CONTENT URLs with client-side alpha filtering"""
    log.debug("== ENTER: showMovieAlphaList() ==")
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'movies')

    libraries = _libraries_for_kind(['movies'])
    if not libraries:
        xbmcplugin.endOfDirectory(handle)
        return

    library_id = menu_params.get('library_id')
    if library_id:
        libraries = [l for l in libraries if l.get('id') == library_id] or libraries[:1]

    library = libraries[0]
    base_path = _library_finder_url(library.get('id'))

    for alpha_name in '#' + string.ascii_uppercase:
        url = (sys.argv[0] + "?url=" + quote(base_path) +
               "&mode=GET_CONTENT&media_type=movies&alpha=" + alpha_name)
        log.debug("addMenuDirectoryItem: {0} ({1})".format(alpha_name, url))
        add_menu_directory_item(alpha_name, url)

    # Utilities pages
    path = "plugin://plugin.video.valencecon/?mode=MOVIE_PAGES&library_id={}".format(library.get('id'))
    add_menu_directory_item(translate_string(30397), path)

    xbmcplugin.endOfDirectory(handle)


def show_tvshow_alpha_list(menu_params):
    """TV shows A-Z: per-letter GET_CONTENT URLs with client-side alpha filtering"""
    log.debug("== ENTER: showTvShowAlphaList() ==")
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'tvshows')

    libraries = _libraries_for_kind(['shows', 'anime'])
    if not libraries:
        xbmcplugin.endOfDirectory(handle)
        return

    library_id = menu_params.get('library_id')
    if library_id:
        libraries = [l for l in libraries if l.get('id') == library_id] or libraries[:1]

    library = libraries[0]
    params = {
        'limit': 500,
        'sort': 'title',
        'fields': get_default_filters(),
    }
    base_path = get_valence_url('/libraries/{}/shows'.format(library.get('id')), params)

    for alpha_name in '#' + string.ascii_uppercase:
        url = (sys.argv[0] + "?url=" + quote(base_path) +
               "&mode=GET_CONTENT&media_type=tvshows&alpha=" + alpha_name)
        log.debug("addMenuDirectoryItem: {0} ({1})".format(alpha_name, url))
        add_menu_directory_item(alpha_name, url)

    xbmcplugin.endOfDirectory(handle)


def show_artist_alpha_list(menu_params):
    """Music artists A-Z with client-side alpha filtering"""
    log.debug("== ENTER: showArtistAlphaList() ==")
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'artists')

    params = {
        'limit': 1000,
        'fields': get_default_filters(),
    }
    base_path = get_valence_url('/music/artists', params)

    for alpha_name in '#' + string.ascii_uppercase:
        url = (sys.argv[0] + "?url=" + quote(base_path) +
               "&mode=GET_CONTENT&media_type=MusicArtist&alpha=" + alpha_name)
        log.debug("addMenuDirectoryItem: {0} ({1})".format(alpha_name, url))
        add_menu_directory_item(alpha_name, url)

    xbmcplugin.endOfDirectory(handle)


def show_genre_list(menu_params):
    """Genre browsing based on library facets, per-library item routes"""
    log.debug("== ENTER: showGenreList() ==")
    handle = int(sys.argv[1])

    kind = menu_params.get("kind") or "movies"
    library_id = menu_params.get("library_id")

    xbmcplugin.setContent(handle, 'genres')

    kinds = ['movies'] if kind == 'movies' else ['shows', 'anime'] if kind == 'shows' else ['music']
    libraries = _libraries_for_kind(kinds)
    if not libraries:
        xbmcplugin.endOfDirectory(handle)
        return

    if library_id:
        libraries = [l for l in libraries if l.get('id') == library_id] or libraries[:1]

    facets = api.get_library_facets()
    genres = facets.get('genres', []) if facets else []

    params = {
        'fields': get_default_filters(),
        'limit': settings.getSetting("show_x_filtered_items"),
    }

    for genre in sorted(genres):
        for library in libraries:
            lib_params = params.copy()
            lib_params['genres'] = quote(genre)
            if kind == 'shows':
                lib_params['type'] = 'episode'
                path = get_valence_url('/libraries/{}/items'.format(library.get('id')), lib_params)
                url = (sys.argv[0] + "?url=" + quote(path) +
                       "&mode=GET_CONTENT&media_type=tvshows")
            else:
                path = get_valence_url('/libraries/{}/items'.format(library.get('id')), lib_params)
                url = sys.argv[0] + "?url=" + quote(path) + "&mode=GET_CONTENT&media_type=movies"
            title = genre if len(libraries) == 1 else "{} ({})".format(genre, library.get('name') or '')
            add_menu_directory_item(title, url)

    xbmcplugin.endOfDirectory(handle)


def show_movie_pages(menu_params):
    """Movie pages: chunks of moviePageSize items via offset paging"""
    log.debug("showMoviePages")
    handle = int(sys.argv[1])
    xbmcplugin.setContent(handle, 'movies')

    libraries = _libraries_for_kind(['movies'])
    if not libraries:
        xbmcplugin.endOfDirectory(handle)
        return

    library_id = menu_params.get('library_id')
    if library_id:
        libraries = [l for l in libraries if l.get('id') == library_id] or libraries[:1]

    library = libraries[0]
    lib_id = library.get('id')

    total_url = get_valence_url('/libraries/{}/items'.format(lib_id), {'limit': 1})
    result = api.get(total_url)
    if not result:
        xbmcplugin.endOfDirectory(handle)
        return
    total_results = result.get('total', 0)
    log.debug("showMoviePages total: {0}".format(total_results))

    page_limit = int(settings.getSetting('moviePageSize'))
    if page_limit == 0:
        page_limit = 20

    start_index = 0
    params = {
        'fields': get_default_filters(),
        'sort': 'title',
    }
    while start_index < total_results:
        page_upper = min(start_index + page_limit, total_results)
        page_params = params.copy()
        page_params['offset'] = start_index
        page_params['limit'] = page_limit
        path = get_valence_url('/libraries/{}/items'.format(lib_id), page_params)
        title = 'Page ({} - {})'.format(start_index + 1, page_upper)
        url = (sys.argv[0] + "?url=" + quote(path) +
               "&mode=GET_CONTENT&media_type=movies")
        add_menu_directory_item(title, url)
        start_index = start_index + page_limit

    xbmcplugin.endOfDirectory(handle)
