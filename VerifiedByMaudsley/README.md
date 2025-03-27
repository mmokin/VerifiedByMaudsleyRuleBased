# Verified by Maudsley

A tool for automated assessment of mental health applications, built on top of the AutoDroid framework.

## Installation

### Quick Installation

```bash
cd AutoDroid/
pip install -e .
```

This will install all required dependencies and make the `verified-maudsley` command available.

### Manual Installation

1. Install the Python dependencies:
```bash
pip install scikit-learn numpy pillow opencv-python networkx requests jinja2 torch
```

2. Set up your Android device:
   - Enable developer options
   - Enable USB debugging
   - Connect to your computer via USB

## Usage

### Command Line

```bash
verified-maudsley <APK_PATH> <OUTPUT_FOLDER> [-c CONFIG_JSON]
```

Or run the Python script directly:

```bash
python -m VerifiedByMaudsley.run_assessment <APK_PATH> <OUTPUT_FOLDER> [-c CONFIG_JSON]
```

On Windows, you can use the batch file:

```
run_assessment.bat <APK_PATH> <OUTPUT_FOLDER> [CONFIG_JSON]
```

### Configuration

Edit `config.json` to customize your assessment:

- **credentials**: Login details for the app (can use "N/A" to ignore)
- **critical_sections**: UI sections to prioritize navigating to (can use "N/A" to ignore)
- **api_keys**: API keys for GPT and other services
- **app_notes**: Notes about the app being assessed (can use "N/A" to ignore)
- **assessments**: Enable/disable specific assessment modules
- **droidbot**: Configure the underlying AutoDroid testing framework
- **memory_settings**: Configure how app knowledge is saved and reused

The system recognizes "N/A" as a special value to ignore specific configuration fields.

## Assessment Reports

After running an assessment, find the HTML report at:
```
<OUTPUT_FOLDER>/maudsley_report.html
```

This report includes:
- Color analysis with mental health considerations
- Navigation complexity assessment
- Button accessibility evaluation
- Memory-guided insights about the app
- Screenshots of all UI states

## Requirements

- Python 3.7+
- Android Debug Bridge (ADB)
- Android device or emulator
- OpenAI API key (for GPT-powered analysis)

## License

This project is licensed under the MIT License - see the LICENSE file for details.