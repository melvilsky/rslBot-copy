import os
from pathlib import Path

import cv2
import np
import pyautogui
from pyautogui import ImageNotFoundException as ImageNotFoundExceptionPyautogui
from pyscreeze import ImageNotFoundException

from helpers.logging_utils import is_debug_mode, log, log_save, sleep
from helpers.screen import axis_to_region, debug_save_screenshot

R_DEFAULT = [0, 0, 906, 533]

def is_close(box1, box2, threshold=5):
    """Check if two boxes are close to each other within a certain threshold."""
    return (abs(box1.left - box2.left) < threshold and
            abs(box1.top - box2.top) < threshold)

def is_close_in_boxes(box, boxes, threshold=20):
    res = False
    for i in range(len(boxes)):
        if is_close(box, boxes[i], threshold):
            res = True
            break
    return res

def filter_close_boxes(boxes, threshold=10):
    """Filter out boxes that are very close to each other."""
    filtered_boxes = []
    for box in boxes:
        if all(not is_close(box, filtered_box, threshold) for filtered_box in filtered_boxes):
            filtered_boxes.append(box)
    return filtered_boxes

def capture_by_source(src, region, confidence=.8, grayscale=False, return_boxes=False, flip=False):
    src = str(Path(src).resolve())

    if flip:
        original_img = cv2.imread(src)
        flip_image = cv2.flip(original_img, 1)
        flipped_needle_img_rgb = cv2.cvtColor(flip_image, cv2.COLOR_BGR2RGB)
        # Convert the flipped image to a Pillow Image
        src = Image.fromarray(flipped_needle_img_rgb)

    try:
        if return_boxes:
            instances = list(
                pyautogui.locateAllOnScreen(src, region=region, confidence=confidence, grayscale=grayscale))
            # Get the center points of all instances
            # center_points = [pyautogui.center(instance) for instance in instances]

            # Filter out close instances (Boxes)
            filtered_instances = filter_close_boxes(instances)

            return filtered_instances
        else:
            return pyautogui.locateCenterOnScreen(src, region=region, confidence=confidence, grayscale=grayscale)
    except ImageNotFoundException:
        pass
    except ImageNotFoundExceptionPyautogui:
        pass

    return None

def pixel_check_new(pixel, mistake=10, label=None):
    x = pixel[0]
    y = pixel[1]
    rgb = pixel[2]
    p = pyautogui.pixel(x, y)
    result = rgb_check(p, rgb, mistake=mistake)

    if is_debug_mode():
        actual_rgb = [p[0], p[1], p[2]]
        diff = [abs(actual_rgb[i] - rgb[i]) for i in range(3)]
        tag = f" ({label})" if label else ""
        log(f"DEBUG pixel_check{tag}: [{x}, {y}] expected={rgb} actual={actual_rgb} diff={diff} mistake={mistake} match={result}")

        throttle_key = label or f"{x}_{y}"
        now = time.time()
        last = _pixel_check_screenshot_times.get(throttle_key, 0)
        if now - last >= 2.0:
            _pixel_check_screenshot_times[throttle_key] = now
            debug_pixel_check_screenshot(x, y, rgb, actual_rgb, result, label=label)

    return result

def rgb_check(rgb_1, rgb_2, mistake=0):
    if all(abs(rgb_1[i] - rgb_2[i]) <= mistake for i in range(3)):
        return True
    return False

def pixels_check(msg, pixels, mistake=0):
    length = len(pixels)
    log('Checking some of ' + str(length) + ' pixels: ' + msg)
    res = []

    for i in range(len(pixels)):
        res.append(pixel_check_new(pixels[i], mistake=mistake))

    return res

def pixel_wait(msg, x, y, rgb, timeout=5, mistake=0):
    log('Waiting pixel: ' + msg)
    while pixel_check_new([x, y, rgb], mistake=mistake) is False:
        sleep(timeout)
    log('Found  pixel: ' + msg)
    return True

