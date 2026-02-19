import os
import json

from helpers.common import *
from helpers.refill_state import get_remaining_refills, increment_purchase
from constants.index import *
from classes.Location import Location

# ============================================================================
# КООРДИНАТЫ ХРАНЯТСЯ В:
#   coordinates/arena_shared.json   — общие для ArenaFactory (Tag + Classic)
#   coordinates/arena_tag.json      — только Arena Tag
#   coordinates/arena_classic.json  — только Arena Classic
# Для изменения координат отредактируйте JSON и перезапустите приложение
# ============================================================================


def load_arena_coordinates(filename):
    """Загружает координаты из JSON файла в папке coordinates/"""
    try:
        coords_path = os.path.join('coordinates', filename)
        if os.path.exists(coords_path):
            with open(coords_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Ошибка загрузки координат из coordinates/{filename}: {e}")
        return None


def get_arena_coordinate(data, key):
    """
    Получает координату из загруженного JSON.
    Returns: [x, y, [r, g, b]] если есть rgb, иначе [x, y]
    Raises: ValueError если ключ не найден
    """
    if not data or key not in data:
        raise ValueError(f"Coordinate '{key}' not found in arena coordinates JSON")
    coord = data[key]
    if 'rgb' in coord:
        return [coord['x'], coord['y'], coord['rgb']]
    return [coord['x'], coord['y']]


def get_arena_mistake(data, key, default=20):
    """Получает значение mistake (погрешность) из JSON"""
    if data and key in data:
        coord = data[key]
        if isinstance(coord, dict):
            return coord.get('mistake', default)
    return default


def _parse_button_locations(data, key):
    """Конвертирует button_locations из JSON формата {str: {x,y}} в {int: [x,y]}"""
    bl = data[key]
    return {int(k): [v['x'], v['y']] for k, v in bl.items()}


def _parse_point(data, key):
    """Конвертирует {x, y} из JSON в [x, y]"""
    p = data[key]
    return [p['x'], p['y']]


# Загружаем координаты при импорте модуля
_shared = load_arena_coordinates('arena_shared.json')
_tag_data = load_arena_coordinates('arena_tag.json')
_classic_data = load_arena_coordinates('arena_classic.json')

# Проверка наличия обязательных JSON (без них арена неработоспособна)
_missing = []
if _shared is None:
    _missing.append('coordinates/arena_shared.json')
if _tag_data is None:
    _missing.append('coordinates/arena_tag.json')
if _classic_data is None:
    _missing.append('coordinates/arena_classic.json')
if _missing:
    raise RuntimeError(
        'Не найдены файлы координат арены: {}. '
        'Скопируйте их из репозитория или восстановите.'.format(', '.join(_missing))
    )

# Общие координаты ArenaFactory (из arena_shared.json)
button_refresh = get_arena_coordinate(_shared, 'button_refresh')
refill_free = get_arena_coordinate(_shared, 'refill_free')
refill_paid = get_arena_coordinate(_shared, 'refill_paid')
defeat = get_arena_coordinate(_shared, 'defeat')
tab_battle = get_arena_coordinate(_shared, 'tab_battle')
battle_end_coord = get_arena_coordinate(_shared, 'battle_end')
start_battle_coord = get_arena_coordinate(_shared, 'start_battle')
refill_click_coord = get_arena_coordinate(_shared, 'refill_click')
claim_chest_coord = get_arena_coordinate(_shared, 'claim_chest')
swipe_attack_coord = _shared['swipe_attack']
swipe_refresh_coord = _shared['swipe_refresh']
swipe_reward_coord = _shared['swipe_reward']

RGB_RED_DOT = _shared['red_dot_rgb']
ATTACK_BUTTON_RGB = _shared['attack_button_rgb']
PAID_REFILL_LIMIT = 0
OUTPUT_ITEMS_AMOUNT = 10

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


class ArenaFactory(Location):
    E_BUTTON_REFRESH = {
        "name": "Refresh button",
        "expect": lambda: pixel_check_new(button_refresh, mistake=5),
        "callback": callback_refresh,
        "interval": 5,
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

        self._apply_props(props=props)

        _be_mistake = get_arena_mistake(_shared, 'battle_end', 3)
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
        res_list = []
        if len(self.results):
            flatten_list = flatten(self.results)
            w = flatten_list.count(True)
            l = flatten_list.count(False)
            str_battles = f"Battles: {str(len(flatten_list))}"
            str_wr = f"(WR: {calculate_win_rate(w, l)})"
            res_list.append(f"{str_battles} {str_wr}")

        return res_list

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

        while self.terminated is False:
            self.attack()

            last_results = self._get_last_results()

            if self.terminated is False:
                # at least one 'Defeat' or continued battles - should refresh
                if last_results.count(False) > 0 or len(last_results) < OUTPUT_ITEMS_AMOUNT:
                    self._refresh_arena()

    def _apply_props(self, props=None):
        if props is not None:
            if 'refill' in props:
                refill_from_config = int(props['refill'])
                self.refill_max_allowed = refill_from_config
                # Загружаем оставшееся количество проходок с учетом уже купленных сегодня
                location_key = self.NAME.lower().replace(' ', '_')
                self.refill = get_remaining_refills(location_key, refill_from_config)
                if self.refill < refill_from_config:
                    self.log(f"Refill state loaded: {refill_from_config - self.refill} already purchased today (UTC), {self.refill} remaining")
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
            self._refill()

        self.awaits([self.E_BUTTON_REFRESH, self.E_TERMINATE])

    def _refill(self):
        refilled = False

        def click_on_refill():
            click(refill_click_coord[0], refill_click_coord[1])
            sleep(0.5)

        sleep(1)
        ruby_button = find_needle_refill_ruby()

        if ruby_button is not None:
            self.log('Free coins are NOT available')
            if self.refill > 0:
                # Сохраняем факт покупки в состояние
                location_key = self.NAME.lower().replace(' ', '_')
                increment_purchase(location_key, self.refill_max_allowed)
                self.refill -= 1
                click_on_refill()
                refilled = True
            else:
                self.log('No more refill')
                self.terminated = True
        elif pixels_wait([refill_free], msg='Free refill sacs', mistake=10, timeout=1, wait_limit=2)[0]:
            self.log('Free coins are available')
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

    def attack(self):
        results_local = []
        should_use_multi_swipe = False
        swipes_done = [0]  # текущее состояние скролла (список не сбрасывается после RETURN TO ARENA)

        _sa = swipe_attack_coord

        def inner_swipe(swipes_amount):
            if should_use_multi_swipe:
                # список не сбрасывается после боя — делаем только дельту свайпов
                delta = swipes_amount - swipes_done[0]
                for _ in range(delta):
                    sleep(1)
                    swipe_new('bottom', _sa['x'], _sa['y'], self.item_height, speed=.5)
                swipes_done[0] = swipes_amount
            elif 0 < i <= self.max_swipe:
                # первый проход по списку: по одному свайпу на шаг
                swipe_new('bottom', _sa['x'], _sa['y'], self.item_height, speed=.5)
                swipes_done[0] = swipes_amount

        for i in range(len(self.item_locations)):
            if self.terminated:
                break

            el = self.item_locations[i]
            swipes = el['swipes']
            position = el['position']
            if i == 0:
                swipes_done[0] = 0  # сброс при новом проходе по списку (после рефреша)

            # После RETURN TO ARENA синхронизируемся с экраном: если следующий противник уже виден — не скроллим
            do_swipe = True
            if should_use_multi_swipe:
                next_i = len(results_local)
                for p in range(1, 5):
                    opponent_at_p = swipes_done[0] + (p - 1)
                    if opponent_at_p == next_i:
                        pos_xy = self.button_locations[p]
                        if pixel_check_new(
                            [pos_xy[0], pos_xy[1], ATTACK_BUTTON_RGB],
                            label=f"attack_button_pos{p}_presync",
                        ):
                            position = p
                            do_swipe = False
                            break
            if do_swipe:
                inner_swipe(swipes)

            pos = self.button_locations[position]
            x = pos[0]
            y = pos[1]

            def click_on_battle():
                click(x, y, smart=True)
                sleep(1.5)

            def click_on_start():
                click(start_battle_coord[0], start_battle_coord[1], smart=True)
                sleep(0.5)

            # checking - is an enemy already attacked
            is_not_attacked = len(results_local) - 1 < i
            if is_debug_mode():
                debug_save_screenshot(suffix_name=f"arena-before-attack-pos{position}-i{i}")
            if pixel_check_new([x, y, ATTACK_BUTTON_RGB], label=f"attack_button_pos{position}") and is_not_attacked:
                self.log(self.name + ' | Attack')
                click_on_battle()

                if self.terminated:
                    self.log('Terminated')
                    break

                # Quick Battle / AutoPlay
                if self.name == 'Arena Tag':
                    self.log('Function: enable_quick_battle')
                    _qb_mistake = get_arena_mistake(_tag_data, 'quick_battle', 10)
                    await_click([self.quick_battle_coord], mistake=_qb_mistake, wait_limit=1)
                else:
                    enable_start_on_auto()

                if is_debug_mode():
                    debug_save_screenshot(suffix_name=f"arena-before-start-i{i}")
                click_on_start()

                # Проверка докупки после нажатия confirm (Start)
                refilled = self._refill()
                if refilled:
                    click_on_start()

                if self.terminated:
                    self.log('Terminated')
                    break

                # Не докупили и диалог докупки всё ещё на экране — бой не начался, выходим
                if not refilled and pixel_check_new(refill_paid, mistake=15, label="refill_dialog_check"):
                    self.log('Refill dialog still visible, battle did not start — terminating')
                    self.terminated = True
                    break

                # Не докупили и диалог закрыли — проверяем, не вернулись ли к списку (бой не стартовал)
                if not refilled:
                    sleep(2)
                    if pixel_check_new([x, y, ATTACK_BUTTON_RGB], mistake=10, label="back_to_list_check"):
                        self.log('Back at list (battle did not start after closing refill dialog) — skipping wait')
                        break

                if self.name == 'Arena Tag':
                    # Arena Tag: ожидаем TAP TO CONTINUE вместо battle_end
                    _ttc_mistake = get_arena_mistake(_tag_data, 'tap_to_continue', 35)

                    if is_debug_mode():
                        debug_click_coordinates(
                            self.tap_to_continue_coord[0], self.tap_to_continue_coord[1],
                            label="tap_to_continue_CHECK_POINT",
                            region=[0, 0, 920, 540],
                            grid=True
                        )

                    E_TAP_TO_CONTINUE = {
                        "name": "TapToContinue",
                        "interval": 2,
                        "expect": lambda: pixel_check_new(self.tap_to_continue_coord, mistake=_ttc_mistake, label="tap_to_continue"),
                    }
                    self.awaits([E_TAP_TO_CONTINUE, self.E_TERMINATE], interval=2)

                    if is_debug_mode():
                        debug_save_screenshot(suffix_name=f"arena-tag-tap-to-continue-i{i}")

                    res = not pixel_check_new(defeat, 20, label="defeat_check")
                    results_local.append(res)
                    result_name = 'VICTORY' if res else 'DEFEAT'
                    self.log(result_name)

                    click(self.tap_to_continue_coord[0], self.tap_to_continue_coord[1])
                    sleep(2)

                    # Arena Tag: ожидаем кнопку RETURN TO ARENA
                    _rta_mistake = get_arena_mistake(_tag_data, 'return_to_arena', 30)

                    if is_debug_mode():
                        debug_click_coordinates(
                            self.return_to_arena_coord[0], self.return_to_arena_coord[1],
                            label="return_to_arena_CHECK_POINT",
                            region=[0, 0, 920, 540],
                            grid=True
                        )

                    E_RETURN_TO_ARENA = {
                        "name": "ReturnToArena",
                        "interval": 2,
                        "expect": lambda: pixel_check_new(self.return_to_arena_coord, mistake=_rta_mistake, label="return_to_arena"),
                    }
                    self.awaits([E_RETURN_TO_ARENA, self.E_TERMINATE], interval=2)
                    self.log('RETURN TO ARENA')
                    click(self.return_to_arena_coord[0], self.return_to_arena_coord[1])
                    sleep(2)
                else:
                    # Arena Classic: старая логика
                    self.waiting_battle_end_regular(self.name, battle_time_limit=self.battle_time_limit)
                    if is_debug_mode():
                        debug_save_screenshot(suffix_name=f"arena-battle-result-i{i}")
                    res = not pixel_check_new(defeat, 20, label="defeat_check")
                    results_local.append(res)
                    result_name = 'VICTORY' if res else 'DEFEAT'
                    self.log(result_name)

                    tap_to_continue(times=2, wait_after=3)
                    sleep(2)

                    max_wait_time = 7
                    check_interval = 0.5
                    waited = 0
                    while pixel_check_new(defeat, 20) and waited < max_wait_time:
                        sleep(check_interval)
                        waited += check_interval

                    if pixel_check_new(defeat, 20):
                        self.log('Victory/defeat screen still visible, retrying tap_to_continue')
                        tap_to_continue(times=2, wait_after=3)
                        sleep(2)

                        waited = 0
                        while pixel_check_new(defeat, 20) and waited < max_wait_time:
                            sleep(check_interval)
                            waited += check_interval

                    if not pixel_check_new(defeat, 20):
                        self.log('Victory/defeat screen closed successfully')
                    else:
                        self.log('Warning: Victory/defeat screen may still be visible')

                # tells to skip several teams by swiping
                should_use_multi_swipe = True

        # appends result from attack series into the global results list
        if len(results_local):
            self.results.append(results_local)
            # @TODO Temp commented
            # self.event_dispatcher.publish('update_results')


class ArenaClassic(ArenaFactory):
    def __init__(self, app, props=None):
        ArenaFactory.__init__(
            self,
            app=app,
            name='Arena Classic',
            x_axis_info=_classic_data['x_axis_info'],
            read_coins_predicate=read_bank_arena_classic,
            item_height=_classic_data['item_height'],
            button_locations=_parse_button_locations(_classic_data, 'button_locations'),
            item_locations=CLASSIC_ITEM_LOCATIONS,
            refill_coordinates=_parse_point(_classic_data, 'coins_refill'),
            tiers_coordinates=_parse_point(_classic_data, 'tiers_coordinate'),
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
            button_locations=_parse_button_locations(_tag_data, 'button_locations'),
            item_locations=TAG_ITEM_LOCATIONS,
            refill_coordinates=_parse_point(_tag_data, 'coins_refill'),
            tiers_coordinates=_parse_point(_tag_data, 'tiers_coordinate'),
            props=props
        )
        self.quick_battle_coord = get_arena_coordinate(_tag_data, 'quick_battle')
        self.tap_to_continue_coord = get_arena_coordinate(_tag_data, 'tap_to_continue')
        self.return_to_arena_coord = get_arena_coordinate(_tag_data, 'return_to_arena')
