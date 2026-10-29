from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import hashlib
import random
import time

import xbmcaddon
import xbmcgui
import xbmcplugin

from .lazylogger import LazyLogger
from .kodi_utils import HomeWindow
from .valence import api
from .utils import (
    get_art_url, get_default_filters, get_valence_url
)
from .dir_functions import process_directory
from .tracking import timer

log = LazyLogger(__name__)

background_items = []
background_current_item = 0


def _get_libraries(kinds):
    """Return libraries whose kind is in kinds (tolerating request errors)"""
    libraries = api.get_libraries()
    if not libraries:
        return []
    return [l for l in libraries if l.get('kind') in kinds]


def _items_urls(libraries, item_limit, extra=None):
    """Build per-library /libraries/{id}/items URLs (combined route is unsupported)"""
    base = {'limit': item_limit, 'fields': get_default_filters()}
    if extra:
        base.update(extra)
    return [
        get_valence_url('/libraries/{}/items'.format(lib.get('id')), base)
        for lib in libraries
    ]


def _fetch_watched_ids():
    """Return the set of media ids marked finished on the server"""
    watched = set()
    progress_result = api.get('/progress')
    if isinstance(progress_result, dict):
        for entry in progress_result.get('progress', []) or []:
            try:
                if entry.get('isFinished'):
                    watched.add(entry.get('mediaId'))
            except AttributeError:
                continue
    return watched


def _filter_unwatched(item_dicts, watched_ids):
    if not watched_ids:
        return item_dicts
    return [i for i in item_dicts if i.get('id') not in watched_ids]


@timer
def set_random_movies():
    log.debug("set_random_movies Called")

    settings = xbmcaddon.Addon()
    item_limit = int(settings.getSetting("show_x_filtered_items") or 20)
    hide_watched = settings.getSetting("hide_watched") == "true"

    movie_libs = _get_libraries(['movies'])
    if not movie_libs:
        return

    watched_ids = _fetch_watched_ids() if hide_watched else set()

    # pick a random window from each library, then merge
    random_ids = []
    for lib in movie_libs:
        lib_id = lib.get('id')
        count_url = get_valence_url(
            '/libraries/{}/items'.format(lib_id), {'limit': 1})
        count_result = api.get(count_url)
        total = count_result.get('total', 0) if isinstance(count_result, dict) else 0
        if not total:
            continue

        window = min(item_limit * 5, total)
        offset = random.randint(0, max(0, total - window)) if total > window else 0
        url = get_valence_url('/libraries/{}/items'.format(lib_id), {
            'limit': window,
            'offset': offset,
            'order': 'title',
        })
        result = api.get(url)
        items = result.get('items', []) if isinstance(result, dict) else []
        items = _filter_unwatched(items, watched_ids)
        for item in items:
            random_ids.append(item.get("id"))

    random.shuffle(random_ids)
    random_ids = random_ids[:item_limit]
    movies_list_string = ",".join([str(i) for i in random_ids if i])

    home_window = HomeWindow()
    m = hashlib.md5()
    m.update(movies_list_string.encode())
    new_widget_hash = m.hexdigest()

    log.debug("set_random_movies : {0}".format(movies_list_string))
    home_window.set_property("random-movies", movies_list_string)
    home_window.set_property("random-movies-changed", new_widget_hash)


@timer
def set_random_tvshows():
    log.debug("set_random_tvshows Called")

    settings = xbmcaddon.Addon()
    item_limit = int(settings.getSetting("show_x_filtered_items") or 20)
    hide_watched = settings.getSetting("hide_watched") == "true"

    show_libs = _get_libraries(['shows', 'anime'])
    if not show_libs:
        return

    watched_ids = _fetch_watched_ids() if hide_watched else set()

    random_ids = []
    for lib in show_libs:
        lib_id = lib.get('id')
        count_url = get_valence_url(
            '/libraries/{}/shows'.format(lib_id), {'limit': 1})
        count_result = api.get(count_url)
        total = 0
        if isinstance(count_result, dict):
            total = count_result.get('total', 0)
            if not total:
                total = len(count_result.get('shows', []) or [])
        if not total:
            continue

        window = min(item_limit * 5, total)
        offset = random.randint(0, max(0, total - window)) if total > window else 0
        url = get_valence_url('/libraries/{}/shows'.format(lib_id), {
            'limit': window,
            'offset': offset,
            'order': 'title',
        })
        result = api.get(url)
        items = result.get('shows', []) if isinstance(result, dict) else []
        items = _filter_unwatched(items, watched_ids)
        for item in items:
            random_ids.append(item.get("id"))

    random.shuffle(random_ids)
    random_ids = random_ids[:item_limit]
    tvshow_list_string = ",".join([str(i) for i in random_ids if i])

    home_window = HomeWindow()
    m = hashlib.md5()
    m.update(tvshow_list_string.encode())
    new_widget_hash = m.hexdigest()

    log.debug("set_random_tvshows: {0}".format(tvshow_list_string))
    home_window.set_property("random-tvshows", tvshow_list_string)
    home_window.set_property("random-tvshows-changed", new_widget_hash)


