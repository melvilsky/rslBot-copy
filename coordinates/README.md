# Координаты для локаций

Эта папка содержит JSON файлы с координатами для различных игровых локаций.

## Структура

- `live_arena.json` — координаты для Live Arena
- `arena_shared.json` — общие координаты для Arena Tag и Arena Classic (рефилл, кнопки, свайпы, defeat, battle_end и т.д.)
- `arena_tag.json` — только Arena Tag: button_locations, item_height, quick_battle, tap_to_continue, return_to_arena, coins_refill
- `arena_classic.json` — только Arena Classic: button_locations, item_height, coins_refill, tiers
- `iron_twins.json` — координаты для Iron Twins (переключатель SUPER RAIDS)

## Формат файла

```json
{
  "claim_free_refill_coins": {
    "x": 878,
    "y": 160,
    "rgb": [218, 0, 0],
    "mistake": 20,
    "description": "Описание координат"
  }
}
```

### Поля:
- `x`, `y` — координаты точки на экране
- `rgb` — ожидаемый цвет в формате [R, G, B] (опционально)
- `mistake` — погрешность при сравнении цвета (опционально, по умолчанию 20)
- `description` — описание координат (опционально)

## Как изменить координаты

1. Откройте соответствующий JSON файл
2. Измените значения `x`, `y`, `rgb` и/или `mistake`
3. Сохраните файл
4. Перезапустите приложение

**Важно:** После изменения координат не требуется пересборка приложения — просто перезапустите его.

## Где используются

Координаты загружаются автоматически при запуске соответствующей локации:
- `live_arena.json` — используется в `locations/live_arena/index.py`
- `arena_shared.json` — используется в `locations/arena/index.py` (ArenaFactory)
- `arena_tag.json` — используется в `locations/arena/index.py` (ArenaTag)
- `arena_classic.json` — используется в `locations/arena/index.py` (ArenaClassic)
- `iron_twins.json` — используется в `locations/iron_twins_fortress/index.py` (Iron Twins Fortress)

