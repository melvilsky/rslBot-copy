import re
import traceback

import cv2
import np
import pyautogui
import pytesseract
from PIL import Image

from helpers.logging_utils import is_debug_mode, log, log_save, sleep
from helpers.screen import axis_to_region, screenshot_to_image, show_image
from helpers.utils import get_higher_occurrence
from helpers.mouse import move_out_cursor
from helpers.vision import (
    find_bank_arena_classic,
    find_bank_arena_tag,
    find_doom_tower_golden_keys,
    find_doom_tower_silver_keys,
    find_faction_keys_bank,
    find_needle_energy_bank,
    find_needle_refill_plus,
)

TESSERACT_CONFIGS_DEFAULT = ['--psm 6 --oem 3']
TESSERACT_CONFIGS_DEALT_DAMAGE = [
    '--psm 1 --oem 3',
    '--psm 3 --oem 3',
    '--psm 4 --oem 3',
    '--psm 7 --oem 3',
    '--psm 8 --oem 3',
    '--psm 10 --oem 3',
]
TESSERACT_CONFIGS_RUN_COST = [
    '--psm 1 --oem 3',
    '--psm 3 --oem 3',
    '--psm 4 --oem 3',
    '--psm 5 --oem 3',
    '--psm 6 --oem 3',
    '--psm 7 --oem 3',
    '--psm 8 --oem 3',
    '--psm 9 --oem 3',
    '--psm 10 --oem 3',
    '--psm 11 --oem 3',
    '--psm 12 --oem 3',
    '--psm 13 --oem 3',
]
TESSERACT_CONFIGS_AVAILABLE_ENERGY = [
    '--psm 1 --oem 3',
    '--psm 3 --oem 3',
    '--psm 4 --oem 3',
    '--psm 6 --oem 3',
    '--psm 7 --oem 3',
    '--psm 8 --oem 3',
    '--psm 9 --oem 3',
    '--psm 10 --oem 3',
    '--psm 11 --oem 3',
    '--psm 12 --oem 3',
]
TESSERACT_CONFIGS_KEYS_BANK = [
    '--psm 1 --oem 3',
    '--psm 3 --oem 3',
    '--psm 4 --oem 3',
    '--psm 6 --oem 3',
    '--psm 7 --oem 3',
    '--psm 8 --oem 3',
    '--psm 9 --oem 3',
    '--psm 10 --oem 3',
    '--psm 11 --oem 3',
    '--psm 12 --oem 3',
]

def transform_image_accurate(img, value1, value2):
    thresh = cv2.threshold(img, value1, value2, cv2.THRESH_BINARY_INV)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    return cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

def transform_image_resource(img):
    return transform_image_accurate(img, 100, 220)

def transform_image_damage_dealt(img):
    return transform_image_accurate(img, 175, 255)

def transform_image_run_cost(img):
    return transform_image_accurate(img, 150, 255)

def transform_image_levels(img):
    return transform_image_accurate(img, 80, 230)

def transform_btn_primary(img):
    return transform_image_accurate(img, 150, 200)

def transform_btn_secondary(img):
    return transform_image_accurate(img, 110, 200)

def parse_dealt_damage(variants):
    def _parse(s):
        arr = re.split(r'\D+', s)
        # removing empty lines
        arr = list(filter(bool, arr))
        # taking only first 2 elements
        arr = arr[0:2]
        # joining to the one string
        str_damage = '.'.join(arr)
        int_damage = 0

        try:
            last_char = str_damage[len(str_damage) - 1]
            multiplier = s[s.index(last_char) + 1].upper()

            if str_damage:
                int_damage = float(str_damage)

            if multiplier in ['K', 'M', 'B']:
                if multiplier == 'K':
                    int_damage = int_damage / 1000
                elif multiplier == 'B':
                    int_damage = int_damage * 1000
                elif multiplier == 'M':
                    int_damage = int_damage
        except Exception:
            error = traceback.format_exc()
            log_save(error)

        return int_damage

    return list(map(lambda x: _parse(x), variants))

def parse_energy_cost(variants):
    extract_numbers = lambda x: [float(match.group()) for match in re.finditer(r'\d+\.?\d*', str(x))]
    res = [num for x in variants for num in extract_numbers(x)]
    return res

def parse_energy_bank(variants):
    # works with examples: 1234/130, 18/12 and etc
    extract_first_number = lambda x: int(re.search(r'(?<!\d)\d+(?=/\d+)', x.replace(',', '')).group()) if re.search(
        r'(?<!\d)\d+/\d+', x) else None

    # extracting Number elements
    res = list(map(extract_first_number, variants))
    # removing None elements
    res = list(filter(lambda x: x is not None, res))
    return res

def parse_levels(data):
    levels = []

    for item in data:
        # Extract numeric values from the item
        numbers = ''.join(filter(lambda x: x.isdigit() or x == '/', item))

        # Check if there are any numeric values extracted
        if numbers:
            levels.append(numbers)

    return levels

