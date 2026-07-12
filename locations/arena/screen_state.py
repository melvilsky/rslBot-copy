"""
Явная классификация экранов Arena Classic/Tag (план, Этап 2).

Классификатор не обращается к экрану напрямую: он принимает pixel_getter —
функцию (x, y) -> (r, g, b). В боевом коде это pyautogui.pixel, в тестах —
чтение из fixture-скриншота. Это позволяет проверять классификацию на
реальных failure screenshots без запуска игры.

Порядок проверок соответствует плану:
  1. ACTIVE_BATTLE исключается первым;
  2. затем RESULT_SUMMARY и RESULT_REWARD (отдельные экраны, разные кнопки);
  3. затем оболочка списка арены (устойчивые элементы страницы, не зависящие
     от Attack/free Refresh) с уточнением ATTACKABLE/EXHAUSTED и сигналами
     REFRESH_AVAILABLE_FREE / REFRESH_COOLDOWN;
  4. затем INDEX;
  5. иначе UNKNOWN.
"""
import time
from enum import Enum


class ScreenState(Enum):
    INDEX = 'INDEX'
    ARENA_LIST_ATTACKABLE = 'ARENA_LIST_ATTACKABLE'
    ARENA_LIST_EXHAUSTED = 'ARENA_LIST_EXHAUSTED'
    REFRESH_AVAILABLE_FREE = 'REFRESH_AVAILABLE_FREE'
    REFRESH_COOLDOWN = 'REFRESH_COOLDOWN'
    TEAM_SETUP = 'TEAM_SETUP'
    REFILL_FREE = 'REFILL_FREE'
    REFILL_PAID = 'REFILL_PAID'
    REFILL_UNKNOWN = 'REFILL_UNKNOWN'
    ACTIVE_BATTLE = 'ACTIVE_BATTLE'
    RESULT_REWARD = 'RESULT_REWARD'
    RESULT_SUMMARY = 'RESULT_SUMMARY'
    UNKNOWN = 'UNKNOWN'


class ScreenObservation:
    def __init__(self, state, score=0.0, signals=None, captured_at=None):
        self.state = state
        self.score = score
        self.signals = signals if signals is not None else []
        self.captured_at = captured_at if captured_at is not None else time.time()

    def __repr__(self):
        return (
            f"ScreenObservation(state={self.state.name}, "
            f"score={self.score}, signals={self.signals})"
        )


# ---------------------------------------------------------------------------
# Сигнатуры. Точки подобраны и проверены по диагностическим скриншотам
# (tests/fixtures/arena/): каждая сигнатура набирает min_score только на
# «своём» экране и ноль/почти ноль на остальных пяти.
# ---------------------------------------------------------------------------

# Оболочка списка арены: вкладка Battle и элементы левой панели.
# Присутствует и на исчерпанном списке с cooldown (кейс 15-54-44).
ARENA_LIST_SHELL = {
    'points': [
        [110, 115, [1, 94, 151]],   # активная вкладка Battle
        [60, 187, [7, 73, 108]],    # панель: Battle Log
        [60, 268, [11, 64, 98]],    # панель: Defense
        [60, 349, [8, 59, 88]],     # панель: Tiers
        [60, 430, [7, 53, 87]],     # панель: Top Players
    ],
    'mistake': 25,
    'min_score': 4,
}

# Зелёный индикатор "Free refresh in Xm Ys" рядом с кнопкой Refresh.
REFRESH_COOLDOWN_SIGNATURE = {
    'points': [
        [725, 89, [185, 246, 63]],
        [734, 90, [35, 113, 38]],
        [770, 95, [25, 127, 113]],
    ],
    'mistake': 60,
    'min_score': 2,
}

# Нижняя жёлтая надпись TAP TO CONTINUE на экране награды.
RESULT_REWARD_SIGNATURE = {
    'points': [
        [407, 493, [236, 235, 152]],
        [500, 492, [246, 233, 163]],
    ],
    'mistake': 40,
    'min_score': 2,
}

# Экран battle summary: жёлтая RETURN TO ARENA + светлое "VS" по центру.
RESULT_SUMMARY_SIGNATURE = {
    'points': [
        [432, 492, [203, 201, 124]],
        [478, 492, [238, 228, 159]],
        [467, 310, [184, 184, 182]],
    ],
    'mistake': 30,
    'min_score': 2,
}

# Index Page: кнопка SHOP слева внизу и красная BATTLE справа внизу.
INDEX_PAGE_SIGNATURE = {
    'points': [
        [60, 497, [174, 189, 196]],
        [845, 497, [131, 30, 0]],
        [795, 497, [105, 12, 0]],
    ],
    'mistake': 40,
    'min_score': 2,
}

# Белые часы таймера активного боя (совпадает с coordinates/arena_shared.json).
ACTIVE_BATTLE_SIGNATURE = {
    'points': [
        [845, 176, [255, 255, 255]],
    ],
    'mistake': 10,
    'min_score': 1,
}

