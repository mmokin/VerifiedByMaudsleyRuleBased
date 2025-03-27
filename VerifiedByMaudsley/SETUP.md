# Verified by Maudsley - Setup Instructions

## Overview
This document provides setup instructions for the Verified by Maudsley assessment framework. The framework is designed to analyze mental health applications on Android devices.

## Prerequisites

- Python 3.7 or later
- Android device or emulator
- Android SDK with ADB installed and in your PATH

## Installation Steps

1. **Install Python dependencies**:
   ```
   pip install opencv-python scikit-learn numpy pillow requests
   ```

2. **Connect your Android device or start an emulator**:
   - For physical devices, connect via USB and enable Developer Options and USB Debugging
   - For emulators, ensure the emulator is running and visible to ADB

3. **Check device connection**:
   ```
   adb devices
   ```
   You should see your device or emulator listed.

4. **Setup DroidBot components**:
   - Run `setup_droidbot.bat` to install required APKs on the device:
   ```
   setup_droidbot.bat
   ```

5. **Optional: Configure for emulator**
   - The default configuration is now emulator-friendly with minicap disabled
   - If you encounter issues, check the "Troubleshooting" section

## Running the Assessment

1. **Basic assessment**:
   ```
   run_assessment.bat <APK_PATH> <OUTPUT_FOLDER> [CONFIG_JSON]
   ```
   Example: `run_assessment.bat C:\path\to\app.apk my_results`

2. **Test with looper.apk**:
   ```
   unified_test.bat [APK_PATH]
   ```
   This script runs a direct DroidBot test and full assessment with minicap disabled.

## Configuration

The framework can be configured through a JSON configuration file (`config.json`). Key settings include:

- **timeout**: Maximum runtime in seconds (default: 600)
- **event_count**: Maximum number of UI events to generate (default: 200)
- **policy**: Exploration policy to use (default: "task")
- **is_emulator**: Set to true when using an emulator (default: true)
- **disable_minicap**: Set to true to avoid minicap issues (default: true)
- **use_cv**: Whether to use OpenCV for view analysis (default: false)

## Troubleshooting

1. **ADB connection issues**:
   - Run `check_device.bat` to verify device connection
   - For wireless debugging, run `adb connect IP_ADDRESS:PORT`

2. **Input Method issues**:
   - Run `fix_ime.bat` to set up the DroidBot IME

3. **Permission problems on newer Android versions**:
   - For Android 11+ (API 30+), you may need to manually grant permissions
   - The framework now defaults to emulator mode which disables problematic features

4. **Import errors when running DroidBot**:
   - Always use `python -m droidbot.start` instead of running scripts directly
   - This ensures proper module resolution

## Files and Structure

- **assessment/**: Contains assessment modules (color, navigation, button analysis)
- **config.json**: Main configuration file
- **run_assessment.bat**: Main entry point for running assessments
- **unified_test.bat**: Combined testing script for quick verification
- **setup_droidbot.bat**: Installs required components on device
- **check_device.bat**: Checks device connection and status