def pixels_wait(pixels, msg=None, timeout=5, mistake=0, wait_limit=None, debug=False):
    length = len(pixels)
    pixels_str = 'pixel'
    if length > 1:
        pixels_str = 'pixels'
    if msg is not None:
        log(f"Waiting {pixels_str}: {msg}")

    if is_debug_mode():
        for idx, px in enumerate(pixels):
            log(f"DEBUG pixels_wait: pixel[{idx}] = [{px[0]}, {px[1]}, {px[2]}] mistake={mistake}")

    def restart():
        res = []
        for i in range(len(pixels)):
            res.append(pixel_check_new(pixels[i], mistake=mistake))
        return res

    checked_pixels = restart()
    counter = 0
    has_wait_limit = type(wait_limit) is int or type(wait_limit) is float

    while checked_pixels.count(False) == length:
        counter += timeout
        checked_pixels = restart()
        if has_wait_limit and counter >= wait_limit:
            break

        log(str(counter) + ' seconds left')
        sleep(timeout)

    if is_debug_mode():
        found_indices = [i for i, v in enumerate(checked_pixels) if v]
        _tag = f" ({msg})" if msg else ""
        if found_indices:
            log(f"DEBUG pixels_wait{_tag}: found pixel(s) at index {found_indices}")
        else:
            log(f"DEBUG pixels_wait{_tag}: TIMEOUT, no pixel matched after {counter}s")
        debug_save_screenshot(suffix_name=f"pixels_wait-{msg or 'unnamed'}")

    if debug and has_wait_limit and counter >= wait_limit:
        debug_save_screenshot(suffix_name=msg)

    return checked_pixels

def pixels_wait_every():
    return 0

def await_needle(image_name, region=None, confidence=None, scale=None, timeout=.5, wait_limit=30):
    counter = 0
    needle_image = find_needle(image_name, region=region, confidence=confidence, scale=scale)
    while needle_image is None and counter < wait_limit:
        needle_image = find_needle(image_name, region=region, confidence=confidence, scale=scale)
        sleep(timeout)
        counter += timeout
    return needle_image

def find_needle(
        image_name,
        region=None,
        confidence=None,
        scale=None,
        retries=0,
        retry_interval=1,
        should_move_out_cursor=False,
        return_boxes=False,
        flip=False,
):
    if region is None:
        region = [0, 0, 900, 530]
        # region = [0, 0, 1000, 1500]
        # region = [0, 0, 1900, 1000]
    if confidence is None:
        confidence = .8
    if should_move_out_cursor:
        move_out_cursor()

    path_image = str(Path.cwd() / 'images/needles' / image_name)

    if scale:
        physical_image = cv2.imread(path_image)
        _height, _width = physical_image.shape
        # Scale the physical image to match the screen size
        # Calculate the new dimensions
        width = _width * scale
        height = _height * scale
        # Resize the image with Lanczos interpolation
        # scaled_image = image.resize((new_width, new_height), Image.LANCZOS)
        scaled_image = cv2.resize(physical_image, (width, height))
        path_image = scaled_image

    # For test
    # show_pyautogui_image(pyautogui.screenshot(region=region))

    def _find_needles():
        return capture_by_source(path_image, region, confidence=confidence, return_boxes=return_boxes, flip=flip)

    position = _find_needles()
    while retries > 0 \
            and (position is None or type(position) is list and not len(position)):
        position = _find_needles()
        retries -= 1
        sleep(retry_interval)

    return position

def find_needle_refill_ruby():
    return find_needle('refill/refill_ruby.jpg', axis_to_region(320, 320, 640, 440))

def find_needle_refill_button(region):
    return find_needle('refill_button.jpg', region)

def find_needle_battles():
    return find_needle('battles.jpg', axis_to_region(730, 430, 900, 530))

def find_needle_close_popup():
    return find_needle('close.png')

def find_needle_burger():
    return find_needle('burger.jpg')

