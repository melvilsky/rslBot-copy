# План исправления незавершённого прохода Arena Classic и refill Arena Tag

Дата анализа: 2026-07-12  
Область: `Arena Classic`, `Arena Tag`, учёт платных refill, обновление списка соперников, итоговые статусы preset.

## 1. Краткий вывод

Проблемы Classic и Tag связаны не с переключением между аренами, а с двумя разными ошибками состояния.

1. **Arena Classic фактически вернулась в список соперников, но бот принял этот экран за `UNKNOWN`.** На диагностическом скриншоте `15-54-44-classic-result-close-failed-unknown.jpg` видно `2/10` оставшихся жетона, все видимые соперники уже имеют статус `Victory`, бесплатное обновление списка будет через `11m 8s`, а сейчас доступно только платное обновление за 5 рубинов. Текущий детектор списка умеет подтверждать список только по жёлтой кнопке `Attack` либо по цвету доступной бесплатной кнопки `Refresh`, поэтому корректный экран не был распознан.
2. После ложного `UNKNOWN` recovery нажал закрытие/`Escape` и вывел бота из арены. Следующие два запуска Classic из preset ждали бесплатный `Refresh` только 60 секунд и завершились раньше окончания 11-минутного cooldown. Поэтому `2/10` жетона остались.
3. **Arena Tag не пыталась сделать покупку в исследуемых запусках**, потому что сохранённое состояние уже содержало одну использованную покупку из разрешённой одной: `purchased=1`, `max_allowed=1`, время записи `2026-07-12T00:28:28.410560Z` (`02:28:28` в Europe/Berlin). Поэтому при загрузке профиль получил `0 remaining`, а затем закономерно выполнил ветку `No more refill`.
4. Имеющихся данных недостаточно, чтобы доказать, была ли покупка Tag в 00:28 UTC реальной. В текущем логе этой ранней сессии нет. Но код действительно способен создать **фантомную покупку**: он записывает `increment_purchase()` до клика и не проверяет, что popup закрылся и жетоны появились.
5. `Done` сейчас не означает, что арена закончена корректно: `RefreshTimeout` и `No more refill` часто завершаются без `abort_reason`, поэтому выглядят как успех.

Исправление должно строиться не вокруг увеличения RGB tolerance или ещё нескольких слепых кликов, а вокруг явной машины состояний, разделения token refill и обновления списка, транзакционного учёта платной покупки и корректных итоговых статусов.

## 2. Использованные данные

- Журнал: `/Users/max/Documents/RaidSL-Telegram-Bot/logs/log-2026-07-12.txt`.
- Активный профиль: `/Users/max/Documents/RaidSL-Telegram-Bot/profiles/Unsainted.json`.
- Состояние покупок: `/Users/max/Documents/RaidSL-Telegram-Bot/temp/refill_state.json`.
- Статистика боёв: `/Users/max/Documents/RaidSL-Telegram-Bot/temp/battle_stats.json`.
- Диагностические скриншоты: `/Users/max/Documents/RaidSL-Telegram-Bot/debug/screenshots/`.
- Код текущего `main`: `locations/arena/index.py`, `helpers/refill_state.py`, `classes/Location.py`, `helpers/startup.py`, `classes/TaskManager.py`.

Важно: журнал объединяет работу двух версий. До 14:57 работала v1.2.62, после обновления — v1.2.63. Таймаут ожидания обновления списка изменился с 900 до 60 секунд, поэтому поведение до и после обновления нельзя считать одним и тем же.

## 3. Подтверждённая хронология

### 3.1. Arena Classic

