"""
Модуль для отслеживания покупок дополнительных проходок в течение дня (UTC).
Автоматически сбрасывает счетчики при переходе на новый день в UTC.
Учёт ведётся отдельно для каждого профиля (warprofile).

Модель данных (на профиль/локацию/UTC-дату):
    {
      "purchased": <число подтверждённых платных покупок>,
      "max_allowed": <лимит из конфига>,
      "last_updated_utc": "...",
      "attempts": [
        {"id", "kind": "paid"|"free", "status": "pending"|"confirmed"|"failed"|"uncertain",
         "tokens_before", "tokens_after", "created_at_utc", "resolved_at_utc"}
      ]
    }

Платная покупка расходует дневной лимит только в статусе "confirmed".
Незавершённая попытка ("pending"/"uncertain") блокирует новую платную попытку
до ручной или автоматической reconciliation (см. план, Этап 4).
"""
from datetime import datetime
import json
import os
import tempfile
import threading
import uuid

from helpers.common import folder_ensure
from helpers.logging_utils import log

_DEFAULT_PROFILE = '_default'
_STATE_LOCK = threading.RLock()

ATTEMPT_PENDING = 'pending'
ATTEMPT_CONFIRMED = 'confirmed'
ATTEMPT_FAILED = 'failed'
ATTEMPT_UNCERTAIN = 'uncertain'

KIND_FREE = 'free'
KIND_PAID = 'paid'

_UNRESOLVED_STATUSES = (ATTEMPT_PENDING, ATTEMPT_UNCERTAIN)


class RefillStateError(Exception):
    """Ошибка учёта покупок. Для платных операций политика fail-closed:
    при невозможности надёжно прочитать/записать состояние покупка запрещена."""


def get_utc_date_string():
    """Возвращает текущую дату в UTC в формате YYYY-MM-DD"""
    return datetime.utcnow().date().isoformat()


def _utc_now_string():
    return datetime.utcnow().isoformat() + 'Z'


def get_state_file_path():
    """Возвращает путь к файлу состояния покупок"""
    folder = 'temp'
    folder_ensure(folder)
    return os.path.join(folder, 'refill_state.json')


def get_audit_file_path():
    """Путь к append-only журналу попыток refill (план, Этап 7)."""
    folder = 'temp'
    folder_ensure(folder)
    return os.path.join(folder, 'refill_audit.log')