def find_needle_energy_bank(region=None):
    if not region:
        region = axis_to_region(220, 32, 790, 68)

    return find_needle('bank_energy.jpg', region)

def find_faction_keys_bank(region=None):
    if not region:
        region = [0, 32, 900, 50]

    return find_needle('bank_faction_keys.jpg', region, confidence=.6)

def find_bank_arena_classic(region=None):
    if not region:
        region = [0, 30, 906, 50]

    return find_needle('bank_arena_classic.jpg', region=region)

def find_bank_arena_tag(region=None):
    if not region:
        region = R_DEFAULT

    return find_needle('bank_arena_tag.jpg', region=region)

def find_needle_refill_plus(region):
    return find_needle('refill_plus.jpg', region=region)

def find_needle_energy_cost(region=None):
    if not region:
        region = axis_to_region(720, 460, 860, 505)

    return find_needle('energy_cost.jpg', region)

def find_needle_red_dot(region=None, confidence=None):
    return find_needle('red_dot.jpg', region=region, confidence=confidence)

def find_needle_arena_reward(region=None):
    if not region:
        region = axis_to_region(177, 424, 880, 450)

    return find_needle('arena_reward.jpg', region=region, confidence=.6)

def find_guardian_ring():
    return find_needle('guardian_ring_2.jpg', confidence=.4)

def find_doom_tower_golden_keys():
    return find_needle('doom_tower/bank_keys_golden.jpg', confidence=.65)

def find_doom_tower_silver_keys():
    return find_needle('doom_tower/bank_keys_silver.jpg', confidence=.65)

def find_doom_tower_next_floor_regular(region=None):
    if region is None:
        region = [130, 70, 700, 460]
    return find_needle('doom_tower/next_floor_regular.jpg', confidence=.7, region=region)

def find_doom_tower_locked_floor(region=None):
    if region is None:
        region = R_DEFAULT
    return find_needle('doom_tower/floor_locked.jpg', confidence=.7, region=region)

def find_doom_tower_edge_top(region=None):
    if region is None:
        region = R_DEFAULT
    return find_needle('doom_tower/swipe_edge_top.jpg', confidence=.9, region=region)

def find_doom_tower_edge_bottom(region=None):
    if region is None:
        region = R_DEFAULT
    return find_needle('doom_tower/swipe_edge_bottom.jpg', confidence=.9, region=region)

def find_hero_filter_default(region=None, confidence=.7, retries=None):
    return find_needle('filter.jpg', region=region, confidence=confidence, retries=retries)

def find_hero_filter_small(region=None, confidence=.7, retries=None):
    return find_needle('filter_small.png', region=region, confidence=confidence, retries=retries)

def find_hero_slot_empty(region):
    return find_needle('hero_slot_empty.jpg', region=region, confidence=.65, retries=2)

def find_popup_error_detector():
    return find_needle('popups/popup_error.jpg', region=[425, 110, 60, 150])

def find_button(variant, size='big', region=None, return_boxes=False):
    # variants: primary | secondary | big | large
    if region is None:
        region = [0, 0, 906, 533]

    # Should handle right 'variant' and 'size'
    src = f"popups/button_{variant}_{size}.jpg"

    if src is not None:
        return find_needle(src, region=region, return_boxes=return_boxes)

    return src

def find_indicator_active():
    region = [250, 360, 150, 100]
    return find_needle('live_arena/indicator_active.jpg', confidence=.6, region=region)

def find_indicator_inactive():
    region = [250, 360, 150, 100]
    return find_needle('live_arena/indicator_inactive.jpg', confidence=.6, region=region)

def find_victory_opponent_left(region=None):
    if region is None:
        region = [390, 32, 160, 50]
    return find_needle('live_arena/victory_opponent_left.jpg', confidence=.7, region=region)

def find_checkbox_locked(region=None):
    if region is None:
        region = R_DEFAULT
    return find_needle('checkbox_locked.jpg', confidence=.8, region=region)

