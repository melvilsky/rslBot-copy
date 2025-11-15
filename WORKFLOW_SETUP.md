# История настройки GitHub Actions Workflow

Этот документ описывает процесс создания автоматической сборки приложения через GitHub Actions и все исправления, которые были сделаны для успешной работы.

## Цель

Настроить автоматическую сборку Windows приложения в exe-файл без необходимости устанавливать зависимости на локальном ПК.

---

## Этап 1: Создание базового workflow

### Что было сделано:

1. **Создан файл `.github/workflows/build.yml`** с базовой конфигурацией:
   - Установка Python 3.7
   - Установка Tesseract OCR через Chocolatey
   - Установка зависимостей из `requirements.txt`
   - Запуск сборки через `build.py`
   - Создание артефактов

2. **Обновлен `main.spec`** для динамического поиска Tesseract:
   - Добавлена функция `find_tesseract_path()` для поиска Tesseract в стандартных путях
   - Поддержка переменной окружения `TESSERACT_PATH`
   - Работает как локально, так и в CI/CD

3. **Обновлен `build.py`**:
   - Добавлена проверка CI/CD окружения
   - Пропуск git commit в CI/CD
   - Улучшена обработка ошибок

### Первая ошибка: Устаревшие версии GitHub Actions

**Проблема:**
```
This request has been automatically failed because it uses a deprecated version of 
`actions/upload-artifact: v3`. Learn more: https://github.blog/changelog/2024-04-16-deprecation-notice-v3-of-the-artifact-actions/
```

**Решение:**
- Обновлены все действия на актуальные версии:
  - `actions/upload-artifact@v3` → `v4`
  - `actions/checkout@v3` → `v4`
  - `actions/setup-python@v4` → `v5`

---

## Этап 2: Улучшение обработки ошибок

### Что было сделано:

1. **Улучшен `build.py`**:
   - Добавлена проверка кода возврата PyInstaller
   - Проверка существования `dist/main` перед копированием файлов
   - Совместимость с Python 3.7 (убрана зависимость от `dirs_exist_ok`)
   - Обработка исключений с выводом traceback
   - Подробное логирование этапов сборки

2. **Улучшен `main.spec`**:
   - Проверка существования `tesseract.exe` перед добавлением в binaries
   - Предупреждения, если Tesseract не найден (сборка продолжается)
   - Более информативные сообщения

3. **Добавлены проверки в workflow**:
   - Проверка установки Python и pip
   - Проверка установки PyInstaller
   - Проверка наличия всех необходимых файлов проекта
   - Проверка результата сборки перед загрузкой артефактов

---

## Этап 3: Исправление проблемы с Tesseract

### Ошибка: Tesseract не найден в PATH

**Проблема:**
```
tesseract : The term 'tesseract' is not recognized as the name of a cmdlet, 
function, script file, or operable program.
```

**Причина:**
- Tesseract был установлен через Chocolatey, но PATH не обновлялся между шагами workflow
- Попытка использовать команду `tesseract --version` вместо полного пути

**Решение:**
1. Использование полного пути к `tesseract.exe` вместо команды `tesseract`
2. Вызов через `& $tesseractExe --version` вместо `tesseract --version`
3. Добавлен отдельный шаг для установки переменной `TESSERACT_PATH` через `GITHUB_ENV`
4. Убраны попытки обновить PATH вручную (не работают между шагами)

**Изменения в workflow:**
```yaml
- name: Verify Tesseract installation
  run: |
    $tesseractPath = "C:\Program Files\Tesseract-OCR"
    $tesseractExe = "$tesseractPath\tesseract.exe"
    
    if (Test-Path $tesseractExe) {
      Write-Host "Tesseract found at: $tesseractPath"
      & $tesseractExe --version
    } else {
      # Поиск в альтернативных местах...
    }

- name: Set Tesseract environment variable
  run: |
    # Установка TESSERACT_PATH через GITHUB_ENV
    Write-Host "TESSERACT_PATH=$tesseractPath" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
```

---

## Этап 4: Исправление синтаксиса PowerShell

### Ошибка: Unexpected token '}'

**Проблема:**
```
ParserError: (:) (), ParseException
FullyQualifiedErrorId: UnexpectedToken
Unexpected token '}' in expression or statement.
```

**Причина:**
- Использование специальных символов (✓ и ✗) в PowerShell скрипте вызывало ошибку парсинга

**Решение:**
- Убраны специальные символы из PowerShell скриптов
- Заменены на простые текстовые метки: `[OK]` и `[ERROR]`
- Упрощены скрипты проверки

**Было:**
```powershell
Write-Host "✓ Tesseract found at: $tesseractPath"
```

**Стало:**
```powershell
Write-Host "Tesseract found at: $tesseractPath"
```

---

## Этап 5: Исправление проверки PyInstaller

### Ошибка: ModuleNotFoundError: No module named 'pyinstaller'

**Проблема:**
```
ModuleNotFoundError: No module named 'pyinstaller'
```

**Причина:**
- Неправильное имя модуля при импорте: использовался `pyinstaller` вместо `PyInstaller`

