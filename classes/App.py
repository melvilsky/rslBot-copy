from helpers.common import *
from helpers.updater import is_update_available, should_check_for_updates, launch_updater
from classes.TaskManager import TaskManager
from classes.Storage import Storage
from classes.Foundation import *
try:
    from classes.Recorder import Recorder
except ImportError:
    Recorder = None
from telegram.error import BadRequest
from locations.rewards.index import *
# from locations.live_arena.index_old import *
from locations.live_arena.index import *
from locations.arena.index import *
from locations.demon_lord.index import *
from locations.faction_wars.index import *
from locations.iron_twins_fortress.index import *
from locations.dungeons.index import *
from locations.hydra.index import *
from locations.doom_tower.index import *
from locations.quests.index import *
from locations.test.index import *
from locations.test_await.index import *
from constants.index import *
import signal
import sys
import subprocess
import psutil
import os
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
from datetime import datetime

INSTANCES_MAP = {
    'arena_live': ArenaLive,
    'arena_classic': ArenaClassic,
    'arena_tag': ArenaTag,
    'demon_lord': DemonLord,
    'hydra': Hydra,
    'dungeon': Dungeons,
    'faction_wars': FactionWars,
    'iron_twins': IronTwins,
    'rewards': Rewards,
    'doom_tower': DoomTower,
    'daily_quests': Quests,
    'test_feature': TestFeature,
    'test_await': TestAwait,
}
SUPPORTED_LANGUAGES = ['eng', 'deu', 'ukr', 'rus']
LANGUAGES_MATRIX = [
    ['eng', None, 'deu'],
    [None, None, None],
    [None, None, None],
    ['ukr', 'rus', None],
    [None],
]

# EMULATE_NETWORK_ERROR = False

def find_process_by_name(name):
    for proc in psutil.process_iter(['pid', 'name']):
        # print(proc.info['name'])
        if proc.info['name'] == name:
            return proc

    log(f"No process found with the title: {name}")
    return False


def terminate_process_by_name(name):
    proc = find_process_by_name(name)
    if proc:
        log(f"Terminating process {proc.info['name']} (PID: {proc.info['pid']})")
        proc.terminate()
        return True

    log(f"No process found with the title: {name}")
    return False


def get_windows(title):
    return pyautogui.getWindowsWithTitle(title)


def get_game_windows():
    return get_windows(GAME_WINDOW)


def resize_window(x_move=0, y_move=0):
    win = None
    wins = get_game_windows()
    if len(wins):
        win = wins[0]
        win.activate()
        time.sleep(.5)
        win.resizeTo(WINDOW_SIZE[0], WINDOW_SIZE[1])
        win.moveTo(int(x_move), int(y_move))
        time.sleep(.5)
    else:
        log("No RAID window found")
    return win


def calibrate_window(window_axis=None):
    BURGER_POSITION = [15, 282]
    is_prepared = False
    x = 0
    y = 0
    wins = get_game_windows()
    if len(wins):
        win = wins[0]
        # going back to the index page
        close_popup_recursive()

        if window_axis is not None:
            print('window_axis', window_axis)
            x = window_axis['x']
            y = window_axis['y']
        else:
            burger = find_needle_burger()
            if burger is not None:
                if burger[0] != BURGER_POSITION[0] or burger[1] != BURGER_POSITION[1]:
                    x_burger = burger[0] - BURGER_POSITION[0]
                    y_burger = burger[1] - BURGER_POSITION[1]
                    x -= x_burger
                    y -= y_burger

        win.move(int(x), int(y))

        is_prepared = True

        # waiting and closing sudden popups
        sleep(3)
        close_popup_recursive()

    if not is_prepared:
        raise Exception("Game windows is NOT prepared")

    return {'x': x, 'y': y}


def prepare_window():
    BURGER_POSITION = [15, 282]
    is_prepared = False
    wins = get_game_windows()
    win = None
    if len(wins):
        win = wins[0]
        win.activate()
        time.sleep(.5)

        x = 0
        y = 0

        win.resizeTo(WINDOW_SIZE[0], WINDOW_SIZE[1])
        win.moveTo(x, y)
        time.sleep(.5)

        # going back to the index page
        close_popup_recursive()

        burger = find_needle_burger()
        if burger is not None:
            if burger[0] != BURGER_POSITION[0] or burger[1] != BURGER_POSITION[1]:
                x_burger = burger[0] - BURGER_POSITION[0]
                y_burger = burger[1] - BURGER_POSITION[1]
                x -= x_burger
                y -= y_burger
                win.move(int(x), int(y))
            is_prepared = True

            # waiting and closing sudden popups
            sleep(3)
            close_popup_recursive()
        else:
            log("No Burger needle found")
    else:
        log("No RAID window found")

    if not is_prepared:
        raise Exception("Game windows is NOT prepared")

    return win


