@echo off
rem Launch the Display Switch UI with the Windows Python in the project .venv.
rem Requires the .venv created on Windows: py -3.10 -m venv .venv && .venv\Scripts\pip install -e .

set "PROJECT_DIR=%~dp0"
rem Drop the trailing backslash so the quoted paths below are clean.
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "VENV_PYW=%PROJECT_DIR%\.venv\Scripts\pythonw.exe"
set "SRC_DIR=%PROJECT_DIR%\src"

if not exist "%VENV_PYW%" (
    echo Virtual environment not found: %VENV_PYW%
    echo Create it with: py -3.10 -m venv .venv ^&^& .venv\Scripts\pip install -e .
    pause
    exit /b 1
)

rem Start elevated (UAC prompt) so PnP commands can disable and enable monitors.
rem pythonw.exe runs without a console window; the working directory is src so
rem "-m display_switch" resolves the package.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "Start-Process -FilePath '%VENV_PYW%' -WorkingDirectory '%SRC_DIR%' -ArgumentList '-m','display_switch','show' -Verb RunAs"
if errorlevel 1 (
    echo Could not start Display Switch. Elevation may have been declined.
    pause
    exit /b 1
)
