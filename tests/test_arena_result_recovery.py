import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


def module(name, **values):
    stub = types.ModuleType(name)
    for key, value in values.items():
        setattr(stub, key, value)
    sys.modules[name] = stub
    return stub


module('pyautogui', press=MagicMock())
module(
    'helpers.common',
    debug_save_screenshot=MagicMock(),
    is_debug_mode=lambda: False,
    prepare_event=lambda event, props: dict(event, **props),
    sleep=MagicMock(),
)
module('helpers.popups', close_popup=MagicMock(return_value=[None, False]), close_popup_recursive=MagicMock())
module(
    'helpers.game_actions',
    calculate_win_rate=MagicMock(),
    click_on_progress_info=MagicMock(),
    enable_start_on_auto=MagicMock(),
    waiting_battle_end_regular=MagicMock(),
)
module('helpers.logging_utils', log=MagicMock())
module(
    'helpers.mouse',
    await_click=MagicMock(),
    click=MagicMock(),
    swipe=MagicMock(),
    swipe_new=MagicMock(),
    tap_to_continue=MagicMock(),
)
module('helpers.ocr', read_bank_arena_classic=MagicMock(), read_bank_arena_tag=MagicMock())
module(
    'helpers.vision',
    find_needle_arena_reward=MagicMock(),
    find_needle_refill_ruby=MagicMock(),
    pixel_check_new=MagicMock(),
    pixels_wait=MagicMock(),
)


def load_coordinates(filename, required=False):
    path = Path(__file__).parents[1] / 'coordinates' / filename
    return json.loads(path.read_text(encoding='utf-8'))


def get_coordinate(data, key, source=None):
    item = data[key]
    result = [item['x'], item['y']]
    if 'rgb' in item:
        result.append(item['rgb'])
    return result


def get_score_config(data, key, default_mistake=20, default_min_score=None):
    item = data.get(key, {})
    points = [[point['x'], point['y'], point['rgb']] for point in item.get('points', [])]
    return (
        points,
        item.get('mistake', default_mistake),
        item.get('min_score', default_min_score if default_min_score is not None else len(points)),
    )


module(
    'helpers.coordinates',
    get_coordinate=get_coordinate,
    get_mistake=lambda data, key, default=20: data.get(key, {}).get('mistake', default),
    get_score_config=get_score_config,
    load_coordinates=load_coordinates,
    parse_button_locations=lambda data, key: {
        int(k): [v['x'], v['y']] for k, v in data[key].items()
    },
    parse_point=lambda data, key: [data[key]['x'], data[key]['y']],
    require_coordinate_files=lambda *args: None,
)
module('helpers.refill_state', get_remaining_refills=MagicMock(), increment_purchase=MagicMock())

location_module = module('classes.Location')


class Location:
    E_BATTLE_END = {}


location_module.Location = Location

from locations.arena.index import ArenaFactory, is_results_screen_visible, result_tap_to_continue


class ArenaResultRecoveryTests(unittest.TestCase):
    def make_arena(self):
        arena = ArenaFactory.__new__(ArenaFactory)
        arena.log = MagicMock()
        arena.button_locations = {1: [855, 205]}
        arena._is_arena_list_visible = MagicMock(return_value=False)
        return arena

    @patch('locations.arena.index.pixel_check_new', return_value=True)
    def test_arena_list_can_be_confirmed_by_refresh_button(self, pixel_check):
        arena = ArenaFactory.__new__(ArenaFactory)
        arena.button_locations = {1: [855, 205]}

        self.assertTrue(arena._is_arena_list_visible())
        pixel_check.assert_called_once()
        self.assertEqual(pixel_check.call_args.args[0][0:2], [817, 133])

    @patch('locations.arena.index.close_popup', return_value=[None, False])
    @patch('locations.arena.index.is_results_screen_visible', return_value=False)
    def test_wait_timeout_remains_unknown_without_positive_signal(self, _results_visible, _close_popup):
        arena = self.make_arena()

        state = arena._wait_for_classic_post_result_state(timeout=1, interval=0.5)

        self.assertEqual(state, 'UNKNOWN')

    @patch('locations.arena.index.pixel_check_new', return_value=True)
    @patch('locations.arena.index.is_victory_screen_visible', return_value=False)
    @patch('locations.arena.index.is_defeat_screen_visible', return_value=False)
    def test_tap_to_continue_pixel_is_result_fallback(self, _defeat, _victory, pixel_check):
        self.assertTrue(is_results_screen_visible())
        pixel_check.assert_called_once_with(
            result_tap_to_continue,
            mistake=45,
            label='result_tap_to_continue',
        )

    @patch('locations.arena.index.tap_to_continue')
    @patch('locations.arena.index.is_results_screen_visible')
    def test_result_close_requires_positive_arena_list_confirmation(self, results_visible, tap):
        arena = self.make_arena()
        results_visible.return_value = True
        arena._wait_for_classic_post_result_state = MagicMock(return_value='UNKNOWN')

        closed = arena._close_classic_result_screen(max_attempts=2, settle_timeout=0.5)

        self.assertFalse(closed)
        self.assertEqual(tap.call_count, 2)

    @patch('locations.arena.index.tap_to_continue')
    @patch('locations.arena.index.is_results_screen_visible')
    def test_battle_end_is_tapped_even_before_result_pixels_settle(self, results_visible, tap):
        arena = self.make_arena()
        results_visible.return_value = False
        arena._wait_for_classic_post_result_state = MagicMock(return_value='ARENA_LIST')

        closed = arena._close_classic_result_screen(settle_timeout=0.5)

        self.assertTrue(closed)
        tap.assert_called_once_with(times=1, wait_before=1, wait_after=2)

    @patch('locations.arena.index.tap_to_continue')
    @patch('locations.arena.index.is_results_screen_visible')
    def test_reward_and_battle_summary_are_closed_before_arena_list(self, results_visible, tap):
        arena = self.make_arena()
        results_visible.return_value = True
        # First tap changes TAP TO CONTINUE into RETURN TO ARENA; the second
        # tap finally exposes the Classic Arena opponent list.
        arena._wait_for_classic_post_result_state = MagicMock(
            side_effect=['RESULTS_SCREEN', 'ARENA_LIST']
        )

        closed = arena._close_classic_result_screen(settle_timeout=0.5)

        self.assertTrue(closed)
        self.assertEqual(tap.call_count, 2)


if __name__ == '__main__':
    unittest.main()
