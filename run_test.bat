@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo ========================================
echo Running SBC Agent CLI Tests
echo ========================================

:: カレントディレクトリをバッチファイルの場所に移動
cd /d "%~dp0"

:: 環境変数ファイルがあれば読み込む
if exist env.bat (
    echo [INFO] Loading env.bat...
    call env.bat
)

:: src ディレクトリを PYTHONPATH に追加
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

:: --- 1. Static Analysis (Optional) ---

:: Lint (Ruff)
where ruff >nul 2>nul
if %errorlevel% equ 0 (
    echo.
    echo [INFO] Running ruff checks...
    ruff check src test
    if !errorlevel! neq 0 (
        echo [WARN] Linting issues found.
    )
)

:: Type Check (Mypy)
where mypy >nul 2>nul
if %errorlevel% equ 0 (
    echo.
    echo [INFO] Running mypy type checks...
    mypy src
    if !errorlevel! neq 0 (
        echo [WARN] Type check issues found.
    )
)

:: --- 2. Run Unit Tests ---
echo.
echo [INFO] Starting Tests...

:: 引数がない場合は自動検出、ある場合は引数をそのまま渡す
if "%~1"=="" (
    python -m unittest discover -v -s test -p "test_*.py"
) else (
    echo [INFO] Running specific tests: %*
    python -m unittest %*
)

set TEST_EXIT=%errorlevel%

if %TEST_EXIT% neq 0 (
    echo.
    echo [ERROR] Tests failed with exit code %TEST_EXIT%.
    color 0c
) else (
    echo.
    echo [SUCCESS] All tests passed successfully.
    color 0a
)

endlocal
pause
exit /b %TEST_EXIT%
