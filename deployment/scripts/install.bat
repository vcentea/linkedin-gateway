@echo off
REM LinkedIn Gateway - Unified Installation Script (Windows)
REM This script deploys LinkedIn Gateway using Docker Compose
REM Usage: install.bat [core|saas|enterprise]

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
echo LinkedIn Gateway - %EDITION_TITLE%
echo ======================================
echo.

REM Step 0: Git pull latest changes
echo [0/7] Pulling latest changes...
cd /d "%PROJECT_ROOT%"

if exist ".git" (
    REM Backup .env files before git operations (protect user configuration)
    set "ENV_BACKUP_CREATED=false"
    if exist "deployment\.env" (
        copy "deployment\.env" "deployment\.env.backup" >nul 2>&1
        if not errorlevel 1 set "ENV_BACKUP_CREATED=true"
    )
    if exist "backend\.env" (
        copy "backend\.env" "backend\.env.backup" >nul 2>&1
        if not errorlevel 1 set "ENV_BACKUP_CREATED=true"
    )
    
    REM Check for uncommitted changes
    git diff-index --quiet HEAD 2>nul
    if errorlevel 1 (
        echo   Warning: Uncommitted changes detected
        echo   Stashing changes...
        for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "DATESTR=%%c%%a%%b"
        for /f "tokens=1-3 delims=:. " %%a in ("%time%") do set "TIMESTR=%%a%%b%%c"
        git stash push -m "Auto-stash before install !DATESTR!_!TIMESTR!" >nul 2>&1
        echo   Done: Changes stashed ^(recover with: git stash pop^)
    )

    REM Pull latest changes (try normal pull first, then with --allow-unrelated-histories if needed)
    echo   Pulling latest code...
    set "GIT_PULL_SUCCESS=0"
    git pull origin main >nul 2>&1
    if not errorlevel 1 (
        echo   Done: Code updated
        set "GIT_PULL_SUCCESS=1"
    )
    if "!GIT_PULL_SUCCESS!"=="0" (
        git pull origin main --allow-unrelated-histories --no-edit >nul 2>&1
        if not errorlevel 1 (
            echo   Done: Code updated (merged unrelated histories)
            set "GIT_PULL_SUCCESS=1"
        )
    )
    if "!GIT_PULL_SUCCESS!"=="0" (
        echo   Warning: Git pull failed (this is OK - continuing with current version)
        echo            If you cloned from the public repo, this is expected.
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
) else (
    echo   Not a git repository, skipping git pull
)
echo.

REM Change to deployment directory
cd /d "%DEPLOYMENT_DIR%"

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed or not accessible.
    echo.
    echo Please install Docker Desktop for Windows first:
    echo   https://docs.docker.com/desktop/install/windows-install/
    echo.
    exit /b 1
)
echo Done: Docker is installed

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is installed but not running.
    echo.
    echo Please start Docker Desktop and try again.
    echo.
    exit /b 1
)

REM Check if docker compose is available
docker compose version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker Compose is not available.
    echo.
    echo Modern Docker includes Compose as a plugin by default.
    echo Please ensure you have Docker Compose installed.
    echo.
    exit /b 1
)
echo Done: Docker Compose is available
echo.

REM Step 1: Check and create .env file
echo [1/6] Checking environment configuration...
if not exist ".env" (
    if exist ".env.example" (
        echo   Creating .env from .env.example...
        copy ".env.example" ".env" >nul
        echo   Done: Created .env file
    ) else (
        echo Error: .env.example not found. Cannot create .env file.
        exit /b 1
    )
) else (
    echo   Done: .env file exists
)

REM Prompt for port
echo.
echo Configuration Setup:
echo.
set /p "USER_PORT=  Port to use (press Enter for default 7778): "
if "%USER_PORT%"=="" set "USER_PORT=7778"
set "PORT=%USER_PORT%"

REM Update port in .env using PowerShell
powershell -Command "(Get-Content .env) -replace '^PORT=.*', 'PORT=%PORT%' | Set-Content .env.tmp" && move /y .env.tmp .env >nul
powershell -Command "(Get-Content .env) -replace '^BACKEND_PORT=.*', 'BACKEND_PORT=%PORT%' | Set-Content .env.tmp" && move /y .env.tmp .env >nul
echo   Done: Port set to %PORT%

REM Step 2: Generate database password and secrets
echo.
echo [2/6] Generating secure credentials...

