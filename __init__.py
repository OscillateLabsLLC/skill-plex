# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from os.path import dirname, join
from typing import List

from ovos_plugin_common_play import MediaType, PlaybackType
from ovos_utils.messagebus import Message
from ovos_workshop.skills.common_play import OVOSCommonPlaybackSkill, ocp_search

from .plex_api import PlexAPI


class PlexSkill(OVOSCommonPlaybackSkill):
    """Plex OCP Skill"""

    def __init__(self, *args, **kwargs):
        super(PlexSkill, self).__init__(*args, **kwargs)
        self.skill_icon = join(dirname(__file__), "ui", "plex.png")
        self._plex_api = self.plex_api
        self.supported_media = [
            MediaType.GENERIC,
            MediaType.MUSIC,
            MediaType.AUDIO,
            MediaType.MOVIE,
            MediaType.SHORT_FILM,
            MediaType.SILENT_MOVIE,
            MediaType.VIDEO,
            MediaType.DOCUMENTARY,
            MediaType.CARTOON,
            MediaType.TV,
        ]

    @property
    def plex_api(self) -> PlexAPI:
        """
        Instantiate PlexAPI class using the token from settings.json
        :returns: PlexAPI class
        """
        if not self._plex_api:
            self.log.info("Initializing PlexAPI")
            if not self.settings.get("token"):
                self.log.info("No Plex token found, initializing PlexAPI login")
                self._init_plex_api_key()
            api_key = self.settings.get("token")
            self.log.info("Plex token found: %s, getting available servers", api_key)
            self._plex_api = PlexAPI(api_key)
        return self._plex_api

    def _init_plex_api_key(self):
        """Login to Plex API with an account pin, if token is missing."""
        # pylint: disable=import-outside-toplevel
        from plexapi.myplex import MyPlexPinLogin

        account = MyPlexPinLogin()
        account.run()
        plex_login_w_pin = f"Visit https://plex.tv/link with PIN: {account.pin}"
        self.gui.show_text(plex_login_w_pin)
        self.log.info(plex_login_w_pin)
        self.bus.emit(Message("enclosure.mouth.text", {"text": plex_login_w_pin}))
        account.waitForLogin()
        token = account.token
        self.settings["token"] = token
        self.settings.store()

    @ocp_search()
    def search_plex(self, phrase, media_type=MediaType.GENERIC) -> List[dict]:
        """
        OCP Search handler to return results for a user request
        :param phrase: search phrase from user
        :param media_type: user requested media type
        :returns: list of dict search results
        """
        # TODO: improved confidence calculation
        confidence = 75
        if self.voc_match(phrase, "plex"):
            confidence += 15
            phrase = self.remove_voc(phrase, "plex")

        # Determine what kind of media to play
        movie_search = self.voc_match(phrase, "movie")
        tv_search = self.voc_match(phrase, "tv")
        phrase = self.remove_voc(phrase, "movie")
        phrase = self.remove_voc(phrase, "tv")
        self.log.info("Media type for search: %s", media_type)
        self.log.info("Perform a movie search? %s", movie_search)
        self.log.info("Perform a tv search? %s", tv_search)
        phrase = phrase.replace(" on ", "").replace("in ", "").strip()

        # Music search
        if media_type in (MediaType.MUSIC, MediaType.AUDIO, MediaType.GENERIC) and (
            "soundtrack" not in phrase and not movie_search
        ):
            # self.extend_timeout(3)
            self.log.info("Searching Plex Music for %s", phrase)
            pl = self.plex_api.search_music(phrase)
            for res in pl:
                self.log.debug(res)
                res["media_type"] = media_type
                res["playback"] = PlaybackType.AUDIO
                if media_type != MediaType.GENERIC:
                    confidence += 10
                res["match_confidence"] = confidence
                res["skill_id"] = self.skill_id
                # yield res
            yield {
                "match_confidence": max(0, sorted([res["match_confidence"] for res in pl], reverse=True)[0]),
                "media_type": MediaType.MUSIC,
                "playlist": pl,
                "playback": PlaybackType.AUDIO,
                "skill_icon": self.skill_icon,
                "image": pl[0].get("image", ""),
                "bg_image": pl[0].get("bg_image", ""),
                "title": pl[0].get("grandparent_title"),
            }

        # # Movie search
        # if media_type in (
        #     MediaType.MOVIE,
        #     MediaType.SHORT_FILM,
        #     MediaType.SILENT_MOVIE,
        #     MediaType.VIDEO,
        #     MediaType.DOCUMENTARY,
        #     MediaType.GENERIC,
        # ):
        #     # self.extend_timeout(3)
        #     self.log.info("Searching Plex Movies for %s", phrase)
        #     for movie in self.plex_api.search_movies(phrase):
        #         movie["media_type"] = media_type
        #         movie["playback"] = PlaybackType.VIDEO
        #         if media_type != MediaType.GENERIC:
        #             confidence += 10
        #         movie["match_confidence"] = confidence
        #         yield movie

        # # TV search
        # if media_type in (MediaType.TV, MediaType.CARTOON, MediaType.GENERIC):
        #     # self.extend_timeout(3)
        #     self.log.info("Searching Plex TV for %s", phrase)
        #     for episode in self.plex_api.search_shows(phrase):
        #         episode["media_type"] = media_type
        #         episode["playback"] = PlaybackType.VIDEO
        #         if media_type != MediaType.GENERIC:
        #             confidence += 10
        #         episode["match_confidence"] = confidence
        #         yield episode
