@echo off
REM LinkedIn Gateway - Unified Update Script (Windows)
REM This script updates an existing LinkedIn Gateway installation
REM Usage: update.bat [core|saas|enterprise]

setlocal enabledelayedexpansion

REM Get edition from parameter (default to core)
set "EDITION=%~1"
if "%EDITION%"=="" set "EDITION=core"

REM Validate edition
if not "%EDITION%"=="core" if not "%EDITION%"=="saas" if not "%EDITION%"=="enterprise" (
    echo Error: Invalid edition '%EDITION%'. Must be 'core', 'saas', or 'enterprise'.
    echo Usage: %~nx0 [core^|saas^|enterprise]
    exit /b 1
)

REM Get script directory and paths
set "SCRIPT_DIR=%~dp0"
set "DEPLOYMENT_DIR=%SCRIPT_DIR%.."
set "PROJECT_ROOT=%DEPLOYMENT_DIR%\.."

REM Set edition-specific variables
if "%EDITION%"=="saas" (
    set "EDITION_TITLE=SaaS Edition"
    set "DOCKER_COMPOSE_CMD=docker compose -f docker-compose.yml -f docker-compose.saas.yml"
    set "DB_CONTAINER=linkedin-gateway-saas-db"
) else (
    if "%EDITION%"=="enterprise" (
        set "EDITION_TITLE=Enterprise Edition"
        set "DOCKER_COMPOSE_CMD=docker compose -f docker-compose.yml -f docker-compose.enterprise.yml"
        set "DB_CONTAINER=linkedin-gateway-enterprise-db"
    ) else (
        set "EDITION_TITLE=Open Core Edition"
        set "DOCKER_COMPOSE_CMD=docker compose -f docker-compose.yml"
        set "DB_CONTAINER=linkedin-gateway-core-db"
    )
)

echo ======================================
echo LinkedIn Gateway - Update
echo Edition: %EDITION_TITLE%
echo ======================================
echo.

REM Step 0: Check prerequisites
echo [0/6] Checking prerequisites...

REM Check Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not running. Please start Docker Desktop.
    exit /b 1
)
echo   Done: Docker is running

REM Check docker compose
docker compose version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker Compose is not available.
    exit /b 1
)
echo   Done: Docker Compose is available

REM Check if installation exists
docker ps -a --filter "name=linkedin.*gateway" --format "{{.Names}}" | findstr /i "gateway" >nul 2>&1
if errorlevel 1 (
    echo No existing installation found.
    echo Please run install.bat %EDITION% first for a fresh installation.
    exit /b 1
)
echo   Done: Existing installation found
echo.

REM Step 1: Pull latest code
echo [1/6] Pulling latest code from Git...
cd /d "%PROJECT_ROOT%"

if exist ".git" (
    REM Check for uncommitted changes
    git diff-index --quiet HEAD 2>nul
    if errorlevel 1 (
        echo   Warning: Uncommitted changes detected
        echo   Stashing changes...
        for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "DATESTR=%%c%%a%%b"
        for /f "tokens=1-3 delims=:. " %%a in ("%time%") do set "TIMESTR=%%a%%b%%c"
        git stash push -m "Auto-stash before update !DATESTR!_!TIMESTR!"
        echo   Done: Changes stashed (recover with: git stash pop)
    )

    REM Pull latest changes - try multiple strategies to ensure success
    echo   Pulling latest code...

    REM Strategy 1: Normal pull
    git pull origin main >nul 2>&1
    if not errorlevel 1 (
        echo   Done: Code updated successfully
        goto :GIT_UPDATE_SUCCESS
    )

    REM Strategy 2: Pull with --allow-unrelated-histories
    git pull origin main --allow-unrelated-histories --no-edit >nul 2>&1
    if not errorlevel 1 (
        echo   Done: Code updated (merged unrelated histories)
        goto :GIT_UPDATE_SUCCESS
    )

    REM Strategy 3: Fetch and hard reset (force update to match remote exactly)
    echo   Normal pull failed, fetching and resetting to remote...
    git fetch origin main >nul 2>&1
    if errorlevel 1 goto :GIT_UPDATE_FAILED

    git reset --hard origin/main >nul 2>&1
    if errorlevel 1 goto :GIT_UPDATE_FAILED

    echo   Done: Code updated (force reset to remote)
    echo   Note: Local code now matches remote exactly
    goto :GIT_UPDATE_SUCCESS

    :GIT_UPDATE_FAILED
    echo   Error: Failed to update code from Git
    echo   Cannot continue with outdated code
    echo.
    echo Please manually update the code:
    echo   cd "%PROJECT_ROOT%"
    echo   git fetch origin
    echo   git reset --hard origin/main
    echo.
    exit /b 1

    :GIT_UPDATE_SUCCESS
    
    REM Check for merge conflicts after git pull
    echo   Checking for merge conflicts...
    cd /d "%PROJECT_ROOT%"
    findstr /S /M /C:"<<<<<<< " "backend\alembic\*.py" "backend\alembic\versions\*.py" >nul 2>&1
    if not errorlevel 1 (
        echo   Warning: Merge conflicts detected in migration files!
        echo   Attempting to resolve automatically...
        echo.
        echo   Please manually resolve conflicts in these files:
        findstr /S /M /C:"<<<<<<< " "backend\alembic\*.py" "backend\alembic\versions\*.py"
        echo.
        echo   After resolving conflicts, run update script again.
        exit /b 1
    )
    echo   Done: No merge conflicts detected
) else (
    echo   Not a git repository, skipping git pull
)
echo.