REM Generate password (LinkedinGW + timestamp + random)
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "D=%%c%%a%%b"
for /f "tokens=1-3 delims=:. " %%a in ("%time%") do set "T=%%a%%b%%c"
set "NEW_PASSWORD=LinkedinGW%D%%T%%RANDOM%"

REM Check if DB_PASSWORD needs to be generated
for /f "tokens=2 delims==" %%a in ('findstr /b "DB_PASSWORD=" .env 2^>nul') do set "DB_PASSWORD=%%a"
set "NEED_PASSWORD="
if "%DB_PASSWORD%"=="" set "NEED_PASSWORD=1"
if "%DB_PASSWORD%"=="CHANGE_THIS_TO_A_RANDOM_SECRET_KEY" set "NEED_PASSWORD=1"
if "%DB_PASSWORD%"=="change_this_password" set "NEED_PASSWORD=1"
if "%DB_PASSWORD%"=="your_strong_password_here" set "NEED_PASSWORD=1"
if "%DB_PASSWORD%"=="postgres" set "NEED_PASSWORD=1"

if defined NEED_PASSWORD (
    set "DB_PASSWORD=!NEW_PASSWORD!"
    echo   Generating new DB password
    powershell -Command "(Get-Content .env) -replace '^DB_PASSWORD=.*', 'DB_PASSWORD=!DB_PASSWORD!' | Set-Content .env.tmp" && move /y .env.tmp .env >nul
    echo   Done: DB_PASSWORD saved to .env
) else (
    echo   Done: DB_PASSWORD already set
)

REM Generate SECRET_KEY if needed
for /f "tokens=2 delims==" %%a in ('findstr /b "SECRET_KEY=" .env 2^>nul') do set "SECRET_KEY_VALUE=%%a"
set "NEED_SECRET="
if "%SECRET_KEY_VALUE%"=="" set "NEED_SECRET=1"
if "%SECRET_KEY_VALUE%"=="CHANGE_THIS_TO_A_RANDOM_SECRET_KEY" set "NEED_SECRET=1"

if defined NEED_SECRET (
    for /f %%i in ('powershell -Command "[System.Convert]::ToBase64String((1..32 | ForEach-Object {Get-Random -Maximum 256}))"') do set "SECRET_KEY=%%i"
    powershell -Command "(Get-Content .env) -replace '^SECRET_KEY=.*', 'SECRET_KEY=!SECRET_KEY!' | Set-Content .env.tmp" && move /y .env.tmp .env >nul
    echo   Done: Generated SECRET_KEY
) else (
    echo   Done: SECRET_KEY already set
)

REM Generate JWT_SECRET_KEY if needed
for /f "tokens=2 delims==" %%a in ('findstr /b "JWT_SECRET_KEY=" .env 2^>nul') do set "JWT_SECRET_VALUE=%%a"
set "NEED_JWT="
if "%JWT_SECRET_VALUE%"=="" set "NEED_JWT=1"
if "%JWT_SECRET_VALUE%"=="CHANGE_THIS_TO_A_RANDOM_SECRET_KEY" set "NEED_JWT=1"

if defined NEED_JWT (
    for /f %%i in ('powershell -Command "[System.Convert]::ToBase64String((1..32 | ForEach-Object {Get-Random -Maximum 256}))"') do set "JWT_SECRET_KEY=%%i"
    powershell -Command "(Get-Content .env) -replace '^JWT_SECRET_KEY=.*', 'JWT_SECRET_KEY=!JWT_SECRET_KEY!' | Set-Content .env.tmp" && move /y .env.tmp .env >nul
    echo   Done: Generated JWT_SECRET_KEY
) else (
    echo   Done: JWT_SECRET_KEY already set
)

REM Set edition
powershell -Command "(Get-Content .env) -replace '^LG_BACKEND_EDITION=.*', 'LG_BACKEND_EDITION=%EDITION%' | Set-Content .env.tmp" && move /y .env.tmp .env >nul
echo   Done: Set edition to %EDITION%

REM Set channel
powershell -Command "(Get-Content .env) -replace '^LG_CHANNEL=.*', 'LG_CHANNEL=default' | Set-Content .env.tmp" && move /y .env.tmp .env >nul
echo   Done: Set channel to default

REM Copy .env to backend
echo.
echo [3/7] Copying configuration to backend...
copy .env "..\backend\.env" >nul
echo   Done: Configuration copied to backend/.env

