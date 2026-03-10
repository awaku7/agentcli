@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ========================================
echo Running Agent CLI Checks and Tests
echo ========================================

:: Move to this batch file directory
cd /d "%~dp0"

:: Load env file if present
if exist env.bat (
    echo [INFO] Loading env.bat...
    call env.bat
)

:: Add src to PYTHONPATH
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

:: --- 1. Static Analysis (Optional) ---

:: Lint (Ruff)
where ruff >nul 2>nul
if !errorlevel! equ 0 (
    echo.
    echo [INFO] Running ruff checks...
    ruff check src tests
    if !errorlevel! neq 0 (
        echo [WARN] Ruff found issues.
    )
) else (
    echo.
    echo [INFO] ruff not found. Skipping ruff checks.
)

:: Format check (Black)
where black >nul 2>nul
if !errorlevel! equ 0 (
    echo.
    echo [INFO] Running black --check...
    black --check src tests
    if !errorlevel! neq 0 (
        echo [WARN] Black formatting issues found.
    )
) else (
    echo.
    echo [INFO] black not found. Skipping format check.
)

:: --- 2. Run Tests (pytest) ---
echo.
echo [INFO] Starting pytest...

:: No args: run all tests under tests/
if "%~1"=="" (
    python -m pytest -q tests
) else (
    echo [INFO] Running pytest with args: %*
    python -m pytest %*
)

set TEST_EXIT=%errorlevel%

if %TEST_EXIT% neq 0 (
    echo.
    echo [ERROR] Tests failed with exit code %TEST_EXIT%.
    color 0c
) else (
    echo.
    echo [SUCCESS] All tests passed.
    color 0a
)

endlocal
pause
exit /b %TEST_EXIT%
