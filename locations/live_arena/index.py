import pyautogui
import pause
import copy
import random
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw

from helpers.common import (
    prepare_event,
    sleep,
)
from helpers.game_actions import (
    calculate_win_rate,
    claim_rewards,
    click_on_progress_info,
    enable_auto_play,
)
from helpers.logging_utils import get_time_for_log, is_debug_mode, log, log_save
from helpers.mouse import await_click, click, tap_to_continue
from helpers.screen import debug_save_screenshot, show_pyautogui_image
from helpers.vision import (
    find_hero_slot_empty,
    find_indicator_active,
    find_indicator_inactive,
    find_needle_refill_ruby,
    find_victory_opponent_left,
    pixel_check_new,
    pixels_wait,
    rgb_check,
)
from helpers.coordinates import get_coordinate, get_mistake, load_coordinates
from helpers.time_mgr import TimeMgr
from helpers.refill_state import RefillStateError, get_remaining_refills, increment_purchase
from locations.hero_filter.index import HeroFilter
from locations.live_arena.availability import is_index_indicator_active
from locations.live_arena.picking import pop_next_character
from classes.Location import Location

# ============================================================================
# КООРДИНАТЫ ХРАНЯТСЯ В: coordinates/live_arena.json
# Для изменения координат отредактируйте этот файл и перезапустите приложение
# ============================================================================
# Загружаем координаты при импорте модуля
_coordinates_data = load_coordinates('live_arena.json', required=True)


def get_live_arena_coordinate(key):
    result = get_coordinate(_coordinates_data, key, source='coordinates/live_arena.json', require_rgb=True)
    return result


def get_coordinate_mistake(key, default_mistake=20):
    return get_mistake(_coordinates_data, key, default_mistake)

# Загружаем координаты из coordinates/live_arena.json
# Все координаты должны быть указаны в JSON файле, дефолтных значений нет
CLAIM_FREE_REFILL_COINS = get_live_arena_coordinate('claim_free_refill_coins')
claim_chest = get_live_arena_coordinate('claim_chest')
refill_free = get_live_arena_coordinate('refill_free')
refill_paid = get_live_arena_coordinate('refill_paid')

time_mgr = TimeMgr()
hero_filter = HeroFilter()

first = [334, 209, [22, 51, 90]]
second = [899, 94, [90, 24, 24]]
cant_find_opponent_button_find = [590, 290, [187, 130, 5]]
cant_find_opponent_button_cancel = [280, 290, [22, 124, 156]]

RGB_EMPTY_SLOT = [49, 54, 49]
EMPTY_SLOT_WIDTH = 48
EMPTY_SLOT_HEIGHT = 64
LIVE_ARENA_HERO_SLOTS = [
    [226, 162, RGB_EMPTY_SLOT],
    [184, 264, RGB_EMPTY_SLOT],
    [146, 162, RGB_EMPTY_SLOT],
    [105, 264, RGB_EMPTY_SLOT],
    [64, 162, RGB_EMPTY_SLOT],
]

enemy_slots = [
    [650, 198, RGB_EMPTY_SLOT],
    [697, 289, RGB_EMPTY_SLOT],
    [728, 199, RGB_EMPTY_SLOT],
    [767, 292, RGB_EMPTY_SLOT],
    [812, 201, RGB_EMPTY_SLOT],
]

# picking heroes
stage_1 = [460, 330, [36, 88, 110]]
# ban hero
stage_2 = [460, 330, [72, 60, 77]]
# choose leader
stage_3 = [460, 330, [72, 87, 77]]

turn_to_pick = [461, 245, [149, 242, 255]]

# Statuses are not working properly (en localization only)
# status_active = [320, 420, [50, 165, 42]]
# status_not_active = [320, 420, [165, 45, 52]]

# the white 'Clock' in the left-top corner
finish_battle = [21, 46, [255, 255, 255]]

victory = [451, 38, [23, 146, 218]]
defeat = [451, 38, [199, 26, 48]]

find_opponent = [500, 460, [255, 190, 0]]
battle_start_turn = [341, 74, [86, 191, 255]]
# Координаты refill_free и refill_paid загружаются выше через get_coordinate()

# return_start_panel = [444, 490]

PAID_REFILL_LIMIT = 1
ARCHIVE_PATTERN_FIRST = [1, 2, 2]
LIVE_ARENA_TOKEN_PACK = 5
MAX_LIVE_ARENA_REENTRIES = 2
MATCHMAKING_TIMEOUT_S = 90
MAX_MATCHMAKING_ATTEMPTS = 3
CANT_FIND_OPPONENT_MISTAKE = 15
MATCHMAKING_TIMEOUT_NAME = 'MatchmakingTimeout'
MATCHMAKING_WAITING_NAME = 'MatchmakingWaiting'

