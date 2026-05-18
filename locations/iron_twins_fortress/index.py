import pyautogui

from helpers.common import sleep
from helpers.game_actions import (
    calculate_win_rate,
    click_on_progress_info,
    dungeons_click_stage_select,
    dungeons_continue_battle,
    dungeons_scroll,
    waiting_battle_end_regular,
)
from helpers.mouse import click
from helpers.popups import close_popup
from helpers.vision import (
    find_needle_refill_ruby,
    pixel_check_new,
)
from helpers.coordinates import get_coordinate, get_mistake, load_coordinates
from classes.Location import Location

TWIN_KEYS_LIMIT = 6


_coordinates_data = load_coordinates('iron_twins.json', required=True)

super_raids_coord = get_coordinate(_coordinates_data, 'super_raids', source='coordinates/iron_twins.json')
super_raids_mistake = get_mistake(_coordinates_data, 'super_raids', 10)
super_raids_rgb_disabled = _coordinates_data['super_raids'].get('rgb_disabled', [8, 20, 24])

# @TODO Refactor is needed
class IronTwins(Location):
    RESULT_DEFEAT = [450, 40, [178, 23, 38]]

    def __init__(self, app, props=None):
        Location.__init__(self, name='Iron Twins Fortress', app=app, report_predicate=self._report)

        self.keys = TWIN_KEYS_LIMIT
        self.super_raids_coord = super_raids_coord
        self.super_raids_mistake = super_raids_mistake
        self.super_raids_rgb_disabled = super_raids_rgb_disabled

        self._apply_props(props=props)

        self.event_dispatcher.subscribe('enter', self._enter)
        self.event_dispatcher.subscribe('run', self._run)

    def _report(self):
        from helpers.battle_stats import load_stats
        res_list = []
        profile = getattr(self.app, 'current_player_name', None)
        stats = load_stats('iron_twins_fortress', profile_name=profile)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        t = wins + losses
        if t:
            str_used = f"Used: {str(wins)}"
            str_attempts = f"(WR: {calculate_win_rate(wins, losses)})"
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
        sleep(2)
        self._ensure_super_raids_enabled()

    def _read_super_raids_state(self):
        """
        Читает реальный цвет пикселя super raids и определяет состояние.
        Returns: True=enabled, False=disabled, None=transitional (ещё грузится)
        """
        x = self.super_raids_coord[0]
        y = self.super_raids_coord[1]
        rgb_enabled = self.super_raids_coord[2]
        rgb_disabled = self.super_raids_rgb_disabled
        mistake = self.super_raids_mistake

        actual = [c for c in pyautogui.pixel(x, y)]
        diff_on = [abs(actual[i] - rgb_enabled[i]) for i in range(3)]
        diff_off = [abs(actual[i] - rgb_disabled[i]) for i in range(3)]
        matches_on = all(d <= mistake for d in diff_on)
        matches_off = all(d <= mistake for d in diff_off)

        self.log(f"SUPER RAIDS pixel ({x}, {y}): actual={actual}")
        self.log(f"  vs enabled  {rgb_enabled}: diff={diff_on}, match={matches_on}")
        self.log(f"  vs disabled {rgb_disabled}: diff={diff_off}, match={matches_off}")

        if matches_on:
            self.log("  → ENABLED")
            return True
        if matches_off:
            self.log("  → DISABLED")
            return False

        self.log("  → TRANSITIONAL (screen still loading)")
        return None

    def _ensure_super_raids_enabled(self):
        x = self.super_raids_coord[0]
        y = self.super_raids_coord[1]

        # Ждём пока экран загрузится — пиксель должен стать либо enabled, либо disabled
        max_wait = 5
        waited = 0
        state = None
        while waited < max_wait:
            state = self._read_super_raids_state()
            if state is not None:
                break
            sleep(0.5)
            waited += 0.5

        if state is None:
            self.log(f"WARNING: SUPER RAIDS pixel did not settle after {max_wait}s, forcing click")

        if state is True:
            self.log("SUPER RAIDS already enabled — no click needed")
            return True

        # Выключено или не определилось — кликаем
        self.log("SUPER RAIDS is OFF — clicking to enable")
        click(x, y)
        sleep(1)

        state = self._read_super_raids_state()
        if state is True:
            self.log("SUPER RAIDS enabled successfully after click")
            return True

        # Повторная попытка
        self.log("SUPER RAIDS still OFF after 1st click — retrying")
        click(x, y)
        sleep(1)

        state = self._read_super_raids_state()
        if state is True:
            self.log("SUPER RAIDS enabled successfully after 2nd click")
            return True

        self.log("ERROR: SUPER RAIDS failed to enable after 2 attempts")
        return False

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
            from helpers.battle_stats import record_win, record_loss
            profile = getattr(self.app, 'current_player_name', None)
            if res:
                record_win('iron_twins_fortress', profile_name=profile)
            else:
                record_loss('iron_twins_fortress', profile_name=profile)
            
            # Не устанавливаем completed по количеству побед — с SUPER RAIDS один бой может использовать несколько ключей
            # Завершение работы происходит только когда _check_refill() обнаружит запрос на покупку за рубины

        # Выходим из локации если цикл завершился без обнаружения запроса на покупку
        # (если запрос был обнаружен, выход уже выполнен в _check_refill())
        if not self.terminated and not self.completed:
            self.log("Exiting Iron Twins Fortress")
            dungeons_click_stage_select()
