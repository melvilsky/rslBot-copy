from bot import TelegramBOT
from classes.App import *
from classes.CommandRouter import CommandRouter
from classes.MessageContext import TelegramMessageContext
from classes.CLI import CLIRepl
from locations.live_arena.index import *
from helpers.common import get_last_chat_id
from constants.index import list_profile_filenames, has_profile_mode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
import os
import sys
import threading
from dotenv import load_dotenv

load_dotenv()
pyautogui.FAILSAFE = False
is_prod = is_production()

if not IS_DEV and is_prod:
    _path = os.path.join(sys._MEIPASS, './vendor/tesseract/tesseract.exe')
    pytesseract.pytesseract.tesseract_cmd = _path
else:
    TESSERACT_CMD = os.getenv('TESSERACT_CMD')
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = os.path.normpath(TESSERACT_CMD)
    else:
        print('Provide TESSERACT_CMD variable')


def main():
    if is_prod:
        log("The App is starting, don't touch the mouse and keyboard")
        sleep(10)

    app = App()

    validation_result = app.validation()
    if not validation_result:
        log("App validation failed - app is outdated")
        log_save('An App is outdated')
        if is_prod:
            input('Press Enter to exit...')
        sys.exit(1)

    if IS_DEV or validation_result:
        game_path = app.config['game_path']
        has_telegram_token = 'telegram_token' in app.config
        telegram_bot = None

        try:
            if app.config['start_immediate']:
                app.start()

            # ── CommandRouter: единый реестр команд для всех транспортов ──
            router = CommandRouter(app)

            # Регистрируем base app commands
            commands_to_apply = copy.copy(app.COMMANDS_GAME_PATH_DEPENDANT) if game_path else []
            commands_to_apply += app.COMMANDS_COMMON
            for command_name in commands_to_apply:
                command_data = app.commands[command_name]
                router.register(
                    name=command_name,
                    description=command_data['description'],
                    category=command_data.get('category', 'Управление'),
                    handler=command_data['handler'],
                )

            # ── Регистрация task/preset команд в router ──
            def register_task_preset_commands_in_router():
                if len(app.config['tasks']):
                    log(f"[startup] Building {len(app.config['tasks'])} task command(s)...")
                    for task in app.config['tasks']:
                        router.register(
                            name=task['command'],
                            description=f"command '{task['title']}'",
                            category='Игровые',
                            handler=app.task(
                                name=task['command'],
                                cb=app.get_entry(command_name=task['command'])['instance'].run
                            ),
                        )

                if len(app.config['presets']):
                    def process_preset_commands(msg_ctx, ctx, preset):
                        for command in preset['commands']:
                            app.task(
                                name=command,
                                cb=app.get_entry(command_name=command)['instance'].run
                            )(msg_ctx, ctx)

                    for preset in app.config['presets']:
                        router.register(
                            name=make_command_key(f"preset {preset['name']}"),
                            description=f"commands in a row: {', '.join(preset['commands'])}",
                            category='Пресеты',
                            handler=lambda msg_ctx, ctx, p=preset: process_preset_commands(msg_ctx, ctx, p),
                        )

            register_task_preset_commands_in_router()
            log('[startup] Task/preset commands registered in router')

            if has_profile_mode():
                def process_loadconfig(i, reply_fn):
                    names = list_profile_filenames()
                    if i < 0 or i >= len(names):
                        reply_fn('Профиль не найден.')
                        return
                    name = names[i]
                    try:
                        log(f'[loadconfig] Loading profile: {name}')

                        # Save old task/preset names before profile switch
                        old_tasks = [t['command'] for t in app.config.get('tasks', [])]
                        old_presets = [make_command_key(f"preset {p['name']}") for p in app.config.get('presets', [])]

                        app.load_profile_by_name(name)

                        if telegram_bot:
                            telegram_bot.remove_task_handlers()
                        # Remove old task/preset commands from router
                        for cmd in old_tasks + old_presets:
                            router.unregister(cmd)
                        # Re-register new task/preset commands
                        register_task_preset_commands_in_router()
                        # Re-register in telegram
                        if telegram_bot:
                            for cmd_info in router.list_commands():
                                if cmd_info['category'] in ('Игровые', 'Пресеты'):
                                    telegram_bot.add({
                                        'command': cmd_info['command'],
                                        'description': cmd_info['description'],
                                        'category': cmd_info['category'],
                                        'handler': make_telegram_handler(cmd_info['command']),
                                        'track': True,
                                    })

                        pid = getattr(app, 'current_player_id', None)
                        msg = f'Игрок {name} ({pid}) загружен и готов к работе.' if pid else f'Конфиг {name} загружен и готов к работе.'
                        log(f'[loadconfig] {msg}')
                        reply_fn(msg)
                    except Exception as e:
                        import traceback
                        err = traceback.format_exc()
                        log_save(f'[loadconfig] Error loading profile {name}: {err}')
                        reply_fn(f'Ошибка загрузки: {e}')

                def loadconfig_router_handler(msg_ctx, ctx):
                    if not has_profile_mode():
                        msg_ctx.reply_text('Режим профилей не активен (нет папки profiles с .json).')
                        return
                    names = list_profile_filenames()
                    if not names:
                        msg_ctx.reply_text('В папке profiles нет конфигов.')
                        return
                    
                    buttons = [[{'text': n, 'callback_data': f'loadconfig:{i}'}] for i, n in enumerate(names)]
                    msg_ctx.reply_text('Выберите конфиг для загрузки:', buttons=buttons)

                def router_loadconfig_callback(data, msg_ctx):
                    idx = data.split(':', 1)[1]
                    try:
                        i = int(idx)
                        process_loadconfig(i, lambda text: msg_ctx.reply_text(text))
                    except ValueError:
                        msg_ctx.reply_text('Неверные данные.')

                router.register_callback('loadconfig:', router_loadconfig_callback)

                router.register(
                    name='loadconfig',
                    description='Выбрать и загрузить конфиг из папки profiles',
                    category='Профили',
                    handler=loadconfig_router_handler,
                )
                log('[startup] loadconfig registered in router (profiles mode)')

            def router_help_text():
                lines = ['Доступные команды:']
                for cat_name, cmds in router.list_commands_grouped():
                    lines.append('')
                    lines.append(cat_name + ':')
                    for c in cmds:
                        if c['command'] in ('start', 'help'):
                            continue
                        lines.append('  /' + c['command'] + ' — ' + c['description'])
                return '\n'.join(lines)

            router.register(
                name='help',
                description='Список команд',
                category='Инфо',
                handler=lambda msg_ctx, ctx: msg_ctx.reply_text(router_help_text()),
            )
            router.register(
                name='start',
                description='Приветствие и список команд',
                category='Инфо',
                handler=lambda msg_ctx, ctx: msg_ctx.reply_text('RSL Bot\n\n' + router_help_text()),
            )

            # Telegram-only commands (checkupdate, update, clearchat, loadconfig)
            # These stay Telegram-specific because they use Telegram bot/chat APIs directly
            # but we also register simplified versions in router for Web/CLI where applicable

            router.register(
                name='checkupdate',
                description='Проверить наличие обновлений',
                category='Инфо',
                handler=lambda msg_ctx, ctx: msg_ctx.reply_text(
                    app.check_update_status(telegram_bot=telegram_bot),
                    parse_mode='HTML'
                ),
            )

            router.register(
                name='update',
                description='Обновить приложение до последней версии',
                category='Инфо',
                handler=lambda msg_ctx, ctx: msg_ctx.reply_text(
                    app.perform_update(telegram_bot=telegram_bot)
                ),
            )

            # ── Web server (daemon thread) ──
            from web.server import start_web
            from web.log_handler import install_web_log_handler
            install_web_log_handler()
            web_thread = threading.Thread(target=start_web, args=(router,), daemon=True)
            web_thread.start()

            # ── CLI REPL (daemon thread) ──
            cli = CLIRepl(router)
            cli.start()

            # ── Telegram bot ──
            if has_telegram_token:
                log('[startup] Creating TelegramBOT...')
                telegram_bot = TelegramBOT({
                    'token': app.config['telegram_token']
                })
                telegram_bot.start()
                log('[startup] TelegramBOT started')

                app.telegram_bot = telegram_bot

                log('[startup] Checking for updates...')
                app.check_for_updates(telegram_bot=telegram_bot)

                # Wrap each router command for Telegram:
                # Telegram handler receives (update, context) -> creates TelegramMessageContext -> calls router
                def make_telegram_handler(cmd_name):
                    def handler(upd, ctx):
                        msg_ctx = TelegramMessageContext(upd, ctx)
                        router.execute(cmd_name, msg_ctx)
                    return handler

                # Register all router commands into telegram bot (/start and /help stay from bot.py)
                for cmd_info in router.list_commands():
                    cmd_name = cmd_info['command']
                    if cmd_name in ('start', 'help'):
                        continue
                    is_task_or_preset = cmd_info['category'] in ('Игровые', 'Пресеты')
                    telegram_bot.add({
                        'command': cmd_name,
                        'description': cmd_info['description'],
                        'category': cmd_info['category'],
                        'handler': make_telegram_handler(cmd_name),
                        'track': is_task_or_preset,
                    })

                # Telegram-only: /clearchat (uses Telegram-specific APIs)
                telegram_bot.add({
                    'command': 'clearchat',
                    'description': 'Очистить чат от сообщений бота',
                    'category': 'Управление',
                    'handler': lambda upd, ctx: app.clear_chat(update=upd, context=ctx, telegram_bot=telegram_bot)
                })

                log('[startup] All commands registered in Telegram')

                # ── Profile mode (Telegram-only with inline keyboards) ──
                log('[startup] Setting up loadconfig...')
                def loadconfig_cmd(upd, ctx):
                    if not has_profile_mode():
                        upd.message.reply_text('Режим профилей не активен (нет папки profiles с .json).')
                        return
                    names = list_profile_filenames()
                    if not names:
                        upd.message.reply_text('В папке profiles нет конфигов.')
                        return
                    keyboard = [[InlineKeyboardButton(n, callback_data=f'loadconfig:{i}')] for i, n in enumerate(names)]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    upd.message.reply_text('Выберите конфиг для загрузки:', reply_markup=reply_markup)

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
                            
                    process_loadconfig(i, reply_fn)
                
                if has_profile_mode():
                    telegram_bot.add({
                        'command': 'loadconfig',
                        'description': 'Выбрать и загрузить конфиг из папки profiles',
                        'category': 'Профили',
                        'handler': loadconfig_cmd,
                    })
                    telegram_bot.dp.add_handler(CallbackQueryHandler(loadconfig_callback, run_async=True))

                    chat_id = get_last_chat_id()
                    if chat_id:
                        names = list_profile_filenames()
                        if names:
                            keyboard = [[InlineKeyboardButton(n, callback_data=f'loadconfig:{i}')] for i, n in enumerate(names)]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            try:
                                telegram_bot.updater.bot.send_message(
                                    chat_id=chat_id,
                                    text='Обнаружена папка profiles. Выберите конфиг для загрузки:',
                                    reply_markup=reply_markup
                                )
                            except Exception:
                                pass

                    # Send same profile selection to Web UI
                    try:
                        from web.server import broadcast_command_result
                        names = list_profile_filenames()
                        if names:
                            buttons = [[{'text': n, 'callback_data': f'loadconfig:{i}'}] for i, n in enumerate(names)]
                            broadcast_command_result('startup', {
                                'text': 'Обнаружена папка profiles. Выберите конфиг для загрузки:',
                                'buttons': buttons,
                            })
                    except Exception:
                        pass

                log('[startup] Starting bot polling (listen)...')
                telegram_bot.listen()
            else:
                # No Telegram token — block the main thread so Web and CLI keep running
                log('[startup] No Telegram token. Web and CLI are running. Press Ctrl+C to exit.')

                # Send profile selection to Web UI
                if has_profile_mode():
                    try:
                        from web.server import broadcast_command_result
                        names = list_profile_filenames()
                        if names:
                            buttons = [[{'text': n, 'callback_data': f'loadconfig:{i}'}] for i, n in enumerate(names)]
                            broadcast_command_result('startup', {
                                'text': 'Обнаружена папка profiles. Выберите конфиг для загрузки:',
                                'buttons': buttons,
                            })
                    except Exception:
                        pass

                threading.Event().wait()

        except KeyboardInterrupt:
            error = traceback.format_exc()
            log_save(error)
        except Exception:
            error = traceback.format_exc()
            log_save(error)

            if has_telegram_token and telegram_bot:
                telegram_bot.join()


if __name__ == '__main__':
    main()
