import copy
import re
import sys
from datetime import datetime, timedelta

import np
from constants.index import BORDER_WIDTH, WINDOW_SIZE, WINDOW_TOP_BAR_HEIGHT
from helpers.time_mgr import TimeMgr

time_mgr = TimeMgr()

def make_command_key(input_string):
    clean_string = re.sub(r'[^a-zA-Z0-9\s]', '', input_string).lower()
    return clean_string.replace(' ', '_')

def make_title(input_string):
    return input_string.replace('_', ' ').title()

def get_closer_axis(arr):
    # Initialize the smallest_point with the first point in the array
    smallest_point = arr[0]

    # Iterate through the rest of the points to find the smallest 'x' and 'y' values
    for point in arr[1:]:
        if point.x < smallest_point.x:
            smallest_point = point
        elif point.x == smallest_point.x and point.y < smallest_point.y:
            smallest_point = point

    return smallest_point

def sort_by_closer_axis(arr):
    # Define a custom sorting key function
    def custom_sort(item):
        # Sort first by 'y', then by 'x'
        return item['y'], item['x']

    # Sort the data using the custom sorting key
    sorted_data = sorted(arr, key=custom_sort)

    return sorted_data

def make_lambda(predicate, *args):
    return lambda: predicate(*args)

def image_path(image):
    # @TODO Does not work as expected
    return str(Path.cwd() / 'image' / image)

def flatten(xss):
    return [x for xs in xss for x in xs]

def find(arr, predicate):
    for i in range(len(arr)):
        el = arr[i]
        if predicate(el):
            return i, el
    return None, None

def archive_list(input_list, pattern):
    result = []
    index = 0

    for group_size in pattern:
        group = input_list[index:index + group_size]
        result.append(group)
        index += group_size

    return result

def pop_random_element(input_list):
    if not input_list:
        return None  # Return None if the list is empty

    random_index = random.randrange(len(input_list))  # Get a random index
    random_element = input_list.pop(random_index)  # Remove and get the element at that index
    return random_element

def get_higher_occurrence(arr):
    if not len(arr):
        return None
    return max(arr, key=arr.count)

def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def is_production():
    return getattr(sys, 'frozen', False)

def merge_dicts(dict1, dict2):
    """
    Merge two dictionaries deeply.
    """
    merged_dict = copy.deepcopy(dict1)

    for key, value in dict2.items():
        if key in merged_dict and isinstance(merged_dict[key], dict) and isinstance(value, dict):
            # If both values are dictionaries, merge them recursively
            merged_dict[key] = merge_dicts(merged_dict[key], value)
        else:
            # Otherwise, update the value in merged_dict with the value from dict2
            merged_dict[key] = value

    return merged_dict

def prepare_event(event, props):
    event_copy = copy.copy(event)
    return merge_dicts(event_copy, props)

def get_result(rgb):
    from helpers.screen import dominant_color_rgb
    from helpers.vision import rgb_check

    REGION_BATTLE_RESULT = [
        WINDOW_SIZE[0] / 2 - BORDER_WIDTH - 25,
        BORDER_WIDTH + WINDOW_TOP_BAR_HEIGHT,
        50,
        10
    ]
    dominant_rgb = dominant_color_rgb(region=REGION_BATTLE_RESULT)
    return rgb_check(rgb, dominant_rgb, mistake=50)

def get_time_future(**kwargs):
    return datetime.now() + timedelta(**kwargs)

