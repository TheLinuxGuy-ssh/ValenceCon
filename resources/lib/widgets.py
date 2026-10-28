from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import hashlib
import random
import time
import datetime

import xbmcaddon
import xbmcplugin
import xbmcgui

from .valence import api
from .utils import (
    get_valence_url, get_art_url, get_default_filters
)
from .lazylogger import LazyLogger
from .kodi_utils import HomeWindow
from .dir_functions import process_directory
from .tracking import timer

log = LazyLogger(__name__)

background_items = []
background_current_item = 0


@timer
def set_random_movies():
    log.debug("set_random_movies Called")

    settings = xbmcaddon.Addon()
    item_limit = settings.getSetting("show_x_filtered_items")
    hide_watched = settings.getSetting("hide_watched") == "true"

    # Get all movie libraries
    libraries = api.get_libraries()
    movie_libs = [l for l in libraries if l.get('kind') == 'movies'] if libraries else []
    if not movie_libs:
        return
    
    lib_ids = ','.join([l['id'] for l in movie_libs])

    url_params = {}
    url_params["limit"] = item_limit
    if hide_watched:
        url_params["filters"] = "unplayed"
    url_params["sort"] = "random"
    url_params["libraryIds"] = lib_ids

    url = get_valence_url("/libraries/items", url_params)

    results = api.get(url)

    randon_movies_list = []
    if results is not None:
        items = results.get("items", [])
        for item in items:
            randon_movies_list.append(item.get("id"))

    random.shuffle(randon_movies_list)
    movies_list_string = ",".join(randon_movies_list)
    home_window = HomeWindow()
    m = hashlib.md5()
    m.update(movies_list_string.encode())
    new_widget_hash = m.hexdigest()

    log.debug("set_random_movies : {0}".format(movies_list_string))
    log.debug("set_random_movies : {0}".format(new_widget_hash))
    home_window.set_property("random-movies", movies_list_string)
    home_window.set_property("random-movies-changed", new_widget_hash)


@timer
def set_random_tvshows():
    log.debug("set_random_tvshows Called")

    settings = xbmcaddon.Addon()
    item_limit = settings.getSetting("show_x_filtered_items")
    hide_watched = settings.getSetting("hide_watched") == "true"

    libraries = api.get_libraries()
    show_libs = [l for l in libraries if l.get('kind') in ['shows', 'anime']] if libraries else []
    if not show_libs:
        return
    
    lib_ids = ','.join([l['id'] for l in show_libs])

    url_params = {}
    url_params["limit"] = item_limit
    if hide_watched:
        url_params["filters"] = "unplayed"
    url_params["sort"] = "random"
    url_params["libraryIds"] = lib_ids

    url = get_valence_url("/libraries/shows", url_params)

    results = api.get(url)

    random_tvshows_list = []
    if results is not None:
        items = results.get("shows", [])
        for item in items:
            random_tvshows_list.append(item.get("id"))

    random.shuffle(random_tvshows_list)
    tvshow_list_string = ",".join(random_tvshows_list)
    home_window = HomeWindow()
    m = hashlib.md5()
    m.update(tvshow_list_string.encode())
    new_widget_hash = m.hexdigest()

    log.debug("set_random_tvshows: {0}".format(tvshow_list_string))
    log.debug("set_random_tvshows: {0}".format(new_widget_hash))
    home_window.set_property("random-tvshows", tvshow_list_string)
    home_window.set_property("random-tvshows-changed", new_widget_hash)


