import json
import os

import pyautogui

from helpers.logging_utils import log, sleep
from helpers.mouse import await_click, click, random_easying
from helpers.popups import click_on_progress_info
from helpers.vision import pixel_check_new, pixels_wait

def waiting_battle_end_regular(msg, timeout=5, x=20, y=46):
    return pixel_wait(msg, x, y, [255, 255, 255], timeout, mistake=10)

def claim_rewards(x, y, fixed_pixel=None, limit=5, x_fixed=50, y_fixed=50, y_tap=444):
    # y_tap: 490 ???
    if fixed_pixel is None:
        rgb_fixed = pyautogui.pixel(x_fixed, y_fixed)
        pixel_fixed = [x_fixed, y_fixed, rgb_fixed]

        # click on the claim reward area
        click(x, y)
        sleep(1)

        # doing 'tap_to_continue' until 'pixel_fixed' is not exists
        while not pixel_check_new(pixel_fixed, mistake=0) and limit > 0:
            tap_to_continue(wait_before=1, wait_after=1, y=y_tap)
            limit -= 1

def dungeons_scroll(direction='bottom', times=2):
    x = 500
    y_axis = [510, 90]

    if direction == 'top':
        y_axis.reverse()

    for index in range(times):
        pyautogui.moveTo(x, y_axis[0], .5, random_easying())
        pyautogui.dragTo(x, y_axis[1], duration=.4)
        sleep(1.5)

    sleep(2)

def dungeons_replay():
    sleep(0.5)
    click(500, 480, smart=True)
    sleep(0.3)

def dungeons_start(x=850, y=475):
    BUTTON_START = [x, y, [187, 130, 5]]
    await_click([BUTTON_START], msg="await 'Button Start'", timeout=1, mistake=10, wait_limit=2)

def dungeons_click_stage_select():
    # click on the "Stage selection"
    sleep(2)
    click(820, 55)
    sleep(2)

def dungeons_continue_battle():
    log('Function: dungeons_continue_battle')
    # @TODO Duplication
    STAGE_ENTER = [890, 200, [93, 25, 27]]
    if pixels_wait([STAGE_ENTER], msg="await 'Stage enter'", mistake=10, wait_limit=2)[0]:
        # click on 'Start'
        dungeons_start()
    else:
        # click on 'Replay'
        dungeons_replay()
    sleep(1)

def dungeons_is_able():
    log('Function: dungeons_is_able')
    # @TODO Duplication
    STAGE_ENTER = [890, 200, [93, 25, 27]]
    return pixel_check_new(STAGE_ENTER, mistake=10)

def dungeon_select_difficulty(difficulty, mistake=5):
    # rgb background exists in dungeon related locations only
    DIFFICULTY_SELECT = [144, 490, [13, 35, 45]]
    RGB_DIFFICULTY = [34, 47, 60]
    DIFFICULTY_NORMAL = [144, 394, RGB_DIFFICULTY]
    DIFFICULTY_HARD = [144, 450, RGB_DIFFICULTY]
    DUNGEON_DIFFICULTY_NORMAL = 'normal'
    DUNGEON_DIFFICULTY_HARD = 'hard'
    DIFFICULTIES = {
        DUNGEON_DIFFICULTY_NORMAL: DIFFICULTY_NORMAL,
        DUNGEON_DIFFICULTY_HARD: DIFFICULTY_HARD,
    }

    if difficulty in DIFFICULTIES:
        await_click([DIFFICULTY_SELECT], mistake=mistake)
        await_click([DIFFICULTIES[difficulty]], mistake=mistake)

def checkbox_toggle(x, y, state=True):
    # @TODO Duplication
    STAGE_ENTER = [890, 200, [93, 25, 27]]
    RGB_CHECK_ICON = [108, 237, 255]

    pixel = [x, y, RGB_CHECK_ICON]
    if pixels_wait([STAGE_ENTER], msg="Waiting for entering the stage", mistake=10, wait_limit=2)[0]:
        is_checked = pixel_check_new(pixel, mistake=10)
        if state and not is_checked or not state and is_checked:
            x = pixel[0]
            y = pixel[1]
            click(x, y)
            sleep(.3)

def _read_pixel_color(x, y):
    """Читает реальный цвет пикселя и возвращает [r, g, b]"""
    p = pyautogui.pixel(x, y)
    return [p[0], p[1], p[2]]

def _is_super_raid_enabled(x, y, rgb_enabled, rgb_disabled, mistake):
    """
    Проверяет состояние SUPER RAIDS, логируя реальный цвет.
    Returns: True если включено, False если выключено
    """
    actual = _read_pixel_color(x, y)
    diff_enabled = [abs(actual[i] - rgb_enabled[i]) for i in range(3)]
    diff_disabled = [abs(actual[i] - rgb_disabled[i]) for i in range(3)]
    max_diff_enabled = max(diff_enabled)
    max_diff_disabled = max(diff_disabled)

    matches_enabled = all(d <= mistake for d in diff_enabled)
    matches_disabled = all(d <= mistake for d in diff_disabled)

    log(f"SUPER RAIDS pixel at ({x}, {y}):")
    log(f"  Actual color:   {actual}")
    log(f"  Enabled color:  {rgb_enabled} (diff={diff_enabled}, max={max_diff_enabled}, match={matches_enabled})")
    log(f"  Disabled color: {rgb_disabled} (diff={diff_disabled}, max={max_diff_disabled}, match={matches_disabled})")

    if matches_enabled:
        log("  Result: ENABLED")
        return True

    log("  Result: DISABLED")
    return False

