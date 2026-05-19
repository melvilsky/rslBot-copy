import os
from pathlib import Path

import cv2
import np
import pyautogui
from PIL import Image

from helpers.logging_utils import folder_ensure, format_string_for_log, get_time_for_log, is_debug_mode, log

_pixel_check_screenshot_times = {}

def test_screenshot(region):
    iml = pyautogui.screenshot(region=region)
    if iml is not None:
        iml.save(r"D:\ComputerVision\bot\test_screenshot.png")
        log('test_screenshot.png has been updated')

def debug_save_screenshot(
        region=None,
        suffix_name=None,
        output=None,
        quality=75,
        ext='jpg',
        x_center=False,
        y=222
):
    R_WINDOW_DEFAULT = [0, 0, 906, 533]
    if not region:
        # game window height includes top-bar height: 32px
        region = R_WINDOW_DEFAULT

    # for capturing small needles
    if x_center:
        region[0] = int(R_WINDOW_DEFAULT[2] / 2 - region[2] / 2)
        region[1] = y

    output_debug = Path('debug/screenshots')

    time = get_time_for_log(s='-')
    folder_ensure(output_debug)
    file_name = format_string_for_log(f"{time}-{str(suffix_name).lower()}" if suffix_name else time)
    screenshot = pyautogui.screenshot(region=region)
    screenshot.save(str(output_debug / f"{file_name}.{ext}"), quality=quality)

def draw_debug_grid(img_np, gap_size=100):
    """Рисует сетку с координатами поверх изображения (BGR numpy array)."""
    height, width = img_np.shape[:2]
    grid_color = (0, 255, 150)  # зелёный (BGR)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.4
    font_color = (0, 255, 150)

    for gx in range(0, width, gap_size):
        cv2.line(img_np, (gx, 0), (gx, height), grid_color, 1)
    for gy in range(0, height, gap_size):
        cv2.line(img_np, (0, gy), (width, gy), grid_color, 1)

    for gy in range(0, height, gap_size):
        for gx in range(0, width, gap_size):
            cx = int(gx + gap_size / 2)
            cy = int(gy + gap_size / 2)
            txt = f"({cx},{cy})"
            ts = cv2.getTextSize(txt, font, font_scale, 1)[0]
            tx = gx + (gap_size - ts[0]) // 2
            ty = gy + (gap_size + ts[1]) // 2
            cv2.putText(img_np, txt, (tx, ty), font, font_scale, font_color, 1, cv2.LINE_AA)

    return img_np

