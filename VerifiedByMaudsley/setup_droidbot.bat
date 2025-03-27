@echo off
REM ======================================================
REM Verified by Maudsley - DroidBot Environment Setup
REM This script prepares the Android device for testing
REM ======================================================

echo Verified by Maudsley - DroidBot Environment Setup
echo =================================================

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
echo Setting up DroidBot environment on device...

REM 1. Install DroidBot App
echo [1/4] Installing DroidBot App...
adb install -r "%~dp0..\droidbot\resources\droidbotApp.apk"
if %ERRORLEVEL% NEQ 0 (
    echo Failed to install DroidBot App. 
    echo This app is required for input injection and accessibility services.
    exit /b 1
)

REM 2. Set up DroidBot IME (keyboard)
echo [2/4] Setting up DroidBot IME...
adb shell ime enable io.github.ylimit.droidbotapp/.DroidBotIME
adb shell ime set io.github.ylimit.droidbotapp/.DroidBotIME

REM 3. Push minicap components
echo [3/4] Setting up minicap for screen capture...
REM This is needed for CV-mode in DroidBot
adb shell mkdir -p /data/local/tmp/minicap-devel

REM Detect device architecture
for /f "tokens=*" %%a in ('adb shell getprop ro.product.cpu.abi') do set DEVICE_ABI=%%a
echo Device architecture: %DEVICE_ABI%

REM Detect Android API level
for /f "tokens=*" %%a in ('adb shell getprop ro.build.version.sdk') do set API_LEVEL=%%a
echo Android API level: %API_LEVEL%

REM Push appropriate minicap binary and library
if "%DEVICE_ABI%"=="armeabi-v7a" (
    adb push "%~dp0..\droidbot\resources\minicap\libs\armeabi-v7a\minicap" "/data/local/tmp/minicap"
    adb push "%~dp0..\droidbot\resources\minicap\jni\libs\android-%API_LEVEL%\armeabi-v7a\minicap.so" "/data/local/tmp/minicap-devel/minicap.so"
) else if "%DEVICE_ABI%"=="arm64-v8a" (
    adb push "%~dp0..\droidbot\resources\minicap\libs\arm64-v8a\minicap" "/data/local/tmp/minicap"
    adb push "%~dp0..\droidbot\resources\minicap\jni\libs\android-%API_LEVEL%\arm64-v8a\minicap.so" "/data/local/tmp/minicap-devel/minicap.so"
) else if "%DEVICE_ABI%"=="x86" (
    adb push "%~dp0..\droidbot\resources\minicap\libs\x86\minicap" "/data/local/tmp/minicap"
    adb push "%~dp0..\droidbot\resources\minicap\jni\libs\android-%API_LEVEL%\x86\minicap.so" "/data/local/tmp/minicap-devel/minicap.so"
) else if "%DEVICE_ABI%"=="x86_64" (
    adb push "%~dp0..\droidbot\resources\minicap\libs\x86_64\minicap" "/data/local/tmp/minicap"
    adb push "%~dp0..\droidbot\resources\minicap\jni\libs\android-%API_LEVEL%\x86_64\minicap.so" "/data/local/tmp/minicap-devel/minicap.so"
)

adb shell chmod 777 /data/local/tmp/minicap

REM 4. Enable accessibility service
echo [4/4] Enabling accessibility services...
echo.
echo IMPORTANT: You must manually enable the DroidBot accessibility service:
echo 1. Go to Settings → Accessibility on your device
echo 2. Find and select "DroidBot"
echo 3. Enable the toggle switch
echo.
echo Press any key when you've completed this step...
pause > nul

REM Test if the configuration was successful
echo.
echo Testing DroidBot configuration...
adb shell pm list packages | findstr "io.github.ylimit.droidbotapp"
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: DroidBot app not found! Setup may have failed.
) else (
    echo DroidBot app is installed.
)

adb shell settings get secure enabled_accessibility_services | findstr "io.github.ylimit.droidbotapp"
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: DroidBot accessibility service may not be enabled.
    echo You must enable it manually in Settings → Accessibility.
) else (
    echo DroidBot accessibility service is enabled.
)

adb shell ime list -a | findstr "DroidBotIME"
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: DroidBot IME may not be set as default.
    echo You may need to set it manually in Settings → Language & Input.
) else (
    echo DroidBot IME is available.
)

echo.
echo Setup complete! You can now run the assessment with:
echo restart.bat "C:\Projects\looper.apk" looper_assessment_results "C:\Projects\FinalDroid\AutoDroid\VerifiedByMaudsley\config.json"
echo.

exit /b 0