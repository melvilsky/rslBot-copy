import os
import json

from helpers.common import *
from classes.Location import Location

TWIN_KEYS_LIMIT = 6


def load_iron_twins_coordinates():
    """Загружает координаты из файла coordinates/iron_twins.json"""
    try:
        coords_path = os.path.join('coordinates', 'iron_twins.json')
        if os.path.exists(coords_path):
            with open(coords_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Ошибка загрузки координат из coordinates/iron_twins.json: {e}")
        return None


def get_iron_twins_coordinate(data, key):
    """
    Получает координату из загруженного JSON.
    Returns: [x, y, [r, g, b]] если есть rgb, иначе [x, y]
    Raises: ValueError если ключ не найден
    """
    if not data or key not in data:
        raise ValueError(f"Coordinate '{key}' not found in coordinates/iron_twins.json")
    coord = data[key]
    if 'rgb' in coord:
        return [coord['x'], coord['y'], coord['rgb']]
    return [coord['x'], coord['y']]


def get_iron_twins_mistake(data, key, default=20):
    """Получает значение mistake (погрешность) из JSON"""
    if data and key in data:
        coord = data[key]
        if isinstance(coord, dict):
            return coord.get('mistake', default)
    return default


_coordinates_data = load_iron_twins_coordinates()
if _coordinates_data is None:
    raise RuntimeError(
        'Не найден файл coordinates/iron_twins.json. '
        'Скопируйте его из репозитория или восстановите.'
    )

super_raids_coord = get_iron_twins_coordinate(_coordinates_data, 'super_raids')
super_raids_mistake = get_iron_twins_mistake(_coordinates_data, 'super_raids', 10)

# @TODO Refactor is needed
class IronTwins(Location):
    RESULT_DEFEAT = [450, 40, [178, 23, 38]]

    def __init__(self, app, props=None):
        Location.__init__(self, name='Iron Twins Fortress', app=app, report_predicate=self._report)

        self.results = []
        self.keys = TWIN_KEYS_LIMIT
        self.super_raids_coord = super_raids_coord
        self.super_raids_mistake = super_raids_mistake

        self._apply_props(props=props)

        self.event_dispatcher.subscribe('enter', self._enter)
        self.event_dispatcher.subscribe('run', self._run)

    def _report(self):
        res_list = []

        if len(self.results):
            used = self.results.count(True)
            attempts = len(self.results)
            str_used = f"Used: {str(used)}"
            str_attempts = f"(WR: {calculate_win_rate(used, attempts-used)})"
            res_list.append(f"{str_used} {str_attempts}")

        return res_list

    def _enter(self):
        click_on_progress_info()
        # Fortress Keys
        click(600, 210)
        sleep(1)

        dungeons_scroll()

        # Enter the stage
        click(830, 460)
        sleep(.5)
        self._ensure_super_raids_enabled()

    def _ensure_super_raids_enabled(self):
        x = self.super_raids_coord[0]
        y = self.super_raids_coord[1]

        if is_debug_mode():
            debug_click_coordinates(
                x,
                y,
                label="iron_twins_super_raids_CHECK_POINT",
                region=[0, 0, 920, 540],
                grid=True
            )
            debug_save_screenshot(suffix_name="iron-twins-super-raids-before-check")

        # Проверяем, включен ли SUPER RAIDS (RGB [108, 237, 255] - цвет когда включено)
        enabled = pixel_check_new(
            self.super_raids_coord,
            mistake=self.super_raids_mistake,
            label="iron_twins_super_raids"
        )
        if enabled:
            self.log("SUPER RAIDS already enabled")
            return True

        # Если не включен - кликаем чтобы включить
        self.log("SUPER RAIDS disabled, trying to enable")
        pyautogui.moveTo(x, y, .5, random_easying())
        sleep(.2)
        click(x, y)
        sleep(.5)

        if is_debug_mode():
            debug_save_screenshot(suffix_name="iron-twins-super-raids-after-click")

        # Проверяем, включился ли после клика
        enabled_after_click = pixel_check_new(
            self.super_raids_coord,
            mistake=self.super_raids_mistake,
            label="iron_twins_super_raids_after_click"
        )
        if enabled_after_click:
            self.log("SUPER RAIDS enabled successfully")
        else:
            self.log("WARNING: failed to enable SUPER RAIDS - may need to check RGB values")

        return enabled_after_click

    def _run(self, props=None):
        self._apply_props(props=props)
        self.attack()

    def _check_refill(self):
        sleep(1)
        ruby_button = find_needle_refill_ruby()

        if ruby_button is not None:
            # Ключи закончились - завершаем работу и выходим из локации
            self.terminated = True
            self.completed = True
            close_popup()
            self.log("Keys exhausted, exiting Iron Twins Fortress")
            dungeons_click_stage_select()

    def _is_available(self):
        # Если завершено принудительно - выходим
        if self.completed or self.terminated:
            return False
        
        # Проверяем, есть ли запрос на покупку за рубины - если есть, ключи закончились
        sleep(0.5)
        ruby_button = find_needle_refill_ruby()
        if ruby_button is not None:
            return False
        
        # Если нет запроса на покупку - можно продолжать бои (есть кнопка Enter Stage или Replay)
        # С SUPER RAIDS один бой может использовать несколько ключей, поэтому не считаем по количеству побед
        return True

    def _apply_props(self, props=None):
        if props:
            if 'keys' in props:
                self.keys = int(props['keys'])

    def attack(self):
        self._check_refill()
        if self.terminated:
            self.log('Terminated')
            return

        while self._is_available():
            dungeons_continue_battle()

            self._check_refill()
            if self.terminated:
                self.log('Terminated')
                break

            self.waiting_battle_end_regular(self.NAME)

            res = not pixel_check_new(self.RESULT_DEFEAT, mistake=10)
            self.results.append(res)
            
            # Не устанавливаем completed по количеству побед — с SUPER RAIDS один бой может использовать несколько ключей
            # Завершение работы происходит только когда _check_refill() обнаружит запрос на покупку за рубины

        # Выходим из локации если цикл завершился без обнаружения запроса на покупку
        # (если запрос был обнаружен, выход уже выполнен в _check_refill())
        if not self.terminated and not self.completed:
            self.log("Exiting Iron Twins Fortress")
            dungeons_click_stage_select()
