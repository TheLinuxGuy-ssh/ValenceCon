from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import sys

from dateutil import tz
from six import ensure_text
from six.moves.urllib.parse import quote
import xbmc
import xbmcgui

from .utils import (
    datetime_from_string, get_art_url, get_current_datetime
)
from .lazylogger import LazyLogger

log = LazyLogger(__name__)


class ItemDetails:

    name = ""
    sort_name = ""
    id = None
    etag = None
    path = None
    is_folder = False
    plot = ""
    series_name = ""
    episode_number = 0
    season_number = 0
    episode_sort_number = 0
    season_sort_number = 0
    track_number = 0
    series_id = None
    art = None

    mpaa = ""
    rating = None
    critic_rating = 0.0
    community_rating = 0.0
    year = None
    premiere_date = ""
    date_added = ""
    location_type = None
    studio = []
    production_location = []
    genres = []
    play_count = 0
    director = []
    writer = []
    cast = []
    tagline = ""
    status = None
    media_streams = None
    tags = []

    resume_time = 0
    duration = 0
    recursive_item_count = 0
    recursive_unplayed_items_count = 0
    total_seasons = 0
    total_episodes = 0
    watched_episodes = 0
    unwatched_episodes = 0
    number_episodes = 0
    original_title = ""
    item_type = ""
    subtitle_available = False
    total_items = 0

    song_artist = ""
    album_artist = ""
    album_name = ""

    program_channel_name = None
    program_end_date = None
    program_start_date = None

    favorite = "false"
    overlay = "0"

    name_format = ""
    mode = ""

    baseline_itemname = None


