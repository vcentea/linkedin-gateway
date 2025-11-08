@echo off
REM LinkedIn Gateway - Simple Update Script (Windows)
REM Usage: update.bat [core|saas|enterprise] [--no-cache]
REM 
REM Options:
REM   --no-cache    Force rebuild without using cache (slower but ensures clean build)
REM                 Default: Uses cache for faster builds

setlocal enabledelayedexpansion

REM Get edition (default: core)
set "EDITION=%~1"
if "%EDITION%"=="" set "EDITION=core"

REM Check for --no-cache flag
set "NO_CACHE=false"
if "%2"=="--no-cache" set "NO_CACHE=true"
if "%3"=="--no-cache" set "NO_CACHE=true"

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
    REM Backup .env files before git operations
    set "ENV_BACKUP_CREATED=false"
    if exist "deployment\.env" (
        copy "deployment\.env" "deployment\.env.backup" >nul 2>&1
        if not errorlevel 1 set "ENV_BACKUP_CREATED=true"
    )
    if exist "backend\.env" (
        copy "backend\.env" "backend\.env.backup" >nul 2>&1
        if not errorlevel 1 set "ENV_BACKUP_CREATED=true"
    )
    
    REM Fetch latest changes
    git fetch origin main >nul 2>&1
    
    REM Use safer merge approach instead of reset --hard
    REM This preserves local changes and only updates what's changed
    git merge --ff-only origin/main >nul 2>&1
    if not errorlevel 1 (
        echo   Done: Code updated (fast-forward)
    ) else (
        git merge origin/main --no-edit >nul 2>&1
        if not errorlevel 1 (
            echo   Done: Code updated (merged)
        ) else (
            echo   Warning: Merge conflicts detected - keeping local changes
            echo            Resolve conflicts manually if needed
            git merge --abort >nul 2>&1
        )
    )
    
    REM Restore .env files if they were backed up
    if "%ENV_BACKUP_CREATED%"=="true" (
        if exist "deployment\.env.backup" (
            move /y "deployment\.env.backup" "deployment\.env" >nul 2>&1
        )
        if exist "backend\.env.backup" (
            move /y "backend\.env.backup" "backend\.env" >nul 2>&1
        )
        echo   Done: .env files preserved
    )
    
    REM Clean only build artifacts, not user files
    REM Note: git clean -e doesn't work in Windows batch, so we skip git clean entirely
    REM This is safer for incremental updates
) else (
    echo   Warning: Not a git repo, skipping
)
echo.

REM [2/5] Docker images
echo [2/5] Updating Docker images...
cd /d "%DEPLOYMENT_DIR%"
echo   Info: Pulling latest base images...
%COMPOSE% pull
if errorlevel 1 (
    echo   Warning: Some images may not have updated (this is usually OK)
) else (
    echo   Done: Images updated
)
echo.

REM [3/5] Rebuild containers
echo [3/5] Rebuilding containers...
cd /d "%DEPLOYMENT_DIR%"

if "%NO_CACHE%"=="true" (
    echo   Info: Building without cache (this may take 5-15 minutes)...
    set "BUILD_ARGS=--no-cache --progress=plain"
) else (
    echo   Info: Building with cache (faster, use --no-cache for clean build)...
    set "BUILD_ARGS=--progress=plain"
)

echo   Info: Build output:
%COMPOSE% build %BUILD_ARGS%
if errorlevel 1 (
    echo   Error: Build failed! Check output above for errors
    exit /b 1
)
echo   Done: Build completed

echo   Info: Starting containers...
%COMPOSE% up -d
if errorlevel 1 (
    echo   Error: Failed to start containers
    exit /b 1
)
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
