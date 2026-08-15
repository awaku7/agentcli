@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"

rem Computer Use browser launcher
rem API keys and provider/model settings are read from the existing environment/.env files.
set "UAGENT_COMPUTER_USE=1"
set "UAGENT_COMPUTER_ENVIRONMENT=browser"
set "UAGENT_COMPUTER_HEADLESS=0"
set "UAGENT_COMPUTER_BROWSER_URL=https://www.wikipedia.org"
set "UAGENT_COMPUTER_REQUIRE_CONFIRMATION=1"
set "UAGENT_COMPUTER_ALLOWED_ACTIONS=screenshot,click,type,keypress,scroll"
set "UAGENT_COMPUTER_ALLOWED_DOMAINS=www.wikipedia.org"
set "UAGENT_COMPUTER_MAX_ACTIONS=20"
set "UAGENT_COMPUTER_MAX_TURNS=10"
set "UAGENT_COMPUTER_TIMEOUT=120"

python -m uagent --computer-use
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
