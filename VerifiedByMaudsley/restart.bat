@echo off
REM Verified by Maudsley - Reset and restart script
REM This script fixes common issues and restarts the assessment process

echo Verified by Maudsley - Reset and Restart
echo -------------------------------------------------

REM Check if DroidBot app is installed on the device
adb shell pm list packages | findstr "io.github.ylimit.droidbotapp" > nul
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: DroidBot app is not installed on the device.
    echo.
    echo Please run setup_emulator.bat first to install required components:
    echo   setup_emulator.bat "%~1"
    echo.
    echo Do you want to continue anyway? (Y/N)
    set /p CONTINUE=
    if /i not "%CONTINUE%"=="Y" exit /b 1
    echo.

REM Check arguments
if "%~1"=="" (
    echo Usage: restart.bat ^<APK_PATH^> ^<OUTPUT_FOLDER^> [CONFIG_JSON]
    echo.
    echo   APK_PATH       - Path to the APK file to assess
    echo   OUTPUT_FOLDER  - Folder to save assessment results
    echo   CONFIG_JSON    - Optional: Path to a custom config.json file
    exit /b 1
)

if "%~2"=="" (
    echo Error: Missing output folder parameter.
    echo Usage: restart.bat ^<APK_PATH^> ^<OUTPUT_FOLDER^> [CONFIG_JSON]
    exit /b 1
)

set APK_PATH=%~1
set OUTPUT_FOLDER=%~2
set CONFIG_PATH=%~3

if "%CONFIG_PATH%"=="" (
    set CONFIG_PATH=%~dp0config.json
)

REM Kill any existing ADB processes
echo Stopping any existing ADB processes...
taskkill /F /IM adb.exe > NUL 2>&1

REM Restart ADB server
echo Restarting ADB server...
adb kill-server > NUL 2>&1
adb start-server > NUL 2>&1

REM Clear any previous output directory
if exist "%OUTPUT_FOLDER%" (
    echo Cleaning previous output directory...
    rd /s /q "%OUTPUT_FOLDER%"
)
mkdir "%OUTPUT_FOLDER%"

REM Run the basic diagnostic test first
echo Running diagnostic test...
python "%~dp0quick_test.py" "%APK_PATH%" "%OUTPUT_FOLDER%\diagnostic" > "%OUTPUT_FOLDER%\diagnostic.log" 2>&1

REM Now run the actual assessment
echo.
echo Starting main assessment...
call "%~dp0run_assessment.bat" "%APK_PATH%" "%OUTPUT_FOLDER%" "%CONFIG_PATH%"

echo.
echo Assessment process completed. Check results in: %OUTPUT_FOLDER%
echo If issues persist, check the diagnostic log: %OUTPUT_FOLDER%\diagnostic.log

exit /b %ERRORLEVEL%