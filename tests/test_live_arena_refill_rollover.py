import json
import importlib.util
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from classes.Duration import Duration


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
from locations.live_arena.index import (
    ArenaLive,
    LIVE_ARENA_TOKEN_PACK,
    MATCHMAKING_TIMEOUT_NAME,
    MATCHMAKING_TIMEOUT_S,
    MAX_LIVE_ARENA_REENTRIES,
    MAX_MATCHMAKING_ATTEMPTS,
)


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
        arena.log.assert_any_call(
            'Paid refill allowance refreshed (profile=Lema): '
            '0 -> 3 remaining (UTC)'
        )


class LiveArenaProgressChestTests(unittest.TestCase):
    def _arena(self):
        arena = ArenaLive.__new__(ArenaLive)
        arena.NAME = 'Arena Live'
        arena.app = SimpleNamespace(current_player_name='Lema')
        arena.refill_max_allowed = 1
        arena.refill = 0
        arena.terminated = False
        arena.log = MagicMock()
        return arena

    def test_refill_stops_immediately_if_find_opponent_already_aborted(self):
        arena = self._arena()

        def click_and_abort(*args, **kwargs):
            arena.terminated = True
            return False

        arena._click_on_find_opponent = MagicMock(side_effect=click_and_abort)
        arena._check_progress_chest = MagicMock()

        with patch('locations.live_arena.index.sleep', MagicMock()):
            result = arena._refill()

        self.assertTrue(result)
        arena._check_progress_chest.assert_not_called()

    def test_progress_chest_does_not_abort_when_pick_phase_is_visible(self):
        arena = self._arena()
        arena._click_on_find_opponent = MagicMock()
        arena._check_progress_chest = MagicMock(return_value=True)
        arena._is_match_started = MagicMock(return_value=True)
        arena._is_find_opponent_visible = MagicMock(return_value=False)
        vision.find_needle_refill_ruby.return_value = None

        with patch('locations.live_arena.index.sleep', MagicMock()), \
             patch('locations.live_arena.index.tap_to_continue', MagicMock()):
            result = arena._refill()

        self.assertFalse(result)
        self.assertFalse(arena.terminated)
        arena._click_on_find_opponent.assert_called_once_with()

    def test_progress_chest_clicks_find_opponent_again_without_aborting(self):
        arena = self._arena()
        arena._click_on_find_opponent = MagicMock()
        arena._check_progress_chest = MagicMock(return_value=True)
        arena._is_match_started = MagicMock(return_value=False)
        arena._is_find_opponent_visible = MagicMock(return_value=True)
        vision.find_needle_refill_ruby.return_value = None
        vision.pixels_wait.return_value = [False]

        with patch('locations.live_arena.index.sleep', MagicMock()), \
             patch('locations.live_arena.index.tap_to_continue', MagicMock()):
            result = arena._refill()

        self.assertFalse(result)
        self.assertFalse(arena.terminated)
        self.assertEqual(arena._click_on_find_opponent.call_count, 2)
        arena._click_on_find_opponent.assert_any_call(abort_on_fail=False, wait_limit=8)

    def test_progress_chest_keeps_remaining_runs_when_search_already_running(self):
        arena = self._arena()
        arena._click_on_find_opponent = MagicMock()
        arena._check_progress_chest = MagicMock(return_value=True)
        arena._is_match_started = MagicMock(return_value=False)
        arena._is_find_opponent_visible = MagicMock(return_value=False)
        vision.find_needle_refill_ruby.return_value = None
        vision.pixels_wait.return_value = [False]

        with patch('locations.live_arena.index.sleep', MagicMock()), \
             patch('locations.live_arena.index.tap_to_continue', MagicMock()):
            result = arena._refill()

        self.assertFalse(result)
        self.assertFalse(arena.terminated)
        arena._click_on_find_opponent.assert_called_once_with()
        arena.log.assert_any_call(
            'Progress chest claimed; find opponent not visible — '
            'assuming search in progress, not aborting remaining runs'
        )

    def test_click_on_find_opponent_does_not_terminate_when_abort_disabled(self):
        arena = self._arena()
        arena.terminate = MagicMock(side_effect=lambda: setattr(arena, 'terminated', True))

        with patch('locations.live_arena.index.await_click', return_value=[False]), \
             patch('locations.live_arena.index.is_debug_mode', return_value=False):
            found = arena._click_on_find_opponent(abort_on_fail=False, wait_limit=8)

        self.assertFalse(found)
        arena.terminate.assert_not_called()
        self.assertFalse(arena.terminated)

    def test_click_on_find_opponent_still_aborts_from_lobby_by_default(self):
        arena = self._arena()
        arena.terminate = MagicMock(side_effect=lambda: setattr(arena, 'terminated', True))

        with patch('locations.live_arena.index.await_click', return_value=[False]), \
             patch('locations.live_arena.index.is_debug_mode', return_value=False):
            found = arena._click_on_find_opponent()

        self.assertFalse(found)
        arena.terminate.assert_called_once_with()
        self.assertTrue(arena.terminated)