| Событие | Доказательство | Значение |
|---|---|---|
| Первый проход прерван после 4 боёв | журнал, строки 57–159 | Не удалось подтвердить возврат с результата, задача `Aborted` |
| Второй проход дождался бесплатного обновления и прервался после 2 боёв | строки 177–239 | Старый длинный timeout позволил дождаться refresh, но result flow снова сломался |
| Третий проход сделал 5 боёв; перед пятым взят бесплатный refill жетонов | строки 313–422, особенно 386–388 | Бесплатный мешочек Classic действительно был получен и бой после него стартовал |
| После обновления выполнено ещё 4 боя | строки 1131–1227 | После четвёртого боя экран снова объявлен `UNKNOWN` |
| На failure screenshot бот уже в списке, осталось `2/10` | `15-54-44-classic-result-close-failed-unknown.jpg` | Возврат с результата фактически состоялся; ошибся классификатор |
| На том же экране free refresh будет через `11m 8s` | тот же скриншот | Повтор через 60 секунд заведомо не мог дождаться refresh |
| Два следующих запуска сделали 0 боёв | строки 1245–1252 и 1325–1332 | Оба завершились ровно через 60 секунд `RefreshTimeout` |

Дополнительный риск подтверждает скриншот `02-56-05-classic-result-close-failed-unknown.jpg`: на нём ещё идёт активный бой, но уже была запущена процедура закрытия результата. Это отдельный дефект классификации `ACTIVE_BATTLE`/`RESULT`, способный прерывать бой и искажать статистику.

### 3.2. Arena Tag

Активный профиль разрешает одну платную докупку Tag:

```json
{
  "task": "arena_tag",
  "props": {
    "refill": 1,
    "initial_refresh": 1
  }
}
```

Но сохранённое состояние уже содержит:

```json
{
  "Unsainted": {
    "arena_tag": {
      "2026-07-12": {
        "purchased": 1,
        "max_allowed": 1,
        "last_updated_utc": "2026-07-12T00:28:28.410560Z"
      }
    }
  }
}
```

Поэтому журнал дважды показывает одну последовательность:

- строки 40 и 473: `1 already purchased today (UTC), 0 remaining`;
- строки 163–164 и 1231–1232: `ruby detected` → `No more refill`;
- строки 169 и 1237: задача объявлена `Done`, хотя не сделала ни боя, ни покупки.

В `battle_stats.json` за этот UTC-день уже есть 30 боёв Tag (`22` победы, `8` поражений), то есть до исследуемого участка журнала активность Tag была. Это делает реальную более раннюю покупку возможной, но не доказывает её: история не хранит token balance до/после и подтверждение транзакции.

## 4. Корневые причины

### P0 — Classic: неполный классификатор списка арены

`ArenaFactory._is_arena_list_visible()` в `locations/arena/index.py` подтверждает список только по:

- видимой активной кнопке `Attack`;
- одной RGB-точке доступной кнопки `Refresh`.

На исчерпанной текущей группе, пока free refresh на cooldown, нет ни одного из этих признаков. При этом заголовок `Classic Arena`, вкладки, строки соперников, счётчик жетонов и контейнер Refresh явно присутствуют. Из-за отсутствия состояния `ARENA_LIST_EXHAUSTED`/`REFRESH_COOLDOWN` корректный экран становится `UNKNOWN`.

Последствие: `_close_classic_result_screen()` считает возврат неудачным, а `_recover_to_arena_list()` применяет общий popup/`Escape` recovery к уже правильному экрану и уводит бота из арены.

### P0 — Classic: 60-секундный timeout конфликтует с cooldown Refresh

В v1.2.63 `ARENA_REFRESH_WAIT_LIMIT` равен 60 секундам. `_refresh_arena()` при timeout сразу ставит `terminated=True`.

Это неверная политика для подтверждённого состояния `REFRESH_COOLDOWN`: игровой cooldown может составлять до 15 минут. В конкретном случае оставалось больше 11 минут. Два следующих элемента preset физически не могли дождаться обновления и закончились без боя.

Параметр `initial_refresh=1` усугубляет проблему: каждый повторный запуск сначала обязан пройти `_refresh_arena()`, даже если разумнее продолжить текущий список либо вернуть отложенный результат с точным временем повтора.

### P0 — Tag: покупка учитывается до подтверждения

Текущая последовательность в `_refill()`:

```text
increment_purchase(...)
self.refill -= 1
click_on_refill()
refilled = True
```

После клика не проверяются:

- исчезновение refill popup;
- увеличение числа жетонов;
- возврат на Team Setup/список;
- фактический старт боя после повторного `Start`;
- ошибка сети или отказ покупки.

Таким образом, промах, потеря фокуса, задержка UI или crash между записью и реальной покупкой могут навсегда исчерпать дневной лимит в JSON.

