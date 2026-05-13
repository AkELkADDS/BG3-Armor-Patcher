@echo off
REM BG3 Armor Patcher — Author: AkELkA
REM GUI only (no console). Set RUN_UI_CONSOLE=1 to show a window for errors/debug.
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if /i "%RUN_UI_CONSOLE%"=="1" goto :console

REM --- No console: pythonw + start -----------------------------------------
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" /D "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0run_ui.py"
    exit /b 0
)
if exist "%~dp0venv\Scripts\pythonw.exe" (
    start "" /D "%~dp0" "%~dp0venv\Scripts\pythonw.exe" "%~dp0run_ui.py"
    exit /b 0
)

where py >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "_PYEXE=%%I"
    if defined _PYEXE (
        set "_PYW=!_PYEXE:\python.exe=\pythonw.exe!"
        if exist "!_PYW!" (
            start "" /D "%~dp0" "!_PYW!" "%~dp0run_ui.py"
            exit /b 0
        )
    )
)

where pythonw >nul 2>&1
if not errorlevel 1 (
    start "" /D "%~dp0" pythonw "%~dp0run_ui.py"
    exit /b 0
)

REM No pythonw found — fall through to console so you still see errors

:console
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0run_ui.py"
    goto :after
)
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0run_ui.py"
    goto :after
)

where py >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0run_ui.py"
    goto :after
)

where python >nul 2>&1
if not errorlevel 1 (
    python "%~dp0run_ui.py"
    goto :after
)

where python3 >nul 2>&1
if not errorlevel 1 (
    python3 "%~dp0run_ui.py"
    goto :after
)

echo Python was not found. Install Python or create .venv — see messages from BG3_Armor_Patcher.bat
pause
exit /b 1

:after
if errorlevel 1 pause
endlocal