def extract_item_info(item, gui_options):
    """
    Extract item info from Valence API response
    Valence item structure differs from Jellyfin
    """
    item_details = ItemDetails()

    # Basic identifiers
    item_details.id = item.get("id")
    item_details.etag = item.get("etag") or item.get("Etag")
    item_details.name = item.get("title") or item.get("Title") or item.get("Name", "")
    item_details.sort_name = item.get("sortName") or item.get("SortName") or item_details.name
    item_details.original_title = item_details.name
    
    # Determine item type from Valence structure
    item_type = item.get("type") or item.get("Type")
    if not item_type:
        # Infer from fields
        if item.get("seasonNumber") is not None and item.get("episodeNumber") is not None:
            item_type = "Episode"
        elif item.get("seasonCount") is not None:
            item_type = "Series"
        elif item.get("trackCount") is not None:
            item_type = "MusicAlbum"
        elif item.get("durationSeconds") is not None:
            item_type = "Movie"
        else:
            item_type = "Movie"
    
    item_details.item_type = item_type
    
    # Check if it's a folder/container
    item_details.is_folder = item_type in ["Series", "Season", "MusicAlbum", "MusicArtist", "CollectionFolder"]
    
    # Type-specific fields
    if item_type == "Episode":
        item_details.episode_number = item.get("episodeNumber") or item.get("episode_number", 0)
        item_details.season_number = item.get("seasonNumber") or item.get("season_number", 0)
        item_details.series_id = item.get("seriesId") or item.get("SeriesId")
        item_details.series_name = item.get("seriesTitle") or item.get("SeriesName", "")
        
        if item_details.season_number != 0:
            item_details.season_sort_number = item_details.season_number
            item_details.episode_sort_number = item_details.episode_number
            
    elif item_type == "Season":
        item_details.season_number = item.get("seasonNumber") or item.get("season_number", 0)
        item_details.series_id = item.get("seriesId") or item.get("SeriesId")
        item_details.total_episodes = item.get("episodeCount") or item.get("episode_count", 0)
        item_details.series_name = item.get("seriesTitle") or item.get("SeriesName", "")
        
    elif item_type == "Series":
        item_details.status = item.get("status") or item.get("Status")
        item_details.total_seasons = item.get("seasonCount") or item.get("season_count", 0)
        item_details.total_episodes = item.get("episodeCount") or item.get("episode_count", 0)
        item_details.unwatched_episodes = item.get("unwatchedCount") or item.get("unwatched_count", 0)
        item_details.watched_episodes = item_details.total_episodes - item_details.unwatched_episodes
        item_details.number_episodes = item_details.total_episodes
        
    elif item_type == "MusicAlbum":
        item_details.album_artist = item.get("artist", {}).get("name") if isinstance(item.get("artist"), dict) else item.get("artist", "")
        item_details.album_name = item_details.name
        item_details.total_episodes = item.get("trackCount") or item.get("track_count", 0)  # track count
        
    elif item_type == "MusicArtist":
        item_details.total_episodes = item.get("albumCount") or item.get("album_count", 0)
        item_details.total_seasons = item.get("trackCount") or item.get("track_count", 0)
        
    elif item_type == "Movie":
        item_details.duration = item.get("durationSeconds", 0)
        item_details.year = item.get("year")
        item_details.premiere_date = item.get("releaseDate") or item.get("release_date", "")
        if item_details.premiere_date and "T" in item_details.premiere_date:
            item_details.premiere_date = item_details.premiere_date.split("T")[0]
        
    elif item_type == "MusicTrack" or item_type == "Audio":
        item_details.track_number = item.get("trackNumber") or item.get("track_number", 0)
        item_details.album_name = item.get("album", {}).get("title") if isinstance(item.get("album"), dict) else item.get("album", "")
        item_details.song_artist = item.get("artist", {}).get("name") if isinstance(item.get("artist"), dict) else item.get("artist", "")
        item_details.duration = item.get("durationSeconds", 0)
        
    elif item_type == "Book":
        item_details.duration = item.get("durationSeconds", 0)
        item_details.year = item.get("year")
        
    elif item_type == "LiveChannel":
        item_details.duration = 0  # Live stream
        
    # Default values
    if not item_details.season_number:
        item_details.season_number = 0
    if not item_details.episode_number:
        item_details.episode_number = 0
    if not item_details.season_sort_number:
        item_details.season_sort_number = 0
    if not item_details.episode_sort_number:
        item_details.episode_sort_number = 0

    # Tagline
    tagline = item.get("tagline") or item.get("Tagline")
    if tagline:
        item_details.tagline = tagline

    # Tags/Genres
    genres = item.get("genres") or item.get("Genres") or []
    if genres:
        item_details.genres = genres

    # Name formatting
    name_format = gui_options.get("name_format")
    name_format_type = gui_options.get("name_format_type")

    if name_format is not None and item_details.item_type == name_format_type:
        name_info = {}
        name_info["ItemName"] = item_details.name
        season_name = item.get("seriesTitle") or item.get("SeriesName", "")
        if season_name:
            name_info["SeriesName"] = season_name
        else:
            name_info["SeriesName"] = ""
        name_info["SeasonIndex"] = u"%02d" % item_details.season_number
        name_info["EpisodeIndex"] = u"%02d" % item_details.episode_number
        log.debug("FormatName: {0} | {1}".format(name_format, name_info))
        item_details.name = ensure_text(name_format).format(**name_info).strip()

    # Year from release date
    if not item_details.year:
        release_date = item.get("releaseDate") or item.get("release_date") or item.get("premiereDate") or item.get("PremiereDate")
        if release_date:
            try:
                item_details.year = int(release_date[:4])
            except:
                pass

    # Date added
    added_at = item.get("addedAt") or item.get("added_at") or item.get("DateCreated")
    if added_at:
        if "T" in added_at:
            item_details.date_added = added_at.split("T")[0].replace("-", "/")
        else:
            item_details.date_added = added_at

    # Plot/Overview
    item_details.plot = item.get("overview") or item.get("Overview") or item.get("plot", "")

    # Media streams (for movies/episodes)
    media_streams = item.get("audioStreams") or item.get("AudioStreams") or item.get("mediaStreams") or []
    if media_streams:
        media_info_list = []
        for mediaStream in media_streams:
            stream_type = mediaStream.get("type") or mediaStream.get("Type")
            if stream_type in ["Video", "video"]:
                media_info = {}
                media_info["type"] = "video"
                media_info["codec"] = mediaStream.get("codec") or mediaStream.get("Codec")
                media_info["height"] = mediaStream.get("height") or mediaStream.get("Height")
                media_info["width"] = mediaStream.get("width") or mediaStream.get("Width")
                aspect_ratio = mediaStream.get("aspectRatio") or mediaStream.get("AspectRatio")
                media_info["aspect"] = aspect_ratio
                if aspect_ratio and len(aspect_ratio) >= 3:
                    try:
                        aspect_width, aspect_height = aspect_ratio.split(':')
                        media_info["apect_ratio"] = float(aspect_width) / float(aspect_height)
                    except:
                        media_info["apect_ratio"] = 1.85
                else:
                    media_info["apect_ratio"] = 1.85
                media_info_list.append(media_info)
            elif stream_type in ["Audio", "audio"]:
                media_info = {}
                media_info["type"] = "audio"
                media_info["codec"] = mediaStream.get("codec") or mediaStream.get("Codec")
                media_info["channels"] = mediaStream.get("channels") or mediaStream.get("Channels")
                media_info["language"] = mediaStream.get("language") or mediaStream.get("Language")
                media_info_list.append(media_info)
            elif stream_type in ["Subtitle", "subtitle"]:
                item_details.subtitle_available = True
                media_info = {}
                media_info["type"] = "sub"
                media_info["language"] = mediaStream.get("language") or mediaStream.get("Language", '')
                media_info_list.append(media_info)

        item_details.media_streams = media_info_list

    # People/Cast
    cast_data = item.get("cast") or item.get("Cast") or []
    if cast_data:
        director = []
        writer = []
        cast = []
        for person in cast_data:
            person_type = person.get("type") or person.get("Type")
            if person_type in ["Director", "director"]:
                director.append(person.get("name") or person.get("Name"))
            elif person_type in ["Writer", "writer", "Writing", "writing"]:
                writer.append(person.get("name") or person.get("Name"))
            elif person_type in ["Actor", "actor", "Cast", "cast"]:
                person_name = person.get("name") or person.get("Name")
                person_role = person.get("role") or person.get("Role")
                person_id = person.get("personId") or person.get("PersonId") or person.get("id")
                person_image = person.get("imageUrl") or person.get("ImageUrl")
                person = {"name": person_name, "role": person_role, "thumbnail": person_image}
                cast.append(person)
        item_details.director = director
        item_details.writer = writer
        item_details.cast = cast

    # Studios (for movies)
    studios = item.get("studios") or item.get("Studios") or []
    if studios:
        studio_list = []
        for studio in studios:
            if isinstance(studio, dict):
                studio_list.append(studio.get("name") or studio.get("Name", ""))
            else:
                studio_list.append(str(studio))
        item_details.studio = studio_list

    # Production locations
    locations = item.get("productionLocations") or item.get("ProductionLocations") or []
    if locations:
        item_details.production_location = locations

    # Ratings
    rating = item.get("rating") or item.get("Rating") or item.get("communityRating") or item.get("CommunityRating")
    if rating:
        item_details.community_rating = float(rating) if isinstance(rating, (int, float, str)) else 0.0
        item_details.critic_rating = item_details.community_rating
    
    critic_rating = item.get("criticRating") or item.get("CriticRating")
    if critic_rating:
        item_details.critic_rating = float(critic_rating) if isinstance(critic_rating, (int, float, str)) else 0.0

    certification = item.get("certification") or item.get("Certification")
    if certification:
        item_details.rating = certification
        item_details.mpaa = certification

    # Playback position / resume
    # Valence uses progress endpoint separately, but check item for position
    position = item.get("userProgress", {}).get("positionSeconds") if item.get("userProgress") else None
    if position is not None:
        item_details.resume_time = int(position)
    
    # Duration
    if not item_details.duration:
        dur = item.get("durationSeconds") or item.get("Duration") or item.get("RunTimeTicks")
        if dur:
            if isinstance(dur, int) and dur > 10000000:  # Ticks
                item_details.duration = dur / 10000000
            else:
                item_details.duration = float(dur)

    # Episode/Season counts for series
    if item_type == "Series":
        item_details.total_seasons = item.get("seasonCount", 0)
        item_details.total_episodes = item.get("episodeCount", 0)
        item_details.unwatched_episodes = item.get("unwatchedCount", 0)
        item_details.watched_episodes = item_details.total_episodes - item_details.unwatched_episodes
        item_details.number_episodes = item_details.total_episodes

    # Artwork
    item_details.art = get_art(item, gui_options["server"])
    
    # User data flags (from progress or item)
    user_data = item.get("userData") or item.get("UserData") or {}
    if user_data.get("Played") or item.get("isPlayed") or item.get("is_finished"):
        item_details.overlay = "6"
        item_details.play_count = 1
    else:
        item_details.overlay = "7"
        item_details.play_count = 0

    if user_data.get("IsFavorite") or item.get("isFavorite") or item.get("is_favorite"):
        item_details.overlay = "5"
        item_details.favorite = "true"
    else:
        item_details.favorite = "false"

    # Unwatched for series
    if item_type == "Series" and item_details.unwatched_episodes == 0:
        item_details.unwatched_episodes = item.get("unwatchedCount", 0)
        item_details.watched_episodes = item_details.total_episodes - item_details.unwatched_episodes

    item_details.mode = "GET_CONTENT"

    return item_details