def find_needle_popup_attention(region=None):
    if region is None:
        region = [0, 0, 906, 533]
    return find_needle('popups/popup_attention.jpg', region)

def find_team_preset_checked(region):
    return find_needle('team_preset_checked.jpg', region, confidence=.9)

def find_team_preset_disabled(region):
    return find_needle('team_preset_disabled.jpg', region, confidence=.9)

def find_team_preset_locked(region):
    return find_needle('team_preset_locked.jpg', region)

def find_boss_reward_crate(region=None):
    if region is None:
        region = [0, 0, 906, 533]
    return find_needle('boss_crate.jpg', region)

def detect_same_variant_buttons_and_return_one(index=0, length=1):
    # ATTENTION -> NOT RELIABLE APPROACH
    if find_popup_error_detector():
        buttons = detect_buttons()
        buttons_len = len(buttons)
        if buttons_len and buttons_len == length:
            for b in range(len(buttons)):
                if buttons[b]['variant'] != 'secondary':
                    return False

            return buttons[index]

    return False

def pixels_some(pixels, predicate):
    res = False
    for i in range(len(pixels)):
        _p = pixels[i]
        if predicate(_p):
            res = True
            break
    return res

def pixels_every(pixels, predicate):
    res = True
    for i in range(len(pixels)):
        _p = pixels[i]
        if not predicate(_p):
            res = False
            break
    return res

def same_pixels_line(pixel, long=3, axis='x'):
    _el = copy.copy(pixel)
    acc = []
    for i in range(long):
        acc.append(copy.copy(_el))
        if axis == 'x':
            _el[0] += 1
        elif axis == 'y':
            _el[1] += 1
    return acc

def same_pixels_line_list(pixels, long=3, axis='x'):
    return list(map(lambda el: pixels_every(
        same_pixels_line(el, long=long, axis=axis), lambda p: pixel_check_new(p, mistake=5)
    ), pixels)).count(True) == len(pixels)

def detect_buttons(confidence=.7, crop=5, lang=None):
    from helpers.ocr import read_text, transform_btn_primary, transform_btn_secondary

    buttons_data = [
        {
            'needle': 'popups/button_primary_generic.jpg',
            'transform_predicate': transform_btn_primary,
            'variant': 'primary',
            'width': 180,
            'height': 54,
        },
        {
            'needle': 'popups/button_secondary_generic.jpg',
            'transform_predicate': transform_btn_secondary,
            'variant': 'secondary',
            'width': 180,
            'height': 54,
        },
    ]

    buttons = []
    boxes = []
    for i in range(len(buttons_data)):
        _needle = buttons_data[i]['needle']
        _transform_predicate = buttons_data[i]['transform_predicate']
        _variant = buttons_data[i]['variant']
        _width = buttons_data[i]['width']
        _height = buttons_data[i]['height']

        boxes_origin = find_needle(_needle, confidence=confidence, return_boxes=True)

        if boxes_origin and len(boxes_origin):

            for j in range(len(boxes_origin)):
                if not is_close_in_boxes(boxes_origin[j], boxes):
                    boxes.append(boxes_origin[j])
                    x = int(boxes_origin[j].left)
                    y = int(boxes_origin[j].top)

                    _region = [x + crop * 2, y, _width - crop * 4, _height]
                    _text = read_text(region=_region, transform_predicate=_transform_predicate, lang=lang)
                    if _text:
                        buttons.append({
                            'text': _text.lower(),
                            'variant': _variant,
                            'region': _region
                        })

    return buttons

def find_detected_button(button_for_click, buttons):
    res = None
    if len(buttons):
        for i in range(len(buttons)):
            button = buttons[i]
            for k, v in button_for_click.items():

                # @TODO Test
                # if button.get(k) == 're-log in':
                #     button[k] = '123123@!#re-log invqwev'

                if button.get(k) and v in button.get(k):
                    res = button
                    log(f"Found detected button with the text '{button['text']}'")

                    break
    return res

