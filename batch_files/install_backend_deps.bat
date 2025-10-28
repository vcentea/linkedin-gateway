@echo off
echo Installing LinkedIn Gateway Backend Dependencies
echo.

echo Activating virtual environment...
call E:\ENVs\LinkedinGateway\Scripts\activate.bat

cd %~dp0..\backend
echo Installing dependencies...
pip install -r requirements/base.txt
pip install pydantic-settings
pip install authlib

echo.
echo Backend dependencies installed successfully.
echo. 