def make_command_key(input_string):
    # Remove special characters and convert to lowercase
    clean_string = re.sub(r'[^a-zA-Z0-9\s]', '', input_string).lower()
    # Replace spaces with underscores
    formatted_string = clean_string.replace(' ', '_')
    return formatted_string


def make_title(input_string):
    return input_string.replace('_', ' ').title()



class App(Foundation):
    COMMANDS_GAME_PATH_DEPENDANT = ['restart', 'launch', 'relogin', 'prepare']
    COMMANDS_COMMON = ['report', 'screen', 'click', 'stop', 'record_on', 'record_off']

    def __init__(self):
        Foundation.__init__(self, name='App')

        self.config = None
        self.window = None
        self.window_region = None
        self.window_axis = None
        self.entries = {}
        self.taskManager = TaskManager()
        self.timeManager = TimeMgr()
        self.lang = None
        self.translations = None
        self.scheduler = None
        self.telegram_bot = None  # Будет установлен из main.py
        self.recorder = Recorder() if Recorder else None
        self.current_player_name = None  # имя профиля (файла) для сообщения в бот
        self.current_player_id = None    # player_id из конфига для сообщения в бот

        # @TODO Temp commented
        # self.storage = Storage(name='storage', folder='temp')

        # Order is matters
        self.read_config()
        self.load_translations()
        self.commands = self.get_commands()

        self.INDEX_PAGE_DETECTED = {
            'name': "Index+",
            'interval': 2,
            'expect': find_needle_burger,
            'callback': close_popup_recursive,
        }

        self.INDEX_PAGE_NOT_DETECTED = {
            'name': "Index-",
            'interval': .5,
            'blocking': False,
            'limit': 120,
            'expect': lambda: not find_needle_burger(),
            'callback': close_popup,
        }

        self.E_INDEX_PAGE_TIMEOUT = {
            'name': "IndexPageTimeout",
            'delay': 180,
            'interval': 1,
            'expect': lambda: True,
            'blocking': True,
        }

        self.E_TERMINATE_GAME = {
            'name': "TerminateGame",
            'interval': 120,
            'delay': 120,
            'limit': 1,
            'blocking': False,
            "expect": lambda: True,
            'callback': lambda *args: self.restart(terminate_list=[PROCESS_GAME_NAME]),
        }

        self.E_TERMINATE_ALL = {
            'name': "TerminateAll",
            'interval': 300,
            'delay': 300,
            'limit': 1,
            'blocking': False,
            'expect': lambda: True,
            'callback': self.restart,
        }

        self.E_POPUP_RELOGIN_ERROR = prepare_event(self.E_POPUP_ERROR, {
            "limit": 1,
            "wait_limit": 2,
            "expect": self._expect_relogin,
            "callback": lambda *args: len(args) and click_detected_button(args[0])
        })

    def _expect_relogin(self):
        # Should return same format for both cases
        if self.lang:
            return find_detected_button({'text': self.translations['relogin']}, detect_buttons(lang=self.lang))
        else:
            return detect_same_variant_buttons_and_return_one(index=0, length=2)

    def get_commands(self):
        return {
            'restart': {
                'description': 'Re-Start the Game',
                'category': 'Управление',
                'handler': self.task('restart', self.restart, task_type='aside'),
            },
            'launch': {
                'description': 'Re-Launch the Game',
                'category': 'Управление',
                'handler': self.task('launch', self.launch, task_type='aside'),
            },
            # @TODO Does not work properly when it's running right after bot starts
            'relogin': {
                'description': 'Re-log in',
                'category': 'Управление',
                'handler': self.task('relogin', self.relogin, task_type='aside'),
            },
            'prepare': {
                'description': 'Prepares the Game window',
                'category': 'Управление',
                'handler': self.task('prepare', lambda *args: self.prepare(calibrate=False), task_type='sync'),
            },
            'screen': {
                'description': 'Capture and send a screenshot',
                'category': 'Управление',
                'handler': self.task('screen', self._screenshot, task_type='sync'),
            },
            'click': {
                'description': 'Click by provided coordinates: x, y',
                'category': 'Управление',
                'handler': self.task('click', self._click, task_type='sync'),
            },
            'stop': {
                'description': 'Terminates instances and clears the queue',
                'category': 'Управление',
                'handler': self.task('stop', self._stop, task_type='sync'),
            },
            'report': {
                'description': 'Report',
                'category': 'Управление',
                'handler': self.task('report', self.report, task_type='sync'),
            },
            'record_on': {
                'description': 'Start recording clicks',
                'category': 'Запись',
                'handler': lambda upd, ctx: upd.message.reply_text(
                    self.recorder.start() if self.recorder else "Recorder unavailable (pynput not installed)"
                ),
            },
            'record_off': {
                'description': 'Stop recording and show results',
                'category': 'Запись',
                'handler': lambda upd, ctx: upd.message.reply_text(
                    self.recorder.stop() if self.recorder else "Recorder unavailable (pynput not installed)"
                ),
            },
        }

    def _screenshot(self, upd, ctx):
        # @TODO Bug
        # if not bool(self.window):
        #     self.prepare()

        if bool(self.window):
            return ctx.bot.send_photo(chat_id=upd.message.chat_id, photo=self.screen())
        else:
            upd.message.reply_text('No window found')
            return False

    def _prepare_config(self, config_json):
        _config = {
            'start_immediate': True,
            'tasks': [],
            'presets': [],
            'after_each': [],
            'game_path': '',
            'lang': None,
            'debug': False
        }

        if 'debug' in config_json:
            _config['debug'] = bool(config_json['debug'])

        # Apply debug mode immediately
        set_debug_mode(_config['debug'])
        if _config['debug']:
            self.log("Debug mode enabled from config")

        # Очистка старых debug-данных и логов при каждом запуске
        # Любые ошибки здесь не должны ломать старт приложения
        try:
            cleanup_debug_data(max_days=7, max_total_mb=500)
            cleanup_old_logs(max_days=30)
        except Exception as e:
            try:
                log_save(f"Debug/log cleanup failed: {e}")
            except Exception:
                # Даже логирование ошибки не должно мешать запуску
                pass

        if 'start_immediate' in config_json:
            _config['start_immediate'] = bool(config_json['start_immediate'])

        if 'game_path' in config_json and bool(config_json['game_path']):
            GAME_PATH = os.getenv('GAME_PATH')
            _config['game_path'] = GAME_PATH if GAME_PATH else os.path.normpath(str(config_json['game_path']))

        if 'telegram_token' in config_json:
            TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
            _config['telegram_token'] = TELEGRAM_BOT_TOKEN if TELEGRAM_BOT_TOKEN else str(config_json['telegram_token'])

        _lang = str(config_json['lang']).lower() if 'lang' in config_json else None
        LANG = os.getenv('LANG')
        self.lang = LANG if LANG in SUPPORTED_LANGUAGES \
            else _lang if _lang in SUPPORTED_LANGUAGES \
            else None

        # Tasks
        tasks_length = len(config_json['tasks'])
        if tasks_length:
            for i in range(tasks_length):
                task = config_json['tasks'][i]
                if 'enable' not in task or bool(task['enable']):

                    _task = task['task'].lower()
                    _props = task['props'] if 'props' in task else None
                    _title = task['title'] if 'title' in task else make_title(_task)
                    _command = task['command'] \
                        if 'command' in task \
                        else f"{_task}_" + make_command_key(f"{task['title']}") \
                        if 'title' in task \
                        else _task

                    # The most important data object for command registration
                    task_d = {
                        'task': _task,
                        'command': _command,
                        'title': _title,
                        'props': _props,
                    }

                    # @TODO Removed: and _task not in self.entries
                    # accumulated instances
                    if _command not in self.entries:
                        if _task in INSTANCES_MAP:
                            # @TODO should take from memory later on

                            self.entries[_command] = {
                                'instance': INSTANCES_MAP[_task](app=self, props=_props),
                            }
                        else:
                            raise Exception(f"No {_task} among all instances")
                    else:
                        raise Exception(f"{_command} is already exist, please provide the different")

                    _config['tasks'].append(task_d)

            # handling presets
            presets_length = len(config_json['presets'])
            if presets_length:
                # @TODO Refactor
                # _config['presets'] = config_json['presets']

                presets_filtered = []
                for i in range(presets_length):
                    preset_name = config_json['presets'][i]['name']
                    preset_tasks = config_json['presets'][i]['commands']

                    presets_filtered.append({
                        'name': preset_name,
                        'commands': list(filter(
                            lambda x: any(dct['command'] == x for dct in _config['tasks']), preset_tasks
                        ))
                    })
                _config['presets'] = presets_filtered

        # After each commands
        if 'after_each' in config_json:
            _config['after_each'] = config_json['after_each']

        return _config

    def validation(self):
        # primitive validation
        date_now = datetime.now()
        # Обновлено для работы в 2025 году и далее
        return date_now.year >= 2024

    def check_for_updates(self, telegram_bot=None):
        """
        Проверяет наличие обновлений и уведомляет пользователя
        Вызывается при запуске приложения (раз в день)
        """
        try:
            # Проверяем, нужно ли проверять обновления (раз в день)
            if not should_check_for_updates():
                return
            
            self.log('Checking for updates...')
            update_info = is_update_available()
            
            if update_info and update_info.get('available'):
                current_version = update_info.get('current_version', 'unknown')
                latest_version = update_info.get('latest_version', 'unknown')
                download_url = update_info.get('download_url')
                release_url = update_info.get('release_url', '')
                release_notes = update_info.get('release_notes', '')
                
                message = (
                    f"🔄 Доступно обновление!\n\n"
                    f"Текущая версия: {current_version}\n"
                    f"Новая версия: {latest_version}\n"
                )
                
                if release_notes:
                    # Обрезаем release notes до 500 символов
                    notes = release_notes[:500] + "..." if len(release_notes) > 500 else release_notes
                    message += f"\nЧто нового:\n{notes}\n"
                
                if release_url:
                    message += f"\nПодробнее: {release_url}"
                
                message += "\n\nИспользуйте команду /update для обновления"
                
                # Уведомляем через Telegram если бот доступен
                if telegram_bot and hasattr(telegram_bot, 'updater'):
                    try:
                        # Отправляем сообщение всем чатам бота
                        # Получаем список обновлений для получения chat_id
                        updates = telegram_bot.updater.bot.get_updates()
                        chat_ids = set()
                        for update in updates:
                            if update.message and update.message.chat_id:
                                chat_ids.add(update.message.chat_id)
                        
                        # Если нет обновлений, пробуем отправить в известные чаты
                        if not chat_ids:
                            # Можно добавить сохранение chat_id при первом использовании
                            pass
                        
                        for chat_id in chat_ids:
                            try:
                                telegram_bot.updater.bot.send_message(
                                    chat_id=chat_id,
                                    text=message,
                                    parse_mode='HTML'
                                )
                            except Exception as e:
                                self.log(f"Error sending update notification to {chat_id}: {e}")
                    except Exception as e:
                        self.log(f"Error sending update notification: {e}")
                
                # Также логируем в консоль
                self.log(message)
                
                # Сохраняем информацию об обновлении для команды /update
                self.pending_update = update_info
            else:
                self.log('No updates available')
                
        except Exception as e:
            self.log(f"Error checking for updates: {e}")
            import traceback
            log_save(traceback.format_exc())

    def check_update_status(self, telegram_bot=None):
        """
        Проверяет статус обновлений и возвращает сообщение для пользователя
        Вызывается по команде /checkupdate из Telegram
        """
        try:
            self.log('Manual update check requested...')
            
            # Получаем текущую версию
            from helpers.updater import get_current_version
            current = get_current_version()
            self.log(f'Current version: {current}')
            
            # Проверяем обновления
            update_info = is_update_available()
            self.log(f'Update check result: {update_info}')
            
            if not update_info:
                self.log('Update info is None - error occurred')
                return "❌ Ошибка при проверке обновлений. Проверьте подключение к интернету."
            
            if update_info.get('available'):
                current_version = update_info.get('current_version', 'unknown')
                latest_version = update_info.get('latest_version', 'unknown')
                release_url = update_info.get('release_url', '')
                release_notes = update_info.get('release_notes', '')
                
                message = (
                    f"🔄 Доступно обновление!\n\n"
                    f"Текущая версия: <b>{current_version}</b>\n"
                    f"Новая версия: <b>{latest_version}</b>\n"
                )
                
                if release_notes:
                    notes = release_notes[:300] + "..." if len(release_notes) > 300 else release_notes
                    message += f"\nЧто нового:\n{notes}\n"
                
                if release_url:
                    message += f"\nПодробнее: {release_url}"
                
                message += "\n\nИспользуйте команду /update для обновления"
                
                # Сохраняем информацию об обновлении
                self.pending_update = update_info
                
                return message
            else:
                current_version = update_info.get('current_version', 'unknown')
                latest_version = update_info.get('latest_version', 'unknown')
                return (
                    f"✅ У вас установлена последняя версия!\n\n"
                    f"Текущая версия: <b>{current_version}</b>\n"
                    f"Последняя версия: <b>{latest_version}</b>"
                )
                
        except Exception as e:
            error_msg = f"❌ Ошибка при проверке обновлений: {e}"
            self.log(error_msg)
            import traceback
            log_save(traceback.format_exc())
            return error_msg

    def clear_chat(self, update=None, context=None, telegram_bot=None):
        """
        Удаляет все отслеживаемые сообщения бота в чате, затем отправляет /help.
        Трекинг ведётся в bot.py через monkey-patch reply_text.
        """
        try:
            if not update or not update.message:
                return
            chat_id = update.message.chat_id
            bot = context.bot

            # Добавляем сюда и саму команду /clearchat чтобы тоже удалить её
            if telegram_bot:
                telegram_bot._record_message(chat_id, update.message.message_id)

            message_ids = []
            if telegram_bot:
                message_ids = telegram_bot.get_and_clear_messages(chat_id)

            self.log(f"Clearing chat {chat_id}: {len(message_ids)} tracked messages")

            deleted_count = 0
            for msg_id in sorted(message_ids, reverse=True):
                try:
                    bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    deleted_count += 1
                    sleep(0.04)
                except Exception:
                    pass  # уже удалено, старше 48ч или пользовательское — ок

            self.log(f"Deleted {deleted_count} messages")

            # Отправляем /help после очистки
            if telegram_bot:
                msg = bot.send_message(
                    chat_id=chat_id,
                    text=telegram_bot._all_commands(),
                    parse_mode='HTML'
                )
                if msg:
                    telegram_bot._record_message(chat_id, msg.message_id)

        except Exception as e:
            import traceback
            self.log(f"clear_chat error: {e}")
            log_save(traceback.format_exc())


    def perform_update(self, telegram_bot=None):
        """
        Выполняет обновление приложения
        Вызывается по команде /update из Telegram
        """
        try:
            if not hasattr(self, 'pending_update') or not self.pending_update:
                # Проверяем обновления заново
                update_info = is_update_available()
                if not update_info or not update_info.get('available'):
                    return "Обновления не найдены"
                self.pending_update = update_info
            
            download_url = self.pending_update.get('download_url')
            if not download_url:
                return "URL для скачивания не найден"
            
            # Определяем путь к приложению
            if hasattr(sys, 'frozen') and sys.frozen:
                app_path = os.path.dirname(sys.executable)
            else:
                app_path = os.getcwd()
            
            # Запускаем updater
            self.log(f"Starting update process...")
            self.log(f"Download URL: {download_url}")
            self.log(f"App path: {app_path}")
            
            if launch_updater(download_url, app_path):
                message = "Обновление запущено. Приложение будет закрыто и перезапущено после обновления."
                
                # Уведомляем через Telegram
                if telegram_bot and hasattr(telegram_bot, 'updater'):
                    try:
                        updates = telegram_bot.updater.bot.get_updates()
                        chat_ids = set()
                        for update in updates:
                            if update.message and update.message.chat_id:
                                chat_ids.add(update.message.chat_id)
                        
                        for chat_id in chat_ids:
                            try:
                                telegram_bot.updater.bot.send_message(
                                    chat_id=chat_id,
                                    text=message
                                )
                            except Exception as e:
                                self.log(f"Error sending update message to {chat_id}: {e}")
                    except Exception as e:
                        self.log(f"Error sending update message: {e}")
                
                # Даем время на отправку сообщения, затем закрываем приложение
                sleep(2)
                sys.exit(0)
                
                return message
            else:
                return "Ошибка при запуске обновления"
                
        except Exception as e:
            error_msg = f"Ошибка при обновлении: {e}"
            self.log(error_msg)
            import traceback
            traceback.print_exc()
            return error_msg

    def load_config(self, config):
        self.config = self._prepare_config(config)
        log('Load App Config')

    def utc_date(self, dt=None):
        if dt is None:
            dt = datetime.utcnow()
        dt_parsed = self.timeManager.timestamp_to_datetime(dt)
        return f"{dt_parsed['day']}-{dt_parsed['month']}-{dt_parsed['year']}"

    def _has_popup_open(self):
        """Проверка: есть ли открытый попап (тот же способ, что для определения попапов в игре)."""
        if find_needle_close_popup() is not None:
            return True
        if find_popup_error_detector():
            return True
        if find_needle_popup_attention():
            return True
        return False

    def _verify_player_id_window_closed(self, timeout=3, step=0.3):
        """Ждём, пока окно с player_id закроется (проверяем как попап — кнопка закрытия не детектируется)."""
        import time as time_mod
        deadline = time_mod.time() + timeout
        while time_mod.time() < deadline:
            if find_needle_close_popup() is None:
                return True
            pyautogui.press('escape')
            time_mod.sleep(step)
        return find_needle_close_popup() is None

    def _collect_player_id_from_game(self):
        """
        Выполняет 3 клика в игре и ESC, проверяет закрытие окна, возвращает нормализованный id из буфера.
        Возвращает None при ошибке или если окно не закрылось.
        """
        try:
            import pyperclip
        except ImportError:
            self.log('pyperclip not installed, cannot read player id from clipboard')
            return None
        if self.get_window_region() is None:
            self.log('Window not available for player id collection')
            return None
        # Экранные координаты: контент окна = window.left + BORDER_WIDTH, window.top + BORDER_TOP
        base_x = self.window.left + BORDER_WIDTH
        base_y = self.window.top + WINDOW_TOP_BAR_HEIGHT + BORDER_WIDTH
        sleep(PLAYER_ID_DELAY_BEFORE_FIRST)
        for coord, (dx, dy) in enumerate([
            PLAYER_ID_CLICK_1,
            PLAYER_ID_CLICK_2,
            PLAYER_ID_CLICK_3,
        ], 1):
            x, y = base_x + dx, base_y + dy
            click(x, y)
            if coord == 1:
                delay = PLAYER_ID_DELAY_AFTER_FIRST
            elif coord < 3:
                delay = PLAYER_ID_DELAY_BETWEEN_CLICKS
            else:
                delay = PLAYER_ID_DELAY_AFTER_COPY
            sleep(delay)
        pyautogui.press('escape')
        sleep(0.3)
        if not self._verify_player_id_window_closed():
            self.log('Player id window did not close after ESC')
            return None
        raw = pyperclip.paste().strip()
        # Нормализация: привести пробелы вокруг | к одному виду
        if '|' in raw:
            parts = [p.strip() for p in raw.split('|', 1)]
            raw = ' | '.join(parts) if len(parts) == 2 else raw
        return raw if raw else None

    def _get_profiles_with_player_id(self):
        """Список (имя_файла_без_json, player_id) для профилей, у которых есть player_id."""
        if not os.path.isdir(PROFILES_DIR):
            return []
        result = []
        for name in sorted(os.listdir(PROFILES_DIR)):
            if not name.endswith('.json'):
                continue
            path = os.path.join(PROFILES_DIR, name)
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
                pid = data.get('player_id')
                if pid and isinstance(pid, str):
                    result.append((name[:-5], pid.strip()))
            except Exception:
                continue
        return result

    def _load_profile_file(self, filename_no_ext):
        """
        Загружает конфиг из profiles/<filename_no_ext>.json.
        Очищает task entries и применяет _prepare_config. Устанавливает current_player_name и current_player_id.
        """
        path = os.path.join(PROFILES_DIR, filename_no_ext + '.json')
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        with open(path, encoding='utf-8') as f:
            config_json = json.load(f)
        for task_d in (self.config or {}).get('tasks', []):
            cmd = task_d.get('command')
            if cmd and cmd in self.entries:
                del self.entries[cmd]
        self.config = self._prepare_config(config_json)
        self.current_player_name = filename_no_ext
        self.current_player_id = config_json.get('player_id') if isinstance(config_json.get('player_id'), str) else None
        self.log(f'Config loaded from profile: {filename_no_ext}')

    def load_profile_by_name(self, filename_no_ext):
        """Публичный метод для ручной загрузки профиля (например по команде /loadconfig)."""
        self._load_profile_file(filename_no_ext)

    def read_config(self):
        """Загружает конфиг: всегда сначала дефолтный (config.json или config.default.json).
        Если есть папка profiles, выбор профиля предлагается в Telegram боте после загрузки."""
        try:
            # Всегда грузим дефолтный конфиг из корня (как раньше)
            config_path = get_config_path()
            if not os.path.exists(CONFIG_PATH) and os.path.exists(CONFIG_DEFAULT_PATH):
                import shutil
                shutil.copy(CONFIG_DEFAULT_PATH, CONFIG_PATH)
                self.log(f'Created {CONFIG_PATH} from {CONFIG_DEFAULT_PATH}')
                config_path = CONFIG_PATH
            with open(config_path, encoding='utf-8') as config_file:
                config = json.load(config_file)
            self.config = self._prepare_config(config)
            self.current_player_name = None
            self.current_player_id = None
            self.log('Config is processed (default config loaded)')

        except SystemError:
            log('An error occurred while reading config file')
        except FileNotFoundError as e:
            log(f'Config file not found: {e}')
        except Exception as e:
            log(f'Error reading config: {e}')

    def report(self, *args):
        print('App -> Report')
        res = None
        instances = list(map(lambda x: x['instance'], self.entries.values()))
        reports = list(map(lambda x: x.report(), instances))

        if reports.count(None) < len(reports):
            res = ''
            for i in range(len(reports)):
                report = reports[i]
                if report:
                    res += f'{report}\n\n'

        return res or "No reports yet"

    def kill(self, *args):
        if self.scheduler is not None:
            self.scheduler.shutdown()
        self.report()
        log('App is terminated')
        input('Confirm by pressing any key')
        sys.exit(0)

    def relogin(self, *args):

        self.awaits(events=[
            self.E_POPUP_RELOGIN_ERROR,
            self.INDEX_PAGE_DETECTED,
            self.INDEX_PAGE_NOT_DETECTED,
            self.E_TERMINATE_GAME,
            self.E_TERMINATE_ALL,
        ])

        return True

    def get_window_region(self):
        if self.window_region is not None:
            return self.window_region

        if self.window is None:
            self.window = resize_window()

        x = self.window.left
        y = self.window.top
        width = self.window.width
        height = self.window.height

        # calculates region
        region = [
            int(x + BORDER_WIDTH),
            int(y + BORDER_WIDTH + WINDOW_TOP_BAR_HEIGHT),
            int(width - BORDER_WIDTH * 2),
            int(height - BORDER_WIDTH * 2 - WINDOW_TOP_BAR_HEIGHT),
        ]

        self.window_region = region
        log(f"Window region: {str(region)}")

        return region

    def screen(self, *args):
        _region = self.get_window_region()
        screenshot = pyautogui.screenshot(region=_region)

        # Convert the screenshot to bytes
        image_bytes = BytesIO()
        screenshot.save(image_bytes, format='PNG')
        image_bytes.seek(0)

        return image_bytes

    def _stop(self, *args):
        # Needs when bot is starting
        sleep(1)

        # Terminates all instances
        for key, value in self.entries.items():
            instance = value['instance']
            instance.terminated = True
            instance.stop = True

        # Empty the queue
        queue = self.taskManager.queue
        while not queue.empty():
            queue.get()

    def _click(self, upd, ctx):
        response = []

        def _get_grid_screenshot():
            gap_size = 100
            font_scale = .5
            font_color = (150, 255, 0)
            grid_color = (150, 255, 0)

            image_bytes = self.screen()
            # Convert the image to a numpy array
            img_np = np.array(Image.open(image_bytes))

            # Get the image dimensions
            height, width, _ = img_np.shape

            # Draw vertical lines
            for x in range(0, width, gap_size):
                cv2.line(img_np, (x, 0), (x, height), grid_color, 1)

            # Draw horizontal lines
            for y in range(0, height, gap_size):
                cv2.line(img_np, (0, y), (width, y), grid_color, 1)

            # Draw pixel coordinates
            font = cv2.FONT_HERSHEY_SIMPLEX
            for y in range(0, height, gap_size):
                for x in range(0, width, gap_size):
                    x_final = int(x + gap_size / 2)
                    y_final = int(y + gap_size / 2)
                    text = f"({x_final},{y_final})"
                    text_size = cv2.getTextSize(text, font, font_scale, 1)[0]
                    text_x = x + (gap_size - text_size[0]) // 2
                    text_y = y + (gap_size + text_size[1]) // 2
                    cv2.putText(img_np, text, (text_x, text_y), font, font_scale, font_color, 1, cv2.LINE_AA)

            # Convert the numpy array back to an image
            img_with_grid = Image.fromarray(img_np)

            # Convert the image to bytes using BytesIO
            buffered_image = BytesIO()
            img_with_grid.save(buffered_image, format="JPEG")  # Change format if necessary
            buffered_image.seek(0)

            return buffered_image

        def _send_grid_screenshot():
            if bool(self.window):
                grid_screen = _get_grid_screenshot()
                ctx.bot.send_photo(
                    chat_id=upd.message.chat_id,
                    photo=grid_screen
                )
            else:
                response.append("No Game window found")

        if len(ctx.args) < 2:
            _send_grid_screenshot()
            response.append('Provide coordinates: x y')

        else:
            x = ctx.args[0]
            y = ctx.args[1]

            if is_number(x) and is_number(y):
                click(
                    int(x) + BORDER_WIDTH,
                    int(y) + WINDOW_TOP_BAR_HEIGHT + BORDER_WIDTH
                )
                sleep(.5)
                _send_grid_screenshot()
            else:
                response.append('X and Y must be numbers')

        if len(response):
            return upd.message.reply_text('\n'.join(response))

    def determine_language(self):
        close_popup_recursive()

        click(40, 70, smart=True)

        if await_click([[150, 346, [8, 73, 107]]], mistake=5, msg='Language Tab', timeout=1)[0]:
            self.lang = self.detect_language()
            self.log(f"Language detected: '{self.lang}'")

        close_popup_recursive()

    def start(self):
        # atexit.register(self.report)
        signal.signal(signal.SIGINT, self.kill)
        signal.signal(signal.SIGTERM, self.kill)

        game_path = self.config['game_path']
        if find_process_by_name(PROCESS_GAME_NAME):
            self.prepare(predicate=self.relogin)
        elif game_path:
            self.launch()
        else:
            raise Exception("No 'game_path' provided field in the config")

    def launch(self, *args):
        game_path = self.config['game_path']
        if game_path:
            # @TODO Test
            # subprocess.run(['cmd', '/c', 'start', '', f"{os.path.normpath(game_path)} -gameid=101 -tray-start"], check=True)
            subprocess.run(f"{game_path} -gameid=101 -tray-start")
            sleep(3)
            self.prepare()
            log('Game window is ready')
        else:
            return "No 'game_path' provided field in the config"

    def restart(self, *args, terminate_list=None):
        if terminate_list is None:
            terminate_list = [PROCESS_GAME_NAME, PROCESS_PLARIUM_SERVICE_NAME, PROCESS_PLARIUM_PLAY_NAME]

        game_path = self.config['game_path']
        if game_path:
            if type(terminate_list) is list and len(terminate_list):
                for t in range(len(terminate_list)):
                    terminate_process_by_name(terminate_list[t])
            sleep(2)
            self.launch()
            sleep(2)
        else:
            return "No 'game_path' provided field in the config"

    def prepare(self, predicate=None, calibrate=True):
        x_move = self.window_axis['x'] if self.window_axis and 'x' in self.window_axis else 0
        y_move = self.window_axis['y'] if self.window_axis and 'y' in self.window_axis else 0
        self.window = resize_window(x_move=x_move, y_move=y_move)

        if predicate is not None:
            predicate()

        result = self.awaits([
            self.E_POPUP_RELOGIN_ERROR,
            self.INDEX_PAGE_DETECTED,
            self.INDEX_PAGE_NOT_DETECTED,
            self.E_INDEX_PAGE_TIMEOUT,
        ])

        if result and result.get('name') == 'IndexPageTimeout':
            self.log('Index page not found within timeout, attempting ESC recovery')
            for _ in range(5):
                pyautogui.press('escape')
                sleep(1)
            close_popup_recursive()
            sleep(2)

        if calibrate:
            self.log('Calibrating the window')
            self.window_axis = calibrate_window(self.window_axis)

        if not self.lang:
            self.log('Determining the language')
            self.determine_language()

        self.load_translations()

    def get_entry(self, command_name):
        return self.entries[command_name] \
            if command_name in self.entries \
            else None

    def get_instance(self, command_name):
        entry = self.get_entry(command_name)
        return entry['instance'] if entry and 'instance' in entry else None

    # def on_message(self, upd, text, retry=True):
    #     global EMULATE_NETWORK_ERROR
    #     try:
    #         if EMULATE_NETWORK_ERROR:
    #             EMULATE_NETWORK_ERROR = False
    #             raise NetworkError('from App.on_message')
    #
    #         upd.message.reply_text(text)
    #     except NetworkError as e:
    #         if retry:
    #             self.on_message(upd, text, retry=False)
    #     except Exception:
    #         pass

    def task(self, name, cb, task_type="aside"):
        # @TODO
        # self.tasks[name] =
        return lambda upd, ctx: self.taskManager.add(name, lambda: cb(upd, ctx), props={
            # 'onDone': lambda text: self.on_message(upd, text),
            # 'onError': lambda text: self.on_message(upd, text),
            'onDone': upd.message.reply_text,
            'onError': upd.message.reply_text,
            'type': task_type,
        })

    def load_translations(self):
        if self.lang and not self.translations:
            PATH_TRANSLATIONS = f"./translations/{self.lang}.json"
            try:
                with open(PATH_TRANSLATIONS, encoding='utf-8') as translations_file:
                    self.translations = json.load(translations_file)
                    self.log(f"Translations loaded: '{self.lang}'")
            except SystemError:
                log('An error occurred while reading ' + PATH_TRANSLATIONS + ' file')

    def detect_language(self):
        RGB_NOT_SELECTED_BUTTON = [17, 51, 67]
        x_offset = 209
        y_offset = 93
        btn_width = 208
        btn_height = 53
        x_gutter = 19
        y_gutter = 15

        lang = None

        for row in range(len(LANGUAGES_MATRIX)):
            for cell in range(len(LANGUAGES_MATRIX[row])):
                lang_btn = LANGUAGES_MATRIX[row][cell]
                if lang_btn and lang_btn in SUPPORTED_LANGUAGES:
                    x_btn = int(x_offset + (btn_width + x_gutter) * cell) + 10
                    y_btn = int(y_offset + (btn_height + y_gutter) * row) + 2

                    if not rgb_check(RGB_NOT_SELECTED_BUTTON, pyautogui.pixel(x_btn, y_btn), mistake=10):
                        lang = lang_btn
                        break

        return lang