**Решение:**
- Исправлен импорт на правильное имя: `import PyInstaller`
- Упрощена проверка: убрана попытка получить путь к модулю

**Было:**
```python
python -c 'import pyinstaller; import os; print(os.path.dirname(pyinstaller.__file__))'
```

**Стало:**
```python
python -c "import PyInstaller; print('PyInstaller module found')"
```

---

## Этап 6: Исправление проблемы с запуском приложения

### Проблема: Приложение не продолжало работу после загрузки переводов

**Причина:**
- Метод `validation()` в `classes/App.py` проверял, что год равен 2024
- В 2025 году валидация возвращала `False`, и приложение завершалось с сообщением "An App is outdated"

**Решение:**
1. **Обновлен метод `validation()`**:
   ```python
   # Было:
   return date_now.year == 2024 and (date_now.month <= 12)
   
   # Стало:
   return date_now.year >= 2024
   ```

2. **Улучшена обработка валидации в `main.py`**:
   - Добавлена явная проверка результата валидации
   - Добавлено логирование при неудачной валидации
   - Добавлен импорт `sys` для корректной работы `sys.exit()`

---

## Итоговая структура workflow

### Основные шаги:

1. **Checkout code** - получение кода из репозитория
2. **Set up Python** - установка Python 3.7
3. **Install Chocolatey** - установка менеджера пакетов
4. **Install Tesseract OCR** - установка Tesseract через Chocolatey
5. **Verify Tesseract installation** - проверка установки Tesseract
6. **Verify Python installation** - проверка Python и pip
7. **Install dependencies** - установка зависимостей из requirements.txt
8. **Verify PyInstaller installation** - проверка PyInstaller
9. **Verify project files** - проверка наличия всех необходимых файлов
10. **Set Tesseract environment variable** - установка переменной окружения
11. **Build executable** - сборка приложения через build.py
12. **Verify build output** - проверка результата сборки
13. **Upload build artifacts** - загрузка папки с собранным приложением
14. **Create release archive** - создание ZIP архива
15. **Upload release archive** - загрузка ZIP архива

---

## Созданные артефакты

После успешной сборки создаются два артефакта:

1. **`windows-build` (134 MB)**
   - Распакованная папка `dist/main/` со всеми файлами
   - Включает exe, DLL, зависимости, images, translations, config.json

2. **`release-zip` (129 MB)**
   - ZIP архив `RaidSL-Telegram-Bot.zip`
   - Те же файлы, упакованные в один архив
   - Рекомендуется для скачивания и распространения

---

## Ключевые изменения в файлах

### `.github/workflows/build.yml`
- Автоматическая установка всех зависимостей
- Правильная работа с Tesseract через полные пути
- Множественные проверки на каждом этапе
- Использование `GITHUB_ENV` для передачи переменных между шагами

### `main.spec`
- Динамический поиск Tesseract OCR
- Поддержка переменной окружения `TESSERACT_PATH`
- Проверка существования файлов перед добавлением в binaries

### `build.py`
- Определение CI/CD окружения
- Проверка кода возврата PyInstaller
- Улучшенная обработка ошибок с подробным логированием
- Совместимость с Python 3.7

### `classes/App.py`
- Обновлена валидация для работы в 2025 году и далее

### `main.py`
- Улучшена обработка валидации
- Добавлено логирование ошибок валидации

---

## Полезные команды

### Локальная проверка workflow (синтаксис YAML)
```bash
# Проверка синтаксиса (если установлен yamllint)
yamllint .github/workflows/build.yml
```

### Ручной запуск workflow
1. Перейдите в раздел **Actions** на GitHub
2. Выберите workflow "Build Windows Executable"
3. Нажмите **Run workflow** → **Run workflow**

### Просмотр логов
- Все логи доступны в разделе **Actions** → выберите запуск → откройте job "build"
- Каждый шаг можно развернуть для просмотра подробного вывода

---

## Решенные проблемы - краткий список

1. ✅ Устаревшие версии GitHub Actions (v3 → v4/v5)
2. ✅ Tesseract не найден в PATH (использование полных путей)
3. ✅ Ошибка синтаксиса PowerShell (убраны специальные символы)
4. ✅ Неправильный импорт PyInstaller (pyinstaller → PyInstaller)
5. ✅ Валидация приложения не работала в 2025 году (обновлена проверка года)
6. ✅ Отсутствие обработки ошибок (добавлено подробное логирование)

---

## Результат

✅ **Успешная автоматическая сборка приложения через GitHub Actions**

- Сборка запускается автоматически при каждом push в ветку `main`
- Все зависимости устанавливаются автоматически
- Создаются готовые артефакты для скачивания
- Не требуется установка зависимостей на локальном ПК

---

## Дополнительная информация

- **Время сборки:** ~3-5 минут
- **Хранение артефактов:** 30 дней
- **Требования:** Python 3.7, Tesseract OCR, все зависимости из requirements.txt
- **Платформа:** Windows (windows-latest runner)

---

*Документ создан: 2025 год*
*Последнее обновление: после успешной настройки workflow*