def read_text(
        region,
        configs=None,
        timeout=0.1,
        parser=None,
        update_screenshot=False,
        debug=False,
        title='match',
        grayscale=True,
        scale=2,
        transform_predicate=None,
        lang=None
):
    # debug = True- removed
    # If debug is explicitly passed as False (default), check global setting
    if not debug:
        debug = is_debug_mode()
        
    res = []
    screenshot = None
    if configs is None:
        configs = TESSERACT_CONFIGS_DEFAULT

    if lang is None:
        lang = 'eng'

    try:
        if not update_screenshot:
            screenshot = pyautogui.screenshot(region=region)
    except ValueError:
        log_save(str(region))

    for i in range(len(configs)):
        if update_screenshot:
            screenshot = pyautogui.screenshot(region=region)

        img = screenshot_to_image(screenshot)
        if grayscale:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        if type(scale) is int or type(scale) is float:
            img = cv2.resize(img, None, fx=int(scale), fy=int(scale))

        if transform_predicate is not None:
            img = transform_predicate(img)

        # Debug
        # Debug
        if debug and i == 0:
            show_image(image=img, title=f"read_text_{title}")

        text = pytesseract.image_to_string(img, config=configs[i], lang=lang)
        res.append(text.strip())
        sleep(timeout)

    # log(res)
    if parser:
        res = parser(res)
    # log(res)

    return get_higher_occurrence(res)

def read_dealt_damage(region=None):
    log('Computing dealt damage...')
    if region is None:
        region = [190, 150, 550, 50]

    move_out_cursor()
    return read_text(
        configs=TESSERACT_CONFIGS_DEALT_DAMAGE,
        region=region,
        timeout=.5,
        update_screenshot=True,
        parser=parse_dealt_damage,
        transform_predicate=transform_image_damage_dealt,
        scale=7,
    )

def read_run_cost(region=None, scale=4):
    log('Computing run cost...')

    x1 = 740
    y1 = 477
    x2 = 852
    y2 = 494

    if not region:
        region = axis_to_region(x1, y1, x2, y2)

    return read_text(
        region=region,
        parser=parse_energy_cost,
        transform_predicate=transform_image_run_cost,
        scale=scale,
        debug=False,
    )

def get_resource_region(needle_predicate, needle_width, predicted_offset_x=150):
    region = None
    IMG_REFILL_SIDE = 12

    position_energy = needle_predicate()
    if position_energy:
        x1_refill_button = position_energy[0] - predicted_offset_x + needle_width
        region_refill_button = [x1_refill_button, 38, 100, 18]
        position_refill_button = find_needle_refill_plus(region=region_refill_button)
        if position_refill_button:
            x1 = int(position_refill_button[0] + IMG_REFILL_SIDE)
            x2 = int(position_energy[0] - needle_width / 2)
            region = axis_to_region(x1, 38, x2, 56)

    return tuple(round(num) for num in region) if region is not None else region

def read_available_energy(region=None):
    log('Computing available energy...')
    if not region:
        region = get_resource_region(needle_predicate=find_needle_energy_bank, needle_width=17)

    return read_text(
        region=region,
        parser=parse_energy_bank,
        transform_predicate=transform_image_resource,
        scale=4,
        debug=False
    )

def read_keys_bank(region=None, key=None):
    log(f"Computing{' ' + key if bool(key) else ''} keys bank...")

    if not region:
        region = get_resource_region(needle_predicate=find_faction_keys_bank, needle_width=24)

    return read_text(
        region=region,
        parser=parse_energy_bank,
        transform_predicate=transform_image_resource,
        scale=4,
        debug=False
    )

def read_bank_arena_classic(region=None):
    log("Computing arena_classic coins...")

    if not region:
        region = get_resource_region(needle_predicate=find_bank_arena_classic, needle_width=22)

    return read_text(
        region=region,
        parser=parse_energy_bank,
        transform_predicate=transform_image_resource,
        scale=4,
        debug=False
    ), region

def read_bank_arena_tag(region=None):
    log("Computing 'arena_tag' coins...")

    if not region:
        region = get_resource_region(needle_predicate=find_bank_arena_tag, needle_width=22)

    return read_text(
        region=region,
        parser=parse_energy_bank,
        transform_predicate=transform_image_resource,
        scale=4,
        debug=False
    ), region

def read_doom_tower_keys(key_type='golden'):
    position = None
    x1 = 0
    x2 = 0

    if key_type == 'golden':
        position = find_doom_tower_golden_keys()
        x1 = 618
    elif key_type == 'silver':
        position = find_doom_tower_silver_keys()
        x1 = 730

    if position:
        x1 = int(position[0] - 68)
        x2 = int(position[0] - 12)

    region = axis_to_region(x1, 38, x2, 56)

    return read_keys_bank(region=region, key=key_type)
