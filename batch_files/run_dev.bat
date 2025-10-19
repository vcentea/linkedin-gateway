@echo off
echo Starting LinkedIn Gateway Development Environment
echo.

cd %~dp0..\frontend
echo Installing dependencies...
call npm install

echo.
echo Starting development server with file watching...
call npm run start

echo.
echo Development server stopped. 