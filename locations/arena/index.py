import pyautogui

from helpers.common import (
    debug_save_screenshot,
    is_debug_mode,
    prepare_event,
    sleep,
)
from helpers.popups import close_popup_recursive
from helpers.game_actions import (
    calculate_win_rate,
    click_on_progress_info,
    enable_start_on_auto,
    waiting_battle_end_regular,
)
from helpers.logging_utils import log
from helpers.mouse import await_click, click, swipe, swipe_new, tap_to_continue
from helpers.ocr import read_bank_arena_classic, read_bank_arena_tag
from helpers.vision import (
    find_needle_arena_reward,
    find_needle_refill_ruby,
    pixel_check_new,
    pixels_wait,
)
from helpers.coordinates import (
    get_coordinate,
    get_mistake,
    get_score_config,
    load_coordinates,
    parse_button_locations,
    parse_point,
    require_coordinate_files,
)
from helpers.refill_state import get_purchased_count, get_remaining_refills
from classes.Location import Location, RunOutcome
from locations.arena.refill_service import RefillKind, RefillOutcome, RefillService
from locations.arena.screen_state import (
    ARENA_LIST_SHELL,
    REFRESH_COOLDOWN_SIGNATURE,
    ScreenState,
    classify_arena_screen,
)

# ============================================================================
# КООРДИНАТЫ ХРАНЯТСЯ В:
#   coordinates/arena_shared.json   — общие для ArenaFactory (Tag + Classic)
#   coordinates/arena_tag.json      — только Arena Tag
#   coordinates/arena_classic.json  — только Arena Classic
# Для изменения координат отредактируйте JSON и перезапустите приложение
# ============================================================================

# Загружаем координаты при импорте модуля
require_coordinate_files('arena_shared.json', 'arena_tag.json', 'arena_classic.json')
_shared = load_coordinates('arena_shared.json', required=True)
_tag_data = load_coordinates('arena_tag.json', required=True)
_classic_data = load_coordinates('arena_classic.json', required=True)

# Общие координаты ArenaFactory (из arena_shared.json)
button_refresh = get_coordinate(_shared, 'button_refresh', source='coordinates/arena_shared.json')
button_refresh_mistake = get_mistake(_shared, 'button_refresh', 45)
refill_free = get_coordinate(_shared, 'refill_free', source='coordinates/arena_shared.json')
refill_paid = get_coordinate(_shared, 'refill_paid', source='coordinates/arena_shared.json')
refill_ruby = get_coordinate(_shared, 'refill_ruby', source='coordinates/arena_shared.json')
defeat = get_coordinate(_shared, 'defeat', source='coordinates/arena_shared.json')
defeat_mistake = get_mistake(_shared, 'defeat', 35)
tab_battle = get_coordinate(_shared, 'tab_battle', source='coordinates/arena_shared.json')
battle_active_coord = get_coordinate(_shared, 'battle_active', source='coordinates/arena_shared.json') if 'battle_active' in _shared else None
start_battle_coord = get_coordinate(_shared, 'start_battle', source='coordinates/arena_shared.json')
refill_click_coord = get_coordinate(_shared, 'refill_click', source='coordinates/arena_shared.json')
claim_chest_coord = get_coordinate(_shared, 'claim_chest', source='coordinates/arena_shared.json')
result_tap_to_continue = get_coordinate(
    _shared,
    'result_tap_to_continue',
    source='coordinates/arena_shared.json',
)
result_tap_to_continue_mistake = get_mistake(_shared, 'result_tap_to_continue', 45)
swipe_attack_coord = _shared['swipe_attack']
swipe_refresh_coord = _shared['swipe_refresh']
swipe_reward_coord = _shared['swipe_reward']

RGB_RED_DOT = _shared['red_dot_rgb']
ATTACK_BUTTON_RGB = _shared['attack_button_rgb']
REFILL_POPUP_POINTS, REFILL_POPUP_MISTAKE, REFILL_POPUP_MIN_SCORE = get_score_config(
    _shared,
    'refill_popup',
    default_mistake=20,
    default_min_score=4
)
REFILL_RUBY_POINTS, REFILL_RUBY_MISTAKE, REFILL_RUBY_MIN_SCORE = get_score_config(
    _shared,
    'refill_ruby_points',
    default_mistake=20,
    default_min_score=2
)
REFILL_POPUP_TAG_POINTS, REFILL_POPUP_TAG_MISTAKE, REFILL_POPUP_TAG_MIN_SCORE = get_score_config(
    _shared,
    'refill_popup_tag',
    default_mistake=20,
    default_min_score=3
)
REFILL_RUBY_TAG_POINTS, REFILL_RUBY_TAG_MISTAKE, REFILL_RUBY_TAG_MIN_SCORE = get_score_config(
    _shared,
    'refill_ruby_points_tag',
    default_mistake=20,
    default_min_score=2
)
TEAM_SETUP_POINTS, TEAM_SETUP_MISTAKE, TEAM_SETUP_MIN_SCORE = get_score_config(
    _shared,
    'team_setup',
    default_mistake=20,
    default_min_score=4
)
DEFEAT_POINTS, DEFEAT_MISTAKE, DEFEAT_MIN_SCORE = get_score_config(
    _shared,
    'defeat_points',
    default_mistake=35,
    default_min_score=3
)
VICTORY_POINTS, VICTORY_MISTAKE, VICTORY_MIN_SCORE = get_score_config(
    _shared,
    'victory_points',
    default_mistake=35,
    default_min_score=2
)
PAID_REFILL_LIMIT = 0
OUTPUT_ITEMS_AMOUNT = 10

def is_team_setup_visible():
    if not TEAM_SETUP_POINTS:
        return False
    matched = 0
    for index, point in enumerate(TEAM_SETUP_POINTS):
        if pixel_check_new(point, mistake=TEAM_SETUP_MISTAKE, label=f"team_setup_{index + 1}"):
            matched += 1
    if is_debug_mode():
        log(f"Team Setup popup score: {matched}/{len(TEAM_SETUP_POINTS)} (need {TEAM_SETUP_MIN_SCORE})")
    return matched >= TEAM_SETUP_MIN_SCORE

def is_defeat_screen_visible():
    if DEFEAT_POINTS:
        matched = 0
        for index, point in enumerate(DEFEAT_POINTS):
            if pixel_check_new(point, mistake=DEFEAT_MISTAKE, label=f"defeat_{index + 1}"):
                matched += 1
        if is_debug_mode():
            log(f"Defeat screen score: {matched}/{len(DEFEAT_POINTS)} (need {DEFEAT_MIN_SCORE})")
        return matched >= DEFEAT_MIN_SCORE
    return pixel_check_new(defeat, defeat_mistake, label="det_defeat")

def is_victory_screen_visible():
    if VICTORY_POINTS:
        matched = 0
        for index, point in enumerate(VICTORY_POINTS):
            if pixel_check_new(point, mistake=VICTORY_MISTAKE, label=f"victory_{index + 1}"):
                matched += 1
        if is_debug_mode():
            log(f"Victory screen score: {matched}/{len(VICTORY_POINTS)} (need {VICTORY_MIN_SCORE})")
        return matched >= VICTORY_MIN_SCORE
    return False

