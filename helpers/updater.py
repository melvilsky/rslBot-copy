"""
Модуль для проверки обновлений через GitHub Releases API
"""
import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
import ssl
import certifi


# GitHub репозиторий (можно переопределить через переменную окружения)
GITHUB_REPO = os.environ.get('GITHUB_REPOSITORY', 'melvilsky/rslBot-copy')
GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}"
# GitHub токен для приватных репозиториев (опционально)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', None)


def get_current_version():
    """Получает текущую версию приложения из version.json"""
    version_file = 'version.json'
    
    # Если запущено из exe, ищем version.json рядом с exe
    import sys
    if hasattr(sys, 'frozen') and sys.frozen:
        # Для PyInstaller
        if hasattr(sys, '_MEIPASS'):
            # Во время выполнения exe
            exe_dir = os.path.dirname(sys.executable)
            version_file = os.path.join(exe_dir, 'version.json')
        else:
            # В собранном приложении
            version_file = os.path.join(os.path.dirname(sys.executable), 'version.json')
    
    if not os.path.exists(version_file):
        return None
    
    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            version_data = json.load(f)
        return version_data.get('version')
    except Exception as e:
        print(f"Error reading version.json: {e}")
        return None


def get_latest_version():
    """Получает последнюю версию с GitHub Releases API"""
    try:
        url = f"{GITHUB_API_BASE}/releases/latest"
        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/vnd.github.v3+json')
        req.add_header('User-Agent', 'RaidSL-Bot-Updater/1.0')
        
        # Добавляем токен если есть (для приватных репозиториев)
        if GITHUB_TOKEN:
            req.add_header('Authorization', f'token {GITHUB_TOKEN}')
            print(f"Fetching latest version from: {url} (with token)")
        else:
            print(f"Fetching latest version from: {url} (public)")
        
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=10, context=context) as response:
            if response.status != 200:
                print(f"HTTP Error {response.status}: {response.reason}")
                return None
                
            data = json.loads(response.read().decode('utf-8'))
            
            # Извлекаем версию из tag_name (формат: v1.2.3)
            tag_name = data.get('tag_name', '')
            version = tag_name.lstrip('v') if tag_name.startswith('v') else tag_name
            
            if not version:
                print("No version found in release data")
                return None
            
            # Находим ZIP архив в assets
            download_url = None
            for asset in data.get('assets', []):
                asset_name = asset.get('name', '')
                if asset_name.endswith('.zip'):
                    download_url = asset.get('browser_download_url')
                    print(f"Found ZIP asset: {asset_name}")
                    break
            
            if not download_url:
                print("WARNING: No ZIP archive found in release assets")
            
            result = {
                'version': version,
                'tag_name': tag_name,
                'download_url': download_url,
                'release_url': data.get('html_url'),
                'published_at': data.get('published_at'),
                'body': data.get('body', '')  # Описание релиза
            }
            
            print(f"Latest version found: {version} (tag: {tag_name})")
            return result
            
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"No releases found (404): {e}")
        else:
            print(f"HTTP Error {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"Network error fetching latest version: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_versions(current_version, latest_version):
    """
    Сравнивает версии в формате MAJOR.MINOR.PATCH
    Возвращает:
    - -1 если current < latest
    - 0 если current == latest
    - 1 если current > latest
    """
    if not current_version or not latest_version:
        return None
    
    try:
        current_parts = [int(x) for x in current_version.split('.')]
        latest_parts = [int(x) for x in latest_version.split('.')]
        
        # Дополняем до 3 частей если нужно
        while len(current_parts) < 3:
            current_parts.append(0)
        while len(latest_parts) < 3:
            latest_parts.append(0)
        
        for i in range(3):
            if current_parts[i] < latest_parts[i]:
                return -1
            elif current_parts[i] > latest_parts[i]:
                return 1
        
        return 0
    except Exception as e:
        print(f"Error comparing versions: {e}")
        return None


def is_update_available():
    """Проверяет, доступно ли обновление"""
    current = get_current_version()
    if not current:
        return None
    
    latest_data = get_latest_version()
    if not latest_data:
        return None
    
    latest = latest_data.get('version')
    if not latest:
        return None
    
    comparison = compare_versions(current, latest)
    if comparison is None:
        return None
    
    if comparison < 0:
        return {
            'available': True,
            'current_version': current,
            'latest_version': latest,
            'download_url': latest_data.get('download_url'),
            'release_url': latest_data.get('release_url'),
            'release_notes': latest_data.get('body', ''),
            'published_at': latest_data.get('published_at')
        }
    
    return {
        'available': False,
        'current_version': current,
        'latest_version': latest
    }


def get_updater_path():
    """Возвращает путь к updater.exe"""
    import sys
    if hasattr(sys, 'frozen') and sys.frozen:
        # Для PyInstaller
        exe_dir = os.path.dirname(sys.executable)
        updater_path = os.path.join(exe_dir, 'updater.exe')
    else:
        # Для разработки
        updater_path = os.path.join(os.path.dirname(__file__), '..', 'updater.exe')
        if not os.path.exists(updater_path):
            updater_path = os.path.join(os.getcwd(), 'updater.exe')
    
    return updater_path


def launch_updater(download_url, app_path=None, excluded_files=None, excluded_dirs=None):
    """
    Запускает updater.exe с параметрами обновления
    
    Args:
        download_url: URL для скачивания обновления
        app_path: Путь к папке приложения (по умолчанию - папка с exe)
        excluded_files: Список файлов для исключения
        excluded_dirs: Список директорий для исключения
    """
    import subprocess
    
    updater_path = get_updater_path()
    
    if not os.path.exists(updater_path):
        print(f"ERROR: Updater not found at {updater_path}")
        return False
    
    if app_path is None:
        if hasattr(os.sys, 'frozen') and os.sys.frozen:
            app_path = os.path.dirname(os.sys.executable)
        else:
            app_path = os.getcwd()
    
    if excluded_files is None:
        excluded_files = ['config.json', 'updater.exe']
    if excluded_dirs is None:
        excluded_dirs = ['logs']
    
    # Формируем команду
    cmd = [
        updater_path,
        '--download-url', download_url,
        '--app-path', app_path,
    ]
    
    if excluded_files:
        cmd.extend(['--excluded-files'] + excluded_files)
    if excluded_dirs:
        cmd.extend(['--excluded-dirs'] + excluded_dirs)
    
    try:
        print(f"Launching updater: {' '.join(cmd)}")
        subprocess.Popen(cmd)
        return True
    except Exception as e:
        print(f"Error launching updater: {e}")
        return False


def should_check_for_updates():
    """
    Проверяет, нужно ли проверять обновления (раз в день)
    Сохраняет дату последней проверки в файл
    """
    check_file = 'last_update_check.json'
    
    # Если запущено из exe, сохраняем рядом с exe
    import sys
    if hasattr(sys, 'frozen') and sys.frozen:
        exe_dir = os.path.dirname(sys.executable)
        check_file = os.path.join(exe_dir, 'last_update_check.json')
    
    try:
        if os.path.exists(check_file):
            with open(check_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            last_check_str = data.get('last_check')
            if last_check_str:
                last_check = datetime.fromisoformat(last_check_str.replace('Z', '+00:00'))
                # Проверяем раз в день
                if datetime.now(last_check.tzinfo) - last_check < timedelta(days=1):
                    return False
        
        # Обновляем дату последней проверки
        with open(check_file, 'w', encoding='utf-8') as f:
            json.dump({
                'last_check': datetime.utcnow().isoformat() + 'Z'
            }, f)
        
        return True
    except Exception as e:
        print(f"Error checking update schedule: {e}")
        # В случае ошибки разрешаем проверку
        return True