### P1 — Free/paid refill классифицируется небезопасно

Логика сейчас бинарная: если рубин распознан — paid, иначе refill считается free. Отдельного `UNKNOWN` нет.

- False negative детектора рубина может привести к клику по платному варианту как по бесплатному.
- False positive может оставить бесплатный мешочек невзятым.
- Ошибка OCR жетонов (`None`) не отделена от реального значения `0`.
- Общий `refill_click` используется без подтверждения конкретного типа popup.

### P1 — Result flow смешивает разные экраны

Classic имеет как минимум:

1. активный бой;
2. reward / `TAP TO CONTINUE`;
3. summary / `RETURN TO ARENA`;
4. список с доступными атаками;
5. список без атак и с cooldown;
6. Index Page.

Текущий код сводит несколько этих экранов к `RESULTS_SCREEN` или `UNKNOWN`, повторяет один и тот же нижний клик и затем использует общий recovery. Противоречивые `VICTORY`/`DEFEAT` в строках 211–227 и 393–410 показывают, что result signal перечитывается на разных стадиях анимации вместо фиксации результата события боя.

### P1 — Итог `Done` маскирует частичное выполнение

`Location.finish()` пишет `Done`, если `abort_reason` не установлен. `RefreshTimeout` и `No more refill` обычно лишь ставят `terminated=True`, поэтому пользователь не видит разницы между:

- корректно исчерпанными ресурсами;
- ожиданием следующего free refresh;
- исчерпанным лимитом платных покупок;
- ошибкой распознавания;
- неподтверждённой покупкой.

### P2 — Хранилище refill не защищено

`helpers/refill_state.py`:

- читает и полностью перезаписывает JSON без lock;
- записывает файл неатомарно;
- при ошибке чтения возвращает `{}` и тем самым fail-open разрешает покупку повторно;
- при ошибке записи только печатает сообщение, а вызывающий код считает операцию успешной;
- не проверяет лимит внутри `increment_purchase()`;
- использует путь относительно текущего working directory;
- не пересчитывает бюджет на новом UTC-дне, пока живой instance не перечитает props/state.

Кроме того, профиль берётся из глобального `app.current_player_name` в момент операции. Смена профиля или update параллельно с задачей может записать результат не тому профилю.

## 5. Целевая модель поведения

### 5.1. Машина состояний экрана

Ввести явные состояния:

```text
INDEX
ARENA_LIST_ATTACKABLE
ARENA_LIST_EXHAUSTED
REFRESH_AVAILABLE_FREE
REFRESH_COOLDOWN
TEAM_SETUP
REFILL_FREE
REFILL_PAID
REFILL_UNKNOWN
ACTIVE_BATTLE
RESULT_REWARD
RESULT_SUMMARY
UNKNOWN
```

Для Tag можно переиспользовать общие состояния, но иметь отдельные screen signatures/координаты.

Правила:

- Сначала исключать `ACTIVE_BATTLE`, только затем проверять result.
- `ARENA_LIST_*` подтверждать по устойчивой оболочке страницы: заголовок арены, активная вкладка Battle, несколько стабильных элементов строк/панели. `Attack` и цвет free Refresh должны быть дополнительными, а не обязательными сигналами.
- `RESULT_REWARD` и `RESULT_SUMMARY` распознавать отдельно и кликать только соответствующую кнопку.
- Для динамических экранов требовать одинаковое состояние на 2–3 последовательных кадрах либо score из нескольких независимых точек.
- `UNKNOWN` не даёт права на `Escape` или произвольный клик. Он сохраняет диагностический кадр, повторяет только безопасное наблюдение и затем возвращает явную ошибку.
- Уже распознанный список никогда не передавать в popup recovery.

### 5.2. Разделение token refill и обновления списка

Текущая `_refresh_arena()` смешивает две разные операции:

1. `ensure_tokens()` — получить бесплатные/купить платные жетоны;
2. `refresh_opponent_list()` — обновить список соперников.

Их нужно разнести.

Предлагаемая политика списка:

