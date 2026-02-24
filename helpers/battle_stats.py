"""
Модуль для персистентного хранения статистики боёв/результатов всех локаций.
Данные хранятся в temp/battle_stats.json по структуре:
  profile -> location_key -> date (UTC) -> stats_data

Автоматически сбрасывает данные при переходе на новый день (UTC).
Учёт ведётся отдельно для каждого профиля (warprofile).
"""
from datetime import datetime
import os
import json
from helpers.common import folder_ensure

_DEFAULT_PROFILE = '_default'
_FILE_NAME = 'battle_stats.json'


def _get_utc_date():
    return datetime.utcnow().date().isoformat()


def _get_file_path():
    folder = 'temp'
    folder_ensure(folder)
    return os.path.join(folder, _FILE_NAME)


def _resolve_profile(profile_name):
    if profile_name and isinstance(profile_name, str) and profile_name.strip():
        return profile_name.strip()
    return _DEFAULT_PROFILE


def _load_all():
    file_path = _get_file_path()
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return {}


def _save_all(data):
    file_path = _get_file_path()
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving battle stats: {e}")


def _clean_old_dates(data):
    """Оставляет только записи за сегодня (UTC)."""
    current_date = _get_utc_date()
    cleaned = {}
    for profile, locations in data.items():
        if not isinstance(locations, dict):
            continue
        cleaned_locs = {}
        for loc_key, loc_data in locations.items():
            if not isinstance(loc_data, dict):
                continue
            if current_date in loc_data:
                cleaned_locs[loc_key] = {current_date: loc_data[current_date]}
        if cleaned_locs:
            cleaned[profile] = cleaned_locs
    return cleaned


def _ensure_path(data, profile, location_key, date):
    if profile not in data:
        data[profile] = {}
    if location_key not in data[profile]:
        data[profile][location_key] = {}
    if date not in data[profile][location_key]:
        data[profile][location_key][date] = {}
    return data[profile][location_key][date]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_win(location_key, profile_name=None):
    """Записывает +1 победу для локации."""
    data = _clean_old_dates(_load_all())
    date = _get_utc_date()
    profile = _resolve_profile(profile_name)
    entry = _ensure_path(data, profile, location_key, date)
    entry['wins'] = entry.get('wins', 0) + 1
    entry.setdefault('losses', 0)
    _save_all(data)


def record_loss(location_key, profile_name=None):
    """Записывает +1 поражение для локации."""
    data = _clean_old_dates(_load_all())
    date = _get_utc_date()
    profile = _resolve_profile(profile_name)
    entry = _ensure_path(data, profile, location_key, date)
    entry['losses'] = entry.get('losses', 0) + 1
    entry.setdefault('wins', 0)
    _save_all(data)


def record_win_loss(location_key, sub_key, is_win, profile_name=None):
    """
    Записывает результат для локации с подкатегориями (dungeons, etc.).
    Данные пишутся в entry["sub"][sub_key].
    """
    data = _clean_old_dates(_load_all())
    date = _get_utc_date()
    profile = _resolve_profile(profile_name)
    entry = _ensure_path(data, profile, location_key, date)
    sub = entry.setdefault('sub', {})
    item = sub.setdefault(sub_key, {'wins': 0, 'losses': 0})
    if is_win:
        item['wins'] = item.get('wins', 0) + 1
    else:
        item['losses'] = item.get('losses', 0) + 1
    _save_all(data)


def update_stats(location_key, stats_dict, profile_name=None):
    """
    Универсальное обновление — мержит stats_dict в текущую запись за сегодня.
    Для вложенных данных используйте sub_key через update_sub_stats().
    """
    data = _clean_old_dates(_load_all())
    date = _get_utc_date()
    profile = _resolve_profile(profile_name)
    entry = _ensure_path(data, profile, location_key, date)
    entry.update(stats_dict)
    _save_all(data)


def update_sub_stats(location_key, sub_key, stats_dict, profile_name=None):
    """Обновляет подкатегорию: entry["sub"][sub_key] мержится с stats_dict."""
    data = _clean_old_dates(_load_all())
    date = _get_utc_date()
    profile = _resolve_profile(profile_name)
    entry = _ensure_path(data, profile, location_key, date)
    sub = entry.setdefault('sub', {})
    item = sub.setdefault(sub_key, {})
    item.update(stats_dict)
    _save_all(data)


def load_stats(location_key, profile_name=None):
    """
    Загружает статистику за сегодня для одной локации.
    Returns: dict с данными или пустой dict.
    """
    data = _clean_old_dates(_load_all())
    date = _get_utc_date()
    profile = _resolve_profile(profile_name)
    return data.get(profile, {}).get(location_key, {}).get(date, {})


def load_all_stats(profile_name=None):
    """
    Загружает всю статистику за сегодня для профиля.
    Returns: dict { location_key: stats_data }
    """
    data = _clean_old_dates(_load_all())
    date = _get_utc_date()
    profile = _resolve_profile(profile_name)
    profile_data = data.get(profile, {})
    result = {}
    for loc_key, loc_data in profile_data.items():
        if date in loc_data:
            result[loc_key] = loc_data[date]
    return result
