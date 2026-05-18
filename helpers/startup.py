import copy
import threading

from bot import TelegramBOT
from classes.CLI import CLIRepl
from classes.MessageContext import TelegramMessageContext
from constants.index import has_profile_mode, list_profile_filenames
from helpers.common import get_last_chat_id, make_command_key
from helpers.logging_utils import log, log_save
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler


class StartupServices:
    def __init__(self, app, router):
        self.app = app
        self.router = router
        self.telegram_bot = None

    def register_router_commands(self):
        self._register_base_commands()
        self.register_task_preset_commands()
        self._register_profile_commands()
        self._register_help_commands()
        self._register_update_commands()

    def _register_base_commands(self):
        commands_to_apply = copy.copy(self.app.COMMANDS_GAME_PATH_DEPENDANT) if self.app.config['game_path'] else []
        commands_to_apply += self.app.COMMANDS_COMMON
        for command_name in commands_to_apply:
            command_data = self.app.commands[command_name]
            self.router.register(
                name=command_name,
                description=command_data['description'],
                category=command_data.get('category', 'Управление'),
                handler=command_data['handler'],
            )

    def register_task_preset_commands(self):
        if len(self.app.config['tasks']):
            log(f"[startup] Building {len(self.app.config['tasks'])} task command(s)...")
            for task in self.app.config['tasks']:
                self.router.register(
                    name=task['command'],
                    description=f"command '{task['title']}'",
                    category='Игровые',
                    handler=self.app.task(
                        name=task['command'],
                        cb=self.app.get_entry(command_name=task['command'])['instance'].run
                    ),
                )

        if len(self.app.config['presets']):
            def process_preset_commands(msg_ctx, ctx, preset):
                for command in preset['commands']:
                    self.app.task(
                        name=command,
                        cb=self.app.get_entry(command_name=command)['instance'].run
                    )(msg_ctx, ctx)

            for preset in self.app.config['presets']:
                self.router.register(
                    name=make_command_key(f"preset {preset['name']}"),
                    description=f"commands in a row: {', '.join(preset['commands'])}",
                    category='Пресеты',
                    handler=lambda msg_ctx, ctx, p=preset: process_preset_commands(msg_ctx, ctx, p),
                )
        log('[startup] Task/preset commands registered in router')

    def _register_profile_commands(self):
        if not has_profile_mode():
            return

        self.router.register_callback('loadconfig:', self._router_loadconfig_callback)
        self.router.register(
            name='loadconfig',
            description='Выбрать и загрузить конфиг из папки profiles',
            category='Профили',
            handler=self._loadconfig_router_handler,
        )
        log('[startup] loadconfig registered in router (profiles mode)')

    def _loadconfig_router_handler(self, msg_ctx, ctx):
        if not has_profile_mode():
            msg_ctx.reply_text('Режим профилей не активен (нет папки profiles с .json).')
            return
        names = list_profile_filenames()
        if not names:
            msg_ctx.reply_text('В папке profiles нет конфигов.')
            return

        buttons = [[{'text': n, 'callback_data': f'loadconfig:{i}'}] for i, n in enumerate(names)]
        msg_ctx.reply_text('Выберите конфиг для загрузки:', buttons=buttons)

    def _router_loadconfig_callback(self, data, msg_ctx):
        idx = data.split(':', 1)[1]
        try:
            self.process_loadconfig(int(idx), lambda text: msg_ctx.reply_text(text))
        except ValueError:
            msg_ctx.reply_text('Неверные данные.')

    def process_loadconfig(self, i, reply_fn):
        names = list_profile_filenames()
        if i < 0 or i >= len(names):
            reply_fn('Профиль не найден.')
            return
        name = names[i]
        try:
            log(f'[loadconfig] Loading profile: {name}')
            old_tasks = [t['command'] for t in self.app.config.get('tasks', [])]
            old_presets = [make_command_key(f"preset {p['name']}") for p in self.app.config.get('presets', [])]

            self.app.load_profile_by_name(name)

            if self.telegram_bot:
                self.telegram_bot.remove_task_handlers()
            for cmd in old_tasks + old_presets:
                self.router.unregister(cmd)
            self.register_task_preset_commands()
            if self.telegram_bot:
                self._register_task_commands_in_telegram()

            pid = getattr(self.app, 'current_player_id', None)
            msg = f'Игрок {name} ({pid}) загружен и готов к работе.' if pid else f'Конфиг {name} загружен и готов к работе.'
            log(f'[loadconfig] {msg}')
            reply_fn(msg)
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            log_save(f'[loadconfig] Error loading profile {name}: {err}')
            reply_fn(f'Ошибка загрузки: {e}')

    def _register_help_commands(self):
        self.router.register(
            name='help',
            description='Список команд',
            category='Инфо',
            handler=lambda msg_ctx, ctx: msg_ctx.reply_text(self.router_help_text()),
            hidden=True,
        )
        self.router.register(
            name='start',
            description='Приветствие и список команд',
            category='Инфо',
            handler=lambda msg_ctx, ctx: msg_ctx.reply_text('RSL Bot\n\n' + self.router_help_text()),
            hidden=True,
        )

    def router_help_text(self):
        lines = ['Доступные команды:']
        for cat_name, cmds in self.router.list_commands_grouped():
            lines.append('')
            lines.append(cat_name + ':')
            for c in cmds:
                if c['command'] in ('start', 'help'):
                    continue
                lines.append('  /' + c['command'] + ' — ' + c['description'])
        return '\n'.join(lines)

    def _register_update_commands(self):
        self.router.register(
            name='checkupdate',
            description='Проверить наличие обновлений',
            category='Инфо',
            handler=lambda msg_ctx, ctx: msg_ctx.reply_text(
                self.app.check_update_status(telegram_bot=self.telegram_bot),
                parse_mode='HTML'
            ),
        )
        self.router.register(
            name='update',
            description='Обновить приложение до последней версии',
            category='Инфо',
            handler=lambda msg_ctx, ctx: msg_ctx.reply_text(
                self.app.perform_update(telegram_bot=self.telegram_bot)
            ),
        )

    def start_web_and_cli(self):
        from web.log_handler import install_web_log_handler
        from web.server import start_web
        install_web_log_handler()
        web_thread = threading.Thread(target=start_web, args=(self.router,), daemon=True)
        web_thread.start()
        CLIRepl(self.router).start()

    def make_telegram_handler(self, cmd_name):
        def handler(upd, ctx):
            msg_ctx = TelegramMessageContext(upd, ctx)
            self.router.execute(cmd_name, msg_ctx)
        return handler

    def start_telegram(self):
        log('[startup] Creating TelegramBOT...')
        self.telegram_bot = TelegramBOT({'token': self.app.config['telegram_token']})
        self.telegram_bot.start()
        self.app.telegram_bot = self.telegram_bot
        log('[startup] TelegramBOT started')

        log('[startup] Checking for updates...')
        self.app.check_for_updates(telegram_bot=self.telegram_bot)

        for cmd_info in self.router.list_commands():
            cmd_name = cmd_info['command']
            if cmd_name in ('start', 'help'):
                continue
            self.telegram_bot.add({
                'command': cmd_name,
                'description': cmd_info['description'],
                'category': cmd_info['category'],
                'handler': self.make_telegram_handler(cmd_name),
                'track': cmd_info['category'] in ('Игровые', 'Пресеты'),
            })

        self.telegram_bot.add({
            'command': 'clearchat',
            'description': 'Очистить чат от сообщений бота',
            'category': 'Управление',
            'handler': lambda upd, ctx: self.app.clear_chat(update=upd, context=ctx, telegram_bot=self.telegram_bot)
        })
        log('[startup] All commands registered in Telegram')

        self._setup_telegram_loadconfig()
        log('[startup] Starting bot polling (listen)...')
        self.telegram_bot.listen()

    def _register_task_commands_in_telegram(self):
        for cmd_info in self.router.list_commands():
            if cmd_info['category'] in ('Игровые', 'Пресеты'):
                self.telegram_bot.add({
                    'command': cmd_info['command'],
                    'description': cmd_info['description'],
                    'category': cmd_info['category'],
                    'handler': self.make_telegram_handler(cmd_info['command']),
                    'track': True,
                })

    def _setup_telegram_loadconfig(self):
        log('[startup] Setting up loadconfig...')
        if not has_profile_mode():
            return

        def loadconfig_cmd(upd, ctx):
            names = list_profile_filenames()
            if not names:
                upd.message.reply_text('В папке profiles нет конфигов.')
                return
            keyboard = [[InlineKeyboardButton(n, callback_data=f'loadconfig:{i}')] for i, n in enumerate(names)]
            upd.message.reply_text(
                'Выберите конфиг для загрузки:',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        def loadconfig_callback(upd, ctx):
            query = upd.callback_query
            query.answer()
            data = query.data
            if not data.startswith('loadconfig:'):
                return
            idx = data.split(':', 1)[1]
            names = list_profile_filenames()
            try:
                i = int(idx)
                if i < 0 or i >= len(names):
                    try:
                        query.edit_message_text(text='Профиль не найден.')
                    except Exception:
                        pass
                    return
            except ValueError:
                try:
                    query.edit_message_text(text='Неверные данные.')
                except Exception:
                    pass
                return

            def reply_fn(text):
                try:
                    query.edit_message_text(text=text)
                except Exception:
                    ctx.bot.send_message(chat_id=query.message.chat_id, text=text)

            self.process_loadconfig(i, reply_fn)

        self.telegram_bot.add({
            'command': 'loadconfig',
            'description': 'Выбрать и загрузить конфиг из папки profiles',
            'category': 'Профили',
            'handler': loadconfig_cmd,
        })
        self.telegram_bot.dp.add_handler(CallbackQueryHandler(loadconfig_callback, run_async=True))
        self.send_startup_profile_selection()

    def send_startup_profile_selection(self):
        if not has_profile_mode():
            return
        names = list_profile_filenames()
        if not names:
            return
        buttons = [[{'text': n, 'callback_data': f'loadconfig:{i}'}] for i, n in enumerate(names)]

        if self.telegram_bot:
            chat_id = get_last_chat_id()
            if chat_id:
                keyboard = [[InlineKeyboardButton(n, callback_data=f'loadconfig:{i}')] for i, n in enumerate(names)]
                try:
                    self.telegram_bot.updater.bot.send_message(
                        chat_id=chat_id,
                        text='Обнаружена папка profiles. Выберите конфиг для загрузки:',
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception:
                    pass

        try:
            from web.server import broadcast_command_result
            broadcast_command_result('startup', {
                'text': 'Обнаружена папка profiles. Выберите конфиг для загрузки:',
                'buttons': buttons,
            })
        except Exception:
            pass
