@echo off
REM LinkedIn Gateway - Core Edition Update Script
REM Convenience wrapper for: update_v2.bat core

REM Get the directory of this script
set "SCRIPT_DIR=%~dp0"

REM Call update_v2.bat with 'core' parameter
call "%SCRIPT_DIR%update_v2.bat" core %*
