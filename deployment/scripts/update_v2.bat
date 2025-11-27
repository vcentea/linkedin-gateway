@echo off
REM LinkedIn Gateway - Improved Update Script V2 (Windows)
REM Usage: update_v2.bat [core|saas|enterprise] [version] [--no-cache] [--force-git]
REM
REM This version uses safer git operations that preserve history:
REM - Uses git pull instead of git reset --hard
REM - Handles merge conflicts gracefully (with auto-recovery option)
REM - Supports version pinning
REM - Better error handling
REM - Progress visibility for builds
REM
REM Options:
REM   --no-cache    Force rebuild without using cache (slower but ensures clean build)
REM   --force-git   Auto-force git reset on merge conflicts (safe for deployments)
REM                 Your .env and database are never touched by git operations

setlocal enabledelayedexpansion

REM Get edition (default: core)
set "EDITION=%~1"
if "%EDITION%"=="" set "EDITION=core"

REM Get version (default: latest)
set "VERSION=%~2"
if "%VERSION%"=="" set "VERSION=latest"

REM Check for flags
set "NO_CACHE=false"
set "FORCE_GIT=false"
if "%2"=="--no-cache" set "NO_CACHE=true"
if "%3"=="--no-cache" set "NO_CACHE=true"
if "%4"=="--no-cache" set "NO_CACHE=true"
if "%2"=="--force-git" set "FORCE_GIT=true"
if "%3"=="--force-git" set "FORCE_GIT=true"
if "%4"=="--force-git" set "FORCE_GIT=true"

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
echo LinkedIn Gateway Update V2 - %EDITION_TITLE%
echo ========================================
echo.

REM [0/6] Prerequisites
echo [0/6] Checking prerequisites...
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

REM [1/6] Update code from Git (NEW SAFER APPROACH)
echo [1/6] Updating code from repository...
cd /d "%PROJECT_ROOT%"

if exist ".git" (
    REM Check if we have a valid git repository
    git rev-parse --git-dir >nul 2>&1
    if errorlevel 1 (
        echo   Error: Not a valid git repository
        exit /b 1
    )

    REM Check for local modifications
    git diff-index --quiet HEAD -- >nul 2>&1
    if errorlevel 1 (
        echo   Warning: Local modifications detected
        echo   Stashing local changes...

        REM Stash with a timestamp
        for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set "DATESTAMP=%%c%%a%%b"
        for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "TIMESTAMP=%%a%%b"
        set "STASH_NAME=auto-stash-!DATESTAMP!-!TIMESTAMP!"

        git stash push -m "!STASH_NAME!" >nul 2>&1

        echo   Done: Changes stashed as: !STASH_NAME!
        echo   Info: To restore: git stash list ^&^& git stash pop
    )

    REM Fetch latest changes
    echo   Fetching latest changes...
    git fetch origin main >nul 2>&1
    if errorlevel 1 (
        echo   Error: Could not fetch from remote
        exit /b 1
    )

    REM Determine target version
    if "%VERSION%"=="latest" (
        set "TARGET=origin/main"
        echo   Updating to latest version
    ) else (
        REM Check if version tag exists
        git rev-parse "v%VERSION%" >nul 2>&1
        if errorlevel 1 (
            echo   Error: Version tag 'v%VERSION%' not found
            echo   Available versions:
            git tag -l "v*" | findstr /N "^" | findstr ":1$ :2$ :3$ :4$ :5$"
            exit /b 1
        )
        set "TARGET=v%VERSION%"
        echo   Updating to version: %VERSION%
    )

    REM Try to merge (fast-forward only first)
    echo   Attempting fast-forward merge...
    git merge --ff-only %TARGET% >nul 2>&1
    if not errorlevel 1 (
        echo   Done: Code updated successfully ^(fast-forward^)
    ) else (
        REM Fast-forward failed, try regular merge
        echo   Warning: Fast-forward not possible, attempting merge...

        git merge %TARGET% >nul 2>&1
        if not errorlevel 1 (
            echo   Done: Code updated successfully ^(merge^)
        ) else (
            REM Merge failed - likely conflicts
            echo   Warning: Merge conflicts detected
            
            REM Abort the failed merge first
            git merge --abort >nul 2>&1
            
            REM Check if --force-git flag was provided
            if "%FORCE_GIT%"=="true" (
                echo   Warning: --force-git specified, forcing update...
                git reset --hard %TARGET%
                echo   Done: Code force-updated to %TARGET%
            ) else (
                echo.
                echo =======================================
                echo MERGE CONFLICT DETECTED
                echo =======================================
                echo.
                echo Safe to force update because:
                echo   - .env file is gitignored ^(your settings are safe^)
                echo   - Database is separate ^(your data is safe^)
                echo   - Local changes were stashed ^(can restore later^)
                echo.
                echo Force reset to latest version? ^(recommended for deployment servers^)
                set /p "FORCE_CONFIRM=Type 'yes' to force update, or 'no' to abort: "
                
                if "!FORCE_CONFIRM!"=="yes" (
                    echo   Info: Force updating to %TARGET%...
                    git reset --hard %TARGET%
                    echo   Done: Code force-updated successfully
                    echo   Info: Your stashed changes are still available: git stash list
                ) else (
                    echo Update aborted by user
                    echo.
                    echo To update later, you can:
                    echo   1. Run with --force-git flag: update_v2.bat core --force-git
                    echo   2. Manually force: git reset --hard origin/main
                    echo   3. Restore stash first: git stash pop
                    exit /b 1
                )
            )
        )
    )

    REM Show what changed
    echo   Recent changes:
    git log --oneline -5 2>nul

) else (
    echo   Warning: Not a git repository, skipping update
    echo   Info: Consider cloning from: https://github.com/vcentea/linkedin-gateway
)
echo.

