import glob
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import np

_DEBUG_MODE = False


class ColoredFormatter(logging.Formatter):
    """Custom formatter to add ANSI colors to console output."""
    COLORS = {
        'DEBUG': '\033[94m',
        'INFO': '\033[0m',
        'WARNING': '\033[93m',
        'ERROR': '\033[91m',
        'CRITICAL': '\033[91m\033[1m',
    }

    TAG_COLORS = {
        '[startup]': '\033[96m',
        '[web]': '\033[94m',
        '[cli]': '\033[92m',
        '[app]': '\033[95m',
        '[error]': '\033[91m',
        '[warning]': '\033[93m',
        '[response]': '\033[92m',
    }

    RESET = '\033[0m'
    BOLD = '\033[1m'

    def format(self, record):
        original_msg = str(record.msg)

        for tag, color in self.TAG_COLORS.items():
            if tag in original_msg:
                original_msg = original_msg.replace(tag, f"{self.BOLD}{color}{tag}{self.RESET}")

        orig_msg_attr = record.msg
        record.msg = original_msg

        formatted = super().format(record)

        record.msg = orig_msg_attr

        if record.levelno >= logging.WARNING:
            color = self.COLORS.get(record.levelname, self.RESET)
            parts = formatted.split(' | ', 1)
            if len(parts) == 2:
                formatted = f"{parts[0]} | {color}{parts[1]}{self.RESET}"
            else:
                formatted = f"{color}{formatted}{self.RESET}"

        return formatted


logger = logging.getLogger('RSLBot')
logger.setLevel(logging.INFO)


def _get_logs_dir():
    return os.path.abspath('logs')


if not logger.handlers:
    c_handler = logging.StreamHandler(sys.stdout)
    c_format = ColoredFormatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    try:
        logs_dir = _get_logs_dir()
        os.makedirs(logs_dir, exist_ok=True)
        log_filename = os.path.join(logs_dir, f"log-{datetime.now().strftime('%Y-%m-%d')}.txt")
        f_handler = RotatingFileHandler(log_filename, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
        f_file_format = logging.Formatter('%(asctime)s | %(message)s', datefmt='%H:%M:%S')
        f_handler.setFormatter(f_file_format)
        logger.addHandler(f_handler)
        logger.info(f"[logging] File log: {log_filename}")
    except Exception as e:
        print(f"Failed to setup log file handler: {e}")


def set_debug_mode(enabled: bool):
    global _DEBUG_MODE
    _DEBUG_MODE = enabled
    if enabled:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)


def is_debug_mode():
    return _DEBUG_MODE


def get_date_for_log():
    return datetime.now().strftime('%Y_%m_%d')


def get_time_for_log(s=':'):
    return '{}'.format(str(datetime.now().strftime(f"%H{s}%M{s}%S")))


def format_string_for_log(input_string):
    clean_string = re.sub(r'[^a-zA-Z0-9-\-\s]', '', input_string).lower()
    return clean_string.replace(' ', '_')


def log_save(message):
    logger.error(message)


LAST_CHAT_ID_FILE = os.path.join('state', 'last_chat_id.txt')


def save_last_chat_id(chat_id):
    try:
        folder_ensure('state')
        with open(LAST_CHAT_ID_FILE, 'w') as f:
            f.write(str(chat_id))
    except Exception:
        pass


def get_last_chat_id():
    try:
        if os.path.isfile(LAST_CHAT_ID_FILE):
            with open(LAST_CHAT_ID_FILE) as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def log(message):
    if type(message) is dict:
        output = json.dumps(message, indent=2)
    elif type(message) is list:
        output = str(np.array(message, dtype=object))
    elif type(message) is str:
        output = message
    else:
        output = str(message)

    logger.info(output)


def folder_ensure(folder_path):
    path = Path(folder_path)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        print(f"Folder '{folder_path}' created successfully.")


def sleep(duration):
    time.sleep(duration)


def clear_folder(path):
    files = glob.glob(path + '/*')
    for f in files:
        os.remove(f)