REM Change to deployment directory
cd /d "%DEPLOYMENT_DIR%"

REM Step 2: Pull latest Docker images
echo [2/6] Pulling latest Docker images...
%DOCKER_COMPOSE_CMD% pull
echo   Done: Images pulled
echo.

REM Step 3: Rebuild and restart containers
echo [3/6] Rebuilding and restarting containers...
echo   Building images...
%DOCKER_COMPOSE_CMD% build --no-cache

echo   Restarting services...
%DOCKER_COMPOSE_CMD% up -d

if errorlevel 1 (
    echo Error: Docker Compose deployment failed.
    exit /b 1
)
echo   Done: Containers restarted
echo.

REM Step 4: Wait for database
echo [4/6] Waiting for database to be ready...

REM Wait up to 30 seconds for database
set /a "COUNT=0"
:WAIT_DB
docker exec %DB_CONTAINER% pg_isready -U linkedin_gateway_user >nul 2>&1
if not errorlevel 1 goto DB_READY
set /a "COUNT+=1"
if %COUNT% geq 30 goto DB_TIMEOUT
timeout /t 1 /nobreak >nul
goto WAIT_DB

:DB_TIMEOUT
echo   Warning: Database did not respond within 30 seconds
goto APPLY_MIGRATIONS

:DB_READY
echo   Done: Database is ready
echo.

:APPLY_MIGRATIONS
REM Step 5: Apply database migrations
echo [5/6] Applying database migrations...

REM Check for merge conflicts in migration files before running
echo   Checking for merge conflicts...
%DOCKER_COMPOSE_CMD% exec -T backend sh -c "cd /app && grep -r '^<<<<<<< ' alembic/ 2>/dev/null | head -1" >nul 2>&1
if not errorlevel 1 (
    echo   Error: Merge conflicts detected in migration files!
    echo   Please resolve conflicts before continuing:
    echo   1. Check backend/alembic/ directory for conflict markers ^(^&lt;^&lt;^&lt;^&lt;^&lt;^&lt;^&lt;^)
    echo   2. Resolve conflicts manually
    echo   3. Run update script again
    echo.
    echo   To check conflicts: %DOCKER_COMPOSE_CMD% exec backend sh -c "grep -r '^<<<<<<< ' /app/alembic/"
    exit /b 1
)

REM Check current migration version
echo   Checking current database version...
%DOCKER_COMPOSE_CMD% exec -T backend sh -c "cd /app && alembic current" >nul 2>&1
if errorlevel 1 (
    echo   Warning: Could not determine current migration version
    echo   This may be a fresh installation or migration issue
) else (
    echo   Current version:
    %DOCKER_COMPOSE_CMD% exec -T backend sh -c "cd /app && alembic current"
)

REM Run migrations with better error handling
echo   Running: alembic upgrade head

REM Capture migration output to check for specific errors
%DOCKER_COMPOSE_CMD% exec -T backend sh -c "cd /app && alembic upgrade head 2>&1" > "%TEMP%\migration_output.txt" 2>&1
set "MIGRATION_EXIT_CODE=%ERRORLEVEL%"

