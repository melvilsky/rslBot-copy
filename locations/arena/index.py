import pyautogui

from helpers.common import (
    debug_save_screenshot,
    is_debug_mode,
    prepare_event,
    sleep,
)
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
from helpers.refill_state import get_remaining_refills, increment_purchase
from classes.Location import Location

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
refill_free = get_coordinate(_shared, 'refill_free', source='coordinates/arena_shared.json')
refill_paid = get_coordinate(_shared, 'refill_paid', source='coordinates/arena_shared.json')
refill_ruby = get_coordinate(_shared, 'refill_ruby', source='coordinates/arena_shared.json')
defeat = get_coordinate(_shared, 'defeat', source='coordinates/arena_shared.json')
defeat_mistake = get_mistake(_shared, 'defeat', 35)
tab_battle = get_coordinate(_shared, 'tab_battle', source='coordinates/arena_shared.json')
battle_end_coord = get_coordinate(_shared, 'battle_end', source='coordinates/arena_shared.json')
battle_active_coord = get_coordinate(_shared, 'battle_active', source='coordinates/arena_shared.json') if 'battle_active' in _shared else None
start_battle_coord = get_coordinate(_shared, 'start_battle', source='coordinates/arena_shared.json')
refill_click_coord = get_coordinate(_shared, 'refill_click', source='coordinates/arena_shared.json')
claim_chest_coord = get_coordinate(_shared, 'claim_chest', source='coordinates/arena_shared.json')
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

def is_results_screen_visible():
    _be_mistake = get_mistake(_shared, 'battle_end', 3)
    if pixel_check_new(battle_end_coord, mistake=_be_mistake, label="results_screen_clock"):
        return True
    return is_defeat_screen_visible() or is_victory_screen_visible()

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


# Таймаут ожидания кнопки Refresh (сек); при превышении — выход без бесконечного ожидания (15 мин)
ARENA_REFRESH_WAIT_LIMIT = 900
# Таймаут ожидания TAP TO CONTINUE / RETURN TO ARENA в Arena Tag (сек)
ARENA_TAG_AWAIT_LIMIT = 180


