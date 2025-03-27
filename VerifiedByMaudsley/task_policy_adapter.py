import os
import sys
import logging
from typing import Dict, Any, Optional, Union

# Add parent directory to path for importing AutoDroid modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import AutoDroid's TaskPolicy
from droidbot.input_policy import TaskPolicy as AutoDroidTaskPolicy

class TaskPolicyAdapter:
    """
    Adapter for AutoDroid's TaskPolicy, translating Verified by Maudsley
    configuration to AutoDroid's expected input.
    """
    
    def __init__(self, device, app, config_json: Dict[str, Any]):
        """
        Initialize the TaskPolicyAdapter.
        
        Args:
            device: Device instance
            app: App instance
            config_json: Verified by Maudsley configuration
        """
        self.logger = logging.getLogger('TaskPolicyAdapter')
        self.config = config_json
        self.device = device
        self.app = app
        
        # Extract task information from config
        self.task_description = self._get_task_description()
        self.task_config = self._prepare_task_config()
        self.task_policy = None
        
        # Track unique screen limits
        self.unique_screens_limit = config_json.get("unique_screens", 0)
        if self.unique_screens_limit > 0:
            self.logger.info(f"Using unique screens limit: {self.unique_screens_limit}")
            
        # Monitor state to track unique screens
        if hasattr(device, "add_state_callback"):
            device.add_state_callback(self._state_callback)
            self.logger.info("Registered state callback for monitoring unique screens")
        
        # Initialize count of unique screens
        self.unique_screens = set()
        
    def _state_callback(self, state):
        """
        Callback to monitor states and check for unique screen limit
        
        Args:
            state: The current device state
        """
        if state and hasattr(state, "state_str"):
            # Add to unique screens if new
            if state.state_str not in self.unique_screens:
                self.unique_screens.add(state.state_str)
                self.logger.info(f"Unique screens count: {len(self.unique_screens)}/{self.unique_screens_limit}")
                
                # Check if we've reached the limit
                if self.unique_screens_limit > 0 and len(self.unique_screens) >= self.unique_screens_limit:
                    self.logger.info(f"Reached target of {self.unique_screens_limit} unique screens, will stop exploration")
                    # We'd like to stop here, but it's better to let the task policy itself handle this
        
        # Check if memory is explicitly enabled in config
        use_memory = False
        if "task" in self.config and isinstance(self.config["task"], dict):
            use_memory = self.config["task"].get("memory_enabled", False)
        else:
            use_memory = self.config.get("memory_settings", {}).get("use_memory", False)
        
        # Log memory settings    
        if use_memory:
            self.logger.info("Memory features enabled in configuration")
        else:
            self.logger.info("Memory features disabled in configuration")
        
        # Initialize TaskPolicy safely
        try:
            # Make sure we have a valid task string
            task_str = self.task_description
            if not isinstance(task_str, str) or not task_str.strip():
                task_str = "Explore the app thoroughly and interact with all UI elements"
                self.logger.warning(f"Task description was invalid, using default: '{task_str}'")
            
            self.logger.info(f"Using task description: '{task_str}'")
            
            if use_memory:
                # Try to initialize with memory features
                self.logger.info("Initializing TaskPolicy with memory features")
                try:
                    self.task_policy = AutoDroidTaskPolicy(
                        device=device,
                        app=app,
                        random_input=self.config.get("droidbot", {}).get("random_input", False),
                        task=task_str,  # Pass string task description
                        use_memory=True,  # Try with memory features
                        debug_mode=self.config.get("droidbot", {}).get("debug_mode", False),
                        config=self.config  # Pass the entire config for app-specific notes
                    )
                    self.logger.info("Successfully initialized TaskPolicy with memory features")
                except (TypeError, ImportError, ModuleNotFoundError, AttributeError) as e:
                    # Handle INSTRUCTOR or other memory-related errors
                    self.logger.warning(f"Failed to initialize TaskPolicy with memory: {e}")
                    self.logger.info("Falling back to TaskPolicy without memory features")
                    use_memory = False
            
            # If memory isn't enabled or failed to initialize with memory
            if not use_memory or self.task_policy is None:
                self.task_policy = AutoDroidTaskPolicy(
                    device=device,
                    app=app,
                    random_input=self.config.get("droidbot", {}).get("random_input", False),
                    task=task_str,  # Pass string task description
                    use_memory=False,  # Disable memory features
                    debug_mode=self.config.get("droidbot", {}).get("debug_mode", False),
                    config=self.config  # Pass the entire config for app-specific notes
                )
                self.logger.info("Successfully initialized TaskPolicy without memory features")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize TaskPolicy: {e}")
            self.logger.error("This is a critical error in the adapter layer")
            self.logger.info("The assessment may continue with limited functionality")
            # Don't raise the exception, allow the caller to handle the None task_policy
    
    def _get_task_description(self) -> str:
        """
        Get a task description string for AutoDroid's TaskPolicy.
        
        Returns:
            A string task description suitable for AutoDroid's TaskPolicy
        """
        # If there's a unique_screens limit in config, add it to the task description
        unique_screens_limit = ""
        if "unique_screens" in self.config:
            unique_screens_limit = f" Explore exactly {self.config['unique_screens']} unique screens, then stop."
            self.logger.info(f"Adding unique screens limit: {unique_screens_limit}")
            
        # If task is already a string in config, use it directly
        if "task" in self.config and isinstance(self.config["task"], str):
            task_description = self.config["task"] + unique_screens_limit
            self.logger.info(f"Using task description from config: {task_description}")
            return task_description
            
        # Otherwise generate from critical sections
        critical_sections = []
        task_description = ""
        
        # If the config has a proper AutoDroid-compatible task definition with sections
        if "task" in self.config and isinstance(self.config["task"], dict) and "sections" in self.config["task"]:
            critical_sections = self.config["task"]["sections"]
        # Or use critical_sections directly
        elif "critical_sections" in self.config and self.config["critical_sections"]:
            # Filter out N/A sections
            for section in self.config["critical_sections"]:
                if section.get("name") == "N/A" or section.get("keywords") == ["N/A"]:
                    continue
                
                if isinstance(section.get("keywords"), list) and "N/A" in section.get("keywords"):
                    continue
                
                if section.get("name") and section.get("keywords"):
                    critical_sections.append(section)
        
        # Get app notes if available
        app_notes = ""
        if "app_notes" in self.config:
            for note_obj in self.config["app_notes"]:
                if "notes" in note_obj and note_obj["notes"] != "N/A":
                    app_notes += note_obj["notes"] + " "
        
        # Create a human-readable task description from critical sections
        if critical_sections:
            section_names = [section.get("name") for section in critical_sections if section.get("name")]
            if section_names:
                task_description = f"Explore the app focusing on these critical sections: {', '.join(section_names)}"
                if app_notes.strip():
                    task_description += f". {app_notes.strip()}"
            else:
                task_description = "Explore the app thoroughly"
        else:
            task_description = "Explore the app and discover unique screens"
            if app_notes.strip():
                task_description += f". {app_notes.strip()}"
        
        self.logger.info(f"Generated task description: {task_description}")
        return task_description
    
    def _prepare_task_config(self) -> Dict[str, Any]:
        """
        Prepare task configuration dictionary for compatibility with other parts of the system.
        
        Returns:
            Dictionary containing the task configuration
        """
        # If the config already has a proper AutoDroid-compatible task definition, use it directly
        if "task" in self.config and isinstance(self.config["task"], dict):
            self.logger.info("Using direct task configuration from config")
            return self.config["task"]
        
        # Otherwise, build a task config from critical sections
        task_config = {}
        critical_sections = []
        
        if "critical_sections" in self.config and self.config["critical_sections"]:
            # Filter out N/A sections
            for section in self.config["critical_sections"]:
                if section.get("name") == "N/A" or section.get("keywords") == ["N/A"]:
                    continue
                
                if isinstance(section.get("keywords"), list) and "N/A" in section.get("keywords"):
                    continue
                
                if section.get("name") and section.get("keywords"):
                    critical_sections.append(section)
        
        # If no valid critical sections, default to exploring unique screens
        if not critical_sections:
            self.logger.info("No valid critical sections found. Using unique screens exploration.")
            task_config = {
                "type": "unique_screens_exploration",
                "target_screens": 5,
                "memory_enabled": self.config.get("memory_settings", {}).get("use_memory", False)
            }
        else:
            # Format critical sections for AutoDroid's TaskPolicy
            task_config = {
                "type": "critical_sections_exploration",
                "sections": critical_sections,
                "memory_enabled": self.config.get("memory_settings", {}).get("use_memory", False)
            }
            
            # Add any app-specific notes if available
            if "app_notes" in self.config:
                notes = ""
                for note_obj in self.config["app_notes"]:
                    if "notes" in note_obj and note_obj["notes"] != "N/A":
                        notes += note_obj["notes"] + " "
                
                if notes.strip():
                    task_config["app_notes"] = notes.strip()
        
        return task_config
    
    def get_task_policy(self):
        """
        Get the initialized AutoDroid TaskPolicy.
        
        Returns:
            AutoDroid TaskPolicy instance
        """
        return self.task_policy
        
    def get_critical_sections(self):
        """
        Get the critical sections from the task configuration.
        
        Returns:
            List of critical section dictionaries
        """
        if self.task_config.get("type") == "critical_sections_exploration" and "sections" in self.task_config:
            return self.task_config["sections"]
        return []
    
    def get_task_description(self):
        """
        Get the task description string.
        
        Returns:
            String task description for AutoDroid
        """
        return self.task_description