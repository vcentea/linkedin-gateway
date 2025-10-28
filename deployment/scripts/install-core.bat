@echo off
REM LinkedIn Gateway - Open Core Edition Installer
REM This is a convenience wrapper for: install.bat core

set "SCRIPT_DIR=%~dp0"

REM Call the main install script with 'core' parameter
call "%SCRIPT_DIR%install.bat" core