1. Если есть доступные Attack и жетоны — атаковать без обязательного initial refresh.
2. Если текущий список исчерпан, жетоны ещё есть и free refresh доступен — обновить и подтвердить появление нового списка.
3. Если список исчерпан, жетоны есть, но free refresh на cooldown — вернуть `DEFERRED_UNTIL(next_refresh_at)` либо ждать только при явно включённой политике ожидания.
4. Никогда не нажимать платный refresh списка за рубины без отдельной настройки. Лимит token refill не должен давать такое разрешение.
5. После клика Refresh подтвердить изменение списка/появление Attack и начало нового cooldown. Сам клик не считается успехом.

Безопасный промежуточный hotfix: вернуть ожидание до 900–960 секунд **только после положительного распознавания `REFRESH_COOLDOWN`**. Не следует возвращать длинное ожидание для любого `UNKNOWN`, иначе preset снова будет зависать на неправильном экране.

Целевой вариант: не блокировать всю FIFO-очередь на 11–15 минут, а вернуть retryable outcome с `retry_at` и поставить продолжение Arena после наступления срока.

### 5.3. Транзакционная модель paid refill

Платную попытку проводить так:

1. Зафиксировать `run_id`, `attempt_id`, профиль, арену, UTC-день и token balance до операции.
2. Положительно классифицировать popup как `FREE`, `PAID` или `UNKNOWN`.
3. Для `UNKNOWN` ничего не кликать.
4. Для `PAID` под lock проверить число **подтверждённых** покупок и наличие незавершённого `pending`.
5. Записать attempt со статусом `pending`, не увеличивая `confirmed_count`.
6. Выполнить один клик по подтверждённой paid-кнопке.
7. Дождаться постусловия: popup исчез и token balance вырос; дополнительным сигналом может быть возврат в Team Setup/список либо успешный старт боя.
8. При подтверждении атомарно перевести attempt в `confirmed`. Только теперь покупка расходует дневной лимит.
9. При доказанном отказе пометить `failed`, не расходуя лимит.
10. При неопределённом результате пометить `uncertain`/оставить `pending` и запретить вторую автоматическую платную попытку до reconciliation. Автоматический rollback опасен: первая покупка могла пройти, а detector не успел это увидеть.

Free refill проходит тем же verification flow, но никогда не создаёт confirmed paid purchase.

Пример целевой записи:

```json
{
  "schema_version": 2,
  "profiles": {
    "Unsainted": {
      "arena_tag": {
        "2026-07-12": {
          "attempts": [
            {
              "id": "uuid",
              "status": "confirmed",
              "kind": "paid",
              "tokens_before": 0,
              "tokens_after": 10,
              "created_at_utc": "...",
              "confirmed_at_utc": "..."
            }
          ]
        }
      }
    }
  }
}
```

## 6. Пошаговый план реализации

### Этап 0. Сохранить доказательства и безопасно восстановить текущую ситуацию

1. Сделать резервную копию `temp/refill_state.json`, `temp/battle_stats.json`, профиля и diagnostic screenshots.
2. Не удалять весь `refill_state.json`: там есть состояние других арен и профилей.
3. Не разрешать повторную платную покупку Tag автоматически только на основании слов пользователя. Сначала проверить внутриигровой баланс и, если возможно, историю расхода рубинов/результаты раннего запуска.
4. Если подтверждено, что запись `00:28:28Z` фантомная, исправлять только ключ `Unsainted/arena_tag/2026-07-12` через отдельную repair-команду с backup и audit trail.
5. Для Classic до выпуска исправления безопасный workaround — дождаться бесплатного refresh списка и запустить Classic повторно либо потратить `2/10` вручную. Не включать платный refresh списка.

### Этап 1. Сначала добавить красные regression-тесты

Затрагиваемые файлы:

- `tests/test_arena_result_recovery.py`;
- новые `tests/test_arena_screen_classifier.py`;
- новые `tests/test_arena_refill_transaction.py`;
- новые `tests/test_refill_state.py`;
- новые `tests/fixtures/arena/`;
- `.github/workflows/build.yml`.

Действия:

