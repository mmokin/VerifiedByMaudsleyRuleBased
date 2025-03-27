@echo off
REM Unified test script for looper.apk with minicap disabled
REM This uses both direct DroidBot execution and the assessment framework

echo ===================================================
echo Verified by Maudsley - Testing with minicap disabled
echo ===================================================

if "%~1"=="" (
    set APK_PATH=C:\Projects\looper.apk
) else (
    set APK_PATH=%~1
)

echo Testing APK: %APK_PATH%

REM Test 1: Direct DroidBot execution with minicap disabled
echo.
echo [Test 1] Direct DroidBot execution with minicap disabled
echo Output directory: droidbot_test_output
mkdir droidbot_test_output 2>nul

echo Running DroidBot directly...
python -m droidbot.start -a "%APK_PATH%" -o droidbot_test_output -is_emulator -keep_app -timeout 120 -count 50 -interval 1 -policy dfs

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Direct DroidBot test failed. See log for details.
    goto test2
)

echo [SUCCESS] Direct DroidBot test completed successfully.

:test2
REM Test 2: Full assessment framework with minicap disabled
echo.
echo [Test 2] Running full assessment with minicap disabled
echo Output directory: assessment_test_output

REM Run the assessment with our config file (minicap disabled)
python "%~dp0run_assessment.py" "%APK_PATH%" assessment_test_output -c "%~dp0config.json"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Assessment test failed. See assessment_test_output\error.log for details.
) else (
    echo [SUCCESS] Assessment completed successfully.
    echo Report available at: assessment_test_output\maudsley_report.html
)

echo.
echo Testing completed. Results available in:
echo - droidbot_test_output (direct DroidBot test)
echo - assessment_test_output (full assessment test)
echo.

pause
