@echo off
REM ======================================================
REM Emulator-Specific Fix Script
REM ======================================================

echo Verified by Maudsley - Emulator Fix Script
echo =========================================

REM Check for connected devices
echo Checking for connected devices...
adb devices

echo.
echo Attempting to fix IME issues...

REM 1. Reinstall DroidBot app
echo Step 1: Reinstalling DroidBot app...
adb uninstall io.github.ylimit.droidbotapp
adb install -r "%~dp0..\droidbot\resources\droidbotApp.apk"
if %ERRORLEVEL% NEQ 0 (
    echo Failed to install DroidBot app.
    exit /b 1
)

REM 2. Try to enable IME through settings
echo Step 2: Setting up IME through settings...
adb shell settings put secure enabled_input_methods io.github.ylimit.droidbotapp/.DroidBotIME

REM 3. Force restart ADB server
echo Step 3: Restarting ADB server...
adb kill-server
adb start-server
timeout /t 3 /nobreak > nul

REM 4. Update config to be more emulator-friendly
echo Step 4: Creating emulator-friendly configuration...
echo {^
  "credentials": [^
    {^
      "username": "N/A",^
      "password": "N/A"^
    }^
  ],^
  "critical_sections": [^
    {^
      "name": "N/A",^
      "keywords": ["N/A"]^
    }^
  ],^
  "api_keys": {^
    "openai": "YOUR_OPENAI_API_KEY_HERE"^
  },^
  "app_notes": [^
    {^
      "notes": "N/A"^
    }^
  ],^
  "assessments": {^
    "color_report": true,^
    "navigation_report": true,^
    "button_report": false^
  },^
  "droidbot": {^
    "timeout": 120,^
    "event_count": 20,^
    "policy": "dfs",^
    "device_serial": "",^
    "random_input": false,^
    "interval": 3^
  },^
  "memory_settings": {^
    "avoid_revisits": true,^
    "use_app_notes": false,^
    "baseline_data_path": "memory/baseline_data.json"^
  }^
} > emulator_simple.json

echo.
echo *** IMPORTANT MANUAL STEPS ***
echo 1. On your emulator, go to:
echo    Settings → System → Languages & input → On-screen keyboard
echo 2. Tap "Manage keyboards"
echo 3. Enable the toggle for "DroidBot IME"
echo 4. Tap "OK" on the warning 
echo.
echo Press any key when you've completed these steps...
pause > nul

echo.
echo Checking IME status...
adb shell ime list -a | findstr "DroidBot"

echo.
echo Now run this command to test with simplified settings:
echo python run_assessment.py "C:\Projects\looper.apk" looper_test -c emulator_simple.json

exit /b 0