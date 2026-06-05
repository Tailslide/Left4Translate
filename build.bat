@echo off
REM Build script for Left4Translate Windows executables.
REM
REM Usage:
REM   build.bat            -> builds the desktop GUI (Left4Translate-GUI.exe)
REM   build.bat gui        -> same as above
REM   build.bat cli        -> builds the console app (Left4Translate.exe)
REM   build.bat all        -> builds both
REM   build.bat <t> --no-deps  -> skip the pip install of requirements
REM
REM Prereqs: a Python 3.10+ environment with requirements.txt installed, and
REM (for the screen) the Turing library cloned into turing-smart-screen-python\.
setlocal enableextensions

set TARGET=%1
set DEP_FLAG=%2
if "%TARGET%"=="" set TARGET=gui
if /I "%TARGET%"=="--no-deps" (
    set TARGET=gui
    set DEP_FLAG=--no-deps
)

if /I "%TARGET%" NEQ "gui" if /I "%TARGET%" NEQ "cli" if /I "%TARGET%" NEQ "all" (
    echo Unknown target "%TARGET%". Use: gui ^| cli ^| all
    exit /b 1
)

echo ========================================
echo Building Left4Translate (%TARGET%)
echo ========================================

REM Activate a local virtual environment if one exists (optional).
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

if /I "%DEP_FLAG%"=="--no-deps" (
    echo Skipping dependency sync ^(--no-deps^).
) else (
    echo Syncing dependencies from requirements.txt...
    python -m pip install -q -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to install requirements.
        exit /b %ERRORLEVEL%
    )
)

REM For the GUI target, confirm PySide6 imports before the long PyInstaller run.
if /I "%TARGET%" NEQ "cli" (
    python -c "import PySide6, shiboken6" 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: PySide6 / shiboken6 are not importable in this environment.
        echo        Run: pip install -r requirements.txt
        exit /b 1
    )
)

if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

set BUILD_FAILED=0

if /I "%TARGET%"=="cli"  goto :build_cli
if /I "%TARGET%"=="gui"  goto :build_gui
if /I "%TARGET%"=="all"  goto :build_all

:build_gui
echo.
echo Building GUI (Left4Translate-gui.spec)...
python -m PyInstaller Left4Translate-gui.spec
if %ERRORLEVEL% NEQ 0 set BUILD_FAILED=1
goto :after_build

:build_cli
echo.
echo Building CLI (Left4Translate.spec)...
python -m PyInstaller Left4Translate.spec
if %ERRORLEVEL% NEQ 0 set BUILD_FAILED=1
goto :after_build

:build_all
echo.
echo Building GUI (Left4Translate-gui.spec)...
python -m PyInstaller Left4Translate-gui.spec
if %ERRORLEVEL% NEQ 0 set BUILD_FAILED=1
echo.
echo Building CLI (Left4Translate.spec)...
python -m PyInstaller Left4Translate.spec
if %ERRORLEVEL% NEQ 0 set BUILD_FAILED=1
goto :after_build

:after_build
if %BUILD_FAILED% NEQ 0 (
    echo.
    echo ERROR: One or more PyInstaller builds failed.
    exit /b 1
)

echo.
echo Copying executables to project root...
if exist "dist\Left4Translate-GUI.exe" (
    copy /Y "dist\Left4Translate-GUI.exe" "Left4Translate-GUI.exe" >nul
    echo   - Left4Translate-GUI.exe (desktop GUI)
)
if exist "dist\Left4Translate.exe" (
    copy /Y "dist\Left4Translate.exe" "Left4Translate.exe" >nul
    echo   - Left4Translate.exe (console app)
)

echo.
echo ========================================
echo Build complete.
echo ========================================
pause
endlocal
