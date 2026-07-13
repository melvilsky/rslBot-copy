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
    folder_ensure=MagicMock()
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
module(
    'helpers.refill_state',
    get_purchased_count=MagicMock(return_value=0),
    get_remaining_refills=MagicMock(),
    increment_purchase=MagicMock(),
    begin_refill_attempt=MagicMock(),
    resolve_refill_attempt=MagicMock(),
    has_unresolved_attempt=MagicMock(return_value=False),
    RefillStateError=type('RefillStateError', (Exception,), {}),
    ATTEMPT_PENDING='pending',
    ATTEMPT_CONFIRMED='confirmed',
    ATTEMPT_FAILED='failed',
    ATTEMPT_UNCERTAIN='uncertain',
    KIND_FREE='free',
    KIND_PAID='paid',
)

location_module = module('classes.Location')


class Location:
    E_BATTLE_END = {}


class RunOutcome:
    class _Value:
        def __init__(self, name):
            self.name = name

    COMPLETED_RESOURCES_EXHAUSTED = _Value('COMPLETED_RESOURCES_EXHAUSTED')
    COMPLETED_POLICY_LIMIT = _Value('COMPLETED_POLICY_LIMIT')
    DEFERRED_REFRESH_COOLDOWN = _Value('DEFERRED_REFRESH_COOLDOWN')
    PARTIAL_LIST_EXHAUSTED = _Value('PARTIAL_LIST_EXHAUSTED')
    ABORTED_NAVIGATION = _Value('ABORTED_NAVIGATION')
    ABORTED_UNKNOWN_SCREEN = _Value('ABORTED_UNKNOWN_SCREEN')
    REFILL_FAILED = _Value('REFILL_FAILED')
    REFILL_UNCERTAIN = _Value('REFILL_UNCERTAIN')
    TERMINATED_BY_USER = _Value('TERMINATED_BY_USER')
    DONE = _Value('DONE')


location_module.Location = Location
location_module.RunOutcome = RunOutcome

from locations.arena.index import ArenaFactory, get_results_screen_signal, result_tap_to_continue


