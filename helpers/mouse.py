import random
import time

import pyautogui

from helpers.logging_utils import log, sleep
from helpers.screen import debug_click_coordinates
from helpers.vision import pixel_check_new, pixels_wait

def track_mouse_position():
    try:
        while True:
            sleep(2)
            x, y = pyautogui.position()
            r, g, b = pyautogui.pixel(x, y)
            positionStr = 'X: ' + str(x).rjust(4) + ' Y: ' + str(y).rjust(4)
            print(positionStr + ' | RGB(' + str(r) + ', ' + str(g) + ', ' + str(b) + ')')
    except KeyboardInterrupt:
        print('\n')

def click(x, y, smart=False, timeout=0.5, interval=2, random_click=None):
    # Отладка: логируем координаты и сохраняем скриншот
    # Отладка: логируем координаты и сохраняем скриншот
    # from constants.index import DEBUG_MODE - removed
    if is_debug_mode():
        log(f"DEBUG click: coordinates [{x}, {y}]")
        debug_click_coordinates(x, y, label="click")
    
    rgb = pyautogui.pixel(x, y) if smart else None

    if random_click is not None:
        max_random = random_click if type(random_click) is int else 5
        x += random.randint(1, max_random)
        y += random.randint(1, max_random)
        if is_debug_mode():
            log(f"DEBUG click: after random offset [{x}, {y}]")
            debug_click_coordinates(x, y, label="click-random")

    pyautogui.click(x, y)

    if smart and rgb:
        counter = 0
        while pixel_check_new([x, y, rgb]) and counter < 3:
            if counter == 0:
                sleep(timeout)
            log('Delay occurred, re-trying to click again')
            click(x, y)
            sleep(interval)
            counter += 1

def click_alt(x, y, duration=1, moving=True):
    if moving:
        pyautogui.moveTo(x, y, duration)
    pyautogui.click(x, y)

def random_easying():
    return random.choice([
        pyautogui.easeInQuad,
        pyautogui.easeOutQuad,
        pyautogui.easeInOutQuad,
        pyautogui.easeInBounce,
        pyautogui.easeInElastic
    ])

def await_click(pixels, msg=None, timeout=5, mistake=0, wait_limit=None, smart=False):
    if is_debug_mode():
        _tag = f" ({msg})" if msg else ""
        log(f"DEBUG await_click{_tag}: waiting for {len(pixels)} pixel(s)")

    res = pixels_wait(pixels, msg=msg, timeout=timeout, mistake=mistake, wait_limit=wait_limit)

    clicked = False
    for i in range(len(res)):
        el = res[i]
        if el:
            pixel = pixels[i]
            x = pixel[0]
            y = pixel[1]

            if is_debug_mode():
                log(f"DEBUG await_click{_tag}: clicking [{x}, {y}]")

            click(x, y, smart=smart)
            time.sleep(.3)
            clicked = True
            break

    if is_debug_mode() and not clicked:
        log(f"DEBUG await_click{_tag}: no matching pixel found, no click performed")

    return res

def move_out_cursor():
    # @TODO Refactor
    pyautogui.moveTo(1000, 1000)

def tap_to_continue(times=1, wait_before=2, wait_after=2, x=420, y=490):
    sleep(wait_before)

    for i in range(times):
        click(x, y)
        sleep(1)

    sleep(wait_after)

def swipe(direction, x1, y1, distance, speed=2, sleep_after_end=1.5, instant_move=False):
    # @TODO The function does not work perfect
    if instant_move:
        pyautogui.moveTo(x1, y1)
    else:
        sleep(1)
        click(x1, y1)
        sleep(0.5)

    pyautogui.mouseDown()

    if direction == 'top':
        pyautogui.moveTo(x1, y1 + distance, speed)
    elif direction == 'bottom':
        pyautogui.moveTo(x1, y1 - distance, speed)
    elif direction == 'right':
        pyautogui.moveTo(x1 - distance, y1, speed)
    elif direction == 'left':
        pyautogui.moveTo(x1 + distance, y1, speed)

    sleep(1)
    pyautogui.mouseUp()
    sleep(sleep_after_end)

def swipe_new(direction, x1, y1, distance, speed=2, sleep_after_end=0, instant_move=False):
    # @TODO The function does not work perfect
    if instant_move:
        pyautogui.moveTo(x1, y1)
    else:
        sleep(1)
        click(x1, y1)
        sleep(0.5)

    pyautogui.mouseDown()
    sleep(0.5)

    if direction == 'top':
        pyautogui.moveTo(x1, y1 + distance, speed)
    elif direction == 'bottom':
        pyautogui.moveTo(x1, y1 - distance, speed)
    elif direction == 'right':
        pyautogui.moveTo(x1 - distance, y1, speed)
    elif direction == 'left':
        pyautogui.moveTo(x1 + distance, y1, speed)

    sleep(0.5)
    pyautogui.mouseUp()
    if sleep_after_end > 0:
        sleep(sleep_after_end)

def click_detected_button(button):
    x = button['region'][0]
    y = button['region'][1]
    click(x, y, random_click=10, smart=True)

