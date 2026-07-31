import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def module(name, **values):
    stub = types.ModuleType(name)
    for key, value in values.items():
        setattr(stub, key, value)
    sys.modules[name] = stub
    return stub


module('pyautogui', pixel=MagicMock(return_value=(0, 0, 0)))
module('pause')
module('helpers.common', prepare_event=MagicMock(), sleep=MagicMock(), folder_ensure=MagicMock())
module(
    'helpers.game_actions',
    calculate_win_rate=MagicMock(),
    claim_rewards=MagicMock(),
    click_on_progress_info=MagicMock(),
    enable_auto_play=MagicMock(),
)
module(
    'helpers.logging_utils',
    get_time_for_log=MagicMock(),
    is_debug_mode=lambda: False,
    log=MagicMock(),
    log_save=MagicMock(),
)
mouse = module(
    'helpers.mouse',
    await_click=MagicMock(return_value=[True]),
    click=MagicMock(),
    tap_to_continue=MagicMock(),
)
module(
    'helpers.screen',
    debug_save_screenshot=MagicMock(),
    show_pyautogui_image=MagicMock(),
)
vision = module(
    'helpers.vision',
    find_hero_slot_empty=MagicMock(),
    find_indicator_active=MagicMock(),
    find_indicator_inactive=MagicMock(),
    find_needle_refill_ruby=MagicMock(),
    find_victory_opponent_left=MagicMock(),
    pixel_check_new=MagicMock(),
    pixels_every=MagicMock(),
    pixels_wait=MagicMock(return_value=[False]),
    rgb_check=MagicMock(),
    same_pixels_line=MagicMock(),
)


def load_coordinates(filename, required=False):
    path = Path(__file__).parents[1] / 'coordinates' / filename
    return json.loads(path.read_text(encoding='utf-8'))


def get_coordinate(data, key, source=None, require_rgb=False):
    item = data[key]
    return [item['x'], item['y'], item['rgb']]


module(
    'helpers.coordinates',
    get_coordinate=get_coordinate,
    get_mistake=lambda data, key, default=20: data.get(key, {}).get('mistake', default),
    load_coordinates=load_coordinates,
)
module('helpers.time_mgr', TimeMgr=MagicMock)

remaining_refills = MagicMock(return_value=3)
increment_purchase = MagicMock(return_value=1)
module(
    'helpers.refill_state',
    RefillStateError=type('RefillStateError', (Exception,), {}),
    get_remaining_refills=remaining_refills,
    increment_purchase=increment_purchase,
)
module('locations.hero_filter.index', HeroFilter=MagicMock)
module('locations.live_arena.availability', is_index_indicator_active=MagicMock())
module('classes.Location', Location=object)

sys.modules.pop('locations.live_arena.index', None)
from locations.live_arena.index import ArenaLive


class LiveArenaRefillRolloverTests(unittest.TestCase):
    def setUp(self):
        remaining_refills.reset_mock(return_value=True)
        remaining_refills.return_value = 3
        increment_purchase.reset_mock(return_value=True)
        increment_purchase.return_value = 1
        mouse.click.reset_mock()
        vision.find_needle_refill_ruby.reset_mock(return_value=True)
        vision.find_needle_refill_ruby.return_value = [100, 100]

    def test_paid_refill_reloads_allowance_after_utc_rollover(self):
        arena = ArenaLive.__new__(ArenaLive)
        arena.NAME = 'Arena Live'
        arena.app = SimpleNamespace(current_player_name='Lema')
        arena.refill_max_allowed = 3
        arena.refill = 0  # Cached before midnight UTC.
        arena.terminated = False
        arena.log = MagicMock()
        arena._click_on_find_opponent = MagicMock()
        arena._check_progress_chest = MagicMock(return_value=False)

        with patch('locations.live_arena.index.sleep', MagicMock()):
            result = arena._refill()

        self.assertFalse(result)
        remaining_refills.assert_called_once_with('arena_live', 3, profile_name='Lema')
        increment_purchase.assert_called_once_with('arena_live', 3, profile_name='Lema')
        self.assertEqual(arena.refill, 2)
        self.assertEqual(arena._click_on_find_opponent.call_count, 2)
        self.assertTrue(any(
            '0 -> 3 remaining' in call.args[0]
            for call in arena.log.call_args_list
        ))


if __name__ == '__main__':
    unittest.main()
