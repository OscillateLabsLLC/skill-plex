from typing import List

from ovos_utils.log import LOG
from ovos_workshop.backwards_compat import MediaEntry, MediaType, PlaybackType
from plexapi.audio import Album, Artist, Track
from plexapi.library import MovieSection, MusicSection, ShowSection
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show


class PlexAPI:
    """Thinly wrapped plexapi library for OVOS Common Play results"""

    def __init__(self, token: str):
        self.servers: List[PlexServer] = []
        self.movies: List[MovieSection] = []
        self.shows: List[ShowSection] = []
        self.music: List[MusicSection] = []
        self.connect_to_servers(token)
        self.init_libraries()

    def connect_to_servers(self, token: str):
        """Provide connections to all servers accessible from the provided token."""
        account = MyPlexAccount(token=token)
        servers = [
            r
            for r in account.resources()
            if "server" in r.provides and r.presence is True
        ]
        LOG.info(
            "Found %s active servers: %s",
            len(servers),
            ",".join([s.name for s in servers]),
        )
        self.servers = [account.resource(server.name).connect() for server in servers]

    def init_libraries(self):
        """Initialize server libraries, specifically Movies, Shows, and Music."""
        for server in self.servers:
            lib = server.library.sections()
            for section in lib:
                if isinstance(section, MovieSection):
                    self.movies.append(section)
                elif isinstance(section, ShowSection):
                    self.shows.append(section)
                elif isinstance(section, MusicSection):
                    self.music.append(section)

    def search_music(self, query: str):
        """Search music libraries"""
        track_list = []
        for music in self.music:
            results = music.hubSearch(query)
            for result in results:
                tracks = self._get_tracks_from_result(result)
                track_list += [self._construct_track_dict(track) for track in tracks]
        LOG.debug("Found %s tracks", len(track_list))
        LOG.debug("Tracks: %s", [x.title for x in track_list])
        return track_list

    def _get_tracks_from_result(self, result):
        """Get music Tracks from search results"""
        if isinstance(result, (Album, Artist)):
            return result.tracks()
        if isinstance(result, Track):
            return [result]
        return []

    def _construct_track_dict(self, track) -> MediaEntry:
        """Construct a dictionary of Tracks for use with OVOS Common Play"""
        return MediaEntry(
            media_type=MediaType.MUSIC,
            uri=track.getStreamURL(),
            title=track.title,
            playback=PlaybackType.AUDIO,
            image=track.thumbUrl if track.thumbUrl else "",
            artist=track.grandparentTitle,
            length=track.duration,
        )

    def search_movies(self, query: str):
        """Search movie libraries"""
        movie_list = []
        for movies in self.movies:
            results = movies.hubSearch(query)
            for result in results:
                if isinstance(result, Movie):
                    movie_list.append(self._construct_movie_dict(result))
        return movie_list

    def _construct_movie_dict(self, mov):
        """Construct a dictionary of Movies for use with OVOS Common Play"""
        return MediaEntry(
            media_type=MediaType.MOVIE,
            uri=mov.getStreamURL(),
            title=mov.title,
            playback=PlaybackType.VIDEO,
            image=mov.thumbUrl if mov.thumbUrl else "",
            artist=(
                ", ".join([director.tag for director in mov.directors])
                if mov.directors
                else ""
            ),
            length=mov.duration,
        )

    def search_shows(self, query: str):
        """Search TV Show libraries"""
        show_list = []
        for shows in self.shows:
            results = shows.hubSearch(query)
            for result in results:
                episodes = self._get_episodes_from_result(result)
                show_list += [self._construct_show_dict(show) for show in episodes]
        return show_list

    def _get_episodes_from_result(self, result):
        """Get TV Episodes from search results"""
        if isinstance(result, Show):
            return result.episodes()
        if isinstance(result, Episode):
            return [result]
        return []

    def _construct_show_dict(self, show):
        """Construct a dictionary of Shows for use with OVOS Common Play"""
        return MediaEntry(
            media_type=MediaType.TV,
            uri=show.getStreamURL(),
            title=f"{show.seasonEpisode if show.seasonEpisode else ''} - {show.title}",
            playback=PlaybackType.VIDEO,
            image=show.thumbUrl if show.thumbUrl else "",
            artist=(
                ", ".join([director.tag for director in show.directors])
                if show.directors
                else ""
            ),
            length=show.duration,
        )