def debug_click_coordinates(x, y, label="click", region=None, grid=False):
    """
    Сохраняет скриншот с отмеченной точкой клика для отладки.
    
    Args:
        x, y: координаты клика
        label: метка для имени файла
        region: область скриншота [x, y, width, height], если None - 200x200 вокруг точки
        grid: если True — рисует сетку с координатами (шаг 100px)
    """
    try:
        if region is None:
            margin = 100
            screen_width, screen_height = pyautogui.size()
            left = max(0, x - margin)
            top = max(0, y - margin)
            right = min(screen_width, x + margin)
            bottom = min(screen_height, y + margin)
            region = [left, top, right - left, bottom - top]
        
        screenshot = pyautogui.screenshot(region=region)
        img_np = np.array(screenshot)
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        if grid:
            draw_debug_grid(img_np, gap_size=100)

        rel_x = x - region[0]
        rel_y = y - region[1]
        
        cv2.circle(img_np, (rel_x, rel_y), 10, (0, 0, 255), 2)
        cv2.circle(img_np, (rel_x, rel_y), 2, (0, 0, 255), -1)
        
        line_length = 15
        cv2.line(img_np, (rel_x - line_length, rel_y), (rel_x + line_length, rel_y), (0, 0, 255), 2)
        cv2.line(img_np, (rel_x, rel_y - line_length), (rel_x, rel_y + line_length), (0, 0, 255), 2)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        text = f"[{x}, {y}]"
        font_scale = 0.6
        thickness = 2
        text_color = (0, 255, 255)
        bg_color = (0, 0, 0)
        
        (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        
        cv2.rectangle(img_np, 
                      (rel_x - text_width // 2 - 5, rel_y - text_height - 25),
                      (rel_x + text_width // 2 + 5, rel_y - text_height - 5),
                      bg_color, -1)
        
        cv2.putText(img_np, text,
                   (rel_x - text_width // 2, rel_y - text_height - 10),
                   font, font_scale, text_color, thickness, cv2.LINE_AA)
        
        output_debug = Path('debug/screenshots')
        folder_ensure(output_debug)
        time_str = get_time_for_log(s='-')
        file_name = f"{time_str}-click-{label}-[{x}-{y}].jpg"
        file_path = output_debug / file_name
        
        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_pil.save(str(file_path), quality=95)
        
        log(f"DEBUG: Click screenshot saved: {file_path} | Coordinates: [{x}, {y}]")
        
    except Exception as e:
        log(f"ERROR saving click debug screenshot: {e}")

def debug_pixel_check_screenshot(x, y, expected_rgb, actual_rgb, match, label=None, margin=150):
    """
    Сохраняет скриншот области вокруг проверяемого пикселя с сеткой 10px
    для визуального определения правильных координат.
    """
    try:
        screen_width, screen_height = pyautogui.size()
        left = max(0, x - margin)
        top = max(0, y - margin)
        right = min(screen_width, x + margin)
        bottom = min(screen_height, y + margin)
        region = [left, top, right - left, bottom - top]

        screenshot = pyautogui.screenshot(region=region)
        img_np = np.array(screenshot)
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        h, w = img_np.shape[:2]

        grid_color = (80, 80, 80)
        grid_color_50 = (0, 200, 100)
        font = cv2.FONT_HERSHEY_SIMPLEX

        for gx_abs in range(left - (left % 10), right + 1, 10):
            rx = gx_abs - left
            if 0 <= rx < w:
                color = grid_color_50 if gx_abs % 50 == 0 else grid_color
                cv2.line(img_np, (rx, 0), (rx, h), color, 1)

        for gy_abs in range(top - (top % 10), bottom + 1, 10):
            ry = gy_abs - top
            if 0 <= ry < h:
                color = grid_color_50 if gy_abs % 50 == 0 else grid_color
                cv2.line(img_np, (0, ry), (w, ry), color, 1)

        for gy_abs in range(left - (left % 50), right + 1, 50):
            rx = gy_abs - left
            if 0 <= rx < w:
                txt = str(gy_abs)
                cv2.putText(img_np, txt, (rx + 2, 12), font, 0.35, (0, 255, 200), 1, cv2.LINE_AA)
        for gy_abs in range(top - (top % 50), bottom + 1, 50):
            ry = gy_abs - top
            if 0 <= ry < h:
                txt = str(gy_abs)
                cv2.putText(img_np, txt, (2, ry - 3), font, 0.35, (0, 255, 200), 1, cv2.LINE_AA)

        rel_x = x - left
        rel_y = y - top
        cv2.circle(img_np, (rel_x, rel_y), 8, (0, 0, 255), 2)
        cv2.circle(img_np, (rel_x, rel_y), 1, (0, 0, 255), -1)
        cv2.line(img_np, (rel_x - 12, rel_y), (rel_x + 12, rel_y), (0, 0, 255), 1)
        cv2.line(img_np, (rel_x, rel_y - 12), (rel_x, rel_y + 12), (0, 0, 255), 1)

        match_str = "OK" if match else "FAIL"
        diff = [abs(expected_rgb[i] - actual_rgb[i]) for i in range(min(len(expected_rgb), len(actual_rgb)))]
        line1 = f"[{x},{y}] {match_str}  exp={expected_rgb}"
        line2 = f"act={actual_rgb} diff={diff}"
        fs = 0.35
        (tw1, th1), _ = cv2.getTextSize(line1, font, fs, 1)
        (tw2, th2), _ = cv2.getTextSize(line2, font, fs, 1)
        bar_h = th1 + th2 + 14
        cv2.rectangle(img_np, (0, h - bar_h), (max(tw1, tw2) + 10, h), (0, 0, 0), -1)
        cv2.putText(img_np, line1, (4, h - th2 - 10), font, fs, (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(img_np, line2, (4, h - 4), font, fs, (0, 255, 255), 1, cv2.LINE_AA)

        output_debug = Path('debug/screenshots')
        folder_ensure(output_debug)
        time_str = get_time_for_log(s='-')
        tag = label or "check"
        file_name = f"{time_str}-pixel-{tag}-[{x}-{y}]-{match_str}.jpg"
        file_path = output_debug / file_name

        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_pil.save(str(file_path), quality=95)

        log(f"DEBUG: Pixel check screenshot saved: {file_path}")
    except Exception as e:
        log(f"ERROR saving pixel check debug screenshot: {e}")

def axis_to_region(x1, y1, x2, y2):
    return x1, y1, x2 - x1, y2 - y1

def axis_list_to_region(l):
    return l[0], l[1], l[2] - l[0], l[3] - l[1]

def show_pyautogui_image(pyautogui_screenshot, title='match'):
    if not is_debug_mode():
        return

    output_debug = Path('debug/screenshots')
    folder_ensure(output_debug)
    time_str = get_time_for_log(s='-')
    
    open_cv_image = np.array(pyautogui_screenshot)
    open_cv_image = open_cv_image[:, :, ::-1].copy()
    
    file_name = f"{time_str}-{title}.jpg"
    cv2.imwrite(str(output_debug / file_name), open_cv_image)
    log(f"Debug image saved: {output_debug / file_name}")

def show_image(path=None, image=None, title='Image'):
    if not is_debug_mode():
        return

    output_debug = Path('debug/screenshots')
    folder_ensure(output_debug)
    time_str = get_time_for_log(s='-')
    file_name = f"{time_str}-image-{title}.jpg"

    if path:
        image = cv2.imread(path)

    if image is not None:
        cv2.imwrite(str(output_debug / file_name), image)
        log(f"Debug image saved: {output_debug / file_name}")

def screenshot_to_image(screenshot):
    return np.array(screenshot)[:, :, ::-1].copy()

def check_image(region):
    screenshot = pyautogui.screenshot(region=region)
    show_pyautogui_image(screenshot)

def scale_up(screenshot=None, image=None, factor=1):
    if screenshot is not None:
        image = Image.frombytes("RGB", screenshot.size, screenshot.tobytes())

        # Calculate the new dimensions
        new_width = image.width * factor
        new_height = image.height * factor

        # Resize the image with Lanczos interpolation
        scaled_image = image.resize((new_width, new_height), Image.LANCZOS)

        return np.array(scaled_image)

    if image is not None:
        # Get the dimensions of the original image
        height, width, _ = image.shape

        # Calculate the new dimensions based on the scaling factor
        new_width = int(width * factor)
        new_height = int(height * factor)

        # Resize the image to the new dimensions
        scaled_image = cv2.resize(image, (new_width, new_height))

        return scaled_image

def crop(image=None, region=None):
    if image is not None and region is not None:
        return image[region[1]:region[1] + region[3], region[0]:region[0] + region[2]]

def dominant_color_hue(region, rank=1):
    screenshot = pyautogui.screenshot(region=region)
    image = screenshot_to_image(screenshot)

    # Convert the image to the HSV color space
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Calculate the histogram of the image in the Hue channel
    histogram = cv2.calcHist([hsv_image], [0], None, [180], [0, 180])

    # Find the rank-th dominant color bin
    dominant_color_bin = np.argsort(histogram.flatten())[-rank]

    # Convert the bin index to the corresponding hue value
    dominant_color_hue = int(dominant_color_bin * 180 / 256)

    return dominant_color_hue

def dominant_color_rgb(region, rank=1, reverse=True):
    screenshot = pyautogui.screenshot(region=region)
    image = screenshot_to_image(screenshot)

    # Reshape the image into a 2D array of pixels
    pixels = image.reshape((-1, 3))

    # Calculate the histogram of pixel values
    histogram = np.zeros((256, 256, 256))
    for pixel in pixels:
        r, g, b = pixel
        histogram[r, g, b] += 1

    # Find the rank-th dominant color (index) in the flattened histogram
    dominant_color_index = np.argsort(histogram.flatten())[-rank]

    # Convert the index to RGB values
    r, g, b = np.unravel_index(dominant_color_index, (256, 256, 256))

    res = [r, g, b]

    # Making right format here
    if not reverse:
        res.reverse()

    return res