def add_gui_item(url, item_details, display_options, folder=True, default_sort=False):

    if not item_details.name:
        return None

    if item_details.mode:
        mode = "&mode=%s" % item_details.mode
    else:
        mode = "&mode=0"

    # Create the URL to pass to the item
    if folder:
        u = sys.argv[0] + "?url=" + quote(url) + mode + "&media_type=" + item_details.item_type
        if item_details.name_format:
            u += '&name_format=' + quote(item_details.name_format)
        if default_sort:
            u += '&sort=none'
    else:
        u = sys.argv[0] + "?item_id=" + url + "&mode=PLAY"

    list_item_name = item_details.name
    item_type = item_details.item_type.lower()
    is_video = item_type not in ['musicalbum', 'audio', 'music', 'musicartist', 'musicalbum', 'track', 'song', 'book']

    # calculate percentage
    capped_percentage = 0
    if item_details.resume_time > 0:
        duration = float(item_details.duration)
        if duration > 0:
            resume = float(item_details.resume_time)
            percentage = int((resume / duration) * 100.0)
            capped_percentage = percentage

    total_items = item_details.total_episodes
    if total_items != 0:
        watched = float(item_details.watched_episodes)
        percentage = int((watched / float(total_items)) * 100.0)
        capped_percentage = percentage

    counts_added = False
    add_counts = display_options["addCounts"]
    if add_counts and item_details.unwatched_episodes != 0:
        counts_added = True
        list_item_name = list_item_name + (" (%s)" % item_details.unwatched_episodes)

    add_resume_percent = display_options["addResumePercent"]
    if (not counts_added
            and add_resume_percent
            and capped_percentage not in [0, 100]):
        list_item_name = list_item_name + (" (%s%%)" % capped_percentage)

    subtitle_available = display_options["addSubtitleAvailable"]
    if subtitle_available and item_details.subtitle_available:
        list_item_name += " (cc)"

    if item_details.item_type == "Program":
        start_time = datetime_from_string(item_details.program_start_date)
        end_time = datetime_from_string(item_details.program_end_date)

        duration = (end_time - start_time).total_seconds()
        now = get_current_datetime()
        time_done = (now - start_time).total_seconds()
        percentage_done = (float(time_done) / float(duration)) * 100.0
        capped_percentage = int(percentage_done)

        # Convert dates to local timezone for display
        local = tz.tzlocal()
        start_time_string = start_time.astimezone(local).strftime("%H:%M")
        end_time_string = end_time.astimezone(local).strftime("%H:%M")

        item_details.duration = int(duration)
        item_details.resume_time = int(time_done)

        if item_details.program_channel_name:
            list_item_name = '{} - {} - {} to {} ({}%)'.format(
                item_details.program_channel_name, list_item_name,
                start_time_string, end_time_string, capped_percentage)
        else:
            list_item_name = '{} - {} to {} ({}%)'.format(
                list_item_name, start_time_string, end_time_string,
                capped_percentage)

        time_info = "Start : " + start_time_string + "\n"
        time_info += "End : " + end_time_string + "\n"
        time_info += "Complete : " + str(int(percentage_done)) + "%\n"
        if item_details.plot:
            item_details.plot = time_info + item_details.plot
        else:
            item_details.plot = time_info

    list_item = xbmcgui.ListItem(list_item_name, offscreen=True)
    if hasattr(list_item, "getVideoInfoTag"):
        # Kodi 20 and newer
        video_tag = list_item.getVideoInfoTag()
    else:
        # Kodi 19
        video_tag = False

    item_properties = {}

    # calculate percentage
    if capped_percentage != 0:
        item_properties["complete_percentage"] = str(capped_percentage)

    item_properties["IsPlayable"] = 'false'

    if not folder and is_video:
        if hasattr(video_tag, "setResumePoint"):
            video_tag.setResumePoint(
                item_details.resume_time,
                item_details.duration
            )
        else:
            item_properties["TotalTime"] = str(item_details.duration)
            item_properties["ResumeTime"] = str(item_details.resume_time)

    list_item.setArt(item_details.art)

    item_properties["fanart_image"] = item_details.art['fanart']  # back compat
    item_properties["discart"] = item_details.art['discart']  # not avail to setArt
    item_properties["tvshow.poster"] = item_details.art['tvshow.poster']  # not avail to setArt

    if item_details.series_id:
        item_properties["series_id"] = item_details.series_id

    # Stores info for legacy metadata
    info_labels = {}

    if hasattr(video_tag, "setTitle"):
        # Kodi 20 and newer
        video_tag.setTitle(list_item_name)
        if item_details.cast:
            cast = []
            # Has to be done at runtime because Actor objects cannot be pickled/cached
            for person in item_details.cast:
                actor = xbmc.Actor(
                    name=person.get("name"),
                    role=person.get("role"),
                    thumbnail=person.get("thumbnail"),
                )
                cast.append(actor)
            video_tag.setCast(cast)

        if item_details.sort_name:
            video_tag.setSortTitle(item_details.sort_name)
        else:
            video_tag.setSortTitle(list_item_name)
        video_tag.setDuration(round(item_details.duration))
        video_tag.setPlaycount(item_details.play_count)
        if item_details.favorite == 'true':
            video_tag.setTop250(1)
        if item_details.year:
            video_tag.setYear(item_details.year)
        if item_details.genres:
            video_tag.setGenres(item_details.genres)
    else:
        # Kodi 19
        info_labels["title"] = list_item_name
        if item_details.cast:
            list_item.setCast(item_details.cast)
        if item_details.sort_name:
            info_labels["sorttitle"] = item_details.sort_name
        else:
            info_labels["sorttitle"] = list_item_name
        info_labels["duration"] = item_details.duration
        info_labels["playcount"] = item_details.play_count
        if item_details.favorite == 'true':
            info_labels["top250"] = "1"

        info_labels["rating"] = item_details.rating
        info_labels["year"] = item_details.year
        if item_details.genres:
            genres_list = []
            for genre in item_details.genres:
                genres_list.append(quote(genre.encode('utf8')))
            item_properties["genres"] = quote("|".join(genres_list))

    mediatype = 'video'

    if item_type == 'movie':
        mediatype = 'movie'
    elif item_type == 'boxset':
        mediatype = 'set'
    elif item_type == 'series':
        mediatype = 'tvshow'
    elif item_type == 'season':
        mediatype = 'season'
    elif item_type == 'episode':
        mediatype = 'episode'
    elif item_type == 'musicalbum':
        mediatype = 'album'
    elif item_type == 'musicartist':
        mediatype = 'artist'
    elif item_type == 'audio' or item_type == 'music' or item_type == 'track' or item_type == 'song':
        mediatype = 'song'
    elif item_type == 'musicvideo':
        mediatype = 'musicvideo'
    elif item_type == 'book':
        mediatype = 'book'

    if hasattr(video_tag, "setMediaType"):
        # Kodi 20 and newer
        video_tag.setMediaType(mediatype)

        if item_type == 'episode':
            video_tag.setEpisode(item_details.episode_number)
            video_tag.setSeason(item_details.season_number)
            video_tag.setSortEpisode(item_details.episode_sort_number)
            video_tag.setSortSeason(item_details.season_sort_number)
            video_tag.setTvShowTitle(item_details.series_name)
            if item_details.season_number == 0:
                item_properties["IsSpecial"] = "true"

        elif item_type == 'season':
            video_tag.setSeason(item_details.season_number)
            video_tag.setEpisode(item_details.total_episodes)
            video_tag.setTvShowTitle(item_details.series_name)
            if item_details.season_number == 0:
                item_properties["IsSpecial"] = "true"

        elif item_type == "series":
            video_tag.setSeason(item_details.total_seasons)
            video_tag.setEpisode(item_details.total_episodes)
            video_tag.setTvShowTitle(item_details.series_name)
            video_tag.setTvShowStatus(item_details.status)

        elif item_type == "musicvideo":
            video_tag.setTrackNumber(item_details.track_number)
            if item_details.album_artist:
                video_tag.setArtists(item_details.album_artist)
            elif item_details.song_artist:
                video_tag.setArtists([item_details.song_artist])
            video_tag.setAlbum(item_details.album_name)

        if is_video:

            video_tag.setTagLine(item_details.tagline)
            if item_details.studio:
                video_tag.setStudios(item_details.studio)
            video_tag.setPremiered(item_details.premiere_date)
            video_tag.setPlot(item_details.plot)
            video_tag.setDirectors(item_details.director)
            video_tag.setWriters(item_details.writer)
            video_tag.setDateAdded(item_details.date_added)
            if item_details.production_location:
                video_tag.setCountries(item_details.production_location)
            video_tag.setMpaa(item_details.mpaa)
            video_tag.setTags(item_details.tags)

            if display_options["addUserRatings"]:
                video_tag.setUserRating(round(item_details.critic_rating))

            if item_type in ('movie', 'series'):
                video_tag.setTrailer("plugin://plugin.video.valencecon?mode=playTrailer&id=" + item_details.id)

            if item_details.media_streams is not None:
                for stream in item_details.media_streams:
                    if stream["type"] == "video":
                        stream_details = xbmc.VideoStreamDetail(
                            duration=round(item_details.duration),
                            aspect=stream["apect_ratio"],
                            codec=stream["codec"],
                            width=stream["width"],
                            height=stream["height"]
                        )
                        video_tag.addVideoStream(stream_details)
                    elif stream["type"] == "audio":
                        stream_details = xbmc.AudioStreamDetail(
                            codec=stream["codec"],
                            channels=stream["channels"],
                            language=stream["language"]
                        )
                        video_tag.addAudioStream(stream_details)
                    elif stream["type"] == "sub":
                        stream_details = xbmc.SubtitleStreamDetail(
                            language=stream["language"]
                        )
                        video_tag.addSubtitleStream(stream_details)

            item_properties["TotalSeasons"] = str(item_details.total_seasons)
            item_properties["TotalEpisodes"] = str(item_details.total_episodes)
            item_properties["NumEpisodes"] = str(item_details.number_episodes)

            video_tag.setRating(item_details.community_rating, 0, "imdb", True)

        else:
            # Non video, must be music related
            music_tag = list_item.getMusicInfoTag()
            music_tag.setTrack(item_details.track_number)
            if item_details.album_artist:
                music_tag.setArtist(item_details.album_artist[0] if isinstance(item_details.album_artist, list) else item_details.album_artist)
            elif item_details.song_artist:
                music_tag.setArtist(item_details.song_artist[0] if isinstance(item_details.song_artist, list) else item_details.song_artist)
            music_tag.setAlbum(item_details.album_name)
    else:
        # Kodi 19
        info_labels["mediatype"] = mediatype

        if item_type == 'episode':
            info_labels["episode"] = item_details.episode_number
            info_labels["season"] = item_details.season_number
            info_labels["sortseason"] = item_details.season_sort_number
            info_labels["sortepisode"] = item_details.episode_sort_number
            info_labels["tvshowtitle"] = item_details.series_name
            if item_details.season_number == 0:
                item_properties["IsSpecial"] = "true"

        elif item_type == 'season':
            info_labels["season"] = item_details.season_number
            info_labels["episode"] = item_details.total_episodes
            info_labels["tvshowtitle"] = item_details.series_name
            if item_details.season_number == 0:
                item_properties["IsSpecial"] = "true"

        elif item_type == "series":
            info_labels["episode"] = item_details.total_episodes
            info_labels["season"] = item_details.total_seasons
            info_labels["status"] = item_details.status
            info_labels["tvshowtitle"] = item_details.name

        if is_video:

            info_labels["Overlay"] = item_details.overlay
            info_labels["tagline"] = item_details.tagline
            info_labels["studio"] = item_details.studio
            info_labels["premiered"] = item_details.premiere_date
            info_labels["plot"] = item_details.plot
            info_labels["director"] = item_details.director
            info_labels["writer"] = item_details.writer
            info_labels["dateadded"] = item_details.date_added
            info_labels["country"] = item_details.production_location
            info_labels["mpaa"] = item_details.mpaa
            info_labels["tag"] = item_details.tags

            if display_options["addUserRatings"]:
                info_labels["userrating"] = item_details.critic_rating

            if item_type in ('movie', 'series'):
                info_labels["trailer"] = "plugin://plugin.video.valencecon?mode=playTrailer&id=" + item_details.id

            list_item.setInfo('video', info_labels)

            if item_details.media_streams is not None:
                for stream in item_details.media_streams:
                    if stream["type"] == "video":
                        list_item.addStreamInfo('video',
                                                {'duration': item_details.duration,
                                                 'aspect': stream["apect_ratio"],
                                                 'codec': stream["codec"],
                                                 'width': stream["width"],
                                                 'height': stream["height"]})
                    elif stream["type"] == "audio":
                        list_item.addStreamInfo('audio',
                                                {'codec': stream["codec"],
                                                 'channels': stream["channels"],
                                                 'language': stream["language"]})
                    elif stream["type"] == "sub":
                        list_item.addStreamInfo('subtitle',
                                                {'language': stream["language"]})

            item_properties["TotalSeasons"] = str(item_details.total_seasons)
            item_properties["TotalEpisodes"] = str(item_details.total_episodes)
            item_properties["NumEpisodes"] = str(item_details.number_episodes)

            list_item.setRating("imdb", item_details.community_rating, 0, True)
            item_properties["TotalTime"] = str(item_details.duration)

        else:
            # Non video, must be music related
            info_labels["tracknumber"] = item_details.track_number
            if item_details.album_artist:
                info_labels["artist"] = item_details.album_artist
            elif item_details.song_artist:
                info_labels["artist"] = item_details.song_artist
            info_labels["album"] = item_details.album_name

            list_item.setInfo('music', info_labels)

    list_item.setContentLookup(False)
    item_properties["ItemType"] = item_details.item_type
    item_properties["id"] = item_details.id

    if item_details.baseline_itemname is not None:
        item_properties["suggested_from_watching"] = item_details.baseline_itemname

    list_item.setProperties(item_properties)

    return u, list_item, folder


