@echo off
REM Setup Emulator for Verified by Maudsley
REM This script installs and configures DroidBot-related components on the emulator

echo Verified by Maudsley - Emulator Setup
echo -------------------------------------------------

REM Restart ADB server
echo Restarting ADB server...
adb kill-server
adb start-server
echo.

REM Check for connected devices
echo Checking for connected devices...
adb devices

adb devices | find "device" > nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No Android device or emulator detected!
    echo Please connect an Android device or start an emulator first.
    exit /b 1
)

echo.
echo Installing DroidBot components on device...

REM Install DroidBot components
echo Step 1: Installing DroidBot App...
adb install "%~dp0..\droidbot\resources\droidbotApp.apk"
if %ERRORLEVEL% NEQ 0 (
    echo Failed to install DroidBot App. Please check if the APK exists.
    exit /b 1
)

echo Step 2: Installing Test App (optional)...
if "%~1" NEQ "" (
    adb install "%~1"
    if %ERRORLEVEL% NEQ 0 (
        echo Warning: Failed to install test app at %~1
        echo You may need to install it manually.
    ) else (
        echo Test app installed successfully.
    )
) else (
    echo No test app specified. Skipping this step.
)

echo Step 3: Enabling DroidBot IME...
adb shell ime enable io.github.ylimit.droidbotapp/.DroidBotIME
adb shell ime set io.github.ylimit.droidbotapp/.DroidBotIME

echo Step 4: Checking IME status...
adb shell ime list -a

echo.
echo Step 5: Enabling accessibility service...
echo Please follow these steps on the emulator:
echo 1. Open Settings
echo 2. Go to Accessibility
echo 3. Find and select "DroidBot"
echo 4. Enable the service
echo.
echo Press any key when you have completed these steps...
pause > nul

echo.
echo Setup completed! You can now run the assessment with:
echo restart.bat "C:\Projects\looper.apk" looper_assessment_results "C:\Projects\FinalDroid\AutoDroid\VerifiedByMaudsley\config.json"
echo.

exit /b 0