def enable_super_raid():
    """
    Включает SUPER RAIDS с проверкой состояния перед и после клика.
    Ждёт загрузки экрана (пиксель должен стать стабильным — enabled или disabled).
    Координаты и цвета из coordinates/iron_twins.json
    Enabled:  (654, 336) RGB (108, 237, 255)
    Disabled: (654, 336) RGB (8, 20, 24)
    """
    log('Function: enable_super_raid')

    x, y = 654, 336
    rgb_enabled = [108, 237, 255]
    rgb_disabled = [8, 20, 24]
    mistake = 10

    try:
        coords_path = os.path.join('coordinates', 'iron_twins.json')
        if os.path.exists(coords_path):
            with open(coords_path, 'r', encoding='utf-8') as f:
                coord = json.load(f).get('super_raids', {})
                x = coord.get('x', x)
                y = coord.get('y', y)
                rgb_enabled = coord.get('rgb', rgb_enabled)
                rgb_disabled = coord.get('rgb_disabled', rgb_disabled)
                mistake = coord.get('mistake', mistake)
    except Exception as e:
        log(f'WARNING: Failed to load iron_twins.json: {e}, using defaults')

    def check_state():
        """Returns: True=enabled, False=disabled, None=transitional"""
        actual = _read_pixel_color(x, y)
        diff_on = [abs(actual[i] - rgb_enabled[i]) for i in range(3)]
        diff_off = [abs(actual[i] - rgb_disabled[i]) for i in range(3)]
        matches_on = all(d <= mistake for d in diff_on)
        matches_off = all(d <= mistake for d in diff_off)

        log(f"SUPER RAIDS pixel ({x}, {y}): actual={actual}")
        log(f"  vs enabled  {rgb_enabled}: diff={diff_on}, match={matches_on}")
        log(f"  vs disabled {rgb_disabled}: diff={diff_off}, match={matches_off}")

        if matches_on:
            log("  → ENABLED")
            return True
        if matches_off:
            log("  → DISABLED")
            return False
        log("  → TRANSITIONAL (screen still loading)")
        return None

    # Ждём пока экран загрузится — пиксель должен стать либо enabled, либо disabled
    max_wait = 5
    waited = 0
    state = None
    while waited < max_wait:
        state = check_state()
        if state is not None:
            break
        sleep(0.5)
        waited += 0.5

    if state is None:
        log(f'WARNING: pixel did not settle after {max_wait}s, forcing click')

    if state is True:
        log('SUPER RAIDS already enabled — no click needed')
        return True

    log('SUPER RAIDS is OFF — clicking to enable')
    click(x, y)
    sleep(1)

    state = check_state()
    if state is True:
        log('SUPER RAIDS enabled successfully after click')
        return True

    log('SUPER RAIDS still OFF after 1st click — retrying')
    click(x, y)
    sleep(1)

    state = check_state()
    if state is True:
        log('SUPER RAIDS enabled successfully after 2nd click')
        return True

    log('ERROR: SUPER RAIDS failed to enable after 2 attempts')
    return False

def disable_auto_climb():
    log('Function: disable_auto_climb')
    checkbox_toggle(710, 410, state=False)

def enable_start_on_auto():
    log('Function: enable_start_on_auto')
    P_START_ON_AUTO_CHECKBOX = [710, 406, [13, 58, 81]]
    await_click([P_START_ON_AUTO_CHECKBOX], mistake=10, wait_limit=1)

def enable_auto_play(*args):
    log('Function: enable_auto_play')
    AUTO_PLAY_BUTTON = [49, 486]
    sleep(2)
    click(AUTO_PLAY_BUTTON[0], AUTO_PLAY_BUTTON[1])

def detect_pause_button():
    log('Function: detect_pause_button')
    # @TODO Duplicate
    BUTTON_PAUSE_ICON = [866, 66, [216, 206, 156]]
    return pixel_check_new(BUTTON_PAUSE_ICON, mistake=10)

def calculate_win_rate(w, l):
    t = w + l
    wr = w * 100 / t
    wr_str = str(round(wr)) + '%'
    return wr_str

def battles_click():
    battle_button = find_needle_battles()
    if battle_button is not None:
        x = battle_button[0]
        y = battle_button[1]
        pyautogui.click(x, y)
    else:
        log('Battle button is not found')

def is_team_provided(array):
    # array = [[1, 2], [3, 4]]
    RGB_NO_TEAM_PROVIDED = [49, 54, 49]
    list_axis = list(map(lambda a: a + [RGB_NO_TEAM_PROVIDED], array))
    return pixels_every(list_axis, lambda p: not pixel_check_new(p))

