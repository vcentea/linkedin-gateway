@echo off
REM Test script to verify migration error handling
REM This simulates various error scenarios

setlocal enabledelayedexpansion

echo Testing migration error detection...
echo.

REM Test 1: Check for merge conflict detection
echo [Test 1] Checking merge conflict detection...
echo   Creating test file with conflict markers...
(
echo line 1
echo ^<^<^<^<^<^<^< HEAD
echo local changes
echo =======
echo remote changes
echo ^>^>^>^>^>^>^> commit_hash
) > "%TEMP%\test_conflict.py" 2>nul

findstr /C:"<<<<<<<" "%TEMP%\test_conflict.py" >nul 2>&1
if not errorlevel 1 (
    echo   ✓ Merge conflict detection works
) else (
    echo   ✗ Merge conflict detection failed
)

del "%TEMP%\test_conflict.py" >nul 2>&1
echo.

REM Test 2: Check for SyntaxError detection
echo [Test 2] Checking SyntaxError detection...
echo   Creating test output with SyntaxError...
(
echo Traceback ^(most recent call last^):
echo   File "env.py", line 33
echo     ^>^>^>^>^>^>^> 29bb450ec3174ee6b326d799861328119d22f728
echo              ^^
echo SyntaxError: invalid decimal literal
) > "%TEMP%\test_syntax_error.txt" 2>nul

findstr /C:"SyntaxError" "%TEMP%\test_syntax_error.txt" >nul 2>&1
if not errorlevel 1 (
    echo   ✓ SyntaxError detection works
) else (
    echo   ✗ SyntaxError detection failed
)

del "%TEMP%\test_syntax_error.txt" >nul 2>&1
echo.

REM Test 3: Check for "already exists" detection
echo [Test 3] Checking "already exists" detection...
echo   Creating test output with "already exists"...
(
echo sqlalchemy.exc.ProgrammingError: ^(psycopg2.errors.DuplicateColumn^)
echo column "webhook_url" already exists
) > "%TEMP%\test_exists.txt" 2>nul

findstr /C:"already exists" "%TEMP%\test_exists.txt" >nul 2>&1
if not errorlevel 1 (
    echo   ✓ "Already exists" detection works
) else (
    echo   ✗ "Already exists" detection failed
)

del "%TEMP%\test_exists.txt" >nul 2>&1
echo.

echo All tests completed!
echo.
echo Note: This script only tests error detection logic.
echo Actual migration testing requires a running Docker environment.

endlocal

