@echo off
REM Update Backend - Pull latest code, rebuild and restart backend service
REM Usage: update-backend.bat [core|saas] [--no-pull] [--branch branch-name]

setlocal enabledelayedexpansion

set EDITION=core
set SKIP_PULL=false
set BRANCH=main

REM Parse arguments
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="core" set EDITION=core & shift & goto parse_args
if /i "%~1"=="saas" set EDITION=saas & shift & goto parse_args
if /i "%~1"=="--no-pull" set SKIP_PULL=true & shift & goto parse_args
if /i "%~1"=="--branch" set BRANCH=%~2 & shift & shift & goto parse_args
shift
goto parse_args
:args_done

echo ========================================
echo LinkedIn Gateway Backend Update
echo Edition: %EDITION%
echo Branch: %BRANCH%
echo ========================================
echo.

cd /d "%~dp0\..\.."

REM Pull latest code from Git
if "%SKIP_PULL%"=="false" (
    echo Pulling latest code from Git ^(%BRANCH%^)...
    git fetch origin
    if errorlevel 1 (
        echo WARNING: Git fetch failed! Continuing with local code...
    ) else (
        REM Check for uncommitted changes
        git diff-index --quiet HEAD
        if errorlevel 1 (
            echo.
            echo WARNING: You have uncommitted changes!
            echo These changes will be included in the build.
            echo.
            choice /C YN /M "Continue with build"
            if errorlevel 2 exit /b 1
        )
        
        REM Pull latest changes
        git pull origin %BRANCH%
        if errorlevel 1 (
            echo ERROR: Git pull failed! Please resolve conflicts manually.
            exit /b 1
        )
        echo Git pull successful!
    )
    echo.
) else (
    echo Skipping git pull (using local code)...
    echo.
)

cd deployment

if "%EDITION%"=="saas" (
    echo Rebuilding SAAS backend...
    docker compose -f docker-compose.yml -f docker-compose.saas.yml build --no-cache backend
    if errorlevel 1 (
        echo ERROR: Build failed!
        exit /b 1
    )
    
    echo Restarting SAAS backend...
    docker compose -f docker-compose.yml -f docker-compose.saas.yml up -d backend
    set "COMPOSE_CMD=docker compose -f docker-compose.yml -f docker-compose.saas.yml"
) else (
    echo Rebuilding CORE backend...
    docker compose build --no-cache backend
    if errorlevel 1 (
        echo ERROR: Build failed!
        exit /b 1
    )
    
    echo Restarting CORE backend...
    docker compose up -d backend
    set "COMPOSE_CMD=docker compose"
)

if errorlevel 1 (
    echo ERROR: Failed to restart backend!
    exit /b 1
)

echo.
echo Applying database migrations...
%COMPOSE_CMD% exec backend alembic upgrade head
if errorlevel 1 (
    echo ERROR: Failed to apply database migrations. Check backend logs.
    exit /b 1
)
echo Database migrations applied successfully.

echo.
echo ========================================
echo Backend updated successfully!
echo ========================================
echo.
echo Checking backend status...
docker compose ps backend

echo.
echo View logs with:
if "%EDITION%"=="saas" (
    echo   docker compose -f docker-compose.yml -f docker-compose.saas.yml logs -f backend
) else (
    echo   docker compose logs -f backend
)

endlocal

