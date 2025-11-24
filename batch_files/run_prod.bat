@echo off
echo Building LinkedIn Gateway for Production
echo.

cd %~dp0..\frontend
echo Installing dependencies...
call npm install

echo.
echo Building production version...
call npm run build

echo.
echo Production build completed. Files are in frontend/build directory.
echo. 