1. Добавить обезличенные/cropped fixtures из существующих failure screenshots.
2. Зафиксировать ожидаемые состояния для каждого fixture.
3. Добавить тест, что `15-54-44` — `ARENA_LIST_EXHAUSTED + REFRESH_COOLDOWN`, а не `UNKNOWN`.
4. Добавить тест, что `02-56-05` — `ACTIVE_BATTLE` и continue/`Escape` не вызываются.
5. Добавить тесты `RESULT_REWARD` и `RESULT_SUMMARY` по `02-12-39`, `13-35-31`, `13-53-14`.
6. Добавить тесты free/paid/unknown refill и successful/failed/uncertain postcondition.
7. Добавить тесты UTC rollover, изоляции профиля, corrupted state и конкурентных записей.
8. Добавить тест повторного запуска одного Arena instance с чистым run-local state.
9. Добавить обязательный test job перед сборкой PyInstaller.

Текущий baseline уже не зелёный: `python3 -m unittest discover -s tests -p 'test_*.py' -v` запускает 11 тестов и даёт 1 failure. `test_arena_list_can_be_confirmed_by_refresh_button` ожидает tolerance `5`, тогда как текущий config использует `45`. Этот тест надо заменить проверкой реальных screenshot-сценариев, а не просто механически поменять `5` на `45`.

### Этап 2. Выделить classifier и явную state machine

Затрагиваемые файлы:

- `locations/arena/index.py`;
- рекомендуется новый `locations/arena/screen_state.py`;
- `coordinates/arena_shared.json`;
- `coordinates/arena_classic.json`;
- `coordinates/arena_tag.json`.

Действия:

1. Вынести перечисление состояний и результат classifier из большого `index.py`.
2. Добавить multi-point/template signature оболочки Classic/Tag list, не зависящую от Attack/free Refresh.
3. Добавить отдельные signatures `ACTIVE_BATTLE`, reward, summary, free/paid refresh и cooldown.
4. Возвращать не строку, а объект `ScreenObservation(state, score, signals, captured_at)`.
5. Добавить стабилизацию 2–3 кадров для динамических переходов.
6. Переделать `_close_classic_result_screen()` на детерминированные переходы `ACTIVE_BATTLE -> RESULT_REWARD -> RESULT_SUMMARY -> ARENA_LIST_*`.
7. Результат боя зафиксировать один раз из battle-end event и не перечитывать после смены стадии UI.
8. Убрать `close_popup_recursive()` и слепой `Escape` из generic result recovery. Разрешать action только таблицей допустимых переходов.

### Этап 3. Разделить ресурсы и список соперников

Затрагиваемые файлы:

- `locations/arena/index.py`;
- `helpers/ocr.py`;
- при реализации deferred retry — `classes/TaskManager.py` и `helpers/startup.py`.

Действия:

1. Разделить `_refresh_arena()` на `ensure_tokens()` и `refresh_opponent_list()`.
2. Ввести типизированный результат OCR: `VALUE(n)`, `UNREADABLE`, `REGION_NOT_FOUND`, а не `int | None`.
3. Сделать `initial_refresh` best-effort policy; при недоступном free refresh сначала оценивать текущий список.
4. Ввести `LIST_EXHAUSTED` и `REFRESH_COOLDOWN` как ожидаемые состояния, а не ошибки.
5. Сначала реализовать безопасное ожидание до 900–960 секунд только для подтверждённого cooldown.
6. Затем добавить outcome `DEFERRED_UNTIL` и отложенный повтор, чтобы не блокировать очередь.
7. На повторе продолжать незавершённую Arena, а не начинать слепой initial refresh.
8. После обновления списка подтверждать новую генерацию (`list_generation`) и сбрасывать run-local progress.
9. Проверить гипотезу о scroll reset после каждого Classic-боя. Если список сбрасывается, перед каждым target нормализовать позицию и прокручивать от известного anchor, а не доверять накопленному `swipes_done`.

### Этап 4. Переделать refill на подтверждаемую транзакцию

Затрагиваемые файлы:

- `locations/arena/index.py`;
- рекомендуется новый `locations/arena/refill_service.py`;
- `helpers/refill_state.py`;
- `helpers/vision.py`;
- координатные JSON.

Действия:

