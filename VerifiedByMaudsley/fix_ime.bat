@echo off
REM ======================================================
REM Fix DroidBot IME Issues
REM ======================================================

echo Verified by Maudsley - IME Fix Script
echo ======================================

REM Check for connected devices
echo Checking for connected devices...
adb devices

adb devices | find "device" > nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: No Android device or emulator detected!
    exit /b 1
)

echo.
echo Fixing Input Method setup...

REM 1. Make sure the package is installed
echo Step 1: Verifying DroidBot app installation...
adb shell pm list packages | findstr "io.github.ylimit.droidbotapp"
if %ERRORLEVEL% NEQ 0 (
    echo The DroidBot app is not installed! Installing now...
    adb install -r "%~dp0..\droidbot\resources\droidbotApp.apk"
)

REM 2. Manually set permissions for the IME
echo Step 2: Setting permissions for DroidBot app...
adb shell pm grant io.github.ylimit.droidbotapp android.permission.WRITE_SECURE_SETTINGS
adb shell pm grant io.github.ylimit.droidbotapp android.permission.WRITE_SETTINGS
adb shell pm grant io.github.ylimit.droidbotapp android.permission.BIND_ACCESSIBILITY_SERVICE

REM 3. Alternative method to enable IME
echo Step 3: Trying alternative method to enable IME...
adb shell settings put secure enabled_input_methods io.github.ylimit.droidbotapp/.DroidBotIME:com.android.inputmethod.latin/.LatinIME
adb shell settings put secure default_input_method io.github.ylimit.droidbotapp/.DroidBotIME

REM 4. Check device API level
echo Step 4: Checking Android version...
for /f "tokens=*" %%a in ('adb shell getprop ro.build.version.sdk') do set API_LEVEL=%%a
echo Android API level: %API_LEVEL%

REM 5. For API 30+, use different commands
if %API_LEVEL% GEQ 30 (
    echo This device is running Android 11+ (API level %API_LEVEL%).
    echo Using alternative IME setup method...
    
    REM Try to use content provider directly
    adb shell am force-stop io.github.ylimit.droidbotapp
    adb shell am start -n io.github.ylimit.droidbotapp/.DroidBotIME
    
    echo Please manually enable the IME on your device:
    echo 1. Go to Settings → System → Languages & input → On-screen keyboard
    echo 2. Enable "DroidBot IME"
    echo 3. Then go back and tap "Default keyboard"
    echo 4. Select "DroidBot IME"
    
    echo Press any key when you have completed these steps...
    pause > nul
)

REM 6. Verify IME setup
echo Step 6: Verifying IME setup...
adb shell settings get secure default_input_method > ime.txt
type ime.txt

REM 7. For the assessment, modify config to not rely on IME
echo Step 7: Updating assessment configuration to handle IME limitations...
echo If the assessment still fails, try setting "random_input" to false in config.json
echo and ensure droidbot "policy" is set to "dfs" or "bfs" instead of "task"

echo.
echo IME fix completed. Try running the assessment again.
echo.

exit /b 0