class ArenaFactory(Location):
    E_BUTTON_REFRESH = {
        "name": "Refresh button",
        "expect": lambda: pixel_check_new(button_refresh, mistake=5),
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

        self._apply_props(props=props)

        _be_mistake = get_mistake(_shared, 'battle_end', 3)
        self.E_BATTLE_END = prepare_event(self.E_BATTLE_END, {
            "expect": lambda: pixel_check_new(battle_end_coord, mistake=_be_mistake)
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
            self._refresh_arena()
            # @TODO Test
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
            # Arena Classic: старая логика с отслеживанием прогресса
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
                    if len(last_results) == OUTPUT_ITEMS_AMOUNT:
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

    def _refresh_arena(self):
        _coins, _region = self.read_coins_predicate()
        if _coins == 0:
            _x = _region[0] - 5
            _y = _region[1] + 5
            click(_x, _y)
            refilled = self._refill()

            if self.terminated:
                return

            if refilled:
                sleep(2)
                click(_x, _y)
                sleep(1)

        response = self.awaits([self.E_BUTTON_REFRESH, self.E_TERMINATE, self.E_REFRESH_TIMEOUT])
        if response and response.get('name') == 'RefreshTimeout':
            self.log(f'Refresh button wait timeout ({ARENA_REFRESH_WAIT_LIMIT}s), stopping')
            self.terminated = True
            return

        if self.classic_defeat_offset > 0:
            self.log(f'Refresh: resetting defeat offset (was {self.classic_defeat_offset})')
            self.classic_defeat_offset = 0

        if self.name == 'Arena Tag':
            _sr = swipe_refresh_coord
            self.log('Scrolling up after refresh to return to list start')
            for index in range(2):
                swipe_new(_sr['direction'], _sr['x'], _sr['y'], _sr['distance'], speed=.2, instant_move=True)
            sleep(1)

    def _refill(self):
        refilled = False

        def click_on_refill():
            click(refill_click_coord[0], refill_click_coord[1])
            sleep(0.5)

        def is_ruby_refill_visible():
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

        # ВАЖНО: Ждем анимацию появления попапа до 3 секунд
        waited_popup = 0
        while not is_refill_popup_visible(self.name == 'Arena Tag') and waited_popup < 3:
            sleep(0.5)
            waited_popup += 0.5

        if not is_refill_popup_visible(self.name == 'Arena Tag'):
            return False

        sleep(1)

        if is_ruby_refill_visible():
            self.log('Free coins are NOT available (ruby detected)')
            if self.refill > 0:
                location_key = self.NAME.lower().replace(' ', '_')
                profile = getattr(self.app, 'current_player_name', None)
                increment_purchase(location_key, self.refill_max_allowed, profile_name=profile)
                self.refill -= 1
                click_on_refill()
                refilled = True
            else:
                self.log('No more refill')
                self.terminated = True
        else:
            self.log('Free coins are available (no ruby detected)')
            click_on_refill()
            refilled = True

        sleep(0.5)

        return refilled

    def _get_last_results(self):
        length = len(self.results)
        if length:
            return self.results[len(self.results) - 1]
        else:
            return self.results

    def determine_current_screen(self, is_tag, x, y):
        _be_mistake = get_mistake(_shared, 'battle_end', 3)
        if pixel_check_new(battle_end_coord, mistake=_be_mistake, label="det_battle"):
            return 'RESULTS_SCREEN'
            
        if is_refill_popup_visible(is_tag):
            return 'REFILL_POPUP'
            
        if is_team_setup_visible():
            return 'TEAM_SETUP'
            
        if pixel_check_new([x, y, ATTACK_BUTTON_RGB], label="det_list"):
            return 'ARENA_LIST'
            
        if is_tag:
            _ttc_mistake = get_mistake(_tag_data, 'tap_to_continue', 35)
            if pixel_check_new(self.tap_to_continue_coord, mistake=_ttc_mistake, label="det_ttc"):
                return 'RESULTS_SCREEN'
            _rta_mistake = get_mistake(_tag_data, 'return_to_arena', 30)
            if pixel_check_new(self.return_to_arena_coord, mistake=_rta_mistake, label="det_rta"):
                return 'RETURN_TO_ARENA'
        else:
            if is_results_screen_visible():
                return 'RESULTS_SCREEN'
                
        return 'UNKNOWN'

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

        for _ in range(3):
            pyautogui.press('escape')
            sleep(1)

        pos = self.button_locations[1]
        if pixel_check_new([pos[0], pos[1], ATTACK_BUTTON_RGB], mistake=10, label="recovery_list_check"):
            self.log('Recovery: back at arena list')
            return True

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
                
                # Проверка 1: Бой начался (белые часы) или уже закончился (серые часы на результатах)
                _be_mistake = get_mistake(_shared, 'battle_end', 3)
                _ba_mistake = get_mistake(_shared, 'battle_active', 30)
                battle_in_progress = battle_active_coord and pixel_check_new(battle_active_coord, mistake=_ba_mistake, label="battle_active_check")
                results_visible = pixel_check_new(self.tap_to_continue_coord, mistake=_ttc_mistake, label="tap_to_continue_active") or pixel_check_new(battle_end_coord, mistake=_be_mistake, label="battle_active_check")
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
                    self.log('Fallback: Unknown state. Attempting recovery with Escape.')
                    pyautogui.press('escape')
                    sleep(2)
                    continue

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
            if pixel_check_new([x, y, ATTACK_BUTTON_RGB], label=f"attack_button_pos{position}") and is_not_attacked:
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

                    # Проверка 1: Битва началась (белые часы во время боя) или уже закончилась (серые часы на результатах)
                    _be_mistake = get_mistake(_shared, 'battle_end', 3)
                    _ba_mistake = get_mistake(_shared, 'battle_active', 30)
                    battle_in_progress = battle_active_coord and pixel_check_new(battle_active_coord, mistake=_ba_mistake, label="battle_active_check")
                    results_visible = pixel_check_new(battle_end_coord, mistake=_be_mistake, label="results_check")
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
                        self.log('Fallback: Unknown state. Attempting recovery with Escape.')
                        pyautogui.press('escape')
                        sleep(2)
                        continue

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

                # Кликаем tap_to_continue 2 раза и ждём возврата на страницу выбора соперника
                tap_to_continue(times=2, wait_after=2)

                # Проверяем что вернулись на страницу списка соперников (кнопка атаки видна)
                _max_close_wait = 8
                _close_interval = 0.5
                _close_waited = 0
                _back_on_list = False
                pos = self.button_locations[1]

                while _close_waited < _max_close_wait:
                    sleep(_close_interval)
                    _close_waited += _close_interval
                    if pixel_check_new([pos[0], pos[1], ATTACK_BUTTON_RGB], mistake=10, label="back_on_list"):
                        self.log('Back on arena list')
                        _back_on_list = True
                        break

                if not _back_on_list:
                    self.log('Still not on arena list, tapping again')
                    tap_to_continue(times=2, wait_after=2)

                sleep(1)

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