1. Переименовать `self.refill` в `paid_refills_remaining`.
2. Реализовать положительную тройную классификацию `FREE`/`PAID`/`UNKNOWN`.
3. Перенести изменение confirmed quota после проверки postcondition.
4. Добавить `pending`, `confirmed`, `failed`, `uncertain` и idempotency key.
5. Проверять token balance до/после; при невозможности OCR использовать комбинацию независимых постусловий и не подтверждать покупку по одному исчезновению popup.
6. После crash/restart не повторять paid click при существующем `pending`/`uncertain`.
7. Добавить ручную диагностическую/repair-команду для просмотра и точечного исправления ledger.
8. Не использовать token-refill policy как разрешение на платный refresh списка соперников.

### Этап 5. Усилить persistence и изоляцию профиля

Затрагиваемые файлы:

- `helpers/refill_state.py`;
- `classes/TaskManager.py`;
- загрузка/смена профиля в `classes/App.py`.

Действия:

1. Хранить state по стабильному app-data пути, независимому от CWD.
2. Делать temp write + flush/fsync + `os.replace`.
3. Добавить thread lock и Windows-compatible inter-process lock.
4. Проверять лимит и отсутствие pending внутри одной атомарной critical section.
5. Ошибки чтения/записи сделать fail-closed для paid actions и отправлять в основной logger/пользователю.
6. На старте каждого Arena run заново читать дневной budget, чтобы пережить UTC rollover и внешнее изменение.
7. Закреплять `profile_id` в task context в момент постановки задачи; запрещать либо сериализовать profile switch/update до завершения игровой задачи.
8. При миграции старую запись `purchased` не превращать автоматически в новую доступную покупку. Маркировать её `legacy_unverified` и требовать безопасной reconciliation.

### Этап 6. Ввести структурированные исходы и отчёт preset

Затрагиваемые файлы:

- `classes/Location.py`;
- `classes/TaskManager.py`;
- `helpers/startup.py`;
- Arena-specific report.

Предлагаемые исходы:

```text
COMPLETED_RESOURCES_EXHAUSTED
COMPLETED_POLICY_LIMIT
DEFERRED_REFRESH_COOLDOWN
PARTIAL_LIST_EXHAUSTED
ABORTED_NAVIGATION
ABORTED_UNKNOWN_SCREEN
REFILL_FAILED
REFILL_UNCERTAIN
TERMINATED_BY_USER
```

Действия:

1. `Location.run()` должен возвращать структурированный `RunOutcome`.
2. `Done` использовать только для ожидаемого terminal state.
3. FIFO preset должен агрегировать outcomes и показывать `complete`, `partial`, `deferred`, `failed`.
4. Для `DEFERRED_REFRESH_COOLDOWN` хранить `retry_at` и ставить продолжение в очередь один раз, с дедупликацией по profile/arena/list generation.
5. Итог Arena должен показывать: бои, tokens before/after, free refills, confirmed paid refills, pending attempts, конечную причину и retry time.

### Этап 7. Наблюдаемость

Добавить структурированные записи:

- app version/build, `run_id`, `profile_id`, arena;
- переходы `FROM -> TO`, score и сработавшие screen signals;
- OCR status, region, tokens before/after;
- `refill_kind`, `attempt_id`, `pending/confirmed/failed/uncertain`;
- индекс соперника, scroll position, list generation;
- cooldown и `retry_at`;
- финальный outcome.

Вести отдельный append-only refill audit. Обычного дневного лога недостаточно: исследуемая запись покупки Tag относится к 00:28 UTC, а доступный журнал начинается с 13:15 и не содержит её контекст.

## 7. Тестовая матрица

