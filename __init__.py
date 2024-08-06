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
from typing import Optional

from ovos_plugin_common_play import MediaType
from ovos_utils import classproperty
from ovos_utils.messagebus import Message
from ovos_utils.process_utils import RuntimeRequirements
from ovos_workshop.backwards_compat import Playlist
from ovos_workshop.skills.common_play import OVOSCommonPlaybackSkill, ocp_search

from .plex_api import PlexAPI


class PlexSkill(OVOSCommonPlaybackSkill):
    """Plex OCP Skill"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skill_icon = join(dirname(__file__), "ui", "plex.png")
        self._plex_api = None
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
        self._plex_api: Optional[PlexAPI] = self.plex_api

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(
            network_before_load=True,
            internet_before_load=False,
            gui_before_load=True,
            requires_internet=False,
            requires_network=True,
            requires_gui=True,
            no_internet_fallback=True,
            no_network_fallback=False,
            no_gui_fallback=True,
        )

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
            self.log.info("Plex token found, getting available servers")
            self._plex_api = PlexAPI(api_key)
        return self._plex_api

    def _init_plex_api_key(self):
        """Login to Plex API with an account pin, if token is missing."""
        # pylint: disable=import-outside-toplevel
        from plexapi.myplex import MyPlexPinLogin

        account = MyPlexPinLogin()
        account.run()
        plex_login_w_pin = f"Visit https://plex.tv/link with PIN: {account.pin}"
        if self.gui:
            self.gui.show_text(plex_login_w_pin)
        self.log.info(plex_login_w_pin)
        self.bus.emit(Message("enclosure.mouth.text", {"text": plex_login_w_pin}))
        success = account.waitForLogin()
        if success:
            token = account.token
            self.settings["token"] = token
            self.settings.store()
        if not success:
            self.log.error(
                "Plex login failed, please set token manually in settings.json"
            )

    @ocp_search()
    def search_plex(self, phrase, media_type=MediaType.GENERIC):
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
        playlist = Playlist(
            skill_id=self.skill_id,
            skill_icon=self.skill_icon,
            media_type=media_type,
            confidence=confidence,
            title=phrase,
            artist=phrase,
        )

        # Music search
        if media_type in (MediaType.MUSIC, MediaType.AUDIO, MediaType.GENERIC) and (
            "soundtrack" not in phrase and not movie_search
        ):
            self.log.info("Searching Plex Music for %s", phrase)
            pl = self.plex_api.search_music(phrase)
            for res in pl:
                res.match_confidence = (
                    confidence if media_type == MediaType.GENERIC else confidence + 10
                )
                res.skill_id = self.skill_id
                playlist.add_entry(res)
            # max_confidence = sorted([res.match_confidence for res in pl], reverse=True)

        # Movie search
        if (
            media_type
            in (
                MediaType.MOVIE,
                MediaType.SHORT_FILM,
                MediaType.SILENT_MOVIE,
                MediaType.VIDEO,
                MediaType.DOCUMENTARY,
                MediaType.GENERIC,
            )
            and movie_search
        ):
            self.log.info("Searching Plex Movies for %s", phrase)
            pl = self.plex_api.search_movies(phrase)
            for res in pl:
                res.match_confidence = (
                    confidence if media_type == MediaType.GENERIC else confidence + 10
                )
                res.skill_id = self.skill_id
                playlist.add_entry(res)

        # TV search
        if (
            media_type in (MediaType.TV, MediaType.CARTOON, MediaType.GENERIC)
            and tv_search
        ):
            self.log.info("Searching Plex TV for %s", phrase)
            pl = self.plex_api.search_shows(phrase)
            for res in pl:
                res.match_confidence = (
                    confidence if media_type == MediaType.GENERIC else confidence + 10
                )
                res.skill_id = self.skill_id
                playlist.add_entry(res)
        self.log.debug(playlist.as_dict)
        self.log.debug(playlist.entries)
        yield playlist
