---
name: version-control
description: Tracks application version and release workflow. Ensures version is bumped for releases and version.json stays consistent with GitHub releases. Use when planning a release, changing version.json, discussing versioning, or when the user mentions release, релиз, версия, or version bump.
---

# Контроль версий приложения

## Источник версии

Версия хранится в **одном месте**: корневой файл `version.json`.

Формат:
```json
{
  "version": "1.1.4",
  "build_date": "2025-01-15T00:00:00Z",
  "download_url": "https://github.com/OWNER/REPO/releases/download/v1.1.4/RaidSL-Telegram-Bot.zip"
}
```

- **version** — строго `MAJOR.MINOR.PATCH` (семантическое версионирование).
- **download_url** — должен соответствовать тегу релиза: `.../releases/download/v{version}/RaidSL-Telegram-Bot.zip`.

Код читает версию через `helpers/updater.get_current_version()`; сравнение с последним релизом — `helpers/updater.get_latest_version()` и `compare_versions()`.

## Как работает версионирование

Версия управляется **полностью автоматически** через CI (`build.yml`).

**При каждом push в main:**
1. CI берёт номер последнего GitHub Release
2. Инкрементирует версию (по умолчанию PATCH)
3. Обновляет `version.json` в сборке
4. Создаёт GitHub Release с тегом `vX.Y.Z` и zip-артефактом
5. Release notes генерируются из коммит-сообщений

**Управление типом инкремента через коммит-сообщение:**
- Обычный коммит → **PATCH** (1.2.4 → 1.2.5)
- Коммит с `#minor` → **MINOR** (1.2.4 → 1.3.0)
- Коммит с `#major` → **MAJOR** (1.2.4 → 2.0.0)

**ВАЖНО:** НЕ создавать теги вручную (`git tag`) и НЕ бампить `version.json` руками — это делает CI.

## Чеклист перед push в main

- [ ] Код протестирован / проверен
- [ ] Коммит-сообщение описывает изменения (оно пойдёт в release notes)
- [ ] Если нужен MINOR/MAJOR bump — в сообщении есть `#minor` или `#major`
- [ ] НЕ создаём теги вручную, НЕ бампим version.json — CI сделает сам

## Правила подъёма версии

- **Patch** (1.1.4 → 1.1.5): багфиксы, мелкие правки, обычные сборки.
- **Minor** (1.1.4 → 1.2.0): новая функциональность без ломающих изменений.
- **Major** (1.1.4 → 2.0.0): ломающие изменения API или поведения.

## Валидация

При изменении `version.json` или при ответах про версию:

1. Проверить, что JSON валидный и есть поля `version`, `build_date`, `download_url`.
2. Проверить, что `version` — три числа через точку (регулярка: `^\d+\.\d+\.\d+$`).
3. Убедиться, что в `download_url` версия в пути совпадает с полем `version` (например `v1.1.4` в URL при `"version": "1.1.4"`).

## Связанные файлы

- `version.json` — единственный источник версии в репозитории.
- `helpers/updater.py` — чтение версии, сравнение с GitHub Releases.
- `build.py` — функция `generate_version_json()` копирует версию в `dist/main/version.json` при сборке (не инкрементирует).
- `.github/workflows/build.yml` — шаг "Auto-increment version": инкремент PATCH и создание релиза при push в main/master.

## Краткий workflow: «Делаем релиз»

1. Пишем код, коммитим с понятным сообщением
2. `git push origin main`
3. CI автоматически: собирает exe → инкрементирует версию → создаёт GitHub Release с release notes из коммитов
4. Пользователи получают обновление через `/update` в Telegram боте

**Для MINOR релиза:** `git commit -m "feat: новая функция #minor"` → push
**Для MAJOR релиза:** `git commit -m "breaking: переделка API #major"` → push
