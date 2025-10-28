@echo off
REM LinkedIn Gateway - Unified Deployment Script (Windows)
REM This script deploys either core or saas edition using Docker Compose
REM Usage: install.bat [core|saas]

setlocal enabledelayedexpansion

REM Get edition from parameter (default to core)
set "EDITION=%~1"
if "%EDITION%"=="" set "EDITION=core"

REM Validate edition
if /i not "%EDITION%"=="core" if /i not "%EDITION%"=="saas" (
    echo [ERROR] Invalid edition '%EDITION%'. Must be 'core' or 'saas'.
    echo Usage: %0 [core^|saas]
    exit /b 1
)

REM Script directory and deployment root
set "SCRIPT_DIR=%~dp0"
set "DEPLOYMENT_DIR=%SCRIPT_DIR%.."
set "PROJECT_ROOT=%DEPLOYMENT_DIR%\.."

REM Set edition-specific variables
if /i "%EDITION%"=="saas" (
    set "EDITION_TITLE=SaaS Edition"
    set "DOCKER_COMPOSE_CMD=docker compose -f docker-compose.yml -f docker-compose.saas.yml"
) else (
    set "EDITION_TITLE=Open Core Edition"
    set "DOCKER_COMPOSE_CMD=docker compose -f docker-compose.yml"
)

echo ======================================
echo LinkedIn Gateway - %EDITION_TITLE%
echo ======================================
echo.

REM Change to deployment directory
cd /d "%DEPLOYMENT_DIR%"

REM Check if Docker is installed and working
docker --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Docker is not installed or not accessible on this system.
    echo.
    echo To install Docker Desktop for Windows:
    echo   1. Download from: https://www.docker.com/products/docker-desktop
    echo   2. Run the installer
    echo   3. Restart your computer
    echo   4. Start Docker Desktop
    echo   5. Run this script again
    echo.
    pause
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('docker --version') do set DOCKER_VERSION=%%i
    echo [OK] Docker is installed: !DOCKER_VERSION!
)

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [WARN] Docker is installed but not running.
    echo.
    echo Please start Docker Desktop and try again.
    echo You can start Docker Desktop from the Start menu.
    echo.
    pause
    exit /b 1
)

REM Check if docker compose is available
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose plugin is not available.
    echo.
    echo Docker Desktop includes Docker Compose by default.
    echo Please ensure you have the latest version of Docker Desktop installed.
    echo.
    pause
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('docker compose version --short 2^>nul') do set COMPOSE_VERSION=%%i
    if "!COMPOSE_VERSION!"=="" (
        echo [OK] Docker Compose is available
    ) else (
        echo [OK] Docker Compose is available: !COMPOSE_VERSION!
    )
)

echo.

REM Step 1: Check and create .env file
echo [1/6] Checking environment configuration...
if not exist ".env" (
    if exist ".env.example" (
        echo   -^> Creating .env from .env.example...
        copy .env.example .env >nul
        echo   [OK] Created .env file
    ) else (
        echo [ERROR] .env.example not found. Cannot create .env file.
        exit /b 1
    )
) else (
    echo   [OK] .env file exists
)

REM Prompt for port
echo.
echo Configuration Setup:
echo.
set /p "USER_PORT=  Port to use (press Enter for default 7778): "
if "!USER_PORT!"=="" set "USER_PORT=7778"

REM Update port in .env (be specific to avoid matching DB_PORT)
findstr /r "^PORT=" .env >nul 2>&1
if not errorlevel 1 (
    powershell -Command "(Get-Content .env) | ForEach-Object { if ($_ -match '^PORT=') { 'PORT=%USER_PORT%' } else { $_ } } | Set-Content .env.tmp; Move-Item -Force .env.tmp .env"
) else (
    echo PORT=!USER_PORT!>> .env
)

findstr /r "^BACKEND_PORT=" .env >nul 2>&1
if not errorlevel 1 (
    powershell -Command "(Get-Content .env) | ForEach-Object { if ($_ -match '^BACKEND_PORT=') { 'BACKEND_PORT=%USER_PORT%' } else { $_ } } | Set-Content .env.tmp; Move-Item -Force .env.tmp .env"
) else (
    echo BACKEND_PORT=!USER_PORT!>> .env
)

echo   [OK] Port set to !USER_PORT!

REM Step 2: Generate database password and secrets
echo.
echo [2/6] Generating secure credentials...

