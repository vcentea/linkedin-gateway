@echo off
REM =============================================================================
REM LinkedIn Gateway - Start Development Enterprise with Hot Reload (Windows)
REM =============================================================================
REM This script starts the Enterprise edition in development mode with hot reload
REM enabled, allowing instant code changes without rebuilding.
REM
REM Usage: start-dev-enterprise.bat
REM =============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "DEPLOYMENT_DIR=%SCRIPT_DIR%.."

echo ==============================================================================
echo LinkedIn Gateway - Development Enterprise with Hot Reload
echo ==============================================================================
echo.

cd /d "%DEPLOYMENT_DIR%"

REM Check if .env exists
if not exist ".env" (
    echo [WARN] No .env file found. Creating from example...
    if exist ".env.enterprise.example" (
        copy /Y ".env.enterprise.example" ".env" >nul
        echo [OK] Created .env file
    ) else if exist ".env.example" (
        copy /Y ".env.example" ".env" >nul
        echo [OK] Created .env file
    ) else (
        echo [ERROR] No .env example file found
        exit /b 1
    )
    echo.
)

REM Ensure LG_BACKEND_EDITION is set to enterprise in .env
findstr /R "^LG_BACKEND_EDITION=enterprise" .env >nul 2>&1
if errorlevel 1 (
    echo [WARN] Setting LG_BACKEND_EDITION=enterprise in .env...
    powershell -Command "(Get-Content .env) -replace '^LG_BACKEND_EDITION=.*', 'LG_BACKEND_EDITION=enterprise' | Set-Content .env" 2>nul || echo LG_BACKEND_EDITION=enterprise >> .env
    echo [OK] Edition configured
    echo.
)

echo Starting Development Enterprise with:
echo   [*] Hot reload: ENABLED
echo   [*] Edition: Enterprise (LG_BACKEND_EDITION=enterprise^)
echo   [*] Debug mode: ON
echo   [*] Source: ../backend (mounted^)
echo.

REM Create a dev override for Enterprise if it doesn't exist
if not exist "docker-compose.dev-enterprise.yml" (
    echo [WARN] Creating docker-compose.dev-enterprise.yml...
    (
        echo # Development overlay for Enterprise edition with hot reload
        echo name: linkedin-gateway-enterprise-dev
        echo.
        echo services:
        echo   backend:
        echo     container_name: linkedin-gateway-enterprise-dev-api
        echo     volumes:
        echo       - ../backend:/app:ro
        echo     environment:
        echo       RELOAD: "true"
    ) > docker-compose.dev-enterprise.yml
    echo [OK] Dev config created
    echo.
)

REM Start services
echo Starting services...
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml up -d

if errorlevel 1 (
    echo [ERROR] Failed to start services
    exit /b 1
)

echo.
echo [OK] Services started
echo.

REM Wait for backend to be ready
echo Waiting for backend to be ready...
for /f "tokens=2 delims==" %%a in ('findstr /R "^PORT=" .env 2^>nul') do set "PORT=%%a"
if not defined PORT set "PORT=7778"

set "MAX_WAIT=60"
set "WAITED=0"

:wait_loop
if %WAITED% GEQ %MAX_WAIT% goto wait_done
curl -s -f "http://localhost:%PORT%/health" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Backend is ready!
    goto wait_done
)
echo|set /p="."
timeout /t 2 /nobreak >nul
set /a WAITED+=2
goto wait_loop

:wait_done
echo.
echo.

REM Show status
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml ps

echo.
echo ==============================================================================
echo [OK] Development Enterprise with Hot Reload is running!
echo ==============================================================================
echo.
echo Access:
echo   Backend:    http://localhost:%PORT%
echo   API Docs:   http://localhost:%PORT%/docs
echo   Health:     http://localhost:%PORT%/health
echo.
echo Features:
echo   [*] Hot Reload: ENABLED - Edit files in backend/ and see changes instantly
echo   [*] Edition: Enterprise - Running with LG_BACKEND_EDITION=enterprise
echo   [*] Debug: ON - Detailed logging for development
echo.
echo Useful commands:
echo   View logs:  docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml logs -f
echo   Stop:       docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml down
echo   Restart:    docker compose -f docker-compose.yml -f docker-compose.enterprise.yml -f docker-compose.dev-enterprise.yml restart backend
echo.
echo Tip: Edit Python files in backend/ and uvicorn will auto-reload!
echo.