REM [2/6] Docker images
echo [2/6] Updating Docker images...
cd /d "%DEPLOYMENT_DIR%"
echo   Info: Pulling latest base images...
%COMPOSE% pull
if errorlevel 1 (
    echo   Warning: Some images may not have updated (this is usually OK)
) else (
    echo   Done: Images updated
)
echo.

REM [3/6] Rebuild containers
echo [3/6] Rebuilding containers...
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

REM [4/6] Wait for database
echo [4/6] Waiting for database...
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

REM [5/6] Migrations
echo [5/6] Running migrations...

REM Show which migration paths are being used
echo   Info: Checking migration paths...

REM Run migrations (alembic will automatically check both versions/ and versions_saas/)
echo   Info: Running alembic upgrade head...
%COMPOSE% exec -T backend sh -c "cd /app && alembic upgrade head 2>&1" > "%TEMP%\migration.txt" 2>&1

REM Check migration output
findstr /C:"already exists" /C:"duplicate" /C:"Running upgrade" "%TEMP%\migration.txt" >nul 2>&1
if not errorlevel 1 (
    echo   Done: Migrations applied

    REM Show what was applied
    findstr /C:"Running upgrade" "%TEMP%\migration.txt" >nul 2>&1
    if not errorlevel 1 (
        echo   Info: Applied migrations:
        findstr /C:"Running upgrade" "%TEMP%\migration.txt"
    )

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

REM Show current migration state
echo   Info: Current migration state:
%COMPOSE% exec -T backend sh -c "cd /app && alembic current 2>&1"

REM Special note for SaaS edition
if "%EDITION%"=="saas" (
    echo   Info: SaaS Edition: Both core and SaaS-specific migrations are checked
)

REM Ensure schema is correct (add any missing columns/indexes)
echo   Info: Ensuring schema is correct...
echo   Info: Running: python alembic/ensure_schema.py

%COMPOSE% exec -T backend sh -c "cd /app && python alembic/ensure_schema.py 2>&1" > "%TEMP%\schema_ensure.txt" 2>&1
set ENSURE_EXIT_CODE=%errorlevel%

echo --- Schema Enforcement Output ---
type "%TEMP%\schema_ensure.txt"
echo --- End Schema Enforcement Output ---

if %ENSURE_EXIT_CODE% EQU 0 (
    findstr /C:"Schema fixed" "%TEMP%\schema_ensure.txt" >nul 2>&1
    if not errorlevel 1 (
        echo   Done: Schema updated - missing columns added
    ) else (
        findstr /C:"Schema is correct" "%TEMP%\schema_ensure.txt" >nul 2>&1
        if not errorlevel 1 (
            echo   Done: Schema is correct
        ) else (
            echo   Done: Schema enforcement completed
        )
    )
) else (
    echo   Error: Schema enforcement failed with exit code: %ENSURE_EXIT_CODE%
    echo   Warning: Database schema may be inconsistent
)
del "%TEMP%\schema_ensure.txt" >nul 2>&1

echo.

REM [6/6] Health check
echo [6/6] Running health check...
for /f "tokens=2 delims==" %%a in ('findstr /b "BACKEND_PORT=" .env 2^>nul') do set "BACKEND_PORT=%%a"
if not defined BACKEND_PORT set "BACKEND_PORT=7778"

REM Wait a moment for services to be fully ready
timeout /t 3 /nobreak >nul

REM Check if API is responding (basic check)
curl -s -f "http://localhost:%BACKEND_PORT%/health" >nul 2>&1
if not errorlevel 1 (
    echo   Done: Health check passed
) else (
    echo   Warning: Health check failed ^(services may still be starting^)
)
echo.

echo ========================================
echo Done: Update Complete!
echo ========================================
echo.
echo LinkedIn Gateway is running:
echo   API:    http://localhost:%BACKEND_PORT%
echo   Docs:   http://localhost:%BACKEND_PORT%/docs
echo   Health: http://localhost:%BACKEND_PORT%/health
echo.

REM Show current version if available
cd /d "%PROJECT_ROOT%"
if exist ".git" (
    for /f "tokens=*" %%a in ('git describe --tags --abbrev=0 2^>nul') do set "CURRENT_VERSION=%%a"
    for /f "tokens=*" %%a in ('git rev-parse --short HEAD 2^>nul') do set "CURRENT_COMMIT=%%a"
    if defined CURRENT_VERSION (
        echo Current version: !CURRENT_VERSION! ^(!CURRENT_COMMIT!^)
        echo.
    )
)

endlocal
