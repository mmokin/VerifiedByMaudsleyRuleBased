@echo off
REM Verified by Maudsley - Mental Health App Assessment Tool
REM This batch file runs the assessment process on a specified APK

echo Verified by Maudsley - Mental Health App UI Assessment
echo -------------------------------------------------

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in the PATH.
    echo Please install Python 3.7 or later and try again.
    exit /b 1
)

REM Check arguments
if "%~1"=="" (
    echo Usage: run_assessment.bat ^<APK_PATH^> ^<OUTPUT_FOLDER^> [CONFIG_JSON]
    echo.
    echo   APK_PATH       - Path to the APK file to assess
    echo   OUTPUT_FOLDER  - Folder to save assessment results
    echo   CONFIG_JSON    - Optional: Path to a custom config.json file
    exit /b 1
)

if "%~2"=="" (
    echo Error: Missing output folder parameter.
    echo Usage: run_assessment.bat ^<APK_PATH^> ^<OUTPUT_FOLDER^> [CONFIG_JSON]
    exit /b 1
)

set APK_PATH=%~1
set OUTPUT_FOLDER=%~2
set CONFIG_PATH=%~dp0config.json

REM Check if APK file exists
if not exist "%APK_PATH%" (
    echo Error: APK file not found at: %APK_PATH%
    exit /b 1
)

REM Use custom config if provided, otherwise use default
if not "%~3"=="" (
    set CONFIG_PATH=%~3
)

REM Verify config file exists
if not exist "%CONFIG_PATH%" (
    echo Error: Config file not found at: %CONFIG_PATH%
    exit /b 1
)

REM Create output directory if it doesn't exist
if not exist "%OUTPUT_FOLDER%" mkdir "%OUTPUT_FOLDER%"

echo Starting assessment with the following parameters:
echo APK Path: %APK_PATH%
echo Output Folder: %OUTPUT_FOLDER%
echo Config File: %CONFIG_PATH%
echo.

REM Run the assessment directly with debug output
echo Running assessment... This may take several minutes.
echo (Running in debug mode to diagnose issues)
python "%~dp0run_assessment.py" "%APK_PATH%" "%OUTPUT_FOLDER%" -c "%CONFIG_PATH%" > "%OUTPUT_FOLDER%\output.log" 2>"%OUTPUT_FOLDER%\error.log"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Assessment completed successfully.
    echo Results are available in: %OUTPUT_FOLDER%
    echo HTML report: %OUTPUT_FOLDER%\maudsley_report.html
) else (
    echo.
    echo Assessment encountered issues. See logs for details:
    echo - %OUTPUT_FOLDER%\assessment.log 
    echo - %OUTPUT_FOLDER%\error.log
)

exit /b %ERRORLEVEL%