def get_results_screen_signal():
    if is_defeat_screen_visible():
        return 'DEFEAT'

    if is_victory_screen_visible():
        return 'VICTORY'

    # The result header can still be animating when BattleEnd is detected.
    # The bottom prompt is an independent fallback captured from the stable
    # Classic Arena victory screen.
    if pixel_check_new(
        result_tap_to_continue,
        mistake=result_tap_to_continue_mistake,
        label="result_tap_to_continue",
    ):
        return 'TAP_TO_CONTINUE'

    return None


def is_results_screen_visible():
    return get_results_screen_signal() is not None

def is_refill_popup_visible(is_tag=False):
    points = REFILL_POPUP_TAG_POINTS if is_tag else REFILL_POPUP_POINTS
    mistake = REFILL_POPUP_TAG_MISTAKE if is_tag else REFILL_POPUP_MISTAKE
    min_score = REFILL_POPUP_TAG_MIN_SCORE if is_tag else REFILL_POPUP_MIN_SCORE

    if points:
        matched = 0
        for index, point in enumerate(points):
            if pixel_check_new(point, mistake=mistake, label=f"refill_popup_{'tag_' if is_tag else ''}{index + 1}"):
                matched += 1
        if is_debug_mode():
            log(f"Refill popup score: {matched}/{len(points)} (need {min_score})")
        if matched >= min_score:
            return True

    _rf_mistake = get_mistake(_shared, 'refill_free', 15)
    _rp_mistake = get_mistake(_shared, 'refill_paid', 15)
    return (
        pixel_check_new(refill_free, mistake=_rf_mistake, label="refill_free_visible")
        or pixel_check_new(refill_paid, mistake=_rp_mistake, label="refill_paid_visible")
    )

# Логика обхода списка противников (не координаты — остаётся в коде)
CLASSIC_ITEM_LOCATIONS = [
    {'swipes': 0, 'position': 1},
    {'swipes': 1, 'position': 1},
    {'swipes': 2, 'position': 1},
    {'swipes': 3, 'position': 1},
    {'swipes': 4, 'position': 1},
    {'swipes': 5, 'position': 1},
    {'swipes': 6, 'position': 1},
    {'swipes': 6, 'position': 2},
    {'swipes': 6, 'position': 3},
    {'swipes': 6, 'position': 4},
]
TAG_ITEM_LOCATIONS = [
    {'swipes': 0, 'position': 1},
    {'swipes': 1, 'position': 1},
    {'swipes': 2, 'position': 1},
    {'swipes': 3, 'position': 1},
    {'swipes': 4, 'position': 1},
    {'swipes': 5, 'position': 1},
    {'swipes': 6, 'position': 1},
    {'swipes': 6, 'position': 2},
    {'swipes': 6, 'position': 3},
    {'swipes': 6, 'position': 4},
]


def callback_refresh(*args):
    click(button_refresh[0], button_refresh[1])
    sleep(3)
    _sr = swipe_refresh_coord
    for index in range(2):
        swipe_new(_sr['direction'], _sr['x'], _sr['y'], _sr['distance'], speed=.2, instant_move=True)
    sleep(2)


# Таймаут ожидания кнопки Refresh (сек). Не блокируем весь preset на 15 минут,
# если экран Arena изменился или пиксель кнопки временно не распознаётся.
ARENA_REFRESH_WAIT_LIMIT = 60
# Длинное ожидание допустимо ТОЛЬКО после положительного распознавания
# зелёного индикатора "Free refresh in ..." (REFRESH_COOLDOWN). Игровой
# cooldown может достигать 15 минут.
ARENA_REFRESH_COOLDOWN_WAIT_LIMIT = 960
# Таймаут ожидания TAP TO CONTINUE / RETURN TO ARENA в Arena Tag (сек)
ARENA_TAG_AWAIT_LIMIT = 180


