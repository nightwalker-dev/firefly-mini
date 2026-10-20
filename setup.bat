@echo off
REM ==============================================================================
REM Firefly Mini — Automated Windows Setup Batch Script v2.1.0
REM ==============================================================================

echo [Firefly Mini] Starting Windows Setup Sentinel...

REM Check for Python
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY_CMD=py -3
    goto :FOUND_PYTHON
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set PY_CMD=python
    goto :FOUND_PYTHON
)

echo [ERROR] Python 3.10+ not found!
echo Please install Python 3.10 or higher from https://python.org or run:
echo   winget install Python.Python.3.11
pause
exit /b 1

:FOUND_PYTHON
echo [Firefly Mini] Found Python: %PY_CMD%

REM Create virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [Firefly Mini] Creating virtual environment in .venv...
    %PY_CMD% -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [Firefly Mini] Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel -q

echo [Firefly Mini] Installing Firefly Mini...
.venv\Scripts\python.exe -m pip install -e ".[dev]" -q

echo [Firefly Mini] Running System Diagnostics...
.venv\Scripts\python.exe -m firefly doctor

echo.
echo ==============================================================================
echo [SUCCESS] Firefly Mini installed!
echo To run:
echo   .venv\Scripts\firefly.exe chat
echo   .venv\Scripts\firefly.exe hud
echo ==============================================================================
