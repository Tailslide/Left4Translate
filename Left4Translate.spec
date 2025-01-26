# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/config.sample.json', 'config'),
        ('docs', 'docs'),
        ('turing-smart-screen-python/library', 'library'),
        ('turing-smart-screen-python/res/fonts/roboto-mono/*.ttf', 'res/fonts/roboto-mono'),
    ],
    hiddenimports=[
        'watchdog',
        'watchdog.observers',
        'watchdog.observers.winapi',
        'watchdog.observers.api',
        'watchdog.observers.read_directory_changes',
        'watchdog.events',
        'google.cloud.translate_v2',
        'cachetools',
        'pydantic',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'serial.tools.list_ports_common',
        'serial.tools.list_ports_windows',
        'serial.win32',
        'structlog',
        'numpy',
        'PIL',
        'requests',
        'python_i18n',  # Fixed package name
        'i18n',         # Alternative import name
        'dotenv',
        'tzdata',
        'google.api_core.operations_v1',
        'google.api_core.gapic_v1',
        'google.api_core.retry',
        'google.api_core.timeout',
        'google.api_core.client_options',
        'google.api_core.exceptions',
        'google.api_core.grpc_helpers',
        'google.api_core.path_template',
        'google.api_core.page_iterator',
        'google.api_core.operations_v1.operations_client'
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Left4Translate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)