import os
import sys
import threading
import traceback

import pyautogui
import pytesseract
from dotenv import load_dotenv

from classes.App import App
from classes.CommandRouter import CommandRouter
from constants.index import IS_DEV
from helpers.common import is_production, log, log_save, sleep
from helpers.startup import StartupServices

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

    if not (IS_DEV or validation_result):
        return

    has_telegram_token = 'telegram_token' in app.config
    services = StartupServices(app, CommandRouter(app))

    try:
        if app.config['start_immediate']:
            app.start()

        services.register_router_commands()
        services.start_web_and_cli()

        if has_telegram_token:
            services.start_telegram()
        else:
            log('[startup] No Telegram token. Web and CLI are running. Press Ctrl+C to exit.')
            services.send_startup_profile_selection()
            threading.Event().wait()

    except KeyboardInterrupt:
        log_save(traceback.format_exc())
    except Exception:
        log_save(traceback.format_exc())
        if has_telegram_token and services.telegram_bot:
            services.telegram_bot.join()


if __name__ == '__main__':
    main()