@timer
def set_random_all():
    log.debug("set_random_all Called")

    settings = xbmcaddon.Addon()
    item_limit = int(settings.getSetting("show_x_filtered_items") or 20)
    hide_watched = settings.getSetting("hide_watched") == "true"

    libraries = _get_libraries(['movies', 'shows', 'anime'])
    if not libraries:
        return

    watched_ids = _fetch_watched_ids() if hide_watched else set()

    random_ids = []
    for lib in libraries:
        lib_id = lib.get('id')
        count_url = get_valence_url(
            '/libraries/{}/items'.format(lib_id), {'limit': 1})
        count_result = api.get(count_url)
        total = count_result.get('total', 0) if isinstance(count_result, dict) else 0
        if not total:
            continue

        window = min(item_limit * 5, total)
        offset = random.randint(0, max(0, total - window)) if total > window else 0
        url = get_valence_url('/libraries/{}/items'.format(lib_id), {
            'limit': window,
            'offset': offset,
            'order': 'title',
        })
        result = api.get(url)
        items = result.get('items', []) if isinstance(result, dict) else []
        items = _filter_unwatched(items, watched_ids)
        for item in items:
            random_ids.append(item.get("id"))

    random.shuffle(random_ids)
    random_ids = random_ids[:item_limit]
    item_list_string = ",".join([str(i) for i in random_ids if i])

    home_window = HomeWindow()
    m = hashlib.md5()
    m.update(item_list_string.encode())
    new_widget_hash = m.hexdigest()

    log.debug("set_random_all: {0}".format(item_list_string))
    home_window.set_property("random-all", item_list_string)
    home_window.set_property("random-all-changed", new_widget_hash)


def set_background_image(force=False):
    log.debug("set_background_image Called forced={0}".format(force))

    global background_current_item
    global background_items

    settings = xbmcaddon.Addon()
    server = settings.getSetting('server_address')

    if force:
        background_current_item = 0
        del background_items
        background_items = []

    if len(background_items) == 0:
        log.debug("Need to load more backgrounds {0} - {1}".format(
            len(background_items), background_current_item)
        )

        libraries = _get_libraries(['movies', 'shows', 'anime'])
        if not libraries:
            return

        background_items = []
        for lib in libraries:
            lib_id = lib.get('id')
            item_count = lib.get('itemCount') or 100
            window = min(100, item_count)
            offset = random.randint(0, max(0, item_count - 100)) if item_count > 100 else 0
            url = get_valence_url('/libraries/{}/items'.format(lib_id), {
                'limit': window,
                'offset': offset,
                'order': 'title',
            })
            result = api.get(url)
            items = result.get('items', []) if isinstance(result, dict) else []
            # only items with backdrops make sense as backgrounds
            items = [
                i for i in items
                if i.get('hasBackdrop') or ('backdropUrl' in i and i.get('backdropUrl'))
            ]
            for item in items:
                bg_image = get_art_url(item, "Backdrop", server=server)
                if bg_image:
                    label = item.get("title") or item.get("Name", "")
                    item_background = {}
                    item_background["image"] = bg_image
                    item_background["name"] = label
                    background_items.append(item_background)

        random.shuffle(background_items)
        background_current_item = 0
        log.debug("set_background_image: Loaded {0} more backgrounds".format(
            len(background_items))
        )

    if len(background_items) > 0:
        if background_current_item >= len(background_items):
            background_current_item = 0

        bg_image = background_items[background_current_item].get("image")
        label = background_items[background_current_item].get("name")
        log.debug(
            "set_background_image: {0} - {1} - {2}".format(
                background_current_item, label, bg_image
            )
        )

        background_current_item += 1
        if background_current_item >= len(background_items):
            background_current_item = 0

        home_window = HomeWindow()
        home_window.set_property("random-gb", bg_image)
        home_window.set_property("random-gb-label", label)


