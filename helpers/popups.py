from helpers.logging_utils import log, sleep
from helpers.mouse import click
from helpers.vision import (
    await_needle,
    find_needle_burger,
    find_needle_close_popup,
    pixel_check_new,
)

special_offer_popup = [300, 370, [22, 124, 156]]

def is_index_page(logger=True):
    flag = False
    message = None
    if find_needle_burger() is not None:
        flag = True
        message = 'Index Page detected'
    else:
        message = 'Index Page is not detected'

    if logger and message:
        log(message)
    return flag

def click_on_progress_info(delay=0.5):
    # keys/coins info
    all_resources = await_needle('all_resources.jpg', region=[0, 0, 900, 100])
    if all_resources:
        x = int(all_resources[0])
        y = int(all_resources[1])
        click(x, y)
        sleep(delay)

def close_popup(*args):
    close_popup_button = find_needle_close_popup()
    if close_popup_button is not None:
        x = close_popup_button[0]
        y = close_popup_button[1]
        click(x, y)
        log('Regular popup closed')

    # closes special offer popup when it appears
    sleep(0.3)
    special_offer_button = pixel_check_new(special_offer_popup, mistake=5)
    if special_offer_button:
        x = special_offer_popup[0]
        y = special_offer_popup[1]
        click(x, y)
        sleep(3)
        log('Special offer popup closed')

    return [close_popup_button, special_offer_button]

def close_popup_recursive(*args, timeout=2, delay=1):
    def _check():
        res = close_popup()
        return res[0] is not None or res[1]

    while _check():
        sleep(timeout)

    sleep(delay)

def go_index_page():
    log('Moving to the Index Page...')
    close_popup()
    sleep(1)
    is_index = is_index_page()
    if is_index is False:
        go_index_page()
    return is_index

