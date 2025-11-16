#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Updater для автоматического обновления приложения
Принимает параметры: download_url, app_path, excluded_files
"""
import os
import sys
import shutil
import subprocess
import time
import zipfile
import urllib.request
import urllib.error
import argparse
import psutil
import json

# Имя процесса основного приложения
MAIN_APP_PROCESS = 'RaidSL-Telegram-Bot.exe'
UPDATER_PROCESS = 'updater.exe'


def log(message):
    """Простое логирование в консоль"""
    print(f"[UPDATER] {message}")


def download_file(url, destination):
    """Скачивает файл по URL"""
    try:
        log(f"Downloading from {url}...")
        urllib.request.urlretrieve(url, destination)
        log(f"Downloaded to {destination}")
        return True
    except urllib.error.URLError as e:
        log(f"Error downloading file: {e}")
        return False
    except Exception as e:
        log(f"Unexpected error during download: {e}")
        return False


def terminate_process_by_name(name):
    """Закрывает процесс по имени"""
    terminated = False
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == name.lower():
                log(f"Terminating process {proc.info['name']} (PID: {proc.info['pid']})")
                proc.terminate()
                terminated = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if terminated:
        # Даем время процессу закрыться
        time.sleep(2)
        # Если процесс еще работает, принудительно завершаем
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == name.lower():
                    log(f"Force killing process {proc.info['name']} (PID: {proc.info['pid']})")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    
    return terminated


def wait_for_processes_to_close(process_names, timeout=30):
    """Ждет закрытия процессов с таймаутом"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        all_closed = True
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name']:
                    for name in process_names:
                        if proc.info['name'].lower() == name.lower():
                            all_closed = False
                            break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        if all_closed:
            return True
        time.sleep(0.5)
    
    return False


def should_exclude_file(file_path, excluded_files, excluded_dirs):
    """Проверяет, нужно ли исключить файл из обновления"""
    file_name = os.path.basename(file_path)
    
    # Проверяем исключенные файлы
    for excluded in excluded_files:
        if file_name == excluded or file_path.endswith(excluded):
            return True
    
    # Проверяем исключенные директории
    for excluded_dir in excluded_dirs:
        if excluded_dir in file_path:
            return True
    
    return False


def update_files(source_dir, target_dir, excluded_files=None, excluded_dirs=None):
    """Обновляет файлы из source_dir в target_dir, исключая указанные файлы/папки"""
    if excluded_files is None:
        excluded_files = ['config.json', 'updater.exe']
    if excluded_dirs is None:
        excluded_dirs = ['logs']
    
    log(f"Updating files from {source_dir} to {target_dir}")
    log(f"Excluded files: {excluded_files}")
    log(f"Excluded dirs: {excluded_dirs}")
    
    updated_count = 0
    skipped_count = 0
    
    for root, dirs, files in os.walk(source_dir):
        # Пропускаем исключенные директории
        rel_root = os.path.relpath(root, source_dir)
        if any(excluded_dir in rel_root for excluded_dir in excluded_dirs):
            continue
        
        for file in files:
            source_path = os.path.join(root, file)
            rel_path = os.path.relpath(source_path, source_dir)
            target_path = os.path.join(target_dir, rel_path)
            
            # Пропускаем исключенные файлы
            if should_exclude_file(rel_path, excluded_files, excluded_dirs):
                log(f"Skipping excluded file: {rel_path}")
                skipped_count += 1
                continue
            
            try:
                # Создаем директорию если нужно
                target_file_dir = os.path.dirname(target_path)
                if target_file_dir and not os.path.exists(target_file_dir):
                    os.makedirs(target_file_dir, exist_ok=True)
                
                # Копируем файл
                shutil.copy2(source_path, target_path)
                updated_count += 1
                log(f"Updated: {rel_path}")
            except Exception as e:
                log(f"Error updating {rel_path}: {e}")
    
    log(f"Update complete: {updated_count} files updated, {skipped_count} files skipped")
    return updated_count > 0