# Сундук прогресса (награда за 35 побед) — попап появляется после нажатия "поиск соперника"
PROGRESS_CHEST = [483, 226, [109, 50, 42]]
PROGRESS_CHEST_MISTAKE = 25

# @TODO Can be useful
error_dialog_button_left = [357, 287, [22, 124, 156]]
error_dialog_button_right = [550, 291, [22, 124, 156]]

# RGB
# arena_classic victory: [59, 37, 11]
# arena_classic defeat: [27, 19, 131]
# arena_live victory: [77, 53, 10]
rgb_victory = [77, 53, 10]
rgb_defeat = [27, 19, 131]

rgb_reward = [220, 0, 0]
rewards_pixels = [
    [875, 118, rgb_reward],
    [875, 472, rgb_reward],
    [875, 422, rgb_reward],
    [875, 372, rgb_reward],
    [875, 322, rgb_reward],
    [875, 272, rgb_reward],
]


class ArenaLive(Location):
    def __init__(self, app, props=None):
        Location.__init__(self, name='Arena Live', app=app, report_predicate=self._report)

        self.results = []
        self.pool = []
        self.leaders = []
        self.refill = PAID_REFILL_LIMIT
        self.idle_after_defeat = 0
        self.refill_max_allowed = PAID_REFILL_LIMIT  # Сохраняем максимальное значение из конфига
        self.ban_priority = None  # 1-5 = слот врага для бана; None = случайный слот
        self._paid_refill_exhausted = False
        self._live_reentries = 0
        self._battles_at_last_reentry = None

        # The variable resets each battle start
        self.current = {
            'counter': 0,
            'slots_counter': 0,
            'battle_time': None,
            'sorted_pool': [],
            'team': [],
            'next_char': None,
            'current_char': None,
        }

        # Applying properties
        if props is not None:
            self._apply_props(props=props)

        # LiveArena related events
        self.E_CANT_FIND_OPPONENT = {
            "name": "CantFindAnOpponent",
            "expect": self._is_cant_find_opponent_visible,
            "blocking": True,
            "interval": 3,
        }
        self.E_OPPONENT_LEFT = {
            "name": "OpponentLeft",
            "expect": find_victory_opponent_left,
            "callback": lambda *args: self.terminate(terminated=False, predicate=lambda: self.handle_result(True)),
            "interval": .5,
        }
        self.E_PICK_FIRST = {
            "name": "PickFirst",
            "expect": lambda: pixel_check_new(first, mistake=5),
        }
        self.E_PICK_SECOND = {
            "name": "PickSecond",
            "expect": lambda: pixel_check_new(second, mistake=5),
        }
        self.E_VICTORY = {
            "name": "Victory",
            "expect": lambda: pixel_check_new(victory, mistake=30),
            "callback": lambda *args: self.handle_result(True),
        }
        self.E_DEFEAT = {
            "name": "Defeat",
            "expect": lambda: pixel_check_new(defeat, mistake=30),
            "callback": lambda *args: self.handle_result(False),
        }

        self.E_STAGE_1 = {
            "name": "Stage 1 | PickingCharacters",
            "expect": lambda: pixel_check_new(stage_1, mistake=10),
            "interval": 2,
        }
        self.E_PICKING_PROCESS = {
            "name": "PickingCharactersProcess",
            "expect": lambda: pixel_check_new(first, mistake=10),
            "interval": 2,
        }
        self.E_STAGE_2 = {
            "name": "Stage 2 | BanHero",
            "expect": lambda: pixel_check_new(stage_2, mistake=10),
            "interval": 2,
        }
        self.E_STAGE_3 = {
            "name": "Stage 3 | ChoosingLeader",
            "expect": lambda: pixel_check_new(stage_3, mistake=10),
            "interval": 2,
        }
        self.E_CHOOSING_LEADER = {
            "name": "ChoosingLeaderProcess",
            "expect": lambda: pixel_check_new(first, mistake=10),
            "interval": 2,
        }
        self.E_BATTLE_START_LIVE = {
            "name": "BattleStartLive",
            "expect": lambda: pixel_check_new(battle_start_turn, mistake=20),
            "callback": enable_auto_play,
            "blocking": False,
            "limit": 1,
        }
        self.E_INDICATOR_ACTIVE = {
            "name": "IndicatorActive",
            "expect": find_indicator_active,
            "limit": 1,
            "wait_limit": 15,
        }
        self.E_INDICATOR_INACTIVE = {
            "name": "IndicatorInactive",
            "expect": find_indicator_inactive,
            "limit": 1,
            "interval": 10,
            "callback": self.terminate,
        }
        # @TODO Not implemented yet (see index_new_2.py)
        self.E_FILLED_HERO_SLOT = {
            'name': 'FilledHeroSlot',
            'expect': lambda: find_hero_slot_empty(region=[
                LIVE_ARENA_HERO_SLOTS[self.current['slots_counter']][0],
                LIVE_ARENA_HERO_SLOTS[self.current['slots_counter']][1],
                EMPTY_SLOT_WIDTH,
                EMPTY_SLOT_HEIGHT
            ]) is None,
            'limit': 1,
            'interval': 1,
            'wait_limit': 30,
            'callback': self._cb_active_hero_slot,
        }

        # PubSub
        self.event_dispatcher.subscribe('enter', self._enter)
        self.event_dispatcher.subscribe('run', self._run)

    def _cb_active_hero_slot(self, *args):
        print('next_char', self.current['next_char'])
        print('current_char', self.current['current_char'])
        self.current['next_char'] = self.current['current_char']

    def _cb_cant_find_opponent(self, *args):
        self._retry_find_opponent_after_no_match()

    def _report(self):
        from helpers.battle_stats import load_stats
        res_list = []
        profile = getattr(self.app, 'current_player_name', None)
        stats = load_stats('arena_live', profile_name=profile)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        t = wins + losses
        if t:
            res_list.append(
                f"Battles: {t} ({wins}W / {losses}L, "
                f"WR: {calculate_win_rate(wins, losses)})"
            )

        return res_list

    def _format_run_battle_summary(self):
        from helpers.battle_stats import load_stats
        profile = getattr(self.app, 'current_player_name', None)
        stats = load_stats('arena_live', profile_name=profile)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        battles = wins + losses
        if battles:
            return f'{battles} battles · {wins}W / {losses}L · WR {calculate_win_rate(wins, losses)}'
        return super()._format_run_battle_summary()

    def _after_duration_end(self):
        from helpers.battle_stats import record_duration
        profile = getattr(self.app, 'current_player_name', None)
        start, end = self.duration.durations[-1]
        self._finish_total_duration_seconds = record_duration(
            'arena_live', (end - start).total_seconds(), profile_name=profile
        )

    def _finish_duration(self):
        seconds = getattr(self, '_finish_total_duration_seconds', None)
        if seconds is None:
            return super()._finish_duration()
        return str(timedelta(seconds=int(seconds)))

    def _report_duration(self):
        from helpers.battle_stats import load_stats
        profile = getattr(self.app, 'current_player_name', None)
        seconds = load_stats('arena_live', profile_name=profile).get('duration_seconds', 0)
        if self.duration.durations:
            start, end = self.duration.durations[-1]
            if start is not None and end is None:
                seconds += max(0, (datetime.utcnow() - start).total_seconds())
        return str(timedelta(seconds=int(seconds))) if seconds else None

    def _enter(self):
        # Additional check for avoiding further proceeding
        if not is_index_indicator_active(pixel_check_new):
            self.log("IndexPage indicator is NOT active")
            self.terminate()
            return

        click_on_progress_info()
        # live arena
        click(600, 175)
        sleep(3)

    def _run(self, props=None):
        if props is not None:
            self._apply_props(props=props)

        def cb_starting(*args):
            self.log('Active')
            has_pool = bool(len(self.pool))
            if has_pool:
                self._paid_refill_exhausted = False
                self._live_reentries = 0
                self._battles_at_last_reentry = None

                self.obtain()
                while True:
                    self._run_live_arena_battles()
                    if not self._should_reenter_live_arena():
                        break
                    if not self._reenter_live_arena():
                        break
                self.obtain()
                # @TODO Temp commented
                # self.event_dispatcher.publish('update_results')

            else:
                self.log("Terminated | The 'pool' property is NOT specified")

        E_INDICATOR_ACTIVE_WITH_CALLBACK = prepare_event(self.E_INDICATOR_ACTIVE, {
            "callback": cb_starting
        })

        if self.awaits([E_INDICATOR_ACTIVE_WITH_CALLBACK])['name'] == self.EVENT_NOT_FOUND:
            self.log('NOT Active')

    def _apply_props(self, props):
        if 'pool' in props:
            pool_copy = copy.deepcopy(props['pool'])
            self.pool = sorted(pool_copy, key=lambda x: (-x.get('priority', 0), x.get('priority', 0)))
            if 'leaders' in props:
                self.leaders = props['leaders']

        if 'refill' in props:
            refill_from_config = int(props['refill'])
            self.refill_max_allowed = refill_from_config
            location_key = self.NAME.lower().replace(' ', '_')
            profile = getattr(self.app, 'current_player_name', None)
            self.refill = get_remaining_refills(location_key, refill_from_config, profile_name=profile)
            if self.refill < refill_from_config:
                self.log(f"Refill state loaded (profile={profile or 'default'}): {refill_from_config - self.refill} already purchased today (UTC), {self.refill} remaining")

        if 'idle_after_defeat' in props:
            self.idle_after_defeat = int(props['idle_after_defeat'])

        if 'ban_priority' in props:
            self.ban_priority = int(props['ban_priority'])

    def _refresh_paid_refills(self):
        """Re-read today's UTC allowance instead of trusting startup state.

        The app can stay running across the UTC day boundary.  In that case
        ``self.refill`` may still contain yesterday's remaining allowance,
        even though refill_state has already rolled over to a new day.
        """
        location_key = self.NAME.lower().replace(' ', '_')
        profile = getattr(self.app, 'current_player_name', None)
        previous = self.refill
        self.refill = get_remaining_refills(
            location_key,
            self.refill_max_allowed,
            profile_name=profile,
        )
        if self.refill != previous:
            self.log(
                f"Paid refill allowance refreshed (profile={profile or 'default'}): "
                f"{previous} -> {self.refill} remaining (UTC)"
            )
        return self.refill

    def _confirm(self):
        click(870, 465)
        sleep(.5)

    def _claim_chest(self):
        # the chest is available
        if pixel_check_new(claim_chest):
            x = claim_chest[0]
            y = claim_chest[1]
            claim_rewards(x, y)

    def _check_progress_chest(self):
        """
        Проверяет попап сундука прогресса (награда за 35 побед) после нажатия "поиск соперника".
        Попап перекрывает экран поиска — если он есть, нужно забрать награду и запустить поиск заново.
        Returns True если сундук был найден и обработан, False если сундука нет.
        """
        x = PROGRESS_CHEST[0]
        y = PROGRESS_CHEST[1]
        expected_rgb = PROGRESS_CHEST[2]

        if is_debug_mode():
            try:
                actual_pixel = pyautogui.pixel(x, y)
                actual_rgb = [actual_pixel[0], actual_pixel[1], actual_pixel[2]]
                from helpers.common import rgb_check
                matches = rgb_check(actual_rgb, expected_rgb, mistake=PROGRESS_CHEST_MISTAKE)
                self.log(f"DEBUG progress_chest check: [{x}, {y}] expected={expected_rgb} actual={actual_rgb} match={matches}")
            except Exception as e:
                self.log(f"ERROR progress_chest debug pixel read: {e}")

        found = pixel_check_new(PROGRESS_CHEST, mistake=PROGRESS_CHEST_MISTAKE, label='progress_chest')

        if found:
            self.log(f"Progress chest detected at ({x}, {y}) — claiming reward")
            if is_debug_mode():
                debug_save_screenshot(suffix_name='live-arena-progress-chest-found')
            click(x, y)
            sleep(2)
            tap_to_continue(wait_before=1, wait_after=1)
            return True

        return False

    def _is_find_opponent_visible(self):
        return pixel_check_new(find_opponent, mistake=20, label='find_opponent')

    def _is_cant_find_opponent_visible(self):
        return (
            pixel_check_new(
                cant_find_opponent_button_cancel,
                mistake=CANT_FIND_OPPONENT_MISTAKE,
                label='cant_find_cancel',
            )
            or pixel_check_new(
                cant_find_opponent_button_find,
                mistake=CANT_FIND_OPPONENT_MISTAKE,
                label='cant_find_find',
            )
        )

    def _is_match_started(self):
        return (
            pixel_check_new(first, mistake=10, label='pick_first')
            or pixel_check_new(second, mistake=10, label='pick_second')
        )

    def _match_start_event_name(self):
        if pixel_check_new(second, mistake=10, label='pick_second'):
            return self.E_PICK_SECOND['name']
        if pixel_check_new(first, mistake=10, label='pick_first'):
            return self.E_PICK_FIRST['name']
        return None

    def _retry_find_opponent_after_no_match(self):
        click(cant_find_opponent_button_cancel[0], cant_find_opponent_button_cancel[1])
        sleep(1)
        if self._is_match_started():
            return True
        if self._is_cant_find_opponent_visible():
            click(cant_find_opponent_button_find[0], cant_find_opponent_button_find[1])
            sleep(1)
            return True
        return self._click_on_find_opponent(abort_on_fail=False, wait_limit=8)

    def _matchmaking_start_events(self):
        heartbeat = {
            "name": MATCHMAKING_WAITING_NAME,
            "expect": lambda: True,
            "blocking": False,
            "delay": 30,
            "interval": 30,
            "callback": lambda *args: self.log('Still searching for opponent'),
        }
        timeout = {
            "name": MATCHMAKING_TIMEOUT_NAME,
            "expect": lambda: True,
            "delay": MATCHMAKING_TIMEOUT_S,
            "interval": 1,
            "limit": 1,
        }
        return [
            self.E_PICK_FIRST,
            self.E_PICK_SECOND,
            self.E_CANT_FIND_OPPONENT,
            self.E_INDICATOR_INACTIVE,
            heartbeat,
            timeout,
        ]

    def _abort_matchmaking(self, reason='live arena matchmaking timeout'):
        self.log('Aborting Live Arena so the preset can continue')
        self.abort_reason = reason
        self.terminate()

    def _wait_for_match_start(self):
        """Wait for pick phase. Time out instead of blocking the rest of the preset."""
        for attempt in range(1, MAX_MATCHMAKING_ATTEMPTS + 1):
            if self.break_loops or self.terminated:
                return None

            result = self.awaits(events=self._matchmaking_start_events(), interval=.1)
            name = result['name'] if result else self.EVENT_NOT_FOUND
            self.log(name)

            if name in (self.E_PICK_FIRST['name'], self.E_PICK_SECOND['name']):
                return name

            if name == self.E_INDICATOR_INACTIVE['name']:
                if not self.terminated:
                    self.terminate()
                return None

            if name == self.E_CANT_FIND_OPPONENT['name']:
                self.log(
                    f'No opponent found (attempt {attempt}/{MAX_MATCHMAKING_ATTEMPTS})'
                )
                if attempt >= MAX_MATCHMAKING_ATTEMPTS:
                    break
                self._retry_find_opponent_after_no_match()
                started = self._match_start_event_name()
                if started:
                    return started
                continue

            if name in (MATCHMAKING_TIMEOUT_NAME, self.EVENT_NOT_FOUND):
                shot = debug_save_screenshot(suffix_name='live-arena-matchmaking-timeout')
                self.log(
                    f'Matchmaking timeout after {MATCHMAKING_TIMEOUT_S}s '
                    f'(attempt {attempt}/{MAX_MATCHMAKING_ATTEMPTS}); '
                    f'screenshot={shot}',
                    level='warning',
                )
                if self._is_match_started():
                    started = self._match_start_event_name()
                    if started:
                        return started
                if self._is_cant_find_opponent_visible() or self._is_find_opponent_visible():
                    if attempt >= MAX_MATCHMAKING_ATTEMPTS:
                        break
                    self._retry_find_opponent_after_no_match()
                    started = self._match_start_event_name()
                    if started:
                        return started
                    continue
                self.log('Search screen looks stuck; not clicking blindly', level='warning')
                self._abort_matchmaking()
                return None

            self.log(f'Unexpected matchmaking event: {name}')
            self._abort_matchmaking(f'live arena unexpected matchmaking event: {name}')
            return None

        self.log(
            f'No opponent after {MAX_MATCHMAKING_ATTEMPTS} attempts'
        )
        self._abort_matchmaking()
        return None

    def _resume_after_progress_chest(self):
        """After the 35-win chest, recover lobby/search instead of aborting leftover runs."""
        for attempt in range(4):
            if self._is_match_started():
                self.log('Progress chest claimed; pick phase visible — continuing remaining runs')
                return
            if self._is_find_opponent_visible():
                self.log('Progress chest claimed; clicking find opponent again')
                self._click_on_find_opponent(abort_on_fail=False, wait_limit=8)
                return
            if attempt < 3:
                tap_to_continue(wait_before=0.4, wait_after=0.4)

        self.log(
            'Progress chest claimed; find opponent not visible — '
            'assuming search in progress, not aborting remaining runs'
        )

    def _claim_free_refill_coins(self):
        from helpers.common import pixel_check_new
        
        # Координаты загружаются из coordinates/live_arena.json
        # Получаем mistake из JSON (по умолчанию 20)
        mistake = get_coordinate_mistake('claim_free_refill_coins', default_mistake=20)
        
        # Логируем используемые координаты для отладки
        x_check = CLAIM_FREE_REFILL_COINS[0]
        y_check = CLAIM_FREE_REFILL_COINS[1]
        expected_rgb = CLAIM_FREE_REFILL_COINS[2]
        self.log(f"Checking claim_free_refill_coins at coordinates ({x_check}, {y_check}) with RGB {expected_rgb}, mistake={mistake}")
        
        # Используем pixel_check_new с координатами из JSON
        # CLAIM_FREE_REFILL_COINS уже загружен из JSON через get_coordinate()
        if pixel_check_new(CLAIM_FREE_REFILL_COINS, mistake=mistake):
            x = CLAIM_FREE_REFILL_COINS[0] - 5
            y = CLAIM_FREE_REFILL_COINS[1] + 5
            self.log(f"Red dot found! Clicking at ({x}, {y})")
            click(x, y)
            sleep(2)
        else:
            self.log(f"Red dot NOT found at ({x_check}, {y_check})")

    def _click_on_find_opponent(self, abort_on_fail=True, wait_limit=65):
        # Отладочный вывод: проверяем цвет пикселя перед ожиданием
        x = find_opponent[0]
        y = find_opponent[1]
        expected_rgb = find_opponent[2]
        
        if is_debug_mode():
            try:
                actual_pixel = pyautogui.pixel(x, y)
                actual_rgb = [actual_pixel[0], actual_pixel[1], actual_pixel[2]]
                diff = [abs(actual_rgb[i] - expected_rgb[i]) for i in range(3)]
                max_diff = max(diff)
                
                from helpers.common import rgb_check
                matches = rgb_check(actual_rgb, expected_rgb, mistake=20)
                
                self.log(f"DEBUG find_opponent pixel check:")
                self.log(f"  Coordinates: [{x}, {y}]")
                self.log(f"  Expected RGB: {expected_rgb}")
                self.log(f"  Actual RGB:   {actual_rgb}")
                self.log(f"  Difference:   {diff} (max: {max_diff})")
                self.log(f"  Threshold:    20")
                self.log(f"  Matches:      {matches}")
            except Exception as e:
                self.log(f"ERROR checking pixel: {e}")
        
        if not await_click([find_opponent], msg="Click on find opponent", mistake=20, wait_limit=wait_limit)[0]:
            # Если не нашли, еще раз проверим цвет для отладки
            if is_debug_mode():
                self.log("Failed to find opponent button. Checking pixel color again...")
                try:
                    actual_pixel = pyautogui.pixel(x, y)
                    actual_rgb = [actual_pixel[0], actual_pixel[1], actual_pixel[2]]
                    diff = [abs(actual_rgb[i] - expected_rgb[i]) for i in range(3)]
                    max_diff = max(diff)
                    from helpers.common import rgb_check
                    matches = rgb_check(actual_rgb, expected_rgb, mistake=20)
                    
                    self.log(f"DEBUG after failure:")
                    self.log(f"  Actual RGB:   {actual_rgb}")
                    self.log(f"  Expected RGB: {expected_rgb}")
                    self.log(f"  Difference:   {diff} (max: {max_diff})")
                    self.log(f"  Matches:      {matches}")
                except Exception as e:
                    self.log(f"ERROR checking pixel after failure: {e}")

            if abort_on_fail:
                shot = debug_save_screenshot(suffix_name='live-arena-find-opponent-missing')
                self.log(
                    f'Find opponent button not found — aborting; screenshot={shot}',
                    level='error',
                )
                self.terminate()
            else:
                shot = debug_save_screenshot(suffix_name='live-arena-find-opponent-missing')
                self.log(
                    f'Find opponent button not found, not aborting remaining runs; '
                    f'screenshot={shot}',
                    level='warning',
                )
            return False

        return True

    def _is_available(self):
        if not find_indicator_active():
            self.terminate()

        return not self.terminated

    def _battles_this_run(self):
        start = getattr(self, '_run_results_start', 0)
        results = self.results if isinstance(self.results, list) else []
        count = 0
        for chunk in results[start:]:
            if isinstance(chunk, list):
                count += len(chunk)
            elif isinstance(chunk, bool):
                count += 1
        return count

    def _run_live_arena_battles(self):
        while self._is_available():
            self.break_loops = False

            self._claim_free_refill_coins()
            self._claim_chest()

            if self._refill():
                break

            self.attack()

    def _should_reenter_live_arena(self):
        if getattr(self, '_live_reentries', 0) >= MAX_LIVE_ARENA_REENTRIES:
            self.log(
                f'Live Arena re-entry limit reached ({MAX_LIVE_ARENA_REENTRIES}), continuing preset'
            )
            return False

        if getattr(self, '_paid_refill_exhausted', False):
            return False

        if getattr(self, 'abort_reason', None):
            return False

        battles = self._battles_this_run()
        if (
            self._battles_at_last_reentry is not None
            and battles == self._battles_at_last_reentry
        ):
            self.log('Live Arena re-entry made no progress, stopping recovery')
            return False

        leftover_tokens = battles % LIVE_ARENA_TOKEN_PACK != 0
        unused_paid_refill = self.refill > 0
        if leftover_tokens or unused_paid_refill:
            self.log(
                f'Live Arena battles this run: {battles}, paid refills left: {self.refill}'
            )
            return True
        return False

    def _reenter_live_arena(self):
        self._live_reentries = getattr(self, '_live_reentries', 0) + 1
        self._battles_at_last_reentry = self._battles_this_run()
        self.log(
            f'Leftover Live Arena tokens likely, returning to index and re-entering '
            f'({self._live_reentries}/{MAX_LIVE_ARENA_REENTRIES})'
        )
        self.terminated = False
        self.break_loops = False
        self.enter()
        if self.terminated:
            self.log('Live Arena re-entry aborted during enter')
            return False

        result = self.awaits([self.E_INDICATOR_ACTIVE])
        if result['name'] == self.EVENT_NOT_FOUND:
            self.log('Live Arena not active after re-entry, stopping recovery')
            return False

        self.obtain()
        return True

    def _save_result(self, result):
        from helpers.battle_stats import record_win, record_loss
        profile = getattr(self.app, 'current_player_name', None)
        if result:
            record_win('arena_live', profile_name=profile)
        else:
            record_loss('arena_live', profile_name=profile)
        self.results.append(bool(result))
        result_msg = 'WIN' if result else 'DEFEAT'
        self.log(result_msg)

    def _refill(self):
        self._click_on_find_opponent()
        if self.terminated:
            return True

        sleep(3)

        # Попап сундука прогресса (35 побед) перекрывает экран поиска — проверяем и забираем
        if self._check_progress_chest():
            self._resume_after_progress_chest()
            if self.terminated:
                return True
            if self._is_match_started():
                return False

        ruby_button = find_needle_refill_ruby()

        if ruby_button is not None:
            self.log('Free coins are NOT available')
            self._refresh_paid_refills()
            if self.refill > 0:
                location_key = self.NAME.lower().replace(' ', '_')
                profile = getattr(self.app, 'current_player_name', None)
                # Fail-closed: сначала фиксируем покупку в учёте, и только
                # затем кликаем. Если учёт недоступен, платный клик запрещён.
                try:
                    increment_purchase(location_key, self.refill_max_allowed, profile_name=profile)
                except RefillStateError as error:
                    self.log(f'Paid refill blocked: {error}')
                    self.abort_reason = f'paid refill accounting failed: {error}'
                    self.terminate()
                    return self.terminated
                self.refill -= 1
                # wait and click on refill_paid
                click(refill_paid[0], refill_paid[1], smart=True)
                self._click_on_find_opponent()
            else:
                self.log('No more refill')
                self._paid_refill_exhausted = True
                self.terminate()
        elif pixels_wait([refill_free], msg='Free refill sacs', mistake=get_coordinate_mistake('refill_free', default_mistake=10), timeout=1, wait_limit=2)[0]:
            self.log('Free coins are available')
            # wait and click on refill_free
            click(refill_free[0], refill_free[1], smart=True)
            self._click_on_find_opponent()

        return self.terminated

    def obtain(self):
        for i in range(len(rewards_pixels)):
            if self.terminated:
                break

            pixel = rewards_pixels[i]
            if pixel_check_new(pixel, mistake=30):
                x = pixel[0]
                y = pixel[1]
                click(x, y)
                sleep(.5)

    def handle_result(self, result):
        self._save_result(bool(result))
        if not result and self.idle_after_defeat:
            sleep(self.idle_after_defeat)

        tap_to_continue(wait_after=2)

    def find_leaders_indicis(self):
        res = []

        for i in range(len(self.leaders)):
            l = self.leaders[i]
            if l in self.current['team']:
                res.append(self.current['team'].index(l))
            if len(res) == 2:
                break

        res.reverse()

        return res

    def attack(self):
        self.current['counter'] += 1
        self.current['battle_time'] = get_time_for_log(s='_')
        self.current['sorted_pool'] = copy.deepcopy(self.pool)
        self.current['team'] = []
        self.current['slots_counter'] = 0

        self.log('Attack | Pool Length: ' + str(len(self.current['sorted_pool'])))

        def find_character(role=None):
            self.log(f"Current pool length: {len(self.current['sorted_pool'])}")

            # @TODO Not implemented yet
            self.current['next_char'] = None
            self.current['current_char'] = None

            if role is None and self.current['sorted_pool']:
                role = self.current['sorted_pool'][0].get('role')

            while (
                self.current['next_char'] is None
                and self.current['sorted_pool']
                and not self.break_loops
            ):
                # Opponent leaves the battle while picking the character
                if self.E_OPPONENT_LEFT['expect']():
                    self.E_OPPONENT_LEFT['callback']()
                    debug_save_screenshot(suffix_name='left while picking')
                    break

                char = pop_next_character(self.current['sorted_pool'], preferred_role=role)

                if char and not self.break_loops:
                    hero_filter.choose(title=char['name'], wait_after=.5)

                    _slot = LIVE_ARENA_HERO_SLOTS[self.current['slots_counter']]
                    _region = [_slot[0], _slot[1], EMPTY_SLOT_WIDTH, EMPTY_SLOT_HEIGHT]
                    # show_pyautogui_image(pyautogui.screenshot(region=_region))
                    _position_empty = find_hero_slot_empty(region=_region)
                    if _position_empty is None and not self.break_loops:
                        self.current['next_char'] = char

                    # if not pixel_check_new(LIVE_ARENA_HERO_SLOTS[self.current['slots_counter']], mistake=10):
                    #     next_char = char

            if (
                self.current['next_char'] is None
                and not self.current['sorted_pool']
                and not self.break_loops
            ):
                self.log('No available hero candidates remain')

            return self.current['next_char']

        def await_stage_1():
            return self.awaits(events=[self.E_STAGE_1, self.E_OPPONENT_LEFT])

        def await_pick():
            return self.awaits(events=[self.E_PICKING_PROCESS, self.E_OPPONENT_LEFT])

        def await_stage_2():
            return self.awaits(events=[self.E_STAGE_2, self.E_OPPONENT_LEFT])

        def await_stage_3():
            return self.awaits(events=[self.E_STAGE_3, self.E_OPPONENT_LEFT])

        def await_choosing_leader():
            return self.awaits(events=[self.E_CHOOSING_LEADER, self.E_OPPONENT_LEFT])

        start_events_name = self._wait_for_match_start()
        if start_events_name is None:
            return

        pattern = ARCHIVE_PATTERN_FIRST[:]
        if self.E_PICK_SECOND['name'] == start_events_name:
            pattern.reverse()

        stage_1_events = await_stage_1()
        if self.E_STAGE_1['name'] == stage_1_events['name']:
            sleep(.5)
            for i in range(len(pattern)):
                if self.break_loops:
                    break

                pick_process_events = await_pick()
                if self.E_PICKING_PROCESS['name'] == pick_process_events['name']:
                    sleep(.2)

                    # picking heroes logic
                    for j in range(pattern[i]):
                        if self.break_loops:
                            break

                        unit = find_character()
                        if unit is not None:
                            self.current['team'].append(unit['name'])
                            sleep(.1)
                            self.log(f"Picked: {unit['name']}")
                            self.current['slots_counter'] += 1

                    self._confirm()

        stage_2_events = await_stage_2()
        if self.E_STAGE_2['name'] == stage_2_events['name']:
            sleep(.5)
            # Выбор слота для бана: ban_priority 1-5 (1=первый слот) или случайный
            if self.ban_priority is not None and 1 <= self.ban_priority <= len(enemy_slots):
                slot = enemy_slots[self.ban_priority - 1]
            else:
                slot = random.choice(enemy_slots)
            x = slot[0]
            y = slot[1]
            click(x, y)
            sleep(.5)

            self._confirm()

        stage_3_events = await_stage_3()
        if self.E_STAGE_3['name'] == stage_3_events['name']:
            sleep(.5)

            choosing_leader_events = await_choosing_leader()
            if self.E_CHOOSING_LEADER['name'] == choosing_leader_events['name']:
                leaders_indicis = self.find_leaders_indicis()

                for i in range(len(leaders_indicis)):
                    leader_index = leaders_indicis[i]
                    slot = LIVE_ARENA_HERO_SLOTS[leader_index]
                    x = slot[0]
                    y = slot[1]
                    click(x, y)
                    sleep(.5)

                self._confirm()

        # Test
        self.awaits(events=[self.E_BATTLE_START_LIVE, self.E_VICTORY, self.E_DEFEAT])

    def check_availability(self):
        # @TODO Finish
        # res = {
        #     'is_active': False,
        #     'open_hour': None
        # }
        # live_arena_open_hours = [[6, 8], [14, 16], [20, 22]]
        utc_timestamp = datetime.utcnow().timestamp()
        utc_datetime = datetime.fromtimestamp(utc_timestamp)
        parsed_time = time_mgr.timestamp_to_datetime(utc_datetime)

        year = parsed_time['year']
        month = parsed_time['month']
        day = parsed_time['day']
        # @TODO
        hour = parsed_time['hour']
        hour = 14
        pause.until(datetime(year, month, day, hour, 1, 0, tzinfo=timezone.utc))