REM Function to generate a random secret using PowerShell (hex string)
set "generate_secret=powershell -NoProfile -ExecutionPolicy Bypass -Command "$bytes = New-Object byte[] 32; (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($bytes); -join ($bytes ^| ForEach-Object { '{0:x2}' -f $_ })""

REM Function to generate a simple password: LinkedinGW + timestamp + random
REM This creates passwords like: LinkedinGW20251018143052
REM Remove all special characters (/, :, spaces) from date/time
set "TIMESTAMP=%date:~-4%%date:~4,2%%date:~7,2%%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP:/=%"
set "TIMESTAMP=%TIMESTAMP::=%"
set "TIMESTAMP=%TIMESTAMP: =0%"

REM Check if DB_PASSWORD is set and not empty or is a placeholder
findstr /r "^DB_PASSWORD=..*" .env >nul 2>&1
if errorlevel 1 goto gen_db_pass
findstr /r "^DB_PASSWORD=CHANGE" .env >nul 2>&1
if not errorlevel 1 goto gen_db_pass
findstr /r "^DB_PASSWORD=+$" .env >nul 2>&1
if not errorlevel 1 goto gen_db_pass
goto skip_db_pass

:gen_db_pass
set "DB_PASSWORD=LinkedinGW%TIMESTAMP%%RANDOM%"
echo   -^> Generated DB password: LinkedinGW%TIMESTAMP%****
findstr /r "^DB_PASSWORD=" .env >nul 2>&1
if not errorlevel 1 (
    powershell -Command "(Get-Content .env) -replace '^DB_PASSWORD=.*', 'DB_PASSWORD=%DB_PASSWORD%' | Set-Content .env.tmp; Move-Item -Force .env.tmp .env"
) else (
    echo DB_PASSWORD=%DB_PASSWORD%>> .env
)
echo   [OK] DB_PASSWORD saved to .env
goto after_db_pass

:skip_db_pass
echo   [OK] DB_PASSWORD already set

:after_db_pass

REM Check if SECRET_KEY is set and not empty
findstr /r "^SECRET_KEY=..*" .env >nul 2>&1
if errorlevel 1 (
    for /f "delims=" %%i in ('%generate_secret%') do set "SECRET_KEY=%%i"
    findstr /r "^SECRET_KEY=" .env >nul 2>&1
    if not errorlevel 1 (
        REM Replace existing empty SECRET_KEY
        powershell -Command "(Get-Content .env) -replace '^SECRET_KEY=.*', 'SECRET_KEY=%SECRET_KEY%' | Set-Content .env.tmp; Move-Item -Force .env.tmp .env"
    ) else (
        REM Append if not exists
        echo SECRET_KEY=!SECRET_KEY!>> .env
    )
    echo   [OK] Generated SECRET_KEY
) else (
    echo   [OK] SECRET_KEY already set
)

REM Check if JWT_SECRET_KEY is set and not empty
findstr /r "^JWT_SECRET_KEY=..*" .env >nul 2>&1
if errorlevel 1 (
    for /f "delims=" %%i in ('%generate_secret%') do set "JWT_SECRET_KEY=%%i"
    findstr /r "^JWT_SECRET_KEY=" .env >nul 2>&1
    if not errorlevel 1 (
        powershell -Command "(Get-Content .env) -replace '^JWT_SECRET_KEY=.*', 'JWT_SECRET_KEY=%JWT_SECRET_KEY%' | Set-Content .env.tmp; Move-Item -Force .env.tmp .env"
    ) else (
        echo JWT_SECRET_KEY=!JWT_SECRET_KEY!>> .env
    )
    echo   [OK] Generated JWT_SECRET_KEY
) else (
    echo   [OK] JWT_SECRET_KEY already set
)

REM Ensure edition is set correctly
findstr /r "^LG_BACKEND_EDITION=%EDITION%" .env >nul 2>&1
if errorlevel 1 (
    findstr /r "^LG_BACKEND_EDITION=" .env >nul 2>&1
    if not errorlevel 1 (
        powershell -Command "(Get-Content .env) -replace '^LG_BACKEND_EDITION=.*', 'LG_BACKEND_EDITION=%EDITION%' | Set-Content .env.tmp; Move-Item -Force .env.tmp .env"
    ) else (
        echo LG_BACKEND_EDITION=%EDITION%>> .env
    )
    echo   [OK] Set edition to %EDITION%
)

REM Ensure channel is set to default
findstr /r "^LG_CHANNEL=default" .env >nul 2>&1
if errorlevel 1 (
    findstr /r "^LG_CHANNEL=" .env >nul 2>&1
    if not errorlevel 1 (
        powershell -Command "(Get-Content .env) -replace '^LG_CHANNEL=.*', 'LG_CHANNEL=default' | Set-Content .env.tmp; Move-Item -Force .env.tmp .env"
    ) else (
        echo LG_CHANNEL=default>> .env
    )
    echo   [OK] Set channel to default
)

REM Copy .env to backend directory (app reads from there)
echo.
echo [3/7] Copying configuration to backend...
copy .env ..\backend\.env >nul
echo   [OK] Configuration copied to backend\.env

REM Step 4: Deploy with Docker Compose
echo.
echo [4/7] Starting Docker Compose deployment...
echo   -^> Building and starting containers...
%DOCKER_COMPOSE_CMD% up -d --build

if errorlevel 1 (
    echo [ERROR] Docker Compose deployment failed.
    exit /b 1
)
echo   [OK] Containers started

REM Step 5: Check database initialization
echo.
echo [5/7] Checking database initialization...
echo   -^> PostgreSQL will automatically:
echo      * Create user and database
echo      * Run init scripts from: deployment\init-scripts\
echo      * Set up all tables, indexes, and initial data
echo.
echo   [INFO] To view database logs:
echo          %DOCKER_COMPOSE_CMD% logs postgres
echo.

REM Step 6: Wait for services and poll health endpoint
echo.
echo [6/7] Waiting for backend API to be ready...

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
    echo   Check logs: %DOCKER_COMPOSE_CMD% logs backend
)

REM Step 7: Print success message and next steps
echo [7/7] Configuration Instructions
echo.
echo ======================================
echo [OK] Installation Complete!
echo ======================================
echo.
echo [WARNING] IMPORTANT: LinkedIn OAuth Setup Required
echo.
echo To enable LinkedIn OAuth, you need to:
echo   1. Get LinkedIn OAuth credentials from: https://www.linkedin.com/developers/apps
echo   2. Edit %DEPLOYMENT_DIR%\.env
echo   3. Set your LinkedIn OAuth credentials:
echo      LINKEDIN_CLIENT_ID=your_client_id_here
echo      LINKEDIN_CLIENT_SECRET=your_client_secret_here
echo      PUBLIC_URL=https://your-domain-or-tunnel.com
echo   4. Restart services: %DOCKER_COMPOSE_CMD% restart
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
echo   Update:         %SCRIPT_DIR%\update-%EDITION%.bat
echo.

endlocal