REM Step 4: Deploy with Docker Compose
echo.
echo [4/7] Starting Docker Compose deployment...
echo   Building and starting containers...
%DOCKER_COMPOSE_CMD% up -d --build

if errorlevel 1 (
    echo Error: Docker Compose deployment failed.
    exit /b 1
)
echo   Done: Containers started

REM Step 5: Verify database initialization
echo.
echo [5/7] Verifying database initialization...
echo   Waiting for PostgreSQL to be ready...

REM Wait up to 30 seconds for database
set /a "COUNT=0"
:WAIT_DB
docker exec %DB_CONTAINER% pg_isready -U linkedin_gateway_user -d LinkedinGateway >nul 2>&1
if not errorlevel 1 goto DB_READY
set /a "COUNT+=1"
if %COUNT% geq 30 goto DB_TIMEOUT
timeout /t 1 /nobreak >nul
goto WAIT_DB

:DB_TIMEOUT
echo   Warning: Database did not respond within 30 seconds
goto CHECK_TABLES

:DB_READY
echo   Done: Database is ready
echo   Waiting for init scripts to complete...
timeout /t 3 /nobreak >nul

:CHECK_TABLES
echo.
echo   Checking if database schema was created...
for /f "delims=" %%i in ('docker exec %DB_CONTAINER% psql -U linkedin_gateway_user -d LinkedinGateway -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2^>^&1') do set "TABLES_COUNT=%%i"
set "TABLES_COUNT=!TABLES_COUNT: =!"
if "!TABLES_COUNT!"=="" (
    echo   Warning: Could not query database, will retry...
    timeout /t 2 /nobreak >nul
    for /f "delims=" %%i in ('docker exec %DB_CONTAINER% psql -U linkedin_gateway_user -d LinkedinGateway -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2^>^&1') do set "TABLES_COUNT=%%i"
    set "TABLES_COUNT=!TABLES_COUNT: =!"
)

REM Check if alembic_version exists
for /f %%i in ('docker exec %DB_CONTAINER% psql -U linkedin_gateway_user -d LinkedinGateway -t -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'alembic_version');" 2^>nul') do set "ALEMBIC_EXISTS=%%i"
set "ALEMBIC_EXISTS=!ALEMBIC_EXISTS: =!"

set "IS_FRESH_INSTALL=false"
if "!TABLES_COUNT!"=="" (
    echo   Warning: Could not determine table count
    set "TABLES_COUNT=0"
)

REM Check if we have tables - if count is 0, try to run init scripts
if "!TABLES_COUNT!"=="0" (
    echo   Warning: No tables found, init scripts may not have run automatically.
    echo   Running init scripts manually...
    set "IS_FRESH_INSTALL=true"

    REM Manually run init scripts
    for %%F in ("..\init-scripts\*.sql") do (
        echo     Executing: %%~nxF
        docker cp "%%F" "%DB_CONTAINER%:/tmp/%%~nxF"
        docker exec %DB_CONTAINER% psql -U linkedin_gateway_user -d LinkedinGateway -f "/tmp/%%~nxF"
        if errorlevel 1 (
            echo     Warning: Script may have failed or tables already exist
        )
        docker exec %DB_CONTAINER% rm "/tmp/%%~nxF"
    )

    REM Verify tables were created after running init scripts
    echo   Verifying schema...
    for /f "delims=" %%i in ('docker exec %DB_CONTAINER% psql -U linkedin_gateway_user -d LinkedinGateway -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2^>^&1') do set "TABLES_COUNT=%%i"
    set "TABLES_COUNT=!TABLES_COUNT: =!"

    REM Check if tables were created successfully
    if "!TABLES_COUNT!"=="" set "TABLES_COUNT=0"
    if "!TABLES_COUNT!"=="0" (
        echo   Error: Failed to create database schema!
        echo   Debug: TABLES_COUNT = "!TABLES_COUNT!"
        echo   Please check Docker logs for more details.
        exit /b 1
    ) else (
        echo   Done: Database schema created successfully (!TABLES_COUNT! tables)
    )
) else (
    REM Tables already exist - this is success!
    echo   Done: Database schema exists (!TABLES_COUNT! tables)
    if not "!ALEMBIC_EXISTS!"=="t" (
        set "IS_FRESH_INSTALL=true"
        echo   Detected fresh installation (no migration history)
    )
)

