@echo off
echo Starting LinkedIn Gateway Backend
echo.

echo Activating virtual environment...
call E:\ENVs\LinkedinGateway\Scripts\activate.bat

echo.
echo Installing/Updating dependencies...
cd %~dp0.. 
REM Go to project root where requirements.txt is
pip install -r requirements.txt
cd %~dp0..\backend 
REM Go back to backend dir

echo.
echo Starting FastAPI server on port 7778...
python main.py

echo.
echo Backend server stopped. 