class LiveArenaTokenPackRecoveryTests(unittest.TestCase):
    def _arena(self, battles=0, refill=0):
        arena = ArenaLive.__new__(ArenaLive)
        arena.NAME = 'Arena Live'
        arena.app = SimpleNamespace(current_player_name='Lema')
        arena.refill = refill
        arena.refill_max_allowed = 1
        arena.terminated = False
        arena.break_loops = False
        arena.abort_reason = None
        arena.log = MagicMock()
        arena.results = [True] * battles
        arena._run_results_start = 0
        arena._paid_refill_exhausted = False
        arena._live_reentries = 0
        arena._battles_at_last_reentry = None
        arena.E_INDICATOR_ACTIVE = {'name': 'IndicatorActive'}
        arena.EVENT_NOT_FOUND = 'EVENT_NOT_FOUND'
        return arena

    def test_should_reenter_when_battle_count_is_not_a_token_pack(self):
        arena = self._arena(battles=11, refill=0)

        self.assertEqual(11 % LIVE_ARENA_TOKEN_PACK, 1)
        self.assertTrue(arena._should_reenter_live_arena())

    def test_should_not_reenter_when_battle_count_fills_complete_packs(self):
        arena = self._arena(battles=10, refill=0)

        self.assertFalse(arena._should_reenter_live_arena())

    def test_should_reenter_when_paid_refill_still_unused(self):
        arena = self._arena(battles=10, refill=1)

        self.assertTrue(arena._should_reenter_live_arena())

    def test_should_not_reenter_when_paid_refill_was_exhausted(self):
        arena = self._arena(battles=11, refill=0)
        arena._paid_refill_exhausted = True

        self.assertFalse(arena._should_reenter_live_arena())

    def test_should_not_reenter_when_accounting_aborted(self):
        arena = self._arena(battles=11, refill=1)
        arena.abort_reason = 'paid refill accounting failed'

        self.assertFalse(arena._should_reenter_live_arena())

    def test_should_not_reenter_after_max_attempts(self):
        arena = self._arena(battles=11, refill=1)
        arena._live_reentries = MAX_LIVE_ARENA_REENTRIES

        self.assertFalse(arena._should_reenter_live_arena())

    def test_should_not_reenter_when_previous_attempt_made_no_progress(self):
        arena = self._arena(battles=11, refill=1)
        arena._live_reentries = 1
        arena._battles_at_last_reentry = 11

        self.assertFalse(arena._should_reenter_live_arena())

    def test_reenter_uses_standard_enter_and_resets_terminated(self):
        arena = self._arena(battles=11, refill=0)
        arena.terminated = True
        arena.break_loops = True
        arena.enter = MagicMock()
        arena.obtain = MagicMock()
        arena.awaits = MagicMock(return_value={'name': 'IndicatorActive'})

        self.assertTrue(arena._reenter_live_arena())

        arena.enter.assert_called_once_with()
        arena.obtain.assert_called_once_with()
        self.assertFalse(arena.terminated)
        self.assertFalse(arena.break_loops)
        self.assertEqual(arena._live_reentries, 1)
        self.assertEqual(arena._battles_at_last_reentry, 11)

    def test_reenter_stops_if_enter_aborts(self):
        arena = self._arena(battles=11, refill=0)

        def enter_and_abort():
            arena.terminated = True

        arena.enter = MagicMock(side_effect=enter_and_abort)
        arena.obtain = MagicMock()
        arena.awaits = MagicMock()

        self.assertFalse(arena._reenter_live_arena())
        arena.awaits.assert_not_called()
        arena.obtain.assert_not_called()

    def test_reenter_stops_if_live_arena_is_not_active(self):
        arena = self._arena(battles=11, refill=0)
        arena.enter = MagicMock()
        arena.obtain = MagicMock()
        arena.awaits = MagicMock(return_value={'name': 'EVENT_NOT_FOUND'})

        self.assertFalse(arena._reenter_live_arena())
        arena.obtain.assert_not_called()

    def test_refill_marks_paid_tokens_exhausted_when_ruby_popup_has_no_allowance(self):
        arena = self._arena(battles=11, refill=0)
        arena._click_on_find_opponent = MagicMock()
        arena._check_progress_chest = MagicMock(return_value=False)
        arena.terminate = MagicMock(side_effect=lambda: setattr(arena, 'terminated', True))
        vision.find_needle_refill_ruby.return_value = [100, 100]
        remaining_refills.return_value = 0

        with patch('locations.live_arena.index.sleep', MagicMock()):
            result = arena._refill()

        self.assertTrue(result)
        self.assertTrue(arena._paid_refill_exhausted)
        arena.terminate.assert_called_once_with()


