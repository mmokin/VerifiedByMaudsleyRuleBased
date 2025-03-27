# Integration Between Verified by Maudsley and AutoDroid

This documentation describes the integration architecture between the Verified by Maudsley system and the underlying AutoDroid framework.

## Architecture Overview

The integration is designed around the adapter pattern, which converts Verified by Maudsley configurations into formats that AutoDroid can understand and process. The key adapters are:

1. **TaskPolicyAdapter**: Converts Verified by Maudsley task configurations into AutoDroid TaskPolicy configurations.
2. **MemoryAdapter**: Provides memory features specific to mental health app assessments.

## Configuration Format

The Verified by Maudsley system can use two different configuration formats for tasks:

### String Task Description (Preferred)

AutoDroid's TaskPolicy expects a string task description. In your config.json, you can provide this directly:

```json
{
  "task": "Explore the app focusing on login, settings, and navigation features"
}
```

### Structured Task Configuration (Alternative)

Alternatively, you can provide a structured task configuration:

```json
{
  "task": {
    "type": "critical_sections_exploration",
    "sections": [
      {
        "name": "Login",
        "keywords": ["login", "sign in", "username"]
      },
      {
        "name": "Settings",
        "keywords": ["settings", "preferences", "configure"]
      }
    ],
    "memory_enabled": false
  }
}
```

## Testing with the Looper App

To test the integration with the looper app, run:

```
unified_test.bat ..\droidbot\resources\bench_apps\app-looper.apk
```

This will:
1. Set up the environment
2. Install and configure the required ADB components
3. Run the assessment with the current config.json
4. Generate a report in the output directory

## Memory Features

Memory features are optional and require the INSTRUCTOR library. To enable:

1. Install the INSTRUCTOR library:
   ```
   pip install InstructorEmbedding
   ```

2. Update your config.json to enable memory:
   ```json
   {
     "task": "Explore the app...",
     "memory_settings": {
       "use_memory": true
     }
   }
   ```

## Troubleshooting

Common issues:

1. **TypeError: can only concatenate str (not "NoneType") to str**
   - Ensure your config.json has a string task description or our adapter has converted the task config to a string.

2. **Device not found/authorized**
   - Ensure the emulator is running and `adb devices` shows it as authorized.

3. **App not installed**
   - Check the path to the APK file.

4. **Memory features failing**
   - Ensure INSTRUCTOR is installed if memory features are enabled.
   - Set `"use_memory": false` in memory_settings if you don't need memory features.

## Best Practices

1. Always test configuration changes with the looper app before running on actual mental health apps.
2. Use string task descriptions for simpler configurations.
3. Keep critical sections focused on the most important parts of the app.
4. Include helpful app_notes to guide the exploration process.