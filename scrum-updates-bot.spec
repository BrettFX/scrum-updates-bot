# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


pyside_datas, pyside_binaries, pyside_hiddenimports = collect_all('PySide6')
shiboken_datas, shiboken_binaries, shiboken_hiddenimports = collect_all('shiboken6')

a = Analysis(
    ['src/scrum_updates_bot/main.py'],
    pathex=['src'],
    binaries=pyside_binaries + shiboken_binaries,
    datas=pyside_datas + shiboken_datas,
    hiddenimports=pyside_hiddenimports + shiboken_hiddenimports + [
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtNetwork',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='scrum-updates-bot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='scrum-updates-bot',
)
