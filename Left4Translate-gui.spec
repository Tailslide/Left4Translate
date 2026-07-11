# -*- mode: python ; coding: utf-8 -*-
# Desktop GUI build of Left4Translate.
# Outputs dist/Left4Translate-GUI.exe — windowed (no console), PySide6-based.
# The lean command-line build lives in Left4Translate.spec (console=True).
import os
import sys
from PyInstaller.utils.hooks import collect_all

# Fail fast if the GUI toolkit is missing, rather than emitting an .exe that
# crashes on launch with "No module named 'PySide6'".
try:
    import PySide6  # noqa: F401
    import shiboken6  # noqa: F401
except ImportError as exc:
    sys.stderr.write(
        "\n[Left4Translate-gui.spec] ERROR: PySide6/shiboken6 are not installed.\n"
        "Install the dependencies before building:\n"
        "    pip install -r requirements.txt\n"
        f"Underlying error: {exc}\n\n"
    )
    raise SystemExit(2)

block_cipher = None
base_path = SPECPATH
icon_path = os.path.join(base_path, 'res', 'icon.ico')
if not os.path.exists(icon_path):
    print(f"WARNING: Icon not found at {icon_path}")
    icon_path = None

# PySide6 ships plugins (platforms, styles, imageformats) PyInstaller can't find
# via static analysis — collect_all pulls them in.
pyside_datas, pyside_binaries, pyside_hiddenimports = collect_all('PySide6')
shiboken_datas, shiboken_binaries, shiboken_hiddenimports = collect_all('shiboken6')

if not pyside_binaries:
    sys.stderr.write(
        "\n[Left4Translate-gui.spec] ERROR: collect_all('PySide6') found no binaries. "
        "Re-install PySide6:\n    pip install --force-reinstall PySide6\n\n"
    )
    raise SystemExit(2)


def _opt(src, dest):
    """Include a data file only if it exists, so an absent optional dependency
    (e.g. the separately-cloned Turing library) doesn't abort the build."""
    return [(src, dest)] if os.path.exists(os.path.join(base_path, src)) else []


engine_datas = (
    _opt('config/config.sample.json', 'config')
    + _opt('config/slang_es.sample.json', 'config')
    + _opt('res/icon.ico', 'res')
    + _opt('docs', 'docs')
    + _opt('turing-smart-screen-python/library', 'library')
    + _opt('turing-smart-screen-python/res/fonts/roboto-mono', 'res/fonts/roboto-mono')
    + _opt('res/fonts/roboto-mono', 'res/fonts/roboto-mono')
)

a = Analysis(
    ['gui_main.py'],
    pathex=[base_path, os.path.join(base_path, 'src')],
    binaries=pyside_binaries + shiboken_binaries,
    datas=engine_datas + pyside_datas + shiboken_datas,
    hiddenimports=[
        # GUI package
        'gui', 'gui.app', 'gui.main_window', 'gui.dashboard_tab', 'gui.voice_tab',
        'gui.settings_tab', 'gui.logs_tab', 'gui.tray', 'gui.widgets',
        'gui.engine_controller', 'gui.settings_store', 'gui.styles', 'gui.theme',
        'gui.log_handler', 'gui.stream_capture', 'gui.crash_guard',
        'gui.overlay_window',
        # Engine (src/) — imported lazily by the controller thread.
        'main',
        'version',
        'config.config_manager',
        'reader.message_reader',
        'translator.translation_service',
        'display.screen_controller', 'display.turing_display',
        'audio.voice_translation_manager', 'audio.voice_recorder',
        'audio.speech_to_text',
        'input.mouse_handler',
        'utils.clipboard_manager',
        # Engine third-party deps (mirrors Left4Translate.spec).
        'watchdog', 'watchdog.observers', 'watchdog.observers.winapi',
        'watchdog.observers.api', 'watchdog.observers.read_directory_changes',
        'watchdog.events',
        'cachetools', 'serial', 'serial.tools', 'serial.tools.list_ports',
        'serial.tools.list_ports_common', 'serial.tools.list_ports_windows',
        'serial.win32', 'numpy', 'PIL', 'requests', 'pynput', 'sounddevice',
        'pyperclip', 'ctypes',
        'google.api_core.operations_v1', 'google.api_core.gapic_v1',
        'google.api_core.retry', 'google.api_core.timeout',
        'google.api_core.client_options', 'google.api_core.exceptions',
        'google.api_core.grpc_helpers', 'google.api_core.path_template',
        'google.api_core.page_iterator',
        'google.api_core.operations_v1.operations_client',
    ] + pyside_hiddenimports + shiboken_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest', 'tkinter', 'matplotlib', 'IPython', 'jupyter', 'notebook',
        # Trim the heaviest unused PySide6 modules to keep the .exe size sane.
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DRender',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'PySide6.QtWebEngine', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
        'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtSerialPort',
        'PySide6.QtPositioning', 'PySide6.QtLocation',
        'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQml', 'PySide6.QtQuickWidgets',
        'PySide6.QtSensors', 'PySide6.QtSvgWidgets', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Left4Translate-GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # windowed — no console window pops up
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