class LiveArenaMatchmakingTests(unittest.TestCase):
    def _arena(self):
        arena = ArenaLive.__new__(ArenaLive)
        arena.log = MagicMock()
        arena.terminated = False
        arena.break_loops = False
        arena.abort_reason = None
        arena.EVENT_NOT_FOUND = 'EVENT_NOT_FOUND'
        arena.E_PICK_FIRST = {'name': 'PickFirst'}
        arena.E_PICK_SECOND = {'name': 'PickSecond'}
        arena.E_CANT_FIND_OPPONENT = {'name': 'CantFindAnOpponent'}
        arena.E_INDICATOR_INACTIVE = {'name': 'IndicatorInactive'}

        def terminate(*args, **kwargs):
            arena.terminated = True
            arena.break_loops = True

        arena.terminate = terminate
        arena.awaits = MagicMock()
        arena._is_match_started = MagicMock(return_value=False)
        arena._is_cant_find_opponent_visible = MagicMock(return_value=False)
        arena._is_find_opponent_visible = MagicMock(return_value=False)
        arena._match_start_event_name = MagicMock(return_value=None)
        arena._retry_find_opponent_after_no_match = MagicMock()
        return arena

    def test_matchmaking_events_include_timeout(self):
        arena = self._arena()

        names = [event['name'] for event in arena._matchmaking_start_events()]
        timeout = next(
            event for event in arena._matchmaking_start_events()
            if event['name'] == MATCHMAKING_TIMEOUT_NAME
        )

        self.assertIn('PickFirst', names)
        self.assertIn('CantFindAnOpponent', names)
        self.assertEqual(timeout['delay'], MATCHMAKING_TIMEOUT_S)
        self.assertTrue(timeout['expect']())

    def test_wait_returns_when_pick_starts(self):
        arena = self._arena()
        arena.awaits.return_value = {'name': 'PickFirst'}

        self.assertEqual(arena._wait_for_match_start(), 'PickFirst')
        self.assertFalse(arena.terminated)
        self.assertIsNone(arena.abort_reason)
        arena.awaits.assert_called_once()

    def test_stuck_search_aborts_so_preset_can_continue(self):
        arena = self._arena()
        arena.awaits.return_value = {'name': MATCHMAKING_TIMEOUT_NAME}

        with patch('locations.live_arena.index.debug_save_screenshot'):
            result = arena._wait_for_match_start()

        self.assertIsNone(result)
        self.assertTrue(arena.terminated)
        self.assertEqual(arena.abort_reason, 'live arena matchmaking timeout')
        arena._retry_find_opponent_after_no_match.assert_not_called()
        arena.awaits.assert_called_once()

    def test_cant_find_retries_then_returns_on_pick(self):
        arena = self._arena()
        arena.awaits.side_effect = [
            {'name': 'CantFindAnOpponent'},
            {'name': 'PickSecond'},
        ]

        self.assertEqual(arena._wait_for_match_start(), 'PickSecond')
        self.assertFalse(arena.terminated)
        arena._retry_find_opponent_after_no_match.assert_called_once()
        self.assertEqual(arena.awaits.call_count, 2)

    def test_cant_find_aborts_after_max_attempts(self):
        arena = self._arena()
        arena.awaits.return_value = {'name': 'CantFindAnOpponent'}

        result = arena._wait_for_match_start()

        self.assertIsNone(result)
        self.assertTrue(arena.terminated)
        self.assertEqual(arena.abort_reason, 'live arena matchmaking timeout')
        self.assertEqual(arena.awaits.call_count, MAX_MATCHMAKING_ATTEMPTS)
        self.assertEqual(
            arena._retry_find_opponent_after_no_match.call_count,
            MAX_MATCHMAKING_ATTEMPTS - 1,
        )

    def test_timeout_retries_when_cant_find_popup_is_visible(self):
        arena = self._arena()
        arena._is_cant_find_opponent_visible.return_value = True
        arena.awaits.side_effect = [
            {'name': MATCHMAKING_TIMEOUT_NAME},
            {'name': 'PickFirst'},
        ]

        with patch('locations.live_arena.index.debug_save_screenshot'):
            result = arena._wait_for_match_start()

        self.assertEqual(result, 'PickFirst')
        self.assertFalse(arena.terminated)
        arena._retry_find_opponent_after_no_match.assert_called_once()

    def test_inactive_indicator_stops_without_abort_reason(self):
        arena = self._arena()
        arena.awaits.return_value = {'name': 'IndicatorInactive'}

        result = arena._wait_for_match_start()

        self.assertIsNone(result)
        self.assertTrue(arena.terminated)
        self.assertIsNone(arena.abort_reason)

    def test_matchmaking_abort_blocks_live_arena_reentry(self):
        arena = LiveArenaTokenPackRecoveryTests()._arena(battles=11, refill=1)
        arena.abort_reason = 'live arena matchmaking timeout'

        self.assertFalse(arena._should_reenter_live_arena())


class LiveArenaDailySummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        path = Path(__file__).parents[1] / 'helpers' / 'battle_stats.py'
        spec = importlib.util.spec_from_file_location('battle_stats_daily_summary_test', path)
        self.stats = importlib.util.module_from_spec(spec)
        common = types.ModuleType('helpers.common')
        common.folder_ensure = MagicMock()
        with patch.dict(sys.modules, {'helpers.common': common}):
            spec.loader.exec_module(self.stats)
        self.stats_path = str(Path(self.temp_dir.name) / 'battle_stats.json')

    def tearDown(self):
        self.temp_dir.cleanup()

    def arena(self, started, seconds):
        arena = ArenaLive.__new__(ArenaLive)
        arena.app = SimpleNamespace(current_player_name='Lema')
        arena.duration = Duration()
        arena.duration.durations = [[started, started + timedelta(seconds=seconds)]]
        arena.results = []
        return arena

    def test_zero_battle_rerun_keeps_all_battles_and_total_time(self):
        first = self.arena(datetime(2026, 9, 28, 9, 4, 33), 4851)
        second = self.arena(datetime(2026, 9, 28, 10, 25, 24), 25)

        with patch.dict(sys.modules, {'helpers.battle_stats': self.stats}), \
                patch.object(self.stats, '_get_file_path', return_value=self.stats_path), \
                patch.object(self.stats, '_get_utc_date', return_value='2026-09-28'), \
                patch('locations.live_arena.index.calculate_win_rate', return_value='40%'):
            self.stats.update_stats('arena_live', {'wins': 8, 'losses': 12}, 'Lema')
            first._after_duration_end()
            second._after_duration_end()

            self.assertEqual(second._finish_duration(), '1:21:16')
            self.assertEqual(second._report_duration(), '1:21:16')
            self.assertEqual(
                second._format_run_battle_summary(),
                '20 battles · 8W / 12L · WR 40%',
            )
            self.assertEqual(second._report(), ['Battles: 20 (8W / 12L, WR: 40%)'])
            self.assertEqual(
                self.stats.load_stats('arena_live', 'Lema')['duration_seconds'],
                4876,
            )
            self.assertEqual(self.stats.load_stats('arena_live', 'Other'), {})

    def test_duration_totals_are_separate_by_profile_and_utc_day(self):
        with patch.object(self.stats, '_get_file_path', return_value=self.stats_path), \
                patch.object(self.stats, '_get_utc_date', return_value='2026-09-28'):
            self.stats.record_duration('arena_live', 60, 'Lema')
            self.stats.record_duration('arena_live', 30, 'Other')
            self.assertEqual(
                self.stats.load_stats('arena_live', 'Lema')['duration_seconds'], 60
            )
            self.assertEqual(
                self.stats.load_stats('arena_live', 'Other')['duration_seconds'], 30
            )

        with patch.object(self.stats, '_get_file_path', return_value=self.stats_path), \
                patch.object(self.stats, '_get_utc_date', return_value='2026-09-29'):
            self.assertEqual(self.stats.load_stats('arena_live', 'Lema'), {})
            self.stats.record_duration('arena_live', 5, 'Lema')
            self.assertEqual(
                self.stats.load_stats('arena_live', 'Lema')['duration_seconds'], 5
            )


if __name__ == '__main__':
    unittest.main()
