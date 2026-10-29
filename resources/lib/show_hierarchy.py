"""Pure transformations for Valence show, season, and episode responses."""


def show_detail_items(data, gui_options):
    """Return Kodi-ready season folders or episodes from a Valence show detail.

    Valence has one detail route per show. Kodi's season folders are synthesized
    from its nested ``seasons`` response; the requested season is filtered here
    because the API does not expose a separate season route.
    """
    seasons = data.get("seasons") or []
    media_type = (gui_options.get("media_type") or "series").lower()
    season_filter = gui_options.get("season_number")
    show_id = data.get("id") or data.get("seriesId")
    show_title = data.get("title") or data.get("seriesTitle") or ""
    library_id = data.get("libraryId") or data.get("library_id")

    def season_number(season):
        try:
            return int(season.get("seasonNumber", season.get("season_number", 0)) or 0)
        except (TypeError, ValueError):
            return 0

    seasons = sorted(seasons, key=season_number)
    if media_type in ("season", "episodes"):
        try:
            selected_number = int(season_filter)
        except (TypeError, ValueError):
            selected_number = None

        episodes = []
        for season in seasons:
            number = season_number(season)
            if selected_number not in (None, -1) and number != selected_number:
                continue
            for episode in season.get("episodes") or []:
                episode = dict(episode)
                episode.setdefault("type", "Episode")
                episode.setdefault("seriesId", show_id)
                episode.setdefault("seriesTitle", show_title)
                episode.setdefault("libraryId", library_id)
                episode.setdefault("seasonNumber", number)
                episodes.append(episode)

        def episode_order(episode):
            try:
                number = int(episode.get("episodeNumber", 0) or 0)
            except (TypeError, ValueError):
                number = 0
            try:
                episode_season = int(episode.get("seasonNumber", 0) or 0)
            except (TypeError, ValueError):
                episode_season = 0
            return episode_season, number, (episode.get("title") or "").lower()

        return sorted(episodes, key=episode_order)

    season_items = []
    for season in seasons:
        number = season_number(season)
        episodes = season.get("episodes") or []
        season_items.append({
            "id": "{}-season-{}".format(show_id, number),
            "type": "Season",
            "title": "Specials" if number == 0 else "Season {:02d}".format(number),
            "seasonNumber": number,
            "episodeCount": len(episodes),
            "seriesId": show_id,
            "seriesTitle": show_title,
            "libraryId": library_id,
            "posterUrl": season.get("posterUrl") or data.get("posterUrl"),
            "backdropUrl": season.get("backdropUrl") or data.get("backdropUrl"),
        })
    return season_items
