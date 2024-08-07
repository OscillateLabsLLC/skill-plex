# pylint: disable=missing-docstring,import-outside-toplevel,protected-access
import shutil
import unittest
from os import mkdir
from os.path import join, dirname, exists
from unittest.mock import Mock
from ovos_utils.messagebus import FakeBus
from ovos_workshop.skill_launcher import SkillLoader

bus = FakeBus()


class TestSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bus.run_in_thread()
        skill_loader = SkillLoader(
            bus=bus, skill_directory=dirname(dirname(__file__)), skill_id="PlexSkill"
        )
        # TODO: Mock the PlexAPI class to prevent network calls
        skill_loader.load()
        cls.skill = skill_loader.instance

        # Define a directory to use for testing
        cls.test_fs = join(dirname(__file__), "skill_fs")
        if not exists(cls.test_fs):
            mkdir(cls.test_fs)

        # Override the configuration and fs paths to use the test directory
        cls.skill.settings_write_path = cls.test_fs
        cls.skill.file_system.path = cls.test_fs

        # Override speak and speak_dialog to test passed arguments
        cls.skill.speak = Mock()
        cls.skill.speak_dialog = Mock()

        # Mock exit/shutdown method to prevent interactions with test runner
        cls.skill._do_exit_shutdown = Mock()

    def setUp(self):
        self.skill.speak.reset_mock()
        self.skill.speak_dialog.reset_mock()
        self.skill._do_exit_shutdown.reset_mock()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.test_fs)

    def test_00_skill_init(self):
        # Test any parameters expected to be set in init or initialize methods
        from ovos_workshop.skills.common_play import OVOSCommonPlaybackSkill

        self.assertIsInstance(self.skill, OVOSCommonPlaybackSkill)