| Сценарий | Ожидаемый результат |
|---|---|
| `15-54-44`, `2/10`, все видимые `Victory`, paid Refresh, cooldown | `ARENA_LIST_EXHAUSTED` + `REFRESH_COOLDOWN`; никаких `Escape` |
| На текущем списке есть Attack и жетоны | Бот атакует без обязательного initial refresh |
| Список полностью исчерпан, жетоны есть, free refresh через 11 минут | `DEFERRED_UNTIL` либо подтверждённое bounded wait; не `Done` через 60 секунд |
| Free refresh стал доступен | Один клик, подтверждение новой list generation, продолжение расхода жетонов |
| На экране ещё активный бой | `ACTIVE_BATTLE`; result-close и `Escape` запрещены |
| Reward сменился Summary | Ровно один допустимый клик на каждой стадии |
| Paid Tag click сработал | Token balance вырос, attempt `confirmed`, quota уменьшилась ровно один раз |
| Paid Tag click не сработал | Нет `confirmed`; доказанный отказ — `failed`, quota доступна |
| Crash после paid click до проверки | `pending/uncertain`; второй автоматический click запрещён |
| Free refill | Paid quota не меняется |
| Ruby detector неоднозначен | `REFILL_UNKNOWN`, клика нет |
| OCR не смог прочитать tokens | Диагностика/retry, но не трактовка как `0` |
| Два одновременных запроса | Confirmed purchases не превышают policy limit |
| Смена UTC-дня без restart | Budget пересчитан для нового дня |
| Смена профиля во время queued task | Запись остаётся у profile snapshot задачи либо switch откладывается |
| Timeout/UNKNOWN/No more refill | Явный partial/deferred/failed outcome, не безусловный `Done` |

## 8. Критерии приёмки

1. Fixture `15-54-44` стабильно определяется как список Classic с исчерпанными видимыми атаками и cooldown; recovery не нажимает `Escape`.
2. При `2/10` и cooldown бот не объявляет задачу успешно завершённой. Он либо ждёт подтверждённый cooldown, либо возвращает `retry_at`, затем продолжает после free refresh.
3. Если на текущем списке ещё есть доступный соперник, недоступный initial free refresh не блокирует атаку.
4. Платный refresh списка соперников за рубины никогда не нажимается без отдельного явного разрешения.
5. Активный бой никогда не классифицируется как результат и не получает continue/`Escape`.
6. `confirmed` paid refill появляется только после подтверждённого postcondition.
7. Неудачный click не создаёт confirmed purchase; uncertain click не допускает автоматического дубля.
8. Free refill не уменьшает paid quota.
9. Повторный запуск и restart не могут подтвердить одну покупку дважды.
10. UTC rollover, corrupted state, конкурентная запись и изоляция профилей покрыты тестами.
11. `RefreshTimeout`, `UNKNOWN`, `No more refill` и ноль боёв не маскируются общим `Done`.
12. Полный автоматический test suite проходит на целевой Windows/Python 3.7, а release build не запускается при падении тестов.
13. Контрольный Classic-прогон с `2/10` заканчивается `0/10` либо явным `DEFERRED/PARTIAL` с причиной и временем продолжения; рубины на refresh списка не тратятся.
14. Контрольный Tag-прогон при tokens=0 и policy=1 создаёт один `pending`, затем один `confirmed` с before/after; повторный запуск покупку не повторяет.

## 9. Порядок выпуска

1. Выпустить classifier/state-machine без paid clicks, в режиме наблюдения, и собрать screen observations на Classic/Tag.
2. Включить новый Classic flow, сохранив платный refresh списка выключенным.
3. Проверить минимум один цикл: result → exhausted list → cooldown → free refresh → продолжение.
4. Затем включить transactional refill в dry-run: определить free/paid/unknown и postcondition, но не нажимать paid.
5. Провести один контролируемый paid Tag refill на тестовом профиле с записью before/after.
6. После успешного canary включить на одном реальном профиле, затем на остальных.
7. Сохранить feature flags для быстрого отключения `verified_paid_refill` и `deferred_arena_retry` без отката всего релиза.

## 10. Что не следует делать

- Не удалять целиком `refill_state.json` и не обнулять все профили.
- Не разрешать вторую покупку Tag без проверки записи `00:28:28Z`: это может привести к двойной трате рубинов.
- Не считать «ruby не распознан» доказательством бесплатного refill.
- Не исправлять Classic простым повышением RGB tolerance: это увеличит false positive на result/других синих панелях.
- Не возвращать 15-минутный timeout для любого `UNKNOWN`; длинное ожидание допустимо только для подтверждённого cooldown.
- Не добавлять больше слепых continue/`Escape` кликов.
- Не считать отсутствие видимой Attack-кнопки доказательством, что бот покинул Arena.