@timer
def check_for_new_content():
    log.debug("checkForNewContent Called")

    home_window = HomeWindow()
    settings = xbmcaddon.Addon()
    simple_new_content_check = settings.getSetting(
        "simple_new_content_check") == "true"

    if simple_new_content_check:
        log.debug("Using simple new content check")
        current_time_stamp = str(time.time())
        home_window.set_property("valencecon_widget_reload", current_time_stamp)
        log.debug("Setting New Widget Hash: {0}".format(current_time_stamp))
        return

    # latest added item across libraries (per-library routes, order=newest)
    last_added_date = ""
    libraries = _get_libraries(['movies', 'shows', 'anime'])
    for lib in libraries:
        url = get_valence_url('/libraries/{}/items'.format(lib.get('id')), {
            'limit': 1,
            'order': 'newest',
        })
        result = api.get(url)
        if isinstance(result, dict):
            items = result.get('items', [])
            if items:
                added_at = items[0].get("addedAt", "")
                if added_at > last_added_date:
                    last_added_date = added_at

    log.debug("last_added_date: {0}".format(last_added_date))

    # latest played item from the shared progress log
    last_played_date = ""
    progress_result = api.get('/progress')
    if isinstance(progress_result, dict):
        for entry in progress_result.get('progress', []) or []:
            updated_at = entry.get("updatedAt", "")
            if updated_at > last_played_date:
                last_played_date = updated_at

    log.debug("last_played_date: {0}".format(last_played_date))

    current_widget_hash = home_window.get_property("valencecon_widget_reload")
    log.debug("Current Widget Hash: {0}".format(current_widget_hash))

    m = hashlib.md5()
    m.update((last_played_date + last_added_date).encode())
    new_widget_hash = m.hexdigest()
    log.debug("New Widget Hash: {0}".format(new_widget_hash))

    if current_widget_hash != new_widget_hash:
        home_window.set_property("valencecon_widget_reload", new_widget_hash)
        log.debug("Setting New Widget Hash: {0}".format(new_widget_hash))


@timer
def get_widget_content_cast(handle, params):
    log.debug("getWigetContentCast Called: {0}".format(params))

    item_id = params["id"]
    media = api.get_media(item_id)
    log.debug("ItemInfo: {0}".format(media))

    if not media:
        return

    if (media.get("type") in ["Episode", "Season"] and
            params.get("auto", "true") == "true"):

        series_id = media.get("seriesId")
        if series_id:
            params["id"] = series_id
            return get_widget_content_cast(handle, params)

    list_items = []
    if media is not None:
        cast = media.get("metadata", {}).get("cast", [])
    else:
        cast = []

    for person in cast:
        if person.get("type") == "Actor":
            person_name = person.get("name")
            person_role = person.get("role")
            person_id = person.get("personId")
            person_image = person.get("imageUrl")
            person_thumbnail = None
            if person_image:
                person_thumbnail = person_image

            list_item = xbmcgui.ListItem(label=person_name, offscreen=True)

            list_item.setProperty("id", person_id)

            if person_thumbnail:
                art_links = {}
                art_links["thumb"] = person_thumbnail
                art_links["poster"] = person_thumbnail
                list_item.setArt(art_links)

            if hasattr(list_item, 'getMusicInfoTag'):
                # Kodi 20 and newer
                music_tag = list_item.getMusicInfoTag()
                music_tag.setMediaType("artist")
            else:
                # Kodi 19
                labels = {}
                labels["mediatype"] = "artist"
                list_item.setInfo(type="music", infoLabels=labels)

            if person_role:
                list_item.setLabel2(person_role)

            item_tuple = ("", list_item, False)
            list_items.append(item_tuple)

    xbmcplugin.setContent(handle, 'artists')
    xbmcplugin.addDirectoryItems(handle, list_items)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