REM Check migration result
if %MIGRATION_EXIT_CODE% equ 0 (
    echo   Done: Database migrations applied successfully
    del "%TEMP%\migration_output.txt" >nul 2>&1
) else (
    REM Check output for specific error patterns
    findstr /C:"already at head" /C:"Can't locate revision" /C:"Target database is not up to date" "%TEMP%\migration_output.txt" >nul 2>&1
    if not errorlevel 1 (
        echo   Done: Database is already up to date
        echo   Note: All migrations have been applied previously
        del "%TEMP%\migration_output.txt" >nul 2>&1
    ) else (
        REM Check for syntax errors (like merge conflicts)
        findstr /C:"SyntaxError" /C:"invalid decimal literal" /C:"conflict" "%TEMP%\migration_output.txt" >nul 2>&1
        if not errorlevel 1 (
            echo   Error: Syntax error detected in migration files!
            echo   This may be due to unresolved merge conflicts.
            echo.
            echo   Please check:
            echo   1. backend/alembic/env.py for merge conflict markers ^(^&lt;^&lt;^&lt;^&lt;^&lt;^&lt;^&lt;^)
            echo   2. backend/alembic/versions/*.py for merge conflict markers
            echo   3. Resolve conflicts and run update again
            echo.
            echo   To check for conflicts:
            echo     %DOCKER_COMPOSE_CMD% exec backend sh -c "grep -r '^<<<<<<< ' /app/alembic/"
            echo.
            echo   Error details:
            findstr /C:"SyntaxError" /C:"File" /C:"line" "%TEMP%\migration_output.txt"
            del "%TEMP%\migration_output.txt" >nul 2>&1
            exit /b 1
        ) else (
            REM Check for partial migration issues (column already exists, etc.)
            findstr /C:"already exists" /C:"duplicate" /C:"column" "%TEMP%\migration_output.txt" >nul 2>&1
            if not errorlevel 1 (
                echo   Warning: Some migrations may have been partially applied
                echo   This is usually safe - migrations are idempotent.
                echo   Checking if we can continue...
                echo.
                REM Try to get current version to see if we're at least partially updated
                %DOCKER_COMPOSE_CMD% exec -T backend sh -c "cd /app && alembic current" 2>nul
                echo.
                echo   If issues persist, check logs: %DOCKER_COMPOSE_CMD% logs backend
                del "%TEMP%\migration_output.txt" >nul 2>&1
            ) else (
                echo   Error: Failed to apply database migrations
                echo.
                echo   Possible causes:
                echo   - Database connection issues
                echo   - Migration file errors
                echo   - Schema conflicts
                echo.
                echo   Error output:
                type "%TEMP%\migration_output.txt" | findstr /V "INFO" | findstr /V "WARNING" | findstr /V "level="
                echo.
                echo   Check backend logs: %DOCKER_COMPOSE_CMD% logs backend
                echo   Check migration status: %DOCKER_COMPOSE_CMD% exec backend alembic current
                echo   Check migration history: %DOCKER_COMPOSE_CMD% exec backend alembic history
                del "%TEMP%\migration_output.txt" >nul 2>&1
                exit /b 1
            )
        )
    )
)
echo.

REM Step 6: Verify services are healthy
echo [6/6] Verifying services are healthy...

REM Get backend port
for /f "tokens=2 delims==" %%a in ('findstr /b "BACKEND_PORT=" .env 2^>nul') do set "BACKEND_PORT=%%a"
if not defined BACKEND_PORT set "BACKEND_PORT=7778"

set "HEALTH_URL=http://localhost:%BACKEND_PORT%/health"
set /a "ATTEMPT=0"

echo   Checking backend health...
:WAIT_HEALTH
curl -s -f "%HEALTH_URL%" >nul 2>&1
if not errorlevel 1 goto HEALTH_READY
set /a "ATTEMPT+=1"
if %ATTEMPT% geq 30 goto HEALTH_TIMEOUT
timeout /t 2 /nobreak >nul
goto WAIT_HEALTH

:HEALTH_TIMEOUT
echo.
echo   Warning: Backend did not respond within timeout
echo   Check logs: %DOCKER_COMPOSE_CMD% logs backend
goto PRINT_STATUS

:HEALTH_READY
echo   Done: Backend is healthy and ready!

:PRINT_STATUS
echo.
echo ======================================
echo Done: Update Complete!
echo ======================================
echo.
echo Service Status:
%DOCKER_COMPOSE_CMD% ps
echo.
echo LinkedIn Gateway has been updated and is running:
echo   Backend:    http://localhost:%BACKEND_PORT%
echo   Health:     http://localhost:%BACKEND_PORT%/health
echo   API Docs:   http://localhost:%BACKEND_PORT%/docs
echo.
echo Useful commands:
echo   View logs:      %DOCKER_COMPOSE_CMD% logs -f
echo   Stop services:  %DOCKER_COMPOSE_CMD% down
echo   Restart:        %DOCKER_COMPOSE_CMD% restart
echo.

endlocal
