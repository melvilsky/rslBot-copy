from bot import TelegramBOT
from classes.App import *
from locations.live_arena.index import *
import os
import sys
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
    # debug_save_screenshot(region=[845, 251, 42, 42], quality=100)
    # return

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
                # print('App is started')
                # sleep(5)
                # app.get_instance('arena_live').attack()

            if has_telegram_token:
                telegram_bot = TelegramBOT({
                    'token': app.config['telegram_token']
                })
                telegram_bot.start()
                
                # Устанавливаем ссылку на бота в app для доступа из методов
                app.telegram_bot = telegram_bot
                
                # Проверяем обновления при запуске
                app.check_for_updates(telegram_bot=telegram_bot)
                
                # Добавляем команду /checkupdate
                telegram_bot.add({
                    'command': 'checkupdate',
                    'description': 'Проверить наличие обновлений',
                    'handler': lambda upd, ctx: upd.message.reply_text(app.check_update_status(telegram_bot=telegram_bot), parse_mode='HTML')
                })
                
                # Добавляем команду /update
                telegram_bot.add({
                    'command': 'update',
                    'description': 'Обновить приложение до последней версии',
                    'handler': lambda upd, ctx: upd.message.reply_text(app.perform_update(telegram_bot=telegram_bot))
                })
                
                # Добавляем команду /clearchat
                telegram_bot.add({
                    'command': 'clearchat',
                    'description': 'Очистить чат от сообщений бота',
                    'handler': lambda upd, ctx: upd.message.reply_text(app.clear_chat(telegram_bot=telegram_bot))
                })

                commands_to_apply = copy.copy(app.COMMANDS_GAME_PATH_DEPENDANT) if game_path else []
                commands_to_apply += app.COMMANDS_COMMON

                for i in range(len(commands_to_apply)):
                    command_name = commands_to_apply[i]
                    command_data = app.commands[command_name]
                    telegram_bot.add({
                        'command': command_name,
                        'description': command_data['description'],
                        'handler': command_data['handler'],
                    })

                # register main commands according to 'tasks'
                regular_command = []
                if len(app.config['tasks']):
                    regular_command = list(map(lambda task: {
                        'command': task['command'],
                        'description': f"command '{task['title']}'",
                        'handler': app.task(
                            name=task['command'],
                            cb=app.get_entry(command_name=task['command'])['instance'].run
                        ),
                    }, app.config['tasks']))

                # register addition commands according to 'presets'
                presets_commands = []
                if len(app.config['presets']):
                    def process_preset_commands(upd, ctx, preset):
                        for i in range(len(preset['commands'])):
                            command = preset['commands'][i]
                            app.task(
                                name=command,
                                cb=app.get_entry(command_name=command)['instance'].run
                            )(upd, ctx)

                    presets_commands = list(map(lambda preset: {
                        'command': make_command_key(f"preset {preset['name']}"),
                        'description': f"commands in a row: {', '.join(preset['commands'])}",
                        'handler': lambda upd, ctx: process_preset_commands(upd, ctx, preset),
                    }, app.config['presets']))

                commands = regular_command + presets_commands

                for i in range(len(commands)):
                    telegram_bot.add(commands[i])

                telegram_bot.listen()
                telegram_bot.updater.idle()



        except KeyboardInterrupt:
            error = traceback.format_exc()
            log_save(error)
        except Exception:
            error = traceback.format_exc()
            log_save(error)

            if has_telegram_token and telegram_bot:
                # Wait for the bot thread to finish
                telegram_bot.join()


if __name__ == '__main__':
    main()
