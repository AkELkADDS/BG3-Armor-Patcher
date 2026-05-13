@echo off
REM BG3 Armor Patcher — Author: AkELkA

setlocal



cd /d "%~dp0"



call :EnsurePython

if errorlevel 1 (

    pause

    exit /b 1

)



set "NEED_INSTALL=0"

if not exist ".venv\Scripts\python.exe" set "NEED_INSTALL=1"



if not exist ".venv\Scripts\python.exe" (

    echo Creating local Python environment...

    %PYTHON_CMD% -m venv ".venv"

    if errorlevel 1 (

        echo Failed to create the Python environment.

        pause

        exit /b 1

    )

)



call ".venv\Scripts\activate.bat"



if not "%BG3_PATCHER_FORCE_PIP%"=="" (

    echo Forcing dependency reinstall ^(BG3_PATCHER_FORCE_PIP is set^)...

    set "NEED_INSTALL=1"

)



if "%NEED_INSTALL%"=="1" goto :InstallDeps



python -c "import PySide6; import bg3_patcher" 2>nul

if errorlevel 1 goto :InstallDeps



echo Dependencies OK, skipping pip install.

goto :RunApp



:InstallDeps

echo Installing dependencies ^(first run, missing packages, or failed import check^)...

python -m pip install -q --upgrade pip

if errorlevel 1 (

    echo Failed to update pip.

    pause

    exit /b 1

)

python -m pip install -q -e .

if errorlevel 1 (

    echo Failed to install dependencies.

    pause

    exit /b 1

)

echo Done.



:RunApp

REM Must launch run_ui.py (not python -m ...) so this folder's src wins over any other install.

set "ROOT=%~dp0"

set "RUN_SCRIPT=%ROOT%run_ui.py"

set "PYW=%ROOT%.venv\Scripts\pythonw.exe"

if exist "%PYW%" (

    start "" /D "%ROOT%" "%PYW%" "%RUN_SCRIPT%"

    exit /b 0

)

if exist "%ROOT%.venv\Scripts\python.exe" (

    start "" /D "%ROOT%" "%ROOT%.venv\Scripts\python.exe" "%RUN_SCRIPT%"

    exit /b 0

)

echo Missing .venv Python. Re-run this script from the project folder.

pause

exit /b 1



:EnsurePython

where py >nul 2>nul

if not errorlevel 1 (

    set "PYTHON_CMD=py -3"

    exit /b 0

)



where python >nul 2>nul

if not errorlevel 1 (

    set "PYTHON_CMD=python"

    exit /b 0

)



echo Python was not found.

echo.

echo Trying to install Python 3 using Windows Package Manager...

echo This may ask for confirmation or administrator permission.

echo.



where winget >nul 2>nul

if errorlevel 1 (

    echo Windows Package Manager "winget" was not found.

    echo Please install Python manually from:

    echo https://www.python.org/downloads/

    echo.

    echo During installation, enable "Add python.exe to PATH" and "py launcher".

    exit /b 1

)



winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements

if errorlevel 1 (

    echo Automatic Python installation failed.

    echo Please install Python manually from:

    echo https://www.python.org/downloads/

    exit /b 1

)



where py >nul 2>nul

if not errorlevel 1 (

    set "PYTHON_CMD=py -3"

    exit /b 0

)



where python >nul 2>nul

if not errorlevel 1 (

    set "PYTHON_CMD=python"

    exit /b 0

)



echo Python was installed, but it is not available in this terminal yet.

echo Close this window and run BG3_Armor_Patcher.bat again.

exit /b 1

