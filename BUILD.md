# Инструкции по сборке приложения

## Варианты сборки без установки зависимостей на локальном ПК

### 1. GitHub Actions (Рекомендуется) ⭐

**Преимущества:**
- ✅ Бесплатно для публичных репозиториев
- ✅ Автоматическая сборка при каждом push
- ✅ Не требует установки зависимостей на вашем ПК
- ✅ Готовые артефакты для скачивания

**Как использовать:**

1. Загрузите проект на GitHub
2. Файл `.github/workflows/build.yml` уже настроен
3. При каждом push в ветку `main` или `master` запустится автоматическая сборка
4. После завершения сборки:
   - Перейдите в раздел **Actions** вашего репозитория
   - Выберите последний запуск workflow
   - Скачайте артефакты:
     - `windows-build` - папка с собранным приложением
     - `release-zip` - готовый ZIP архив

**Ручной запуск:**
- Перейдите в **Actions** → **Build Windows Executable** → **Run workflow**

---

### 2. GitLab CI/CD

Если используете GitLab, создайте файл `.gitlab-ci.yml`:

```yaml
build:
  image: mcr.microsoft.com/windows/servercore:ltsc2019
  stage: build
  before_script:
    - choco install python --version=3.7.0 -y
    - choco install tesseract -y
    - refreshenv
  script:
    - pip install -r requirements.txt
    - python build.py
  artifacts:
    paths:
      - dist/main/
    expire_in: 30 days
```

---

### 3. Облачные виртуальные машины

**Варианты:**
- **AWS EC2** (Windows Server) - платно, но есть бесплатный tier
- **Azure Virtual Machines** - платно, есть бесплатный trial
- **Google Cloud Compute Engine** - платно, есть бесплатный trial

**Шаги:**
1. Создайте Windows VM в облаке
2. Подключитесь через RDP
3. Установите зависимости (Python, Tesseract, OpenCV)
4. Клонируйте репозиторий
5. Запустите `python build.py`
6. Скачайте результат

---

### 4. Docker (для разработки, не для финальной сборки)

**Примечание:** Docker на Windows может быть сложным для сборки Windows exe. Рекомендуется использовать GitHub Actions.

---

## Локальная сборка (если все же нужно)

Если вы хотите собрать локально, но изолировать зависимости:

### Использование виртуального окружения

```bash
# Создать виртуальное окружение
python -m venv venv

# Активировать (Windows)
venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt

# Собрать
python build.py
```

### Использование Docker для изоляции

Создайте `Dockerfile` (для разработки, не для финальной сборки exe):

```dockerfile
FROM python:3.7-windowsservercore

# Установка зависимостей Windows
RUN choco install tesseract -y

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "build.py"]
```

---

## Изменения в проекте

### Что было изменено:

1. **`main.spec`** - теперь динамически ищет Tesseract OCR:
   - Проверяет переменную окружения `TESSERACT_PATH`
   - Проверяет стандартные пути установки
   - Работает как локально, так и в CI/CD

2. **`build.py`** - добавлена проверка CI/CD окружения:
   - Пропускает git commit в CI/CD
   - Работает корректно в GitHub Actions

3. **`.github/workflows/build.yml`** - новый файл для автоматической сборки:
   - Устанавливает Python 3.7
   - Устанавливает Tesseract через Chocolatey
   - Устанавливает зависимости из requirements.txt
   - Собирает приложение
   - Создает артефакты для скачивания

---

## Требования для сборки

- Python 3.7
- Tesseract OCR
- Все зависимости из `requirements.txt`
- PyInstaller (устанавливается через requirements.txt)

---

## Решение проблем

### Tesseract не найден

Убедитесь, что Tesseract установлен в одном из стандартных путей:
- `C:/Program Files (x86)/Tesseract-OCR/`
- `C:/Program Files/Tesseract-OCR/`
- `C:/Tesseract-OCR/`

Или установите переменную окружения `TESSERACT_PATH` с путем к установке.

### Ошибки при сборке в GitHub Actions

1. Проверьте логи в разделе Actions
2. Убедитесь, что все файлы закоммичены
3. Проверьте, что `main.spec` использует правильный путь к Tesseract

---

## Полезные ссылки

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [PyInstaller Documentation](https://pyinstaller.org/)
- [Tesseract OCR](https://tesseract-ocr.github.io/)

