@echo off
echo Starting LinkedIn Gateway Extension Development Build Watcher
echo.

cd %~dp0..\frontend

echo.
echo Installing/Updating dependencies (if needed)...
REM call npm install # Uncomment if you want to ensure deps are installed each time

echo.
echo Starting watcher (npm run watch:build)...
echo Press CTRL+C to stop.
echo.

call npm run watch:build

echo Watcher stopped. 