class ArenaFactory(Location):
    E_BUTTON_REFRESH = {
        "name": "Refresh button",
        "expect": lambda: pixel_check_new(button_refresh, mistake=button_refresh_mistake),
        "callback": callback_refresh,
        "interval": 5,
    }
    E_REFRESH_TIMEOUT = {
        "name": "RefreshTimeout",
        "delay": ARENA_REFRESH_WAIT_LIMIT,
        "interval": 1,
        "expect": lambda: True,
        "blocking": True,
    }
    E_REFRESH_COOLDOWN_TIMEOUT = {
        "name": "RefreshCooldownTimeout",
        "delay": ARENA_REFRESH_COOLDOWN_WAIT_LIMIT,
        "interval": 1,
        "expect": lambda: True,
        "blocking": True,
    }
    E_TAG_AWAIT_TIMEOUT = {
        "name": "TagAwaitTimeout",
        "delay": ARENA_TAG_AWAIT_LIMIT,
        "interval": 1,
        "expect": lambda: True,
        "blocking": True,
    }

    name = None
    item_height = None
    button_locations = None
    item_locations = None
    x_axis_info = None
    read_coins_predicate = None

    max_swipe = None
    refill = None
    results = None

    def __init__(
            self,
            app,
            name,
            x_axis_info,
            read_coins_predicate,
            item_height,
            button_locations,
            item_locations,
            refill_coordinates,
            tiers_coordinates,
            props=None
    ):
        Location.__init__(self, name=name, app=app, report_predicate=self._report)

        if self.results is None:
            self.results = []

        self.name = name
        self.x_axis_info = x_axis_info
        self.read_coins_predicate = read_coins_predicate
        self.item_height = item_height
        self.button_locations = button_locations
        self.item_locations = item_locations
        self.refill_coordinates = refill_coordinates
        self.tiers_coordinates = tiers_coordinates

        self.refill = PAID_REFILL_LIMIT
        self.refill_max_allowed = PAID_REFILL_LIMIT  # Сохраняем максимальное значение из конфига
        self.initial_refresh = False
        self.battle_time_limit = True
        self.max_swipe = 0
        self.classic_defeat_offset = 0
        self.classic_last_pass_battles = 0
        self.classic_last_pass_reached_end = False
        self.classic_last_pass_no_attackable = False

        self._apply_props(props=props)

        self.E_BATTLE_END = prepare_event(self.E_BATTLE_END, {
            "expect": lambda: is_defeat_screen_visible() or is_victory_screen_visible()
        })

        for i in range(len(self.item_locations)):
            item = self.item_locations[i]
            swipes = item['swipes']
            if swipes > self.max_swipe:
                self.max_swipe = swipes

        self.event_dispatcher.subscribe('enter', self._enter)
        self.event_dispatcher.subscribe('run', self._run)

    def _report(self):
        from helpers.battle_stats import load_stats
        res_list = []
        profile = getattr(self.app, 'current_player_name', None)
        location_key = self.NAME.lower().replace(' ', '_')
        stats = load_stats(location_key, profile_name=profile)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        t = wins + losses
        if t:
            str_battles = f"Battles: {str(t)}"
            str_wr = f"(WR: {calculate_win_rate(wins, losses)})"
            res_list.append(f"{str_battles} {str_wr}")

        if self.refill_max_allowed > 0:
            purchased = get_purchased_count(location_key, profile_name=profile)
            res_list.append(f"Paid refills today (UTC): {purchased}/{self.refill_max_allowed}")

        return res_list

    def _persist_results(self, results_local):
        from helpers.battle_stats import record_win, record_loss
        profile = getattr(self.app, 'current_player_name', None)
        location_key = self.NAME.lower().replace(' ', '_')
        for r in results_local:
            if r:
                record_win(location_key, profile_name=profile)
            else:
                record_loss(location_key, profile_name=profile)

    def _enter(self):
        click_on_progress_info()
        click(600, self.x_axis_info, smart=True)
        sleep(1)

        self.obtain()

    def _run(self, props=None):
        # for i in range(2):
        #     sleep(1)
        # return
        if props is not None:
            self._apply_props(props=props)

        if self.initial_refresh:
            # Best-effort policy (план, Этап 3): если на текущем списке ещё
            # есть доступные соперники, недоступный free refresh не должен
            # блокировать атаку.
            if self._has_attackable_targets():
                self.log('Initial refresh skipped: current list still has available opponents')
            else:
                self._refresh_arena()
                sleep(1)

        is_tag = (self.name == 'Arena Tag')

        if is_tag:
            # Arena Tag: attack() проходит все 10 позиций за один вызов,
            # после — всегда refresh (повторно атаковать тех же бессмысленно)
            while self.terminated is False:
                self.attack()
                if self.terminated is False:
                    self._refresh_arena()
        else:
            # Arena Classic: старая логика с отслеживанием прогресса.
            # Смещение поражений из прошлого запуска устарело: список мог
            # смениться, а форсированный refresh без жетонов завершает ран
            # впустую даже при доступных соперниках (лог 02:51:14).
            if self.classic_defeat_offset:
                self.log(f'New run: resetting stale defeat offset (was {self.classic_defeat_offset})')
                self.classic_defeat_offset = 0

            last_results_count = 0
            no_progress_iterations = 0
            MAX_NO_PROGRESS_ITERATIONS = 3

            while self.terminated is False:
                if self.classic_defeat_offset >= len(self.item_locations):
                    self.log(f'All positions exhausted (offset={self.classic_defeat_offset}), forcing refresh')
                    self._refresh_arena()
                    no_progress_iterations = 0
                    last_results_count = 0
                    continue

                self.attack()

                last_results = self._get_last_results()
                current_results_count = len(last_results)

                if current_results_count == last_results_count:
                    no_progress_iterations += 1
                else:
                    no_progress_iterations = 0
                    last_results_count = current_results_count

                if self.terminated is False:
                    should_refresh = False
                    if self.classic_last_pass_reached_end:
                        self.log('Completed opponent pass through end of list, refreshing')
                        should_refresh = True
                    elif self.classic_last_pass_no_attackable:
                        self.log('No attackable opponents found in pass, refreshing list')
                        should_refresh = True
                    elif len(last_results) == OUTPUT_ITEMS_AMOUNT:
                        should_refresh = True
                    elif len(last_results) == 0:
                        should_refresh = True
                    elif no_progress_iterations >= MAX_NO_PROGRESS_ITERATIONS:
                        self.log(f'No progress for {no_progress_iterations} iterations, refreshing list')
                        should_refresh = True

                    if should_refresh:
                        self._refresh_arena()
                        no_progress_iterations = 0
                        last_results_count = 0

    def _apply_props(self, props=None):
        if props is not None:
            if 'refill' in props:
                refill_from_config = int(props['refill'])
                self.refill_max_allowed = refill_from_config
                location_key = self.NAME.lower().replace(' ', '_')
                profile = getattr(self.app, 'current_player_name', None)
                self.refill = get_remaining_refills(location_key, refill_from_config, profile_name=profile)
                if self.refill < refill_from_config:
                    self.log(f"Refill state loaded (profile={profile or 'default'}): {refill_from_config - self.refill} already purchased today (UTC), {self.refill} remaining")
            if 'initial_refresh' in props:
                self.initial_refresh = bool(props['initial_refresh'])
            if 'battle_time_limit' in props:
                self.battle_time_limit = int(props['battle_time_limit'])

    def ensure_tokens(self) -> bool:
        _coins, _region = self.read_coins_predicate()
        if _coins == 0:
            _x = _region[0] - 5
            _y = _region[1] + 5
            click(_x, _y)
            refilled = self._refill()

            if self.terminated:
                return False

            if refilled:
                sleep(2)
                click(_x, _y)
                sleep(1)
                return True
            return False
        return True

    def _has_attackable_targets(self):
        for position, pos in self.button_locations.items():
            if pixel_check_new([pos[0], pos[1], ATTACK_BUTTON_RGB], mistake=10, label=f"attackable_{position}"):
                return True
        return False

    def _observe_arena_screen(self):
        return classify_arena_screen(pyautogui.pixel, self.button_locations)

    def _is_arena_list_exhausted(self):
        observation = self._observe_arena_screen()
        if observation.state == ScreenState.ARENA_LIST_EXHAUSTED:
            return True
        return self._is_arena_list_shell_visible() and not self._has_attackable_targets()

    def _refresh_cooldown_detected(self, observation=None):
        if observation is None:
            observation = self._observe_arena_screen()
        return (
            'REFRESH_COOLDOWN' in observation.signals
            or self._is_refresh_cooldown_visible()
        )

    def _wait_for_free_refresh_available(self):
        self.log(
            f'Waiting for free refresh up to {ARENA_REFRESH_COOLDOWN_WAIT_LIMIT}s'
        )
        response = self.awaits([
            self.E_BUTTON_REFRESH,
            self.E_TERMINATE,
            self.E_REFRESH_COOLDOWN_TIMEOUT,
        ])
        if response and response.get('name') == 'RefreshCooldownTimeout':
            self.log(
                f'Free refresh did not become available within '
                f'{ARENA_REFRESH_COOLDOWN_WAIT_LIMIT}s, deferring'
            )
            self.run_outcome = RunOutcome.DEFERRED_REFRESH_COOLDOWN
            self.terminated = True
            return False
        if self.terminated:
            return False
        return True

    def _is_arena_list_shell_visible(self):
        """Устойчивая оболочка страницы арены (вкладка Battle + левая панель).
        Присутствует и на исчерпанном списке, когда нет ни Attack, ни синей
        кнопки Refresh (кейс 15-54-44)."""
        matched = 0
        for index, point in enumerate(ARENA_LIST_SHELL['points']):
            if pixel_check_new(point, mistake=ARENA_LIST_SHELL['mistake'], label=f"list_shell_{index + 1}"):
                matched += 1
        if is_debug_mode():
            log(f"Arena list shell score: {matched}/{len(ARENA_LIST_SHELL['points'])} (need {ARENA_LIST_SHELL['min_score']})")
        return matched >= ARENA_LIST_SHELL['min_score']

    def _is_refresh_cooldown_visible(self):
        """Зелёный индикатор 'Free refresh in Xm Ys' рядом с кнопкой Refresh."""
        matched = 0
        for index, point in enumerate(REFRESH_COOLDOWN_SIGNATURE['points']):
            if pixel_check_new(point, mistake=REFRESH_COOLDOWN_SIGNATURE['mistake'], label=f"refresh_cooldown_{index + 1}"):
                matched += 1
        if is_debug_mode():
            log(f"Refresh cooldown score: {matched}/{len(REFRESH_COOLDOWN_SIGNATURE['points'])} (need {REFRESH_COOLDOWN_SIGNATURE['min_score']})")
        return matched >= REFRESH_COOLDOWN_SIGNATURE['min_score']

    def refresh_opponent_list(self):
        response = self.awaits([self.E_BUTTON_REFRESH, self.E_TERMINATE, self.E_REFRESH_TIMEOUT])
        if response and response.get('name') == 'RefreshTimeout':
            observation = self._observe_arena_screen()
            if self._is_arena_list_exhausted():
                cooldown_hint = (
                    'cooldown confirmed'
                    if self._refresh_cooldown_detected(observation)
                    else 'no free refresh button'
                )
                self.log(
                    f'Exhausted arena list detected ({observation.state.name}, '
                    f'{cooldown_hint}), waiting for free refresh'
                )
                if not self._wait_for_free_refresh_available():
                    return False
            elif self._is_arena_list_shell_visible() and self._refresh_cooldown_detected(observation):
                self.log(
                    f'Refresh cooldown confirmed, waiting for free refresh '
                    f'up to {ARENA_REFRESH_COOLDOWN_WAIT_LIMIT}s'
                )
                if not self._wait_for_free_refresh_available():
                    return False
            else:
                self.log(
                    f'Refresh button wait timeout ({ARENA_REFRESH_WAIT_LIMIT}s) '
                    f'without confirmed cooldown, stopping'
                )
                debug_save_screenshot(suffix_name='arena-refresh-timeout-unconfirmed')
                self.abort_reason = 'refresh button not found and cooldown not confirmed'
                self.run_outcome = RunOutcome.ABORTED_UNKNOWN_SCREEN
                self.terminated = True
                return False

        if self.terminated:
            return False

        if self.classic_defeat_offset > 0:
            self.log(f'Refresh: resetting defeat offset (was {self.classic_defeat_offset})')
            self.classic_defeat_offset = 0

        if self.name == 'Arena Tag':
            _sr = swipe_refresh_coord
            self.log('Scrolling up after refresh to return to list start')
            for index in range(2):
                swipe_new(_sr['direction'], _sr['x'], _sr['y'], _sr['distance'], speed=.2, instant_move=True)
            sleep(1)
        return True

    def _refresh_arena(self):
        """Legacy method for backward compatibility. Use ensure_tokens and refresh_opponent_list instead."""
        if not self.ensure_tokens():
            return
        self.refresh_opponent_list()

    def _is_ruby_refill_visible(self):
        is_tag = self.name == 'Arena Tag'
        points = REFILL_RUBY_TAG_POINTS if is_tag else REFILL_RUBY_POINTS
        mistake = REFILL_RUBY_TAG_MISTAKE if is_tag else REFILL_RUBY_MISTAKE
        min_score = REFILL_RUBY_TAG_MIN_SCORE if is_tag else REFILL_RUBY_MIN_SCORE

        if points:
            matched = 0
            for index, point in enumerate(points):
                if pixel_check_new(point, mistake=mistake, label=f"refill_ruby_points_{'tag_' if is_tag else ''}{index + 1}"):
                    matched += 1
            if matched >= min_score:
                return True

        # Фоллбэк на старую логику, если точки не сработали
        ruby_mistake = get_mistake(_shared, 'refill_ruby', 40)
        if pixel_check_new(refill_ruby, mistake=ruby_mistake, label="refill_ruby_visible"):
            return True
        return find_needle_refill_ruby() is not None

    def _is_free_refill_button_visible(self):
        _rf_mistake = get_mistake(_shared, 'refill_free', 15)
        return pixel_check_new(refill_free, mistake=_rf_mistake, label="refill_free_visible")

    def _classify_refill_popup(self):
        """Положительная тройная классификация popup (план, Этап 4):
        рубин подтверждён -> PAID; жёлтая кнопка без рубина -> FREE;
        ни один вариант не подтверждён -> UNKNOWN (кликать запрещено)."""
        if self._is_ruby_refill_visible():
            return RefillKind.PAID
        if self._is_free_refill_button_visible():
            return RefillKind.FREE
        return RefillKind.UNKNOWN

    def _read_token_balance(self):
        tokens, _region = self.read_coins_predicate()
        return tokens

    def _refill(self):
        is_tag = self.name == 'Arena Tag'

        # ВАЖНО: Ждем анимацию появления попапа до 3 секунд
        waited_popup = 0
        while not is_refill_popup_visible(is_tag) and waited_popup < 3:
            sleep(0.5)
            waited_popup += 0.5

        if not is_refill_popup_visible(is_tag):
            return False

        sleep(1)

        location_key = self.NAME.lower().replace(' ', '_')
        profile = getattr(self.app, 'current_player_name', None)

        service = RefillService(
            location_key=location_key,
            profile_name=profile,
            max_allowed=self.refill_max_allowed,
            classify_popup=self._classify_refill_popup,
            is_popup_visible=lambda: is_refill_popup_visible(is_tag),
            click_refill=lambda: click(refill_click_coord[0], refill_click_coord[1]),
            read_tokens=self._read_token_balance,
            wait=sleep,
            logger=self.log,
        )
        result = service.execute()

        if result.outcome is RefillOutcome.SUCCESS:
            if result.kind is RefillKind.PAID:
                self.refill = max(0, self.refill - 1)
                self.log(
                    f'Paid refill confirmed (tokens {result.tokens_before}->{result.tokens_after}), '
                    f'{self.refill} paid refills remaining'
                )
            else:
                self.log('Free refill confirmed')
            sleep(0.5)
            return True

        if result.outcome is RefillOutcome.LIMIT_REACHED:
            self.log('No more refill')
            self.run_outcome = RunOutcome.COMPLETED_POLICY_LIMIT
            self.terminated = True
            return False

        if result.outcome is RefillOutcome.UNKNOWN_POPUP:
            debug_save_screenshot(suffix_name='refill-popup-unknown')
            self.abort_reason = 'refill popup could not be classified as FREE or PAID'
            self.run_outcome = RunOutcome.ABORTED_UNKNOWN_SCREEN
            self.terminated = True
            return False

        if result.outcome is RefillOutcome.FAILED:
            self.abort_reason = f'refill failed: {result.reason}'
            self.run_outcome = RunOutcome.REFILL_FAILED
            self.terminated = True
            return False

        # UNCERTAIN / BLOCKED_PENDING / STATE_ERROR: повторный автоматический
        # платный клик запрещён до reconciliation (план, Этап 4, шаг 10).
        self.abort_reason = f'refill outcome {result.outcome.name}: {result.reason}'
        self.run_outcome = RunOutcome.REFILL_UNCERTAIN
        self.terminated = True
        return False

    def _get_last_results(self):
        length = len(self.results)
        if length:
            return self.results[len(self.results) - 1]
        else:
            return self.results

    def determine_current_screen(self, is_tag, x, y):
        if is_results_screen_visible():
            return 'RESULTS_SCREEN'

        if is_refill_popup_visible(is_tag):
            return 'REFILL_POPUP'
            
        if is_team_setup_visible():
            return 'TEAM_SETUP'
            
        if pixel_check_new([x, y, ATTACK_BUTTON_RGB], label="det_list") or self._is_arena_list_visible():
            return 'ARENA_LIST'
            
        if is_tag:
            _ttc_mistake = get_mistake(_tag_data, 'tap_to_continue', 35)
            if pixel_check_new(self.tap_to_continue_coord, mistake=_ttc_mistake, label="det_ttc"):
                return 'RESULTS_SCREEN'
            _rta_mistake = get_mistake(_tag_data, 'return_to_arena', 30)
            if pixel_check_new(self.return_to_arena_coord, mistake=_rta_mistake, label="det_rta"):
                return 'RETURN_TO_ARENA'

        return 'UNKNOWN'

    def _is_arena_list_visible(self, mistake=10):
        self._last_arena_list_signal = None
        for position, pos in self.button_locations.items():
            if pixel_check_new([pos[0], pos[1], ATTACK_BUTTON_RGB], mistake=mistake, label=f"list_button_{position}"):
                self._last_arena_list_signal = f'ATTACK_BUTTON_{position}'
                return True

        # Основной признак списка — устойчивая оболочка страницы (вкладка
        # Battle + левая панель). Она присутствует и на исчерпанном списке
        # с cooldown, когда нет ни Attack, ни синей кнопки Refresh, поэтому
        # такой экран больше не превращается в UNKNOWN (план, Этап 2).
        if self._is_arena_list_shell_visible():
            self._last_arena_list_signal = 'LIST_SHELL'
            return True

        # The refresh-button colour also occurs in the blue result panels.
        # A loose tolerance therefore produces false ARENA_LIST detections
        # immediately after BattleEnd. Keep this fallback for a fully used
        # opponent list. A tolerance of 45 accepts the real Refresh button
        # from the supplied Arena-list screenshot, while the victory panels
        # differ by more than that.
        if pixel_check_new(
            button_refresh,
            mistake=button_refresh_mistake,
            label="list_refresh_button",
        ):
            self._last_arena_list_signal = 'REFRESH_BUTTON'
            return True
        return False

    def _wait_for_classic_post_result_state(self, timeout=10, interval=0.5):
        """Wait for a visible result screen or positive Arena list signal."""
        checks = max(1, int(timeout / interval))
        for check in range(checks):
            # Result detection has priority. Some blue pixels on the victory
            # panels resemble the Arena list and must not suppress the next
            # continue tap.
            result_signal = get_results_screen_signal()
            if result_signal:
                self.log(f'Post-result state: RESULTS_SCREEN ({result_signal})')
                return 'RESULTS_SCREEN'

            if self._is_arena_list_visible():
                list_signal = getattr(self, '_last_arena_list_signal', 'UNKNOWN_SIGNAL')
                self.log(f'Post-result state: ARENA_LIST ({list_signal})')
                return 'ARENA_LIST'

            sleep(interval)

        # Absence of result pixels is not proof that the result was closed.
        # During medal/progress animations neither result nor list can be
        # recognized for several seconds.
        self.log(f'Post-result state: UNKNOWN after {timeout}s')
        return 'UNKNOWN'

    def _close_classic_result_screen(self, max_attempts=8, settle_timeout=15):
        """
        Close both Classic Arena result stages and require positive
        confirmation of the Arena list:

        1. Reward / TAP TO CONTINUE.
        2. Battle summary / RETURN TO ARENA.

        BattleEnd itself authorizes a safe tap on the bottom result area. This
        is important while the Victory header is still animating and its
        detector points have not settled yet.
        """
        for attempt in range(1, max_attempts + 1):
            # The method is entered only after BattleEnd. Always perform at
            # least one safe continue tap: a false list-colour match used to
            # return here without touching the victory screen.
            if attempt > 1 and self._is_arena_list_visible():
                list_signal = getattr(self, '_last_arena_list_signal', 'UNKNOWN_SIGNAL')
                self.log(f'Back on arena list ({list_signal})')
                return True

            result_signal = get_results_screen_signal() or 'BATTLE_END/UNSTABLE'
            self.log(f'Result close attempt {attempt}/{max_attempts}: {result_signal}')

            # One tap per attempt prevents a second click from landing on the
            # Arena list if the transition completes quickly.
            tap_to_continue(times=1, wait_before=1, wait_after=2)
            self.log(f'Continue tap sent (attempt {attempt}/{max_attempts})')

            state = self._wait_for_classic_post_result_state(timeout=settle_timeout)
            if state == 'ARENA_LIST':
                self.log('Back on arena list')
                return True
            if state == 'RESULTS_SCREEN':
                continue
            self.log('Neither result screen nor arena list is confirmed; retrying continue tap')

        # Primary attempts can end while a reward/summary screen is still open
        # (log 13:53:52: TAP_TO_CONTINUE after attempt 5/5). Keep tapping until
        # the list is confirmed or the grace budget is exhausted.
        if not self._is_arena_list_visible():
            self.log('Result screen still open after primary attempts, running grace taps')
            for grace in range(1, 4):
                if self._is_arena_list_visible():
                    list_signal = getattr(self, '_last_arena_list_signal', 'UNKNOWN_SIGNAL')
                    self.log(f'Back on arena list after grace tap ({list_signal})')
                    return True

                result_signal = get_results_screen_signal() or 'GRACE/UNSTABLE'
                self.log(f'Grace result close {grace}/3: {result_signal}')
                tap_to_continue(times=1, wait_before=1, wait_after=2)

                state = self._wait_for_classic_post_result_state(timeout=settle_timeout)
                if state == 'ARENA_LIST':
                    self.log('Back on arena list after grace tap')
                    return True

        if self._is_arena_list_visible():
            list_signal = getattr(self, '_last_arena_list_signal', 'UNKNOWN_SIGNAL')
            self.log(f'Back on arena list ({list_signal})')
            return True

        current_screen = self.determine_current_screen(is_tag=False, x=self.button_locations[1][0], y=self.button_locations[1][1])
        self.log(f'Failed to close result screen, current screen detected as: {current_screen}')
        try:
            refresh_actual = list(pyautogui.pixel(button_refresh[0], button_refresh[1]))
            continue_actual = list(pyautogui.pixel(result_tap_to_continue[0], result_tap_to_continue[1]))
            self.log(
                f'Result-close diagnostic RGB: refresh expected={button_refresh[2]} actual={refresh_actual} '
                f'mistake={button_refresh_mistake}; continue expected={result_tap_to_continue[2]} actual={continue_actual} '
                f'mistake={result_tap_to_continue_mistake}'
            )
            debug_save_screenshot(suffix_name=f'classic-result-close-failed-{current_screen.lower()}')
            self.log('Saved failure screenshot to debug/screenshots')
        except Exception as error:
            self.log(f'Could not save failure screenshot: {error}')
        return False

    def _recover_to_arena_list(self):
        """
        Последняя попытка вернуться к списку арены: закрыть положительно
        распознанные попапы и повторно наблюдать экран.

        Слепой Escape запрещён (план, Этап 2): именно он в кейсе 15-54-44
        увёл бота с уже корректного списка арены. UNKNOWN даёт право только
        на безопасное наблюдение и диагностику.
        """
        self.log('Recovery: closing popups and re-checking arena list')
        close_popup_recursive()

        for attempt in range(1, 7):
            if self._is_arena_list_visible():
                list_signal = getattr(self, '_last_arena_list_signal', 'UNKNOWN_SIGNAL')
                self.log(f'Recovery: back at arena list ({list_signal})')
                return True

            result_signal = get_results_screen_signal()
            if result_signal:
                self.log(f'Recovery: result screen still open ({result_signal}), tapping continue')
                tap_to_continue(times=1, wait_before=1, wait_after=2)
                continue

            sleep(2)

        debug_save_screenshot(suffix_name='arena-recovery-unknown')
        self.log('Recovery: arena list not confirmed; blind Escape is not allowed, stopping')
        return False

    def obtain(self):
        x = self.tiers_coordinates[0]
        y = self.tiers_coordinates[1]
        tiers_pixel = [x, y, RGB_RED_DOT]
        if pixel_check_new(tiers_pixel, mistake=20):
            click(x, y)
            sleep(1)

            _sw = swipe_reward_coord
            dot = find_needle_arena_reward()
            for i in range(3):
                swipe(_sw['direction'], _sw['x'], _sw['y'], _sw['distance'], speed=.6, sleep_after_end=.2)
                dot = find_needle_arena_reward()
                if dot is not None:
                    x = dot[0]
                    y = dot[1] + 20
                    click(x, y)
                    sleep(1)
                    click(claim_chest_coord[0], claim_chest_coord[1])
                    sleep(1)
                    break

            click(tab_battle[0], tab_battle[1])
            sleep(.3)

    def _recover_from_tag_timeout(self, rta_mistake=30):
        """
        Попытка восстановления после TagAwaitTimeout.
        Кликает по tap_to_continue / return_to_arena, жмёт ESC.
        Returns True если удалось вернуться к списку (attack button видна).
        """
        self.log('Recovery: clicking tap_to_continue area')
        click(self.tap_to_continue_coord[0], self.tap_to_continue_coord[1])
        sleep(2)

        if pixel_check_new(self.return_to_arena_coord, mistake=rta_mistake, label="recovery_rta"):
            self.log('Recovery: ReturnToArena detected, clicking')
            click(self.return_to_arena_coord[0], self.return_to_arena_coord[1])
            sleep(2)
            return True

        self.log('Recovery: clicking return_to_arena area')
        click(self.return_to_arena_coord[0], self.return_to_arena_coord[1])
        sleep(2)

        # Слепой Escape запрещён (план, Этап 2): только повторное наблюдение
        # с положительным подтверждением списка.
        for _ in range(3):
            if self._is_arena_list_visible():
                self.log('Recovery: back at arena list')
                return True
            sleep(2)

        debug_save_screenshot(suffix_name='tag-recovery-unknown')
        self.log('Recovery: could not return to arena list')
        return False

    def attack(self):
        if self.name == 'Arena Tag':
            self._attack_tag()
        else:
            self._attack_classic()

    def _attack_tag(self):
        """
        Arena Tag: линейный обход списка.
        Всегда атакуем позицию из item_locations. Скролл инкрементальный.
        После RETURN TO ARENA список остаётся на месте — scroll_pos не сбрасывается.
        """
        results_local = []
        scroll_pos = 0
        _sa = swipe_attack_coord

        for i in range(len(self.item_locations)):
            if self.terminated:
                break

            el = self.item_locations[i]
            target_scroll = el['swipes']
            position = el['position']

            while scroll_pos < target_scroll:
                sleep(0.5)
                swipe_new('bottom', _sa['x'], _sa['y'], self.item_height, speed=.5)
                scroll_pos += 1

            pos = self.button_locations[position]
            x = pos[0]
            y = pos[1]

            if is_debug_mode():
                debug_save_screenshot(suffix_name=f"tag-before-attack-pos{position}-i{i}-scroll{scroll_pos}")

            if not pixel_check_new([x, y, ATTACK_BUTTON_RGB], label=f"attack_button_pos{position}"):
                self.log(f'Arena Tag | Position {position} (i={i}) — no attack button, skipping')
                continue

            self.log(f'Arena Tag | Attack position {position} (i={i}, scroll={scroll_pos})')
            click(x, y, smart=True)
            sleep(1.5)

            if self.terminated:
                break

            if TEAM_SETUP_POINTS:
                waited = 0
                while not is_team_setup_visible() and waited < 5:
                    sleep(0.5)
                    waited += 0.5
                if is_team_setup_visible():
                    self.log('Team Setup screen detected')
                else:
                    self.log('Team Setup screen not detected within timeout, proceeding anyway')

            self.log('Function: enable_quick_battle')
            _qb_mistake = get_mistake(_tag_data, 'quick_battle', 10)
            await_click([self.quick_battle_coord], mistake=_qb_mistake, wait_limit=1)

            if is_debug_mode():
                debug_save_screenshot(suffix_name=f"tag-before-start-i{i}")

            click(start_battle_coord[0], start_battle_coord[1], smart=True)
            sleep(0.5)

            # Умный цикл определения текущего экрана после нажатия "Start"
            waited_for_state = 0
            battle_started = False
            _ttc_mistake = get_mistake(_tag_data, 'tap_to_continue', 35)
            
            while waited_for_state < 15 and not self.terminated:
                sleep(0.5)
                waited_for_state += 0.5
                
                # Проверка 1: Бой начался (белые часы) или уже закончился (defeat/victory)
                _ba_mistake = get_mistake(_shared, 'battle_active', 30)
                battle_in_progress = battle_active_coord and pixel_check_new(battle_active_coord, mistake=_ba_mistake, label="battle_active_check")
                results_visible = pixel_check_new(self.tap_to_continue_coord, mistake=_ttc_mistake, label="tap_to_continue_active") or is_results_screen_visible()
                if battle_in_progress or results_visible:
                    self.log('Battle active or finished (tap to continue visible)')
                    battle_started = True
                    break
                    
                # Проверка 2: Окно рефилла
                if is_refill_popup_visible(is_tag=True):
                    self.log('Refill popup detected')
                    refilled = self._refill()
                    if refilled:
                        wait_ts = 0
                        while not is_team_setup_visible() and wait_ts < 5:
                            sleep(0.5)
                            wait_ts += 0.5
                        if is_team_setup_visible():
                            self.log('Returned to Team Setup after refill, clicking start again')
                        else:
                            self.log('Team Setup not clearly visible, trying to start anyway')
                        click(start_battle_coord[0], start_battle_coord[1], smart=True)
                    else:
                        self.log('Refill failed or out of tokens, terminating')
                        self.terminated = True
                        break
                        
                # Проверка 3: Всё ещё на экране Team Setup
                elif is_team_setup_visible():
                    if waited_for_state % 3 == 0:
                        self.log('Still on Team Setup screen, clicking start again')
                        click(start_battle_coord[0], start_battle_coord[1], smart=True)
                        
                # Проверка 4: Вернулись в список
                elif pixel_check_new([x, y, ATTACK_BUTTON_RGB], mistake=10, label="back_to_list_check"):
                    self.log('Back at arena list, battle did not start')
                    break

            if self.terminated:
                break
                
            if not battle_started:
                self.log('Battle failed to start after 15s wait. Performing full screen re-check...')
                current_screen = self.determine_current_screen(is_tag=True, x=x, y=y)
                self.log(f'Current screen detected as: {current_screen}')
                
                if current_screen == 'TEAM_SETUP':
                    self.log('Fallback: Stuck on Team Setup. Pressing Escape to return to list.')
                    pyautogui.press('escape')
                    sleep(2)
                    continue
                elif current_screen == 'REFILL_POPUP':
                    self.log('Fallback: Stuck on Refill Popup. Canceling and terminating.')
                    pyautogui.press('escape')
                    self.terminated = True
                    break
                elif current_screen == 'ARENA_LIST':
                    self.log('Fallback: We are on Arena List. Proceeding to next opponent.')
                    continue
                elif current_screen in ['RESULTS_SCREEN', 'ACTIVE_BATTLE', 'RETURN_TO_ARENA']:
                    self.log('Fallback: We actually progressed to battle/results. Continuing flow.')
                else:
                    # UNKNOWN не даёт права на Escape (план, Этап 2): только
                    # диагностика и явная ошибка.
                    self.log('Fallback: Unknown state. Saving diagnostics and stopping without blind Escape.')
                    debug_save_screenshot(suffix_name='tag-battle-start-unknown')
                    self.abort_reason = 'unknown screen after battle start'
                    self.run_outcome = RunOutcome.ABORTED_UNKNOWN_SCREEN
                    self.terminated = True
                    break

            # TAP TO CONTINUE
            _ttc_mistake = get_mistake(_tag_data, 'tap_to_continue', 35)
            _rta_mistake = get_mistake(_tag_data, 'return_to_arena', 30)
            E_TAP_TO_CONTINUE = {
                "name": "TapToContinue",
                "interval": 2,
                "expect": lambda: pixel_check_new(self.tap_to_continue_coord, mistake=_ttc_mistake, label="tap_to_continue"),
            }
            r_ttc = self.awaits([E_TAP_TO_CONTINUE, self.E_TERMINATE, self.E_TAG_AWAIT_TIMEOUT], interval=2)
            if r_ttc and r_ttc.get('name') == 'TagAwaitTimeout':
                self.log(f'Tap to continue wait timeout ({ARENA_TAG_AWAIT_LIMIT}s), attempting recovery')
                recovered = self._recover_from_tag_timeout(_rta_mistake)
                if not recovered:
                    self.log('Recovery failed, stopping')
                    self.terminated = True
                break

            res = not is_defeat_screen_visible()
            results_local.append(res)
            self.log('VICTORY' if res else 'DEFEAT')

            click(self.tap_to_continue_coord[0], self.tap_to_continue_coord[1])
            sleep(2)

            # RETURN TO ARENA
            E_RETURN_TO_ARENA = {
                "name": "ReturnToArena",
                "interval": 2,
                "expect": lambda: pixel_check_new(self.return_to_arena_coord, mistake=_rta_mistake, label="return_to_arena"),
            }
            r_rta = self.awaits([E_RETURN_TO_ARENA, self.E_TERMINATE, self.E_TAG_AWAIT_TIMEOUT], interval=2)
            if r_rta and r_rta.get('name') == 'TagAwaitTimeout':
                self.log(f'Return to arena wait timeout ({ARENA_TAG_AWAIT_LIMIT}s), attempting recovery')
                recovered = self._recover_from_tag_timeout(_rta_mistake)
                if not recovered:
                    self.log('Recovery failed, stopping')
                    self.terminated = True
                break
            self.log('RETURN TO ARENA')
            click(self.return_to_arena_coord[0], self.return_to_arena_coord[1])
            sleep(2)
            # scroll_pos остаётся прежним — список на той же позиции

        if len(results_local):
            self.results.append(results_local)
            self._persist_results(results_local)

    def _attack_classic(self):
        """Arena Classic: после боя список сбрасывается в начало."""
        results_local = []
        _sa = swipe_attack_coord
        self.classic_last_pass_battles = 0
        self.classic_last_pass_reached_end = False
        self.classic_last_pass_no_attackable = False

        start_index = self.classic_defeat_offset
        swipes_done = 0

        if start_index > 0:
            initial_swipes = min(self.item_locations[start_index]['swipes'], self.max_swipe)
            self.log(f'Scrolling past defeated opponents (offset={start_index}, swipes={initial_swipes})')
            for _ in range(initial_swipes):
                swipe_new('bottom', _sa['x'], _sa['y'], self.item_height, speed=.5)
                sleep(0.3)
            swipes_done = initial_swipes

        for i in range(start_index, len(self.item_locations)):
            if self.terminated:
                break

            el = self.item_locations[i]
            position = el['position']
            target_swipes = el['swipes']

            if swipes_done < target_swipes:
                self.log(
                    f'Scrolling to next Classic Arena opponent '
                    f'(i={i}, swipes={swipes_done}->{target_swipes})'
                )
            while swipes_done < target_swipes:
                swipe_new('bottom', _sa['x'], _sa['y'], self.item_height, speed=.5)
                swipes_done += 1

            pos = self.button_locations[position]
            x = pos[0]
            y = pos[1]

            def click_on_battle():
                click(x, y, smart=True)
                sleep(1.5)

            def click_on_start():
                click(start_battle_coord[0], start_battle_coord[1], smart=True)
                sleep(0.5)

            is_not_attacked = len(results_local) - 1 < (i - start_index)
            if is_debug_mode():
                debug_save_screenshot(suffix_name=f"classic-before-attack-pos{position}-i{i}")
            has_attack_button = pixel_check_new([x, y, ATTACK_BUTTON_RGB], label=f"attack_button_pos{position}")
            if not has_attack_button:
                self.log(f'Position {position} (i={i}, swipes={swipes_done}) — no attack button, skipping')
            if has_attack_button and is_not_attacked:
                self.log(self.name + ' | Attack')
                click_on_battle()

                if self.terminated:
                    self.log('Terminated')
                    break

                if TEAM_SETUP_POINTS:
                    waited = 0
                    while not is_team_setup_visible() and waited < 5:
                        sleep(0.5)
                        waited += 0.5
                    if is_team_setup_visible():
                        self.log('Team Setup screen detected')
                    else:
                        self.log('Team Setup screen not detected within timeout, proceeding anyway')

                enable_start_on_auto()

                if is_debug_mode():
                    debug_save_screenshot(suffix_name=f"classic-before-start-i{i}")
                click_on_start()

                # Умный цикл определения текущего экрана после нажатия "Start"
                waited_for_state = 0
                battle_started = False
                while waited_for_state < 15 and not self.terminated:
                    sleep(0.5)
                    waited_for_state += 0.5

                    # Проверка 1: Битва началась (белые часы во время боя) или уже закончилась (defeat/victory)
                    _ba_mistake = get_mistake(_shared, 'battle_active', 30)
                    battle_in_progress = battle_active_coord and pixel_check_new(battle_active_coord, mistake=_ba_mistake, label="battle_active_check")
                    results_visible = is_results_screen_visible()
                    if battle_in_progress or results_visible:
                        self.log('Battle active or already finished')
                        battle_started = True
                        break

                    # Проверка 2: Окно рефилла
                    if is_refill_popup_visible():
                        self.log('Refill popup detected')
                        refilled = self._refill()
                        if refilled:
                            # Ожидаем возврата к экрану выбора команды
                            wait_ts = 0
                            while not is_team_setup_visible() and wait_ts < 5:
                                sleep(0.5)
                                wait_ts += 0.5
                            if is_team_setup_visible():
                                self.log('Returned to Team Setup after refill, clicking start again')
                            else:
                                self.log('Team Setup not clearly visible, trying to start anyway')
                            click_on_start()
                            # Продолжаем цикл ожидания состояния
                        else:
                            self.log('Refill failed or out of tokens, terminating')
                            self.terminated = True
                            break

                    # Проверка 3: Всё ещё на экране Team Setup (может быть клик не сработал)
                    elif is_team_setup_visible():
                        if waited_for_state % 3 == 0:  # Периодически повторяем клик
                            self.log('Still on Team Setup screen, clicking start again')
                            click_on_start()

                    # Проверка 4: Вернулись в список противников (возможно из-за отмены рефилла)
                    elif pixel_check_new([x, y, ATTACK_BUTTON_RGB], mistake=10, label="back_to_list_check"):
                        self.log('Back at arena list, battle did not start')
                        break

                if self.terminated:
                    self.log('Terminated')
                    break
                
                if not battle_started:
                    self.log('Battle failed to start after 15s wait. Performing full screen re-check...')
                    current_screen = self.determine_current_screen(is_tag=False, x=x, y=y)
                    self.log(f'Current screen detected as: {current_screen}')
                    
                    if current_screen == 'TEAM_SETUP':
                        self.log('Fallback: Stuck on Team Setup. Pressing Escape to return to list.')
                        pyautogui.press('escape')
                        sleep(2)
                        continue
                    elif current_screen == 'REFILL_POPUP':
                        self.log('Fallback: Stuck on Refill Popup. Canceling and terminating.')
                        pyautogui.press('escape')
                        self.terminated = True
                        break
                    elif current_screen == 'ARENA_LIST':
                        self.log('Fallback: We are on Arena List. Proceeding to next opponent.')
                        continue
                    elif current_screen in ['RESULTS_SCREEN', 'ACTIVE_BATTLE']:
                        self.log('Fallback: We actually progressed to battle/results. Continuing flow.')
                    else:
                        # UNKNOWN не даёт права на Escape (план, Этап 2): только
                        # диагностика и явная ошибка.
                        self.log('Fallback: Unknown state. Saving diagnostics and stopping without blind Escape.')
                        debug_save_screenshot(suffix_name='classic-battle-start-unknown')
                        self.abort_reason = 'unknown screen after battle start'
                        self.run_outcome = RunOutcome.ABORTED_UNKNOWN_SCREEN
                        self.terminated = True
                        break

                self.waiting_battle_end_regular(self.name, battle_time_limit=self.battle_time_limit)
                if is_debug_mode():
                    debug_save_screenshot(suffix_name=f"classic-battle-result-i{i}")
                res = not is_defeat_screen_visible()
                results_local.append(res)
                result_name = 'VICTORY' if res else 'DEFEAT'
                self.log(result_name)

                if not res:
                    self.classic_defeat_offset = i + 1
                    self.log(f'Defeat at position {i}, next pass will start from offset {self.classic_defeat_offset}')

                if not self._close_classic_result_screen():
                    if not self._recover_to_arena_list():
                        screen = self.determine_current_screen(is_tag=False, x=self.button_locations[1][0], y=self.button_locations[1][1])
                        self.abort_reason = f'could not return to arena list after battle result (screen: {screen})'
                        self.run_outcome = RunOutcome.ABORTED_NAVIGATION
                        self.log('Could not return to arena list after result, stopping Arena Classic')
                        self.terminated = True
                        break
                    self.log('Recovered to arena list after failed result close, continuing')

                # Игра сбрасывает список Classic Arena в начало после каждого
                # боя, поэтому накопленный счётчик свайпов больше не
                # соответствует экрану. После победы это приводило к молчаливым
                # пропускам позиций (строка показывает "Victory" вместо
                # Attack), после поражения — к повторной атаке того же
                # соперника. Прокручиваем следующего противника заново от верха.
                if swipes_done:
                    self.log(f'Battle finished: list reset to top by the game, re-scrolling from 0 (was {swipes_done})')
                swipes_done = 0
                sleep(1)

        else:
            if not self.terminated:
                self.classic_last_pass_reached_end = True

        self.classic_last_pass_battles = len(results_local)
        if not self.terminated and len(results_local) == 0:
            self.classic_last_pass_no_attackable = True

        if len(results_local):
            self.results.append(results_local)
            self._persist_results(results_local)


