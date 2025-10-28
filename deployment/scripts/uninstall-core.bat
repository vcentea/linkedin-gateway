@echo off
REM LinkedIn Gateway - Open Core Teardown Script (Windows)
REM This script stops and optionally removes the open-core deployment

setlocal enabledelayedexpansion

REM Script directory and deployment root
set "SCRIPT_DIR=%~dp0"
set "DEPLOYMENT_DIR=%SCRIPT_DIR%.."
set "PROJECT_ROOT=%DEPLOYMENT_DIR%\.."

echo ======================================
echo LinkedIn Gateway - Teardown
echo ======================================
echo.

REM Change to deployment directory
cd /d "%DEPLOYMENT_DIR%"

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running.
    exit /b 1
)

REM Check if docker compose is available
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not available.
    exit /b 1
)

REM Step 1: Stop and remove containers
echo [1/3] Stopping containers...
docker compose -f docker-compose.yml down

if errorlevel 1 (
    echo [ERROR] Failed to stop containers.
    exit /b 1
)
echo   [OK] Containers stopped and removed

REM Step 2: Ask about volumes
echo.
echo [2/3] Volume management
echo.
echo Do you want to remove data volumes? [WARNING: This will delete all data!]
echo   1) Keep volumes (data preserved for next deployment)
echo   2) Remove volumes (all data will be lost)
echo   3) Skip (exit now)
echo.
set /p choice="Enter choice [1-3]: "

if "%choice%"=="1" (
    echo   [OK] Volumes preserved
    goto :summary
)

if "%choice%"=="2" (
    echo.
    echo [WARNING] This will permanently delete:
    echo   - Database data (PostgreSQL^)
    echo   - Application logs
    echo.
    set /p confirm="Are you absolutely sure? Type 'YES' to confirm: "
    
    if "!confirm!"=="YES" (
        echo.
        echo Removing volumes...
        docker compose -f docker-compose.yml down -v
        
        if not errorlevel 1 (
            echo   [OK] Volumes removed
        ) else (
            echo [ERROR] Failed to remove volumes.
            exit /b 1
        )
    ) else (
        echo   [WARNING] Volume removal cancelled. Volumes preserved.
    )
    goto :summary
)

if "%choice%"=="3" (
    echo   [WARNING] Teardown cancelled.
    exit /b 0
)

echo   [WARNING] Invalid choice. Volumes preserved by default.

:summary
REM Step 3: Summary
echo.
echo [3/3] Cleanup summary

REM Check what's still running
for /f %%i in ('docker ps --filter "name=linkedin_gateway" --format "{{.Names}}" 2^>nul ^| find /c /v ""') do set RUNNING_CONTAINERS=%%i

if "%RUNNING_CONTAINERS%"=="0" (
    echo   [OK] No LinkedIn Gateway containers running
) else (
    echo   [WARNING] Some containers may still be running
    docker ps --filter "name=linkedin_gateway"
)

REM Check volumes
for /f %%i in ('docker volume ls --filter "name=linkedingateway-saas" --format "{{.Name}}" 2^>nul ^| find /c /v ""') do set VOLUMES=%%i

if not "%VOLUMES%"=="0" (
    echo   [OK] Data volumes still exist (data preserved^)
    docker volume ls --filter "name=linkedingateway-saas"
) else (
    echo   [INFO] No volumes found (data was removed or never created^)
)

REM Final message
echo.
echo ======================================
echo [OK] Teardown Complete!
echo ======================================
echo.
echo Useful commands:
echo   Redeploy:           cd %DEPLOYMENT_DIR%\scripts ^&^& deploy-core.bat
echo   List volumes:       docker volume ls
echo   Remove old images:  docker image prune
echo   System cleanup:     docker system prune
echo.

endlocal

