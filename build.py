import os
import shutil
import subprocess
import sys
import json
from datetime import datetime

# win32com.client нужен только для создания ярлыков (не используется в CI/CD)
try:
    import win32com.client
    HAS_WIN32COM = True
except ImportError:
    HAS_WIN32COM = False
    print("Warning: win32com.client not available (not needed in CI/CD)")

root_dir = os.path.normpath(os.path.normpath(os.path.join(os.getcwd(), 'dist')))
name = 'RaidSL-Telegram-Bot'
app_dir_name = name
app_dir = os.path.join(root_dir, app_dir_name)
archive_path = os.path.join(root_dir, f'{name}.zip')
bot_path = root_dir


def find_occurrences(string, substrings):
    occurrences = []
    for sub in substrings:
        if sub in string:
            occurrences.append(sub)
    return occurrences


def remove_files_and_folders(folder_path, ignore=None):
    if ignore is None:
        ignore = []

    files_removed = 0
    folders_removed = 0

    for root, dirs, files in os.walk(folder_path, topdown=False):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if not len(find_occurrences(file_path, ignore)):
                os.remove(file_path)
                files_removed += 1

        for dir_name in dirs[:]:
            dir_path = os.path.join(root, dir_name)
            if not len(find_occurrences(dir_path, ignore)):
                remove_files_and_folders(dir_path, ignore)  # Recursively remove files and folders
                os.rmdir(dir_path)
                folders_removed += 1

    print(f"Files removed: {files_removed} | Folders removed: {folders_removed}")


def clear_dist():
    if os.path.isdir(root_dir):
        shutil.rmtree(root_dir)


def zipper():
    if os.path.exists(archive_path):
        os.remove(archive_path)
    shutil.make_archive(os.path.join(root_dir, name), format='zip', root_dir=app_dir)
    print(f"Release archive created: {archive_path}")


def git_commit_file(repo_path, commit_message, remote_name='origin', branch_name='master'):
    try:
        os.chdir(repo_path)

        # Add the file to the index
        subprocess.run(["git", "add", '.'])

        # Commit the file with the provided commit message
        subprocess.run(["git", "commit", "-m", commit_message])

        # Push the changes to the remote repository
        subprocess.run(["git", "push", remote_name, branch_name])

        print(f"Committed file '{repo_path}' successfully.")
    except Exception as e:
        print(f"Error: {e}")


def copy_images():
    shutil.copytree('images/needles', os.path.join(app_dir, 'images', 'needles'))


def copy_config():
    shutil.copy('config.json', app_dir)


def generate_version_json():
    """Генерирует version.json для сборки"""
    version_file = 'version.json'
    
    # Читаем текущую версию или используем дефолтную (utf-8-sig на случай BOM от PowerShell на Windows)
    if os.path.exists(version_file):
        with open(version_file, 'r', encoding='utf-8-sig') as f:
            version_data = json.load(f)
        current_version = version_data.get('version', '1.0.0')
    else:
        current_version = '1.0.0'
    
    # Генерируем новую дату сборки
    build_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Формируем download_url
    # Если есть переменная окружения GITHUB_REPOSITORY, используем её
    # Иначе используем дефолтный путь
    github_repo = os.environ.get('GITHUB_REPOSITORY', 'melvilsky/rslBot-copy')
    download_url = f"https://github.com/{github_repo}/releases/download/v{current_version}/RaidSL-Telegram-Bot.zip"
    
    version_data = {
        "version": current_version,
        "build_date": build_date,
        "download_url": download_url
    }
    
    # Сохраняем в финальную папку приложения
    os.makedirs(app_dir, exist_ok=True)
    version_path = os.path.join(app_dir, 'version.json')
    with open(version_path, 'w', encoding='utf-8') as f:
        json.dump(version_data, f, indent=2, ensure_ascii=False)
    
    print(f"Generated version.json: {current_version} ({build_date})")
    return version_data


def build():
    # subprocess.call(r"pyinstaller --onefile --collect-submodules vendor main.py")
    # subprocess.call(fr"pyinstaller --distpath {bot_path} main.spec")
    # subprocess.call(r"pyinstaller --onedir --distpath ./dist main.py")
    # subprocess.call(r"pyinstaller main.py")
    # subprocess.call(r"pyinstaller --distpath ./test main-one-file.spec")
    # subprocess.call(r"pyinstaller --distpath ./dist main.spec")
    print("Running PyInstaller...")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python version: {sys.version}")
    
    # Запускаем PyInstaller с выводом в консоль
    result = subprocess.call(
        r"pyinstaller main.spec",
        shell=True,
        stdout=sys.stdout,
        stderr=subprocess.STDOUT
    )
    
    if result != 0:
        print(f"\nERROR: PyInstaller failed with exit code {result}")
        print("Check the output above for details.")
        raise Exception(f"PyInstaller failed with exit code {result}")
    
    print("PyInstaller completed successfully!")
    return result