def get_art(item, server):

    art = {
        'thumb': '',
        'fanart': '',
        'poster': '',
        'banner': '',
        'clearlogo': '',
        'clearart': '',
        'discart': '',
        'landscape': '',
        'tvshow.fanart': '',
        'tvshow.poster': '',
        'tvshow.clearart': '',
        'tvshow.clearlogo': '',
        'tvshow.banner': '',
        'tvshow.landscape': ''
    }

    item_type = item.get("type") or item.get("Type", "")
    item_id = item.get("id") or item.get("Id")
    
    if not item_id or not server:
        return art

    # For episodes/seasons, get series artwork
    if item_type in ["Episode", "Season"]:
        series_id = item.get("seriesId") or item.get("SeriesId")
        if series_id:
            # Use series for backdrop/fanart
            art['tvshow.fanart'] = get_art_url({"id": series_id, "type": "Series"}, "Backdrop", server=server)
            art['tvshow.poster'] = get_art_url({"id": series_id, "type": "Series"}, "Primary", server=server)
            art['tvshow.clearart'] = get_art_url({"id": series_id, "type": "Series"}, "Art", server=server)
            art['tvshow.clearlogo'] = get_art_url({"id": series_id, "type": "Series"}, "Logo", server=server)
            art['tvshow.banner'] = get_art_url({"id": series_id, "type": "Series"}, "Banner", server=server)
            art['tvshow.landscape'] = get_art_url({"id": series_id, "type": "Series"}, "Thumb", server=server)
            art['fanart'] = art['tvshow.fanart']
    
    # Item-specific artwork
    if item_type in ["Episode", "Season"]:
        # Episode/Season specific
        art['poster'] = get_art_url({"id": item_id, "type": item_type}, "Primary", server=server)
        art['thumb'] = art['poster']
        if item_type == "Season":
            art['season.poster'] = art['poster']
    elif item_type == "Series":
        art['tvshow.poster'] = get_art_url(item, "Primary", server=server)
        art['poster'] = art['tvshow.poster']
        art['tvshow.clearart'] = get_art_url(item, "Art", server=server)
        art['clearart'] = art['tvshow.clearart']
        art['tvshow.clearlogo'] = get_art_url(item, "Logo", server=server)
        art['clearlogo'] = art['tvshow.clearlogo']
        art['tvshow.banner'] = get_art_url(item, "Banner", server=server)
        art['banner'] = art['tvshow.banner']
        art['tvshow.landscape'] = get_art_url(item, "Thumb", server=server)
        art['landscape'] = art['tvshow.landscape']
        art['tvshow.fanart'] = get_art_url(item, "Backdrop", server=server)
        art['fanart'] = art['tvshow.fanart']
    elif item_type == "Movie":
        art['poster'] = get_art_url(item, "Primary", server=server)
        art['thumb'] = art['poster']
        art['landscape'] = get_art_url(item, "Thumb", server=server)
        art['banner'] = get_art_url(item, "Banner", server=server)
        art['clearlogo'] = get_art_url(item, "Logo", server=server)
        art['clearart'] = get_art_url(item, "Art", server=server)
        art['discart'] = get_art_url(item, "Disc", server=server)
        art['fanart'] = get_art_url(item, "Backdrop", server=server)
    elif item_type == "MusicAlbum":
        art['poster'] = get_art_url(item, "Primary", server=server)
        art['thumb'] = art['poster']
        art['fanart'] = get_art_url(item, "Backdrop", server=server)
    elif item_type == "MusicArtist":
        art['poster'] = get_art_url(item, "Primary", server=server)
        art['thumb'] = art['poster']
        art['fanart'] = get_art_url(item, "Backdrop", server=server)
    elif item_type == "MusicTrack":
        art['thumb'] = get_art_url(item, "Primary", server=server)
        art['fanart'] = get_art_url(item, "Backdrop", server=server)
    elif item_type == "Book":
        art['poster'] = get_art_url(item, "Primary", server=server)
        art['thumb'] = art['poster']
        art['fanart'] = get_art_url(item, "Backdrop", server=server)
    elif item_type == "LiveChannel":
        art['poster'] = get_art_url(item, "Primary", server=server)
        art['thumb'] = art['poster']
        art['fanart'] = get_art_url(item, "Backdrop", server=server)

    # Ensure fanart is set
    if not art['fanart']:
        art['fanart'] = get_art_url(item, "Backdrop", server=server)

    return art