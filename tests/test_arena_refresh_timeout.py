import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from locations.arena.screen_state import ScreenState


def module(name, **values):
    stub = types.ModuleType(name)
    for key, value in values.items():
        setattr(stub, key, value)
    sys.modules[name] = stub
    return stub


module('pyautogui', press=MagicMock(), pixel=MagicMock(return_value=(0, 0, 0)))
module(
    'helpers.common',
    debug_save_screenshot=MagicMock(),
    is_debug_mode=lambda: False,
    prepare_event=lambda event, props: dict(event, **props),
    sleep=MagicMock(),
    folder_ensure=MagicMock(),
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

from locations.arena.index import ArenaFactory
from locations.arena.screen_state import ScreenObservation


class ArenaRefreshTimeoutTests(unittest.TestCase):
    def make_arena(self):
        arena = ArenaFactory.__new__(ArenaFactory)
        arena.log = MagicMock()
        arena.button_locations = {1: [855, 205], 2: [855, 295], 3: [855, 380], 4: [855, 470]}
        arena.name = 'Arena Classic'
        arena.classic_defeat_offset = 0
        arena.terminated = False
        arena.run_outcome = None
        arena.abort_reason = None
        arena.E_BUTTON_REFRESH = {'name': 'Refresh button'}
        arena.E_TERMINATE = {'name': 'Terminate'}
        arena.E_REFRESH_TIMEOUT = {'name': 'RefreshTimeout'}
        arena.E_REFRESH_COOLDOWN_TIMEOUT = {'name': 'RefreshCooldownTimeout'}
        arena.awaits = MagicMock()
        return arena

    @patch('locations.arena.index.callback_refresh')
    def test_exhausted_list_waits_for_free_refresh_instead_of_aborting(self, _refresh_callback):
        arena = self.make_arena()
        exhausted = ScreenObservation(
            state=ScreenState.ARENA_LIST_EXHAUSTED,
            score=1.0,
            signals=['LIST_SHELL', 'REFRESH_COOLDOWN'],
        )
        arena.awaits = MagicMock(side_effect=[
            {'name': 'RefreshTimeout'},
            {'name': 'Refresh button'},
        ])
        arena._observe_arena_screen = MagicMock(return_value=exhausted)
        arena._is_arena_list_exhausted = MagicMock(return_value=True)
        arena._refresh_cooldown_detected = MagicMock(return_value=True)

        result = arena.refresh_opponent_list()

        self.assertTrue(result)
        self.assertEqual(arena.awaits.call_count, 2)
        self.assertFalse(arena.terminated)

    def test_unknown_screen_still_aborts_on_refresh_timeout(self):
        arena = self.make_arena()
        arena.awaits = MagicMock(return_value={'name': 'RefreshTimeout'})
        arena._observe_arena_screen = MagicMock(
            return_value=ScreenObservation(state=ScreenState.UNKNOWN, score=0.0, signals=[])
        )
        arena._is_arena_list_exhausted = MagicMock(return_value=False)
        arena._is_arena_list_shell_visible = MagicMock(return_value=False)
        arena._refresh_cooldown_detected = MagicMock(return_value=False)

        result = arena.refresh_opponent_list()

        self.assertFalse(result)
        self.assertTrue(arena.terminated)
        self.assertEqual(arena.run_outcome.name, 'ABORTED_UNKNOWN_SCREEN')


if __name__ == '__main__':
    unittest.main()
