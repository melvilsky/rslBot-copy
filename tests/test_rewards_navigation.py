import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# Keep this unit test independent of the Windows-only game automation stack.
common = types.ModuleType('helpers.common')
common.axis_to_region = lambda *args: args
common.is_index_page = MagicMock()
common.close_popup = MagicMock()
common.sleep = MagicMock()
common.pyautogui = MagicMock()
sys.modules['helpers.common'] = common

location_module = types.ModuleType('classes.Location')


class Location:
    pass


location_module.Location = Location
sys.modules['classes.Location'] = location_module

from locations.rewards.index import Rewards


class RewardsNavigationTests(unittest.TestCase):
    def make_rewards(self):
        rewards = Rewards.__new__(Rewards)
        rewards.abort_reason = None
        rewards.log = MagicMock()
        return rewards

    @patch('locations.rewards.index.sleep')
    @patch('locations.rewards.index.close_popup')
    @patch('locations.rewards.index.pyautogui.press')
    @patch('locations.rewards.index.is_index_page')
    def test_ensure_index_page_uses_escape_after_passive_attempts(
        self, is_index_page, press, close_popup, sleep
    ):
        rewards = self.make_rewards()
        is_index_page.side_effect = [False, False, True]

        restored = rewards._ensure_index_page(
            attempts=2,
            escape_attempts=2,
            context='after Quests',
        )

        self.assertTrue(restored)
        press.assert_called_once_with('escape')
        self.assertEqual(close_popup.call_count, 3)
        rewards.log.assert_called_with(
            'after Quests: returned to Index Page after Escape (1/2)'
        )

    def test_reward_step_aborts_when_it_cannot_return_to_index(self):
        rewards = self.make_rewards()
        rewards._ensure_index_page = MagicMock(side_effect=[True, False])
        callback = MagicMock()

        completed = rewards._run_reward_step('Quests', callback)

        self.assertFalse(completed)
        callback.assert_called_once_with()
        self.assertEqual(
            rewards.abort_reason,
            'could not return to Index Page after Quests',
        )

    def test_run_stops_before_following_steps_after_navigation_failure(self):
        rewards = self.make_rewards()
        rewards._run_reward_step = MagicMock(return_value=False)
        rewards.quests_run = MagicMock()
        rewards.play_time_run = MagicMock()
        rewards.clan_war_rewards = MagicMock()
        rewards.clan_quests_rewards = MagicMock()

        rewards._run()

        rewards._run_reward_step.assert_called_once_with(
            'Quests', rewards.quests_run
        )


if __name__ == '__main__':
    unittest.main()
