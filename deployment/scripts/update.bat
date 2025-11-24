@echo off
REM LinkedIn Gateway - Update Script
REM This is a wrapper that calls update_v2.bat with your edition

REM Get the directory of this script
set "SCRIPT_DIR=%~dp0"

REM Pass all arguments to update_v2.bat
call "%SCRIPT_DIR%update_v2.bat" %*
