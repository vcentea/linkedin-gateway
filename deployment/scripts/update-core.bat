@echo off
REM LinkedIn Gateway - Open Core Update Script (Windows)
REM This script updates an existing LinkedIn Gateway installation

setlocal enabledelayedexpansion

REM Script directory and deployment root
set "SCRIPT_DIR=%~dp0"
set "DEPLOYMENT_DIR=%SCRIPT_DIR%.."
set "PROJECT_ROOT=%DEPLOYMENT_DIR%\.."

echo ======================================
echo LinkedIn Gateway - Update
echo ======================================
echo.

REM Change to deployment directory
cd /d "%DEPLOYMENT_DIR%"

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Please start Docker and try again.
    exit /b 1
)

REM Check if docker compose is available
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not available. Please install Docker Compose and try again.
    exit /b 1
)

REM Check if installation exists
docker ps -a --filter "name=linkedin_gateway" --format "{{.Names}}" | findstr "linkedin_gateway" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] No existing installation found.
    echo Please run install-core.bat first for a fresh installation.
    exit /b 1
)

echo [1/3] Updating LinkedIn Gateway...
echo.

REM Pull latest images and rebuild
echo   -^> Pulling latest changes and rebuilding...
docker compose -f docker-compose.yml up -d --build

if errorlevel 1 (
    echo [ERROR] Update failed.
    exit /b 1
)
echo   [OK] Update completed

REM Wait for services and poll health endpoint
echo.
echo [2/3] Waiting for services to be ready...

REM Get the backend port from .env or use default
set "BACKEND_PORT=7778"
for /f "tokens=2 delims==" %%i in ('findstr "^BACKEND_PORT=" .env 2^>nul') do set "BACKEND_PORT=%%i"
set "HEALTH_URL=http://localhost:%BACKEND_PORT%/health"

set "MAX_ATTEMPTS=30"
set "ATTEMPT=0"
set "READY=false"

:wait_loop
if !ATTEMPT! geq %MAX_ATTEMPTS% goto :wait_done

curl -s -f "%HEALTH_URL%" >nul 2>&1
if not errorlevel 1 (
    set "READY=true"
    goto :wait_done
)

set /a ATTEMPT=!ATTEMPT!+1
echo|set /p="."
timeout /t 2 /nobreak >nul
goto :wait_loop

:wait_done
echo.

if "!READY!"=="true" (
    echo   [OK] Backend is healthy and ready!
) else (
    echo   [WARNING] Backend did not respond within timeout period.
    echo   Check logs: docker compose -f %DEPLOYMENT_DIR%\docker-compose.yml logs backend
)

REM Print success message
echo.
echo [3/3] Update summary
docker compose -f docker-compose.yml ps

echo.
echo ======================================
echo [OK] Update Complete!
echo ======================================
echo.
echo LinkedIn Gateway has been updated and is running:
echo   Backend:    http://localhost:%BACKEND_PORT%
echo   Health:     http://localhost:%BACKEND_PORT%/health
echo   API Docs:   http://localhost:%BACKEND_PORT%/docs
echo.
echo Useful commands:
echo   View logs:      docker compose -f %DEPLOYMENT_DIR%\docker-compose.yml logs -f
echo   Restart:        docker compose -f %DEPLOYMENT_DIR%\docker-compose.yml restart
echo   Uninstall:      cd %SCRIPT_DIR% ^&^& uninstall-core.bat
echo.

endlocal

