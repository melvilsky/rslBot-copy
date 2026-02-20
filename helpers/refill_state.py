"""
Модуль для отслеживания покупок дополнительных проходок в течение дня (UTC).
Автоматически сбрасывает счетчики при переходе на новый день в UTC.
Учёт ведётся отдельно для каждого профиля (warprofile).
"""
from datetime import datetime
import os
import json
from helpers.common import folder_ensure

_DEFAULT_PROFILE = '_default'


def get_utc_date_string():
    """Возвращает текущую дату в UTC в формате YYYY-MM-DD"""
    return datetime.utcnow().date().isoformat()


def get_state_file_path():
    """Возвращает путь к файлу состояния покупок"""
    folder = 'temp'
    folder_ensure(folder)
    return os.path.join(folder, 'refill_state.json')


def _resolve_profile(profile_name):
    """Возвращает ключ профиля: имя профиля или '_default' если не указан"""
    if profile_name and isinstance(profile_name, str) and profile_name.strip():
        return profile_name.strip()
    return _DEFAULT_PROFILE


def load_state():
    """
    Загружает состояние покупок из файла.
    Поддерживает два формата:
      - Новый: { "profile_name": { "location": { "date": {...} } } }
      - Старый (миграция): { "location": { "date": {...} } } -> перемещается в "_default"

    Returns:
        dict: Словарь с состоянием покупок или пустой словарь
    """
    file_path = get_state_file_path()
    current_date = get_utc_date_string()

    if not os.path.exists(file_path):
        return {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Миграция: если верхний уровень — локации (старый формат), оборачиваем в _default
        if data and not _is_new_format(data):
            data = {_DEFAULT_PROFILE: data}

        # Очистка устаревших дат
        cleaned = {}
        for profile, locations in data.items():
            if not isinstance(locations, dict):
                continue
            cleaned_locs = {}
            for loc_name, loc_data in locations.items():
                if not isinstance(loc_data, dict):
                    continue
                if current_date in loc_data:
                    cleaned_locs[loc_name] = {current_date: loc_data[current_date]}
            if cleaned_locs:
                cleaned[profile] = cleaned_locs

        if cleaned != data:
            save_state(cleaned)

        return cleaned
    except (json.JSONDecodeError, KeyError, Exception) as e:
        print(f"Error loading refill state: {e}")
        return {}


def _is_new_format(data):
    """
    Определяет формат файла: новый (профили) или старый (без профилей).
    В старом формате значения верхнего уровня содержат даты (YYYY-MM-DD).
    В новом — значения верхнего уровня содержат словари локаций.
    """
    for key, value in data.items():
        if not isinstance(value, dict):
            return False
        for inner_key in value:
            # Старый формат: ключ = дата (YYYY-MM-DD)
            if len(inner_key) == 10 and inner_key.count('-') == 2:
                try:
                    datetime.strptime(inner_key, '%Y-%m-%d')
                    return False
                except ValueError:
                    pass
            break
        break
    return True


def save_state(state):
    """Сохраняет состояние покупок в файл."""
    file_path = get_state_file_path()
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving refill state: {e}")


def get_purchased_count(location_name, profile_name=None):
    """
    Получает количество уже купленных проходок для локации и профиля на текущую UTC дату.

    Args:
        location_name: Название локации (например, 'arena_live')
        profile_name: Имя профиля (None -> '_default')
    """
    state = load_state()
    current_date = get_utc_date_string()
    profile = _resolve_profile(profile_name)

    profile_data = state.get(profile, {})
    loc_data = profile_data.get(location_name, {})
    date_data = loc_data.get(current_date, {})
    return date_data.get('purchased', 0)


def increment_purchase(location_name, max_allowed, profile_name=None):
    """
    Увеличивает счетчик покупок для локации и профиля на текущую UTC дату.

    Args:
        location_name: Название локации
        max_allowed: Максимальное разрешенное количество покупок из конфига
        profile_name: Имя профиля (None -> '_default')

    Returns:
        int: Новое количество купленных проходок
    """
    state = load_state()
    current_date = get_utc_date_string()
    profile = _resolve_profile(profile_name)

    if profile not in state:
        state[profile] = {}
    if location_name not in state[profile]:
        state[profile][location_name] = {}
    if current_date not in state[profile][location_name]:
        state[profile][location_name][current_date] = {
            'purchased': 0,
            'max_allowed': max_allowed
        }

    entry = state[profile][location_name][current_date]
    entry['purchased'] += 1
    entry['max_allowed'] = max_allowed
    entry['last_updated_utc'] = datetime.utcnow().isoformat() + 'Z'

    save_state(state)
    return entry['purchased']


def get_remaining_refills(location_name, max_allowed_from_config, profile_name=None):
    """
    Вычисляет сколько проходок осталось доступно для покупки.

    Args:
        location_name: Название локации
        max_allowed_from_config: Максимальное количество из конфига
        profile_name: Имя профиля (None -> '_default')

    Returns:
        int: Количество оставшихся проходок (не может быть отрицательным)
    """
    purchased = get_purchased_count(location_name, profile_name=profile_name)
    remaining = max_allowed_from_config - purchased
    return max(0, remaining)

