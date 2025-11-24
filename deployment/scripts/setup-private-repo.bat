@echo off
REM LinkedIn Gateway - Private Repository Setup Script (Windows)
REM 
REM This script helps you set up access to the private repository for Enterprise/SaaS editions.
REM It will:
REM 1. Check if you're using the public or private repository
REM 2. Switch to the private repository if needed
REM 3. Test authentication
REM
REM Authentication methods supported:
REM - GitHub Personal Access Token (PAT)
REM - SSH Key (if already configured)

setlocal enabledelayedexpansion

REM Repository URLs
set "PUBLIC_REPO=https://github.com/vcentea/linkedin-gateway.git"
set "PRIVATE_REPO_HTTPS=https://github.com/vcentea/linkedin-gateway-saas.git"
set "PRIVATE_REPO_SSH=git@github.com:vcentea/linkedin-gateway-saas.git"

echo ========================================
echo LinkedIn Gateway - Private Repo Setup
echo ========================================
echo.

REM Get script directory and project root
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\"
cd /d "%PROJECT_ROOT%"

echo Project location: %CD%
echo.

REM Check if we're in a git repository
if not exist ".git" (
    echo [ERROR] Not a git repository!
    echo.
    echo This directory was not cloned from git.
    echo Please clone the private repository instead:
    echo.
    echo   git clone %PRIVATE_REPO_HTTPS%
    echo.
    exit /b 1
)

REM Check current remote
for /f "delims=" %%i in ('git remote get-url origin 2^>nul') do set "CURRENT_ORIGIN=%%i"

echo [1/4] Checking current repository...
echo   Current origin: %CURRENT_ORIGIN%
echo.

REM Determine if using public or private repo
echo %CURRENT_ORIGIN% | findstr /C:"linkedin-gateway.git" >nul
if %errorlevel%==0 (
    echo %CURRENT_ORIGIN% | findstr /C:"linkedin-gateway-saas" >nul
    if !errorlevel!==1 (
        set "IS_PUBLIC=true"
    ) else (
        set "IS_PUBLIC=false"
    )
) else (
    set "IS_PUBLIC=false"
)

if "%IS_PUBLIC%"=="true" (
    echo [WARNING] You are using the PUBLIC repository!
    echo.
    echo The public repository only contains the Core edition.
    echo For Enterprise/SaaS editions, you need the PRIVATE repository.
    echo.
    set /p "SWITCH_REPO=Do you want to switch to the private repository? (Y/N): "
    
    if /i not "!SWITCH_REPO!"=="Y" (
        echo Setup cancelled.
        exit /b 0
    )
    
    set "NEEDS_SWITCH=true"
) else (
    echo %CURRENT_ORIGIN% | findstr /C:"linkedin-gateway-saas" >nul
    if !errorlevel!==0 (
        echo [OK] Already using the private repository!
        echo.
        echo Testing authentication...
        set "NEEDS_SWITCH=false"
    ) else (
        echo [WARNING] Unknown repository URL: %CURRENT_ORIGIN%
        echo.
        echo Expected one of:
        echo   - %PUBLIC_REPO% (public^)
        echo   - %PRIVATE_REPO_HTTPS% (private, HTTPS^)
        echo   - %PRIVATE_REPO_SSH% (private, SSH^)
        echo.
        exit /b 1
    )
)