def _audit(record):
    """Пишет одну append-only строку аудита. Ошибки аудита не блокируют работу."""
    try:
        record = dict(record)
        record['ts_utc'] = _utc_now_string()
        with open(get_audit_file_path(), 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as e:
        log(f"Refill audit write failed: {e}")


def _resolve_profile(profile_name):
    """Возвращает ключ профиля: имя профиля или '_default' если не указан"""
    if profile_name and isinstance(profile_name, str) and profile_name.strip():
        return profile_name.strip()
    return _DEFAULT_PROFILE


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


def _load_state_locked(strict=False):
    """
    Читает и нормализует состояние. Вызывается только под _STATE_LOCK.

    strict=True — политика fail-closed: ошибка чтения поднимает RefillStateError
    (используется перед платными операциями). strict=False — legacy-поведение
    для чтения статистики: ошибка логируется, возвращается пустое состояние.
    """
    file_path = get_state_file_path()
    current_date = get_utc_date_string()

    if not os.path.exists(file_path):
        return {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        message = f"Error loading refill state: {e}"
        log(message)
        if strict:
            raise RefillStateError(message)
        return {}

    if not isinstance(data, dict):
        message = f"Refill state has unexpected root type: {type(data).__name__}"
        log(message)
        if strict:
            raise RefillStateError(message)
        return {}

    # Миграция: если верхний уровень — локации (старый формат), оборачиваем в _default
    if data and not _is_new_format(data):
        data = {_DEFAULT_PROFILE: data}

    # Очистка устаревших дат (UTC rollover)
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
        _save_state_locked(cleaned)

    return cleaned


def _save_state_locked(state):
    """Атомарная запись (temp file + fsync + os.replace). Только под _STATE_LOCK."""
    file_path = get_state_file_path()
    dir_name = os.path.dirname(file_path) or '.'
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix='refill_state_tmp_', suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, file_path)
        temp_path = None
    except Exception as e:
        message = f"Error saving refill state atomically: {e}"
        log(message)
        raise RefillStateError(message)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def load_state():
    """Загружает состояние покупок (не strict). Returns: dict."""
    with _STATE_LOCK:
        return _load_state_locked(strict=False)


def save_state(state):
    """Сохраняет состояние покупок в файл с использованием блокировки."""
    with _STATE_LOCK:
        _save_state_locked(state)


def _entry_locked(state, location_name, max_allowed, profile_name):
    """Возвращает (и при необходимости создаёт) запись текущего UTC-дня."""
    current_date = get_utc_date_string()
    profile = _resolve_profile(profile_name)

    state.setdefault(profile, {})
    state[profile].setdefault(location_name, {})
    if current_date not in state[profile][location_name]:
        state[profile][location_name][current_date] = {
            'purchased': 0,
            'max_allowed': max_allowed,
            'attempts': [],
        }

    entry = state[profile][location_name][current_date]
    entry.setdefault('purchased', 0)
    entry.setdefault('attempts', [])
    if max_allowed is not None:
        entry['max_allowed'] = max_allowed
    return entry


def get_purchased_count(location_name, profile_name=None):
    """
    Получает количество подтверждённых покупок для локации и профиля
    на текущую UTC дату.
    """
    state = load_state()
    current_date = get_utc_date_string()
    profile = _resolve_profile(profile_name)

    profile_data = state.get(profile, {})
    loc_data = profile_data.get(location_name, {})
    date_data = loc_data.get(current_date, {})
    return date_data.get('purchased', 0)


def get_remaining_refills(location_name, max_allowed_from_config, profile_name=None):
    """
    Вычисляет сколько проходок осталось доступно для покупки.
    Returns: int (не может быть отрицательным).
    """
    purchased = get_purchased_count(location_name, profile_name=profile_name)
    remaining = max_allowed_from_config - purchased
    return max(0, remaining)


def has_unresolved_attempt(location_name, profile_name=None):
    """True, если за текущий UTC-день есть незавершённая (pending/uncertain)
    платная попытка. Такая попытка блокирует новый автоматический платный клик."""
    state = load_state()
    current_date = get_utc_date_string()
    profile = _resolve_profile(profile_name)

    entry = state.get(profile, {}).get(location_name, {}).get(current_date, {})
    for attempt in entry.get('attempts', []):
        if attempt.get('kind') == KIND_PAID and attempt.get('status') in _UNRESOLVED_STATUSES:
            return True
    return False


def increment_purchase(location_name, max_allowed, profile_name=None):
    """
    Увеличивает счетчик подтверждённых покупок в одной критической секции.
    Проверяет лимит внутри операции: превышение поднимает RefillStateError.

    Returns:
        int: Новое количество купленных проходок
    """
    with _STATE_LOCK:
        state = _load_state_locked(strict=True)
        entry = _entry_locked(state, location_name, max_allowed, profile_name)

        if entry['purchased'] >= max_allowed:
            raise RefillStateError(
                f"Purchase limit reached for {location_name}: "
                f"{entry['purchased']}/{max_allowed}"
            )

        entry['purchased'] += 1
        entry['last_updated_utc'] = _utc_now_string()
        _save_state_locked(state)
        return entry['purchased']


def begin_refill_attempt(location_name, kind, max_allowed, profile_name=None, tokens_before=None):
    """
    Транзакционно регистрирует попытку refill со статусом 'pending',
    НЕ расходуя дневной лимит (план, Этап 4, шаги 4-5).

    Для kind='paid' в одной критической секции проверяется:
      - число подтверждённых покупок меньше лимита;
      - отсутствие незавершённой (pending/uncertain) платной попытки.

    Returns:
        str: attempt_id

    Raises:
        RefillStateError: лимит исчерпан, есть незавершённая попытка либо
        состояние не удалось надёжно прочитать/записать (fail-closed).
    """
    if kind not in (KIND_FREE, KIND_PAID):
        raise ValueError(f"Unknown refill kind: {kind}")

    with _STATE_LOCK:
        state = _load_state_locked(strict=(kind == KIND_PAID))
        entry = _entry_locked(state, location_name, max_allowed, profile_name)

        if kind == KIND_PAID:
            if entry['purchased'] >= entry.get('max_allowed', max_allowed):
                raise RefillStateError(
                    f"Paid refill limit reached for {location_name}: "
                    f"{entry['purchased']}/{entry.get('max_allowed', max_allowed)}"
                )
            for attempt in entry['attempts']:
                if attempt.get('kind') == KIND_PAID and attempt.get('status') in _UNRESOLVED_STATUSES:
                    raise RefillStateError(
                        f"Unresolved paid refill attempt {attempt.get('id')} "
                        f"({attempt.get('status')}) blocks a new paid attempt"
                    )

        attempt_id = str(uuid.uuid4())
        attempt = {
            'id': attempt_id,
            'kind': kind,
            'status': ATTEMPT_PENDING,
            'tokens_before': tokens_before,
            'tokens_after': None,
            'created_at_utc': _utc_now_string(),
            'resolved_at_utc': None,
        }
        entry['attempts'].append(attempt)
        entry['last_updated_utc'] = _utc_now_string()
        _save_state_locked(state)

    _audit({
        'event': 'attempt_created',
        'location': location_name,
        'profile': _resolve_profile(profile_name),
        'attempt_id': attempt_id,
        'kind': kind,
        'tokens_before': tokens_before,
    })
    return attempt_id


def resolve_refill_attempt(location_name, attempt_id, status, profile_name=None, tokens_after=None):
    """
    Переводит попытку в конечный статус. Только переход в 'confirmed'
    платной попытки расходует дневной лимит (план, Этап 4, шаги 8-9).

    Raises:
        RefillStateError: попытка не найдена либо состояние недоступно.
    """
    if status not in (ATTEMPT_CONFIRMED, ATTEMPT_FAILED, ATTEMPT_UNCERTAIN):
        raise ValueError(f"Unknown attempt status: {status}")

    with _STATE_LOCK:
        state = _load_state_locked(strict=True)
        current_date = get_utc_date_string()
        profile = _resolve_profile(profile_name)
        entry = state.get(profile, {}).get(location_name, {}).get(current_date)
        if not entry:
            raise RefillStateError(
                f"No refill entry for {location_name}/{profile}/{current_date}"
            )

        attempt = None
        for item in entry.get('attempts', []):
            if item.get('id') == attempt_id:
                attempt = item
                break
        if attempt is None:
            raise RefillStateError(f"Refill attempt {attempt_id} not found")

        previous_status = attempt.get('status')
        attempt['status'] = status
        attempt['tokens_after'] = tokens_after
        attempt['resolved_at_utc'] = _utc_now_string()

        if (
            status == ATTEMPT_CONFIRMED
            and attempt.get('kind') == KIND_PAID
            and previous_status != ATTEMPT_CONFIRMED
        ):
            entry['purchased'] = entry.get('purchased', 0) + 1

        entry['last_updated_utc'] = _utc_now_string()
        _save_state_locked(state)
        purchased = entry.get('purchased', 0)

    _audit({
        'event': 'attempt_resolved',
        'location': location_name,
        'profile': _resolve_profile(profile_name),
        'attempt_id': attempt_id,
        'status': status,
        'tokens_after': tokens_after,
        'purchased': purchased,
    })
