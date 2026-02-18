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

## Когда поднимать версию

1. **Релиз через CI (push в main/master)**  
   Версию поднимать не нужно: шаг "Auto-increment version" в `.github/workflows/build.yml` сам берёт последний тег (или `version.json`), инкрементирует **PATCH**, обновляет `version.json` и создаёт релиз с тегом `vX.Y.Z`.

2. **Ручной релиз или сборка под новую версию**  
   Нужно **до сборки/релиза** вручную обновить `version.json`:
   - Увеличить `version` (как минимум PATCH: `1.1.4` → `1.1.5`).
   - Обновить `build_date` (ISO 8601 UTC).
   - Проверить `download_url` (репозиторий и версия в URL).

## Чеклист перед релизом

При любом обсуждении релиза или изменении версии проверять:

- [ ] В `version.json` поле `version` в формате `X.Y.Z` (три числа).
- [ ] Версия **поднята** относительно последнего релиза (или текущего значения в `version.json`).
- [ ] Тег релиза будет `v{version}` (например `v1.1.5`) — без расхождений.
- [ ] В `download_url` указаны правильные владелец/репозиторий и та же версия, что в `version`.
- [ ] При ручном релизе: после изменения `version.json` либо запущена сборка, либо создан тег/релиз вручную.

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

**Через CI:** залить изменения в main → workflow сам поднимет PATCH и создаст релиз.

**Вручную:**
1. Открыть `version.json`.
2. Увеличить `version` (минимум PATCH).
3. Обновить `build_date` на текущее время (UTC).
4. Сохранить, собрать приложение, создать тег `v{version}` и GitHub Release с артефактом `RaidSL-Telegram-Bot.zip`.

После релиза пользователи получают новую версию через проверку обновлений в приложении (логика в `helpers/updater.py` и UI в `classes/App.py`).
