# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Динамический поиск Tesseract OCR
def find_tesseract_path():
    possible_paths = [
        os.environ.get('TESSERACT_PATH'),
        'C:/Program Files (x86)/Tesseract-OCR/',
        'C:/Program Files/Tesseract-OCR/',
        'C:/Tesseract-OCR/',
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            tesseract_exe = os.path.join(path, 'tesseract.exe')
            if os.path.exists(tesseract_exe):
                return path
    
    # Если не найден, возвращаем путь по умолчанию (для CI/CD)
    return 'C:/Program Files/Tesseract-OCR/'

tesseract_path = find_tesseract_path()
print(f'Using Tesseract path: {tesseract_path}')

binaries = [
    ( tesseract_path, 'vendor/tesseract' ) if os.path.exists(tesseract_path) else None
]
binaries = [b for b in binaries if b is not None]  # Удаляем None значения

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RaidSL-Telegram-Bot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