# Синяя доступная кнопка Refresh (из coordinates/arena_shared.json).
REFRESH_AVAILABLE_SIGNATURE = {
    'points': [
        [817, 133, [22, 124, 156]],
    ],
    'mistake': 45,
    'min_score': 1,
}

ATTACK_BUTTON_RGB = [187, 130, 5]
ATTACK_BUTTON_MISTAKE = 10


def _pixel_matches(pixel_getter, point, mistake):
    x, y, rgb = point[0], point[1], point[2]
    actual = pixel_getter(x, y)
    return all(abs(actual[i] - rgb[i]) <= mistake for i in range(3))


def score_signature(pixel_getter, signature):
    """Возвращает (matched, total) для сигнатуры."""
    matched = 0
    for point in signature['points']:
        if _pixel_matches(pixel_getter, point, signature['mistake']):
            matched += 1
    return matched, len(signature['points'])


def signature_visible(pixel_getter, signature):
    matched, _total = score_signature(pixel_getter, signature)
    return matched >= signature['min_score']


def find_attackable_positions(pixel_getter, button_locations):
    """Возвращает список позиций с видимой жёлтой кнопкой Attack."""
    positions = []
    for position, pos in (button_locations or {}).items():
        point = [pos[0], pos[1], ATTACK_BUTTON_RGB]
        if _pixel_matches(pixel_getter, point, ATTACK_BUTTON_MISTAKE):
            positions.append(position)
    return positions


def classify_arena_screen(pixel_getter, button_locations=None):
    """
    Классифицирует текущий экран арены.

    Args:
        pixel_getter: функция (x, y) -> (r, g, b)
        button_locations: dict позиций кнопок Attack ({1: [x, y], ...})

    Returns:
        ScreenObservation
    """
    signals = []

    shell_matched, shell_total = score_signature(pixel_getter, ARENA_LIST_SHELL)
    shell_visible = shell_matched >= ARENA_LIST_SHELL['min_score']

    # 1. Активный бой исключается первым и только вне оболочки списка.
    if not shell_visible and signature_visible(pixel_getter, ACTIVE_BATTLE_SIGNATURE):
        return ScreenObservation(
            state=ScreenState.ACTIVE_BATTLE,
            score=1.0,
            signals=['BATTLE_TIMER'],
        )

    # 2. Результаты: сначала summary (RETURN TO ARENA), затем reward
    #    (TAP TO CONTINUE) — у них разные допустимые действия.
    if not shell_visible:
        if signature_visible(pixel_getter, RESULT_SUMMARY_SIGNATURE):
            return ScreenObservation(
                state=ScreenState.RESULT_SUMMARY,
                score=1.0,
                signals=['RETURN_TO_ARENA'],
            )
        if signature_visible(pixel_getter, RESULT_REWARD_SIGNATURE):
            return ScreenObservation(
                state=ScreenState.RESULT_REWARD,
                score=1.0,
                signals=['TAP_TO_CONTINUE'],
            )

    # 3. Список арены: оболочка страницы — основной признак, Attack и цвет
    #    Refresh — дополнительные сигналы (план, Этап 2, правило 2).
    if shell_visible:
        signals.append('LIST_SHELL')

        attackable = find_attackable_positions(pixel_getter, button_locations)
        for position in attackable:
            signals.append(f'ATTACK_BUTTON_{position}')

        if signature_visible(pixel_getter, REFRESH_AVAILABLE_SIGNATURE):
            signals.append('REFRESH_AVAILABLE_FREE')
        if signature_visible(pixel_getter, REFRESH_COOLDOWN_SIGNATURE):
            signals.append('REFRESH_COOLDOWN')

        state = (
            ScreenState.ARENA_LIST_ATTACKABLE
            if attackable
            else ScreenState.ARENA_LIST_EXHAUSTED
        )
        return ScreenObservation(
            state=state,
            score=float(shell_matched) / shell_total,
            signals=signals,
        )

    # 4. Index Page.
    if signature_visible(pixel_getter, INDEX_PAGE_SIGNATURE):
        return ScreenObservation(
            state=ScreenState.INDEX,
            score=1.0,
            signals=['INDEX_BOTTOM_BAR'],
        )

    # 5. UNKNOWN: не даёт права на Escape или произвольный клик.
    return ScreenObservation(state=ScreenState.UNKNOWN, score=0.0, signals=[])


class ArenaScreenClassifier:
    """Обёртка со стабилизацией: хранит историю последних кадров и умеет
    подтверждать состояние на 2-3 последовательных наблюдениях."""

    HISTORY_LIMIT = 3

    def __init__(self, pixel_getter, button_locations=None):
        self.pixel_getter = pixel_getter
        self.button_locations = button_locations
        self._history = []

    def observe(self):
        obs = classify_arena_screen(self.pixel_getter, self.button_locations)
        self._history.append(obs)
        if len(self._history) > self.HISTORY_LIMIT:
            self._history.pop(0)
        return obs

    def is_stable(self, state, frames=2):
        """True, если состояние повторяется на последних `frames` кадрах."""
        if len(self._history) < frames:
            return False
        return all(obs.state == state for obs in self._history[-frames:])