REM If we need to switch
if "%NEEDS_SWITCH%"=="true" (
    echo.
    echo [2/4] Choose authentication method:
    echo.
    echo 1^) GitHub Personal Access Token (PAT^) - Recommended
    echo 2^) SSH Key (if already configured^)
    echo 3^) Cancel
    echo.
    set /p "AUTH_METHOD=Enter choice (1-3): "
    
    if "!AUTH_METHOD!"=="1" (
        echo.
        echo Using Personal Access Token (PAT^)
        echo.
        echo To create a GitHub PAT:
        echo 1. Go to: https://github.com/settings/tokens
        echo 2. Click 'Generate new token' -^> 'Generate new token (classic^)'
        echo 3. Give it a name (e.g., 'LinkedIn Gateway'^)
        echo 4. Select scopes: repo (full control^)
        echo 5. Click 'Generate token'
        echo 6. Copy the token (you won't see it again!^)
        echo.
        set /p "GH_USERNAME=Enter your GitHub username: "
        set /p "GH_TOKEN=Enter your Personal Access Token: "
        
        REM Build authenticated URL
        set "NEW_REMOTE=https://!GH_USERNAME!:!GH_TOKEN!@github.com/vcentea/linkedin-gateway-saas.git"
        
        REM Test access
        echo.
        echo [2/4] Testing access to private repository...
        git ls-remote "!NEW_REMOTE!" HEAD >nul 2>&1
        if !errorlevel!==0 (
            echo [OK] Authentication successful!
        ) else (
            echo [ERROR] Authentication failed!
            echo.
            echo Failed to authenticate with the provided credentials.
            echo Please check your username and token and try again.
            exit /b 1
        )
        
    ) else if "!AUTH_METHOD!"=="2" (
        echo.
        echo Using SSH Key
        echo.
        echo Make sure you have:
        echo 1. Generated an SSH key: ssh-keygen -t ed25519 -C "your_email@example.com"
        echo 2. Added it to your GitHub account: https://github.com/settings/keys
        echo 3. Tested it: ssh -T git@github.com
        echo.
        
        REM Test SSH access
        echo [2/4] Testing access to private repository...
        git ls-remote "%PRIVATE_REPO_SSH%" HEAD >nul 2>&1
        if !errorlevel!==0 (
            echo [OK] Authentication successful!
            set "NEW_REMOTE=%PRIVATE_REPO_SSH%"
        ) else (
            echo [ERROR] Authentication failed!
            echo.
            echo Failed to authenticate via SSH.
            echo Please set up your SSH key first and try again.
            exit /b 1
        )
        
    ) else (
        echo Setup cancelled.
        exit /b 0
    )
    
    echo.
    echo [3/4] Switching to private repository...
    
    REM Change the remote URL
    git remote set-url origin "!NEW_REMOTE!"
    if !errorlevel!==0 (
        echo [OK] Remote URL updated
    ) else (
        echo [ERROR] Failed to update remote URL
        exit /b 1
    )
    
    REM Fetch from new remote
    echo   Fetching from private repository...
    git fetch origin main >nul 2>&1
    if !errorlevel!==0 (
        echo [OK] Fetch successful
    ) else (
        echo [ERROR] Fetch failed
        echo Reverting remote URL...
        git remote set-url origin "%CURRENT_ORIGIN%"
        exit /b 1
    )
    
    REM Pull latest changes
    echo   Pulling latest changes...
    git pull origin main --allow-unrelated-histories --no-edit >nul 2>&1
    if !errorlevel!==0 (
        echo [OK] Successfully pulled from private repository
    ) else (
        echo [WARNING] Pull had conflicts or issues
        echo You may need to resolve conflicts manually.
    )
    
) else (
    REM Just test current access
    echo [2/4] Testing access to private repository...
    git ls-remote "%CURRENT_ORIGIN%" HEAD >nul 2>&1
    if !errorlevel!==0 (
        echo [OK] Access to private repository is working!
    ) else (
        echo [ERROR] Cannot access private repository
        echo.
        echo Your remote is configured correctly, but authentication is failing.
        echo Please check your credentials or SSH keys.
        exit /b 1
    )
)

echo.
echo [4/4] Verification...

REM Verify we can see enterprise files
if exist "deployment\docker-compose.enterprise.yml" (
    echo [OK] Enterprise files present
) else (
    echo [ERROR] Enterprise files not found
    echo The private repository should contain enterprise edition files.
)

REM Check current branch and commit
for /f "delims=" %%i in ('git rev-parse --abbrev-ref HEAD') do set "CURRENT_BRANCH=%%i"
for /f "delims=" %%i in ('git rev-parse --short HEAD') do set "CURRENT_COMMIT=%%i"
echo   Current branch: !CURRENT_BRANCH!
echo   Current commit: !CURRENT_COMMIT!

echo.
echo ========================================
echo  Private Repository Setup Complete!
echo ========================================
echo.
echo You can now install Enterprise or SaaS editions:
echo.
echo   cd deployment\scripts
echo   install-enterprise.bat
echo.
echo Or update existing installations:
echo.
echo   update-enterprise.bat
echo.

pause