@timer
def set_random_all():
    log.debug("set_random_all Called")

    settings = xbmcaddon.Addon()
    item_limit = settings.getSetting("show_x_filtered_items")
    hide_watched = settings.getSetting("hide_watched") == "true"

    libraries = api.get_libraries()
    if not libraries:
        return
    
    lib_ids = ','.join([l['id'] for l in libraries])

    url_params = {}
    url_params["limit"] = item_limit
    if hide_watched:
        url_params["filters"] = "unplayed"
    url_params["sort"] = "random"
    url_params["libraryIds"] = lib_ids

    url = get_valence_url("/libraries/items", url_params)

    results = api.get(url)

    random_items = []
    if results is not None:
        items = results.get("items", [])
        for item in items:
            random_items.append(item.get("id"))

    random.shuffle(random_items)
    item_list_string = ",".join(random_items)
    home_window = HomeWindow()
    m = hashlib.md5()
    m.update(item_list_string.encode())
    new_widget_hash = m.hexdigest()

    log.debug("set_random_all: {0}".format(item_list_string))
    log.debug("set_random_all: {0}".format(new_widget_hash))
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

        libraries = api.get_libraries()
        if not libraries:
            return
        
        lib_ids = ','.join([l['id'] for l in libraries])

        url_params = {}
        url_params["limit"] = 100
        url_params["sort"] = "random"
        url_params["libraryIds"] = lib_ids

        url = get_valence_url('/libraries/items', url_params)

        results = api.get(url)

        if results is not None:
            items = results.get("items", [])
            background_current_item = 0
            background_items = []
            for item in items:
                bg_image = get_art_url(
                    item, "Backdrop", server=server)
                if bg_image:
                    label = item.get("title") or item.get("Name", "")
                    item_background = {}
                    item_background["image"] = bg_image
                    item_background["name"] = label
                    background_items.append(item_background)

        log.debug("set_background_image: Loaded {0} more backgrounds".format(
            len(background_items))
        )

    if len(background_items) > 0:
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

    # For Valence, check recently added and progress
    libraries = api.get_libraries()
    if not libraries:
        return
    
    lib_ids = ','.join([l['id'] for l in libraries])

    # Check latest added
    url_params = {}
    url_params["limit"] = 1
    url_params["sort"] = "addedAt"
    url_params["sortOrder"] = "desc"
    url_params["libraryIds"] = lib_ids

    added_url = get_valence_url('/libraries/items', url_params)

    result = api.get(added_url)
    log.debug("LATEST_ADDED_ITEM: {0}".format(result))

    last_added_date = ""
    if result is not None:
        items = result.get("items", [])
        if len(items) > 0:
            item = items[0]
            last_added_date = item.get("etag", "") or item.get("addedAt", "")

    log.debug("last_added_date: {0}".format(last_added_date))

    # Check latest played
    url_params = {}
    url_params["limit"] = 1
    url_params["sort"] = "datePlayed"
    url_params["sortOrder"] = "desc"
    url_params["libraryIds"] = lib_ids

    played_url = get_valence_url(
        '/libraries/items', url_params
    )

    result = api.get(played_url)
    log.debug("LATEST_PLAYED_ITEM: {0}".format(result))

    last_played_date = ""
    if result is not None:
        items = result.get("items", [])
        if len(items) > 0:
            item = items[0]
            progress = item.get("userProgress")
            if progress:
                last_played_date = progress.get("updatedAt", "")

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
    settings = xbmcaddon.Addon()
    server = settings.getSetting('server_address')

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
    item_limit = int(settings.getSetting("show_x_filtered_items"))
    hide_watched = settings.getSetting("hide_watched") == "true"
    use_cached_widget_data = settings.getSetting(
        "use_cached_widget_data") == "true"

    widget_type = params.get("type")
    if widget_type is None:
        log.error("getWigetContent type not set")
        return

    libraries = api.get_libraries()
    if not libraries:
        return
    
    lib_ids = ','.join([l['id'] for l in libraries])

    log.debug("widget_type: {0}".format(widget_type))

    url_params = {}
    url_params["limit"] = item_limit
    url_params["fields"] = get_default_filters()
    url_params["libraryIds"] = lib_ids

    if widget_type == "recent_movies":
        xbmcplugin.setContent(handle, 'movies')
        url_params["sort"] = "addedAt"
        url_params["sortOrder"] = "desc"
        url_params["filters"] = "notfolder"
        if hide_watched:
            url_params["filters"] = "unplayed"
        url_params["kind"] = "movies"

    elif widget_type == "inprogress_movies":
        xbmcplugin.setContent(handle, 'movies')
        url_params["sort"] = "datePlayed"
        url_params["sortOrder"] = "desc"
        url_params["filters"] = "resumable"
        url_params["kind"] = "movies"

    elif widget_type == "random_movies":
        home_window = HomeWindow()
        xbmcplugin.setContent(handle, 'movies')
        url_params["ids"] = home_window.get_property("random-movies")

    elif widget_type == "random_tvshows":
        home_window = HomeWindow()
        xbmcplugin.setContent(handle, 'tvshows')
        url_params["ids"] = home_window.get_property("random-tvshows")

    elif widget_type == "recent_tvshows":
        xbmcplugin.setContent(handle, 'episodes')
        url_params["sort"] = "addedAt"
        url_params["sortOrder"] = "desc"
        url_params["filters"] = "notfolder"
        if hide_watched:
            url_params["filters"] = "unplayed"
        url_params["kind"] = "shows"
        url_params["type"] = "episode"

    elif widget_type == "recent_episodes":
        xbmcplugin.setContent(handle, 'episodes')
        url_params["sort"] = "addedAt"
        url_params["sortOrder"] = "desc"
        url_params["filters"] = "notfolder"
        if hide_watched:
            url_params["filters"] = "unplayed"
        url_params["type"] = "episode"
        url_params["kind"] = "shows"

    elif widget_type == "inprogress_episodes":
        xbmcplugin.setContent(handle, 'episodes')
        url_params["sort"] = "datePlayed"
        url_params["sortOrder"] = "desc"
        url_params["filters"] = "resumable"
        url_params["type"] = "episode"
        url_params["kind"] = "shows"

    elif widget_type == "nextup_episodes":
        xbmcplugin.setContent(handle, 'episodes')
        # Use /api/up-next endpoint
        url = api.server + "/api/up-next"
        params["name_format"] = "Episode|episode_name_format"
        
        list_items, detected_type, total_records = process_directory(
            url, None, params, use_cached_widget_data)
        
        xbmcplugin.addDirectoryItems(handle, list_items)
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return

    elif widget_type == "movie_recommendations":
        # Valence doesn't have recommendations endpoint yet
        xbmcgui.Dialog().ok("ValenceCon", "Movie recommendations not available for Valence yet")
        return

    elif widget_type == "random_all":
        home_window = HomeWindow()
        xbmcplugin.setContent(handle, 'movies')
        url_params["ids"] = home_window.get_property("random-all")

    elif widget_type == "recent_all":
        xbmcplugin.setContent(handle, 'movies')
        url_params["sort"] = "addedAt"
        url_params["sortOrder"] = "desc"
        url_params["filters"] = "notfolder"
        if hide_watched:
            url_params["filters"] = "unplayed"
        url_params["kind"] = "movies,shows"
        url_params["type"] = "movie,episode"

    elif widget_type == "favorites_all":
        xbmcplugin.setContent(handle, 'movies')
        url_params["filters"] = "favorite"
        url_params["sort"] = "name"
        url_params["sortOrder"] = "asc"

    items_url = get_valence_url('/libraries/items', url_params)

    if (url_params.get('type', '') == 'episode' or
            params.get('type', '') == 'nextup_episodes'):
        params["name_format"] = "Episode|episode_name_format"

    list_items, detected_type, total_records = process_directory(
        items_url, None, params, use_cached_widget_data)

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