REM Apply migrations or stamp version
echo.
if "%IS_FRESH_INSTALL%"=="true" (
    echo Marking database as up-to-date (alembic stamp head)...
    %DOCKER_COMPOSE_CMD% exec -T backend sh -c "cd /app && alembic stamp head"
    if errorlevel 1 (
        echo   Error: Failed to stamp alembic version
        echo   Check backend logs: %DOCKER_COMPOSE_CMD% logs backend
        exit /b 1
    )
    echo   Done: Database marked as up-to-date
) else (
    echo Applying database migrations (alembic upgrade head)...
    
    REM Check for merge conflicts before running migrations
    %DOCKER_COMPOSE_CMD% exec -T backend sh -c "cd /app && grep -r '^<<<<<<< ' alembic/ 2>/dev/null | head -1" >nul 2>&1
    if not errorlevel 1 (
        echo   Error: Merge conflicts detected in migration files!
        echo   Please resolve conflicts before continuing.
        echo   Check: %DOCKER_COMPOSE_CMD% exec backend sh -c "grep -r '^<<<<<<< ' /app/alembic/"
        exit /b 1
    )
    
    REM Run migrations with error handling
    %DOCKER_COMPOSE_CMD% exec -T backend sh -c "cd /app && alembic upgrade head 2>&1" > "%TEMP%\migration_output.txt" 2>&1
    if errorlevel 1 (
        REM Check for syntax errors (merge conflicts)
        findstr /C:"SyntaxError" /C:"invalid decimal literal" /C:"conflict" "%TEMP%\migration_output.txt" >nul 2>&1
        if not errorlevel 1 (
            echo   Error: Syntax error in migration files ^(likely merge conflicts^)
            echo   Please resolve conflicts in backend/alembic/ files
            echo   Error details:
            findstr /C:"SyntaxError" /C:"File" /C:"line" "%TEMP%\migration_output.txt"
            del "%TEMP%\migration_output.txt" >nul 2>&1
            exit /b 1
        ) else (
            echo   Error: Failed to run alembic migrations
            echo   Error output:
            type "%TEMP%\migration_output.txt" | findstr /V "INFO" | findstr /V "WARNING" | findstr /V "level="
            echo   Check backend logs: %DOCKER_COMPOSE_CMD% logs backend
            del "%TEMP%\migration_output.txt" >nul 2>&1
            exit /b 1
        )
    )
    echo   Done: Database migrations applied
    del "%TEMP%\migration_output.txt" >nul 2>&1
)

echo.
echo   To verify database: .\scripts\verify-db.bat
echo.

REM Step 6: Wait for backend health
echo [6/7] Waiting for backend API to be ready...

REM Get backend port
for /f "tokens=2 delims==" %%a in ('findstr /b "BACKEND_PORT=" .env 2^>nul') do set "BACKEND_PORT=%%a"
if not defined BACKEND_PORT set "BACKEND_PORT=7778"

set "HEALTH_URL=http://localhost:%BACKEND_PORT%/health"
set /a "ATTEMPT=0"
set "READY=false"

:WAIT_HEALTH
curl -s -f "%HEALTH_URL%" >nul 2>&1
if not errorlevel 1 (
    set "READY=true"
    goto HEALTH_READY
)
set /a "ATTEMPT+=1"
if %ATTEMPT% geq 30 goto HEALTH_TIMEOUT
timeout /t 2 /nobreak >nul
goto WAIT_HEALTH

:HEALTH_TIMEOUT
echo.
echo   Warning: Backend did not respond within timeout
echo   Check logs: %DOCKER_COMPOSE_CMD% logs backend
goto FINISH

:HEALTH_READY
echo.
echo   Done: Backend is healthy and ready!

:FINISH
REM Step 7: Success message
echo.
echo [7/7] Configuration Instructions
echo.
echo ======================================
echo Done: Installation Complete!
echo ======================================
echo.
echo IMPORTANT: LinkedIn OAuth Setup Required
echo.
echo To enable LinkedIn OAuth, you need to:
echo   1. Get credentials from: https://www.linkedin.com/developers/apps
echo   2. Edit %DEPLOYMENT_DIR%\.env
echo   3. Set: LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, PUBLIC_URL
echo   4. Restart: %DOCKER_COMPOSE_CMD% restart
echo.
echo LinkedIn Gateway is running:
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