@timer
def get_widget_content(handle, params):
    log.debug("getWigetContent Called: {0}".format(params))

    settings = xbmcaddon.Addon()
    item_limit = int(settings.getSetting("show_x_filtered_items") or 20)
    use_cached_widget_data = settings.getSetting(
        "use_cached_widget_data") == "true"

    widget_type = params.get("type")
    if widget_type is None:
        log.error("getWigetContent type not set")
        return

    log.debug("widget_type: {0}".format(widget_type))

    fetch_urls = []

    if widget_type == "recent_movies":
        xbmcplugin.setContent(handle, 'movies')
        fetch_urls = _items_urls(_get_libraries(['movies']), item_limit,
                                 {'order': 'newest'})

    elif widget_type == "inprogress_movies":
        xbmcplugin.setContent(handle, 'movies')
        inprogress_ids = _get_inprogress_ids()
        if not inprogress_ids:
            xbmcplugin.addDirectoryItems(handle, [])
            xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
            return
        for lib in _get_libraries(['movies']):
            fetch_urls.append(get_valence_url(
                '/libraries/{}/items'.format(lib.get('id')),
                {'limit': item_limit, 'fields': get_default_filters(),
                 'ids': ','.join(inprogress_ids)}
            ))

    elif widget_type == "random_movies":
        home_window = HomeWindow()
        xbmcplugin.setContent(handle, 'movies')
        id_list = home_window.get_property("random-movies")
        for lib in _get_libraries(['movies']):
            fetch_urls.append(get_valence_url(
                '/libraries/{}/items'.format(lib.get('id')),
                {'fields': get_default_filters(),
                 'ids': id_list}
            ))

    elif widget_type == "random_tvshows":
        home_window = HomeWindow()
        xbmcplugin.setContent(handle, 'tvshows')
        id_list = home_window.get_property("random-tvshows")
        for lib in _get_libraries(['shows', 'anime']):
            fetch_urls.append(get_valence_url(
                '/libraries/{}/items'.format(lib.get('id')),
                {'fields': get_default_filters(),
                 'ids': id_list}
            ))

    elif widget_type == "random_all":
        home_window = HomeWindow()
        xbmcplugin.setContent(handle, 'movies')
        id_list = home_window.get_property("random-all")
        for lib in _get_libraries(['movies', 'shows', 'anime']):
            fetch_urls.append(get_valence_url(
                '/libraries/{}/items'.format(lib.get('id')),
                {'fields': get_default_filters(),
                 'ids': id_list}
            ))

    elif widget_type == "recent_tvshows":
        xbmcplugin.setContent(handle, 'episodes')
        fetch_urls = _items_urls(_get_libraries(['shows', 'anime']), item_limit,
                                 {'order': 'newest', 'type': 'episode'})

    elif widget_type == "recent_episodes":
        xbmcplugin.setContent(handle, 'episodes')
        fetch_urls = _items_urls(_get_libraries(['shows', 'anime']), item_limit,
                                 {'order': 'newest', 'type': 'episode'})

    elif widget_type == "inprogress_episodes":
        xbmcplugin.setContent(handle, 'episodes')
        inprogress_ids = _get_inprogress_ids()
        if not inprogress_ids:
            xbmcplugin.addDirectoryItems(handle, [])
            xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
            return
        for lib in _get_libraries(['shows', 'anime']):
            fetch_urls.append(get_valence_url(
                '/libraries/{}/items'.format(lib.get('id')),
                {'limit': item_limit, 'fields': get_default_filters(),
                 'type': 'episode', 'ids': ','.join(inprogress_ids)}
            ))

    elif widget_type == "nextup_episodes":
        xbmcplugin.setContent(handle, 'episodes')
        # Use /api/up-next endpoint
        next_url = '/up-next'
        params["name_format"] = "Episode|episode_name_format"

        list_items, detected_type, total_records = process_directory(
            next_url, None, params, use_cached_widget_data)

        xbmcplugin.addDirectoryItems(handle, list_items)
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return

    elif widget_type == "movie_recommendations":
        # No recommendations endpoint on Valence 1.7; fall back to newest movies
        xbmcplugin.setContent(handle, 'movies')
        fetch_urls = _items_urls(_get_libraries(['movies']), item_limit,
                                 {'order': 'newest'})

    elif widget_type == "recent_all":
        xbmcplugin.setContent(handle, 'movies')
        movie_urls = _items_urls(_get_libraries(['movies']), item_limit,
                                 {'order': 'newest'})
        episode_urls = _items_urls(_get_libraries(['shows', 'anime']),
                                   item_limit,
                                   {'order': 'newest', 'type': 'episode'})
        fetch_urls = movie_urls + episode_urls

    elif widget_type == "favorites_all":
        xbmcplugin.setContent(handle, 'movies')
        fetch_urls = ['/favourites']

    else:
        log.error("unknown widget type: {0}".format(widget_type))
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return

    if (params.get("type") in ("recent_tvshows", "recent_episodes",
                              "inprogress_episodes", "nextup_episodes")):
        params["name_format"] = "Episode|episode_name_format"

    list_items, detected_type, total_records = process_directory(
        fetch_urls, None, params, use_cached_widget_data)

    if detected_type is not None:
        # if the media type is not set then try to use the detected type
        log.debug("Detected content type: {0}".format(detected_type))
        content_type = None

        if detected_type == "Movie":
            content_type = 'movies'
        elif detected_type == "Episode":
            content_type = 'episodes'
        elif detected_type == "Series":
            content_type = 'tvshows'
        elif detected_type in ["Music", "Audio", "MusicAlbum", "MusicTrack"]:
            content_type = 'songs'

        if content_type:
            xbmcplugin.setContent(handle, content_type)

    xbmcplugin.addDirectoryItems(handle, list_items)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def _get_inprogress_ids():
    """Media ids with a resume point that are not finished, newest first"""
    ids = []
    progress_result = api.get('/progress')
    if isinstance(progress_result, dict):
        entries = [
            e for e in (progress_result.get('progress') or [])
            if not e.get('isFinished') and (e.get('positionSeconds') or 0) > 0
        ]
        entries.sort(key=lambda e: e.get('updatedAt', ''), reverse=True)
        ids = [e.get('mediaId') for e in entries]
    return ids