class ArenaResultRecoveryTests(unittest.TestCase):
    def make_arena(self):
        arena = ArenaFactory.__new__(ArenaFactory)
        arena.log = MagicMock()
        arena.button_locations = {1: [855, 205]}
        arena._is_arena_list_visible = MagicMock(return_value=False)
        return arena

    @patch('locations.arena.index.pixel_check_new', return_value=True)
    def test_arena_list_can_be_confirmed_by_page_shell(self, pixel_check):
        # Оболочка страницы (вкладка Battle + левая панель) — основной
        # признак списка: он работает и без Attack/free Refresh.
        arena = ArenaFactory.__new__(ArenaFactory)
        arena.button_locations = {}

        self.assertTrue(arena._is_arena_list_visible())
        self.assertEqual(arena._last_arena_list_signal, 'LIST_SHELL')

    @patch('locations.arena.index.pixel_check_new')
    def test_arena_list_falls_back_to_refresh_button(self, pixel_check):
        # Если оболочка не подтверждена, список ещё может быть подтверждён
        # по синей кнопке Refresh с tolerance 45.
        def only_refresh_matches(point, mistake=10, label=None):
            return point[0:2] == [817, 133]

        pixel_check.side_effect = only_refresh_matches
        arena = ArenaFactory.__new__(ArenaFactory)
        arena.button_locations = {}

        self.assertTrue(arena._is_arena_list_visible())
        self.assertEqual(arena._last_arena_list_signal, 'REFRESH_BUTTON')
        last_call = pixel_check.call_args
        self.assertEqual(last_call[0][0][0:2], [817, 133])
        self.assertEqual(last_call[1]['mistake'], 45)

    @patch('locations.arena.index.get_results_screen_signal', return_value='VICTORY')
    def test_result_screen_has_priority_over_false_arena_list_match(self, _results_visible):
        arena = self.make_arena()
        arena._is_arena_list_visible.return_value = True

        state = arena._wait_for_classic_post_result_state(timeout=1, interval=0.5)

        self.assertEqual(state, 'RESULTS_SCREEN')
        arena._is_arena_list_visible.assert_not_called()

    @patch('locations.arena.index.get_results_screen_signal', return_value=None)
    def test_wait_timeout_remains_unknown_without_positive_signal(self, _results_visible):
        arena = self.make_arena()

        state = arena._wait_for_classic_post_result_state(timeout=1, interval=0.5)

        self.assertEqual(state, 'UNKNOWN')

    @patch('locations.arena.index.pixel_check_new', return_value=True)
    @patch('locations.arena.index.is_victory_screen_visible', return_value=False)
    @patch('locations.arena.index.is_defeat_screen_visible', return_value=False)
    def test_tap_to_continue_pixel_is_result_fallback(self, _defeat, _victory, pixel_check):
        self.assertEqual(get_results_screen_signal(), 'TAP_TO_CONTINUE')
        pixel_check.assert_called_once_with(
            result_tap_to_continue,
            mistake=45,
            label='result_tap_to_continue',
        )

    @patch('locations.arena.index.tap_to_continue')
    @patch('locations.arena.index.get_results_screen_signal')
    def test_result_close_requires_positive_arena_list_confirmation(self, results_visible, tap):
        arena = self.make_arena()
        results_visible.return_value = 'VICTORY'
        arena._wait_for_classic_post_result_state = MagicMock(return_value='UNKNOWN')

        closed = arena._close_classic_result_screen(max_attempts=2, settle_timeout=0.5)

        self.assertFalse(closed)
        # 2 primary attempts + 3 grace taps
        self.assertEqual(tap.call_count, 5)

    @patch('locations.arena.index.tap_to_continue')
    @patch('locations.arena.index.get_results_screen_signal')
    def test_battle_end_is_tapped_even_before_result_pixels_settle(self, results_visible, tap):
        arena = self.make_arena()
        results_visible.return_value = None
        arena._wait_for_classic_post_result_state = MagicMock(return_value='ARENA_LIST')

        closed = arena._close_classic_result_screen(settle_timeout=0.5)

        self.assertTrue(closed)
        tap.assert_called_once_with(times=1, wait_before=1, wait_after=2)

    @patch('locations.arena.index.tap_to_continue')
    @patch('locations.arena.index.get_results_screen_signal', return_value=None)
    def test_false_list_match_cannot_skip_first_battle_end_tap(self, _results_visible, tap):
        arena = self.make_arena()
        arena._is_arena_list_visible.return_value = True
        arena._wait_for_classic_post_result_state = MagicMock(return_value='ARENA_LIST')

        closed = arena._close_classic_result_screen(settle_timeout=0.5)

        self.assertTrue(closed)
        tap.assert_called_once_with(times=1, wait_before=1, wait_after=2)

    @patch('locations.arena.index.tap_to_continue')
    @patch('locations.arena.index.get_results_screen_signal')
    def test_reward_and_battle_summary_are_closed_before_arena_list(self, results_visible, tap):
        arena = self.make_arena()
        results_visible.return_value = 'VICTORY'
        # First tap changes TAP TO CONTINUE into RETURN TO ARENA; the second
        # tap finally exposes the Classic Arena opponent list.
        arena._wait_for_classic_post_result_state = MagicMock(
            side_effect=['RESULTS_SCREEN', 'ARENA_LIST']
        )

        closed = arena._close_classic_result_screen(settle_timeout=0.5)

        self.assertTrue(closed)
        self.assertEqual(tap.call_count, 2)

    @patch('locations.arena.index.tap_to_continue')
    @patch('locations.arena.index.get_results_screen_signal')
    def test_grace_taps_close_remaining_result_screen(self, results_visible, tap):
        arena = self.make_arena()
        results_visible.side_effect = ['DEFEAT', 'TAP_TO_CONTINUE', 'TAP_TO_CONTINUE', None]
        arena._wait_for_classic_post_result_state = MagicMock(
            side_effect=['UNKNOWN', 'RESULTS_SCREEN', 'ARENA_LIST']
        )

        closed = arena._close_classic_result_screen(max_attempts=2, settle_timeout=0.5)

        self.assertTrue(closed)
        self.assertGreaterEqual(tap.call_count, 3)


if __name__ == '__main__':
    unittest.main()
