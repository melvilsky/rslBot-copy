"""
Модуль для отслеживания покупок дополнительных проходок в течение дня (UTC).
Автоматически сбрасывает счетчики при переходе на новый день в UTC.
"""
from datetime import datetime
import os
import json
from helpers.common import folder_ensure


def get_utc_date_string():
    """Возвращает текущую дату в UTC в формате YYYY-MM-DD"""
    return datetime.utcnow().date().isoformat()


def get_state_file_path():
    """Возвращает путь к файлу состояния покупок"""
    folder = 'temp'
    folder_ensure(folder)
    return os.path.join(folder, 'refill_state.json')


def load_state():
    """
    Загружает состояние покупок из файла.
    Если файла нет или дата в файле отличается от текущей UTC даты - возвращает пустой словарь.
    
    Returns:
        dict: Словарь с состоянием покупок или пустой словарь
    """
    file_path = get_state_file_path()
    current_date = get_utc_date_string()
    
    # Если файла нет - возвращаем пустой словарь
    if not os.path.exists(file_path):
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Проверяем все локации и удаляем записи с устаревшими датами
        cleaned_data = {}
        for location_name, location_data in data.items():
            # Если есть запись для текущей даты - оставляем её
            if current_date in location_data:
                cleaned_data[location_name] = {
                    current_date: location_data[current_date]
                }
        
        # Если данные изменились (удалили старые записи) - сохраняем
        if cleaned_data != data:
            save_state(cleaned_data)
            return cleaned_data
        
        return cleaned_data
    except (json.JSONDecodeError, KeyError, Exception) as e:
        # Если ошибка чтения - возвращаем пустой словарь
        print(f"Error loading refill state: {e}")
        return {}


def save_state(state):
    """
    Сохраняет состояние покупок в файл.
    
    Args:
        state: Словарь с состоянием покупок
    """
    file_path = get_state_file_path()
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving refill state: {e}")


def get_purchased_count(location_name):
    """
    Получает количество уже купленных проходок для указанной локации на текущую UTC дату.
    
    Args:
        location_name: Название локации (например, 'arena_live', 'arena_classic')
    
    Returns:
        int: Количество уже купленных проходок (0 если записей нет)
    """
    state = load_state()
    current_date = get_utc_date_string()
    
    if location_name not in state:
        return 0
    
    if current_date not in state[location_name]:
        return 0
    
    return state[location_name][current_date].get('purchased', 0)


def increment_purchase(location_name, max_allowed):
    """
    Увеличивает счетчик покупок для указанной локации на текущую UTC дату.
    
    Args:
        location_name: Название локации (например, 'arena_live', 'arena_classic')
        max_allowed: Максимальное разрешенное количество покупок из конфига
    
    Returns:
        int: Новое количество купленных проходок
    """
    state = load_state()
    current_date = get_utc_date_string()
    
    # Инициализируем структуру если её нет
    if location_name not in state:
        state[location_name] = {}
    
    if current_date not in state[location_name]:
        state[location_name][current_date] = {
            'purchased': 0,
            'max_allowed': max_allowed
        }
    
    # Увеличиваем счетчик
    state[location_name][current_date]['purchased'] += 1
    state[location_name][current_date]['max_allowed'] = max_allowed
    state[location_name][current_date]['last_updated_utc'] = datetime.utcnow().isoformat() + 'Z'
    
    save_state(state)
    
    return state[location_name][current_date]['purchased']


def get_remaining_refills(location_name, max_allowed_from_config):
    """
    Вычисляет сколько проходок осталось доступно для покупки.
    
    Args:
        location_name: Название локации
        max_allowed_from_config: Максимальное количество из конфига
    
    Returns:
        int: Количество оставшихся проходок (не может быть отрицательным)
    """
    purchased = get_purchased_count(location_name)
    remaining = max_allowed_from_config - purchased
    return max(0, remaining)