def build_updater():
    """Собирает updater.exe"""
    print("Building updater.exe...")
    print(f"Current directory: {os.getcwd()}")
    
    if not os.path.exists('updater.spec'):
        raise Exception("updater.spec file not found!")
    
    # Запускаем PyInstaller для updater
    result = subprocess.call(
        r"pyinstaller updater.spec",
        shell=True,
        stdout=sys.stdout,
        stderr=subprocess.STDOUT
    )
    
    if result != 0:
        print(f"\nERROR: PyInstaller failed for updater with exit code {result}")
        raise Exception(f"PyInstaller failed for updater with exit code {result}")
    
    # Копируем updater.exe в финальную папку приложения
    updater_exe_src = os.path.join('dist', 'updater', 'updater.exe')
    updater_exe_dst = os.path.join(app_dir, 'updater.exe')
    
    if os.path.exists(updater_exe_src):
        if os.path.exists(updater_exe_dst):
            os.remove(updater_exe_dst)
        shutil.copy(updater_exe_src, updater_exe_dst)
        print(f"Updater.exe copied to {updater_exe_dst}")
    else:
        raise Exception(f"Updater.exe not found at {updater_exe_src}")

    updater_build_dir = os.path.join(root_dir, 'updater')
    if os.path.isdir(updater_build_dir):
        shutil.rmtree(updater_build_dir)
        print(f"Removed temporary updater build directory: {updater_build_dir}")

    print("Updater build completed successfully!")
    return result


def copy_files():
    if not os.path.exists(app_dir):
        raise Exception(f"Build directory '{app_dir}' does not exist. Build may have failed.")
    
    # Создаем директорию для images если её нет
    images_dir = os.path.join(app_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    # Копируем images/needles (для Python 3.7 используем проверку существования)
    needles_dest = os.path.join(images_dir, 'needles')
    if os.path.exists(needles_dest):
        shutil.rmtree(needles_dest)
    shutil.copytree('images/needles', needles_dest)
    
    # Копируем coordinates (координаты для различных локаций)
    coordinates_dest = os.path.join(app_dir, 'coordinates')
    if os.path.exists('coordinates'):
        if os.path.exists(coordinates_dest):
            shutil.rmtree(coordinates_dest)
        shutil.copytree('coordinates', coordinates_dest)
        print(f"Coordinates copied to {coordinates_dest}")
    else:
        print("WARNING: coordinates directory not found, skipping...")
    
    # Копируем config.default.json (пользовательский config.json создается при первом запуске)
    if os.path.exists('config.default.json'):
        shutil.copy('config.default.json', app_dir)
    elif os.path.exists('config.json'):
        # Для обратной совместимости, если еще не переименован
        shutil.copy('config.json', app_dir)


def create_symlink():
    if not HAS_WIN32COM:
        print("Skipping symlink creation: win32com.client not available")
        return
    
    file = f'{name}.lnk'
    original_file_path = os.path.join(root_dir, file)
    symlink_path = os.path.join(app_dir, f'{name}.exe')

    # Create a shortcut object
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(original_file_path)

    # Set the target path for the shortcut
    shortcut.TargetPath = symlink_path

    # Save the shortcut
    shortcut.Save()


# Проверка, запущено ли в CI/CD окружении
is_ci = os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'

try:
    print("=" * 60)
    print("BUILD PROCESS STARTED")
    print("=" * 60)
    print(f"CI/CD mode: {is_ci}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Python executable: {sys.executable}")
    print("=" * 60)
    
    # Полная очистка dist, чтобы старые артефакты не смешивались с новой структурой
    if os.path.exists(root_dir):
        print(f"Removing previous build output: {root_dir}")
        clear_dist()
    else:
        print(f"Directory {root_dir} does not exist, skipping cleanup")
    os.makedirs(root_dir, exist_ok=True)
    
    # Проверка существования main.spec
    if not os.path.exists('main.spec'):
        raise Exception("main.spec file not found!")
    print("main.spec found, proceeding with build...")
    
    # Сборка основного приложения
    print("\n" + "=" * 60)
    print("STARTING PYINSTALLER BUILD")
    print("=" * 60)
    build()
    print("=" * 60)
    print("BUILD COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    
    # Сборка updater
    print("\n" + "=" * 60)
    print("BUILDING UPDATER")
    print("=" * 60)
    build_updater()
    print("=" * 60)
    print("UPDATER BUILD COMPLETED!")
    print("=" * 60)
    
    # Генерация version.json
    print("\n" + "=" * 60)
    print("GENERATING VERSION.JSON")
    print("=" * 60)
    generate_version_json()
    
    # Копирование файлов
    print("\n" + "=" * 60)
    print("COPYING ADDITIONAL FILES")
    print("=" * 60)
    copy_files()
    print("Files copied successfully!")

    # Архивирование финальной папки приложения
    print("\n" + "=" * 60)
    print("CREATING RELEASE ARCHIVE")
    print("=" * 60)
    zipper()

    # create_symlink()
    
    # Git commit только если dist является отдельным git-репозиторием
    if not is_ci and os.path.isdir(os.path.join(bot_path, '.git')):
        git_commit_file(repo_path=bot_path, commit_message="Automatic build update")
    else:
        print("Skipping automatic git commit for build artifacts")
    
    print("\n" + "=" * 60)
    print("BUILD PROCESS COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    
except Exception as e:
    print("\n" + "=" * 60)
    print("BUILD FAILED!")
    print("=" * 60)
    print(f"ERROR: {e}")
    print("=" * 60)
    import traceback
    traceback.print_exc()
    print("=" * 60)
    sys.exit(1)
