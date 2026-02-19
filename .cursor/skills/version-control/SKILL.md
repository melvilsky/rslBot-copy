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

Версия управляется **автоматически** через CI (`build.yml`).

**При каждом push в main/master:**
1. CI собирает exe, берёт последний GitHub Release (или version.json)
2. Инкрементирует PATCH (или #minor → MINOR, #major → MAJOR в коммите)
3. Обновляет version.json в сборке
4. Создаёт GitHub Release с тегом vX.Y.Z и zip; release notes из коммитов

**Ручной релиз:** release.yml по тегу `v*` — если нужно собрать под конкретный тег.

## Чеклист перед push в main

- [ ] Код готов; коммит-сообщение описывает изменения (пойдёт в release notes)
- [ ] Для MINOR: в коммите есть `#minor`; для MAJOR: `#major`
- [ ] Не бампить version.json и не создавать теги вручную — CI сделает сам

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

1. Коммит с понятным сообщением → `git push origin main`
2. CI сам: сборка → инкремент версии → создание Release с release notes из коммитов
3. Пользователи обновляются через `/update` в боте

**#minor** или **#major** в сообщении коммита — для MINOR/MAJOR bump.