def extract_zip(zip_path, extract_to):
    """Распаковывает ZIP архив"""
    try:
        log(f"Extracting {zip_path} to {extract_to}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        log(f"Extracted successfully")
        return True
    except Exception as e:
        log(f"Error extracting zip: {e}")
        return False


def find_main_exe(app_path):
    """Находит главный exe файл приложения"""
    possible_names = ['RaidSL-Telegram-Bot.exe', 'main.exe', 'bot.exe']
    for name in possible_names:
        exe_path = os.path.join(app_path, name)
        if os.path.exists(exe_path):
            return exe_path
    return None


def main():
    parser = argparse.ArgumentParser(description='Application Updater')
    parser.add_argument('--download-url', required=True, help='URL для скачивания обновления')
    parser.add_argument('--app-path', required=True, help='Путь к папке приложения')
    parser.add_argument('--excluded-files', nargs='*', default=['config.json', 'updater.exe'],
                       help='Файлы для исключения из обновления')
    parser.add_argument('--excluded-dirs', nargs='*', default=['logs'],
                       help='Директории для исключения из обновления')
    
    args = parser.parse_args()
    
    log("=" * 60)
    log("UPDATER STARTED")
    log("=" * 60)
    log(f"Download URL: {args.download_url}")
    log(f"App Path: {args.app_path}")
    log(f"Excluded files: {args.excluded_files}")
    log(f"Excluded dirs: {args.excluded_dirs}")
    
    # Проверяем путь к приложению
    if not os.path.exists(args.app_path):
        log(f"ERROR: App path does not exist: {args.app_path}")
        input("Press Enter to exit...")
        sys.exit(1)
    
    # Создаем временную папку для обновления
    temp_dir = os.path.join(args.app_path, 'update_temp')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    
    zip_path = os.path.join(temp_dir, 'update.zip')
    
    try:
        # Шаг 1: Закрываем основное приложение
        log("Step 1: Closing main application...")
        terminate_process_by_name(MAIN_APP_PROCESS)
        
        # Ждем закрытия процессов
        if not wait_for_processes_to_close([MAIN_APP_PROCESS], timeout=10):
            log("WARNING: Some processes may still be running")
        
        # Шаг 2: Скачиваем обновление
        log("Step 2: Downloading update...")
        if not download_file(args.download_url, zip_path):
            log("ERROR: Failed to download update")
            input("Press Enter to exit...")
            sys.exit(1)
        
        # Шаг 3: Распаковываем
        log("Step 3: Extracting update...")
        extract_dir = os.path.join(temp_dir, 'extracted')
        os.makedirs(extract_dir, exist_ok=True)
        
        if not extract_zip(zip_path, extract_dir):
            log("ERROR: Failed to extract update")
            input("Press Enter to exit...")
            sys.exit(1)
        
        # Шаг 4: Находим папку с файлами (может быть в подпапке)
        files_dir = extract_dir
        # Проверяем, есть ли подпапка main
        main_subdir = os.path.join(extract_dir, 'main')
        if os.path.exists(main_subdir):
            files_dir = main_subdir
        
        # Шаг 5: Обновляем файлы
        log("Step 4: Updating files...")
        if not update_files(files_dir, args.app_path, args.excluded_files, args.excluded_dirs):
            log("ERROR: Failed to update files")
            input("Press Enter to exit...")
            sys.exit(1)
        
        # Шаг 6: Запускаем обновленное приложение
        log("Step 5: Starting updated application...")
        main_exe = find_main_exe(args.app_path)
        if main_exe:
            log(f"Launching: {main_exe}")
            # Запускаем в фоне
            subprocess.Popen([main_exe], cwd=args.app_path)
            time.sleep(2)
        else:
            log("WARNING: Could not find main executable")
        
        # Шаг 7: Очищаем временные файлы
        log("Step 6: Cleaning up...")
        try:
            shutil.rmtree(temp_dir)
            log("Cleanup complete")
        except Exception as e:
            log(f"WARNING: Could not clean up temp directory: {e}")
        
        log("=" * 60)
        log("UPDATE COMPLETED SUCCESSFULLY!")
        log("=" * 60)
        time.sleep(2)
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)


if __name__ == '__main__':
    main()

