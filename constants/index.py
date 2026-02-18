# System
# @TODO Should move to the env variables file
IS_DEV = False
# IS_DEV = True

# Debug mode - включает отладку координат кликов и проверки цвета пикселей
# Включает: сохранение скриншотов с отмеченными точками кликов, логирование координат, отладку цвета пикселей
# DEBUG_MODE = True
# DEBUG_MODE = False
# DEPRECATED: DEBUG_MODE is now managed dynamically via helpers.common.is_debug_mode()
# and loaded from config.json

# Settings related
GAME_WINDOW = 'Raid: Shadow Legends'
PROCESS_GAME_NAME = 'Raid.exe'
PROCESS_PLARIUM_SERVICE_NAME = 'PlariumPlayClientService.exe'
PROCESS_PLARIUM_PLAY_NAME = 'PlariumPlay.exe'
WINDOW_TOP_BAR_HEIGHT = 25
BORDER_WIDTH = 7
CONFIG_PATH = "config.json"
CONFIG_DEFAULT_PATH = "config.default.json"
WINDOW_SIZE = [920, 540]


def get_config_path():
    """Возвращает путь к конфигу: сначала ищет config.json, если нет - config.default.json"""
    import os
    if os.path.exists(CONFIG_PATH):
        return CONFIG_PATH
    return CONFIG_DEFAULT_PATH
