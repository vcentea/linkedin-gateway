@echo off
REM LinkedIn Gateway - Simple Update Script (Windows)
REM Usage: update.bat [core|saas|enterprise]

setlocal enabledelayedexpansion

REM Get edition (default: core)
set "EDITION=%~1"
if "%EDITION%"=="" set "EDITION=core"

REM Validate edition
if not "%EDITION%"=="core" if not "%EDITION%"=="saas" if not "%EDITION%"=="enterprise" (
    echo Error: Invalid edition. Use: core, saas, or enterprise
    exit /b 1
)

REM Paths
set "SCRIPT_DIR=%~dp0"
set "DEPLOYMENT_DIR=%SCRIPT_DIR%.."
set "PROJECT_ROOT=%DEPLOYMENT_DIR%\.."

REM Edition config
if "%EDITION%"=="saas" (
    set "EDITION_TITLE=SaaS Edition"
    set "COMPOSE=docker compose -f docker-compose.yml -f docker-compose.saas.yml"
    set "DB_CONTAINER=linkedin-gateway-saas-db"
) else if "%EDITION%"=="enterprise" (
    set "EDITION_TITLE=Enterprise Edition"
    set "COMPOSE=docker compose -f docker-compose.yml -f docker-compose.enterprise.yml"
    set "DB_CONTAINER=linkedin-gateway-enterprise-db"
) else (
    set "EDITION_TITLE=Open Core Edition"
    set "COMPOSE=docker compose -f docker-compose.yml"
    set "DB_CONTAINER=linkedin-gateway-core-db"
)

echo ========================================
echo LinkedIn Gateway Update - %EDITION_TITLE%
echo ========================================
echo.

REM [0/5] Prerequisites
echo [0/5] Checking prerequisites...
docker info >nul 2>&1
if errorlevel 1 (
    echo Error: Docker not running
    exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker Compose not available
    exit /b 1
)
echo   Done: Docker ready
echo.

REM [1/5] Update code from Git
echo [1/5] Updating code from repository...
cd /d "%PROJECT_ROOT%"
if exist ".git" (
    git fetch origin main >nul 2>&1
    git merge --abort >nul 2>&1
    git reset --hard origin/main >nul 2>&1
    git clean -fdx >nul 2>&1
    echo   Done: Code updated (forced to match remote)
) else (
    echo   Warning: Not a git repo, skipping
)
echo.

REM [2/5] Docker images
echo [2/5] Updating Docker images...
cd /d "%DEPLOYMENT_DIR%"
%COMPOSE% pull >nul 2>&1
echo   Done: Images updated
echo.

REM [3/5] Rebuild containers
echo [3/5] Rebuilding containers...
%COMPOSE% build --no-cache >nul 2>&1
%COMPOSE% up -d
echo   Done: Containers running
echo.

REM [4/5] Wait for database
echo [4/5] Waiting for database...
set /a "COUNT=0"
:WAIT_DB
docker exec %DB_CONTAINER% pg_isready -U linkedin_gateway_user >nul 2>&1
if not errorlevel 1 (
    echo   Done: Database ready
    goto DB_READY
)
set /a "COUNT+=1"
if %COUNT% geq 30 goto DB_READY
timeout /t 1 /nobreak >nul
goto WAIT_DB
:DB_READY
echo.

REM [5/5] Migrations
echo [5/5] Running migrations...
%COMPOSE% exec -T backend sh -c "cd /app && alembic upgrade head 2>&1" > "%TEMP%\migration.txt" 2>&1

REM Check migration output
findstr /C:"already exists" /C:"duplicate" /C:"Running upgrade" "%TEMP%\migration.txt" >nul 2>&1
if not errorlevel 1 (
    echo   Done: Migrations applied
    del "%TEMP%\migration.txt" >nul 2>&1
    goto MIGRATION_DONE
)

findstr /C:"SyntaxError" /C:"<<<<<<<" "%TEMP%\migration.txt" >nul 2>&1
if not errorlevel 1 (
    echo   Error: Merge conflict in migration files
    type "%TEMP%\migration.txt"
    del "%TEMP%\migration.txt" >nul 2>&1
    exit /b 1
)

REM Check if at head
%COMPOSE% exec -T backend sh -c "cd /app && alembic current 2>&1" | findstr /C:"head" >nul 2>&1
if not errorlevel 1 (
    echo   Done: Already at latest migration
) else (
    echo   Done: Migrations completed
)
del "%TEMP%\migration.txt" >nul 2>&1

:MIGRATION_DONE
echo.

REM Get port
for /f "tokens=2 delims==" %%a in ('findstr /b "BACKEND_PORT=" .env 2^>nul') do set "BACKEND_PORT=%%a"
if not defined BACKEND_PORT set "BACKEND_PORT=7778"

echo ========================================
echo Done: Update Complete!
echo ========================================
echo.
echo LinkedIn Gateway is running:
echo   API:    http://localhost:%BACKEND_PORT%
echo   Docs:   http://localhost:%BACKEND_PORT%/docs
echo   Health: http://localhost:%BACKEND_PORT%/health
echo.

endlocal