class ArenaClassic(ArenaFactory):
    def __init__(self, app, props=None):
        ArenaFactory.__init__(
            self,
            app=app,
            name='Arena Classic',
            x_axis_info=_classic_data['x_axis_info'],
            read_coins_predicate=read_bank_arena_classic,
            item_height=_classic_data['item_height'],
            button_locations=parse_button_locations(_classic_data, 'button_locations'),
            item_locations=CLASSIC_ITEM_LOCATIONS,
            refill_coordinates=parse_point(_classic_data, 'coins_refill'),
            tiers_coordinates=parse_point(_classic_data, 'tiers_coordinate'),
            props=props
        )


class ArenaTag(ArenaFactory):
    def __init__(self, app, props=None):
        ArenaFactory.__init__(
            self,
            app=app,
            name='Arena Tag',
            x_axis_info=_tag_data['x_axis_info'],
            read_coins_predicate=read_bank_arena_tag,
            item_height=_tag_data['item_height'],
            button_locations=parse_button_locations(_tag_data, 'button_locations'),
            item_locations=TAG_ITEM_LOCATIONS,
            refill_coordinates=parse_point(_tag_data, 'coins_refill'),
            tiers_coordinates=parse_point(_tag_data, 'tiers_coordinate'),
            props=props
        )
        self.quick_battle_coord = get_coordinate(_tag_data, 'quick_battle', source='coordinates/arena_tag.json')
        self.tap_to_continue_coord = get_coordinate(_tag_data, 'tap_to_continue', source='coordinates/arena_tag.json')
        self.return_to_arena_coord = get_coordinate(_tag_data, 'return_to_arena', source='coordinates/arena_tag.json')
