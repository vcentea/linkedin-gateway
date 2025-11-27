@echo off
REM LinkedIn Gateway - Local Database Upgrade Script
REM Runs Alembic migrations and ensures schema is correct

echo ========================================
echo LinkedIn Gateway - Database Upgrade
echo ========================================
echo.

REM Activate virtual environment
echo Activating virtual environment...
call E:\ENVs\LinkedinGateway\Scripts\activate.bat

REM Go to backend directory
cd /d %~dp0..\backend

REM Run Alembic migrations
echo.
echo [1/2] Running Alembic migrations...
alembic upgrade head
if errorlevel 1 (
    echo ERROR: Alembic migration failed!
    pause
    exit /b 1
)

REM Run schema enforcement
echo.
echo [2/2] Ensuring schema is correct...
python alembic/ensure_schema.py
if errorlevel 1 (
    echo ERROR: Schema enforcement failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Database upgrade completed successfully!
echo ========================================
echo.
pause

