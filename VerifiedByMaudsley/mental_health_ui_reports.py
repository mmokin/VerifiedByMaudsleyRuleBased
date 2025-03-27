import os
import json
import logging
import importlib.util
import sys

# Add parent directory to path for importing AutoDroid modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import assessment modules
from assessment.color_report import ColorReport
from assessment.navigation_report import NavigationReport
from assessment.button_report import ButtonReport
from report_generator import ReportGenerator
from memory_adapter import MemoryAdapter
from task_policy_adapter import TaskPolicyAdapter

class MentalHealthUIReports:
    """
    Main class for running mental health UI assessments.
    Manages assessment modules and generates comprehensive reports.
    """
    
    def __init__(self, apk_path, output_dir, config_json=None):
        """
        Initialize the MentalHealthUIReports class.
        
        Args:
            apk_path: Path to the APK file to analyze
            output_dir: Directory to save assessment output
            config_json: Configuration settings as JSON string or dict
        """
        self.apk_path = apk_path
        self.output_dir = output_dir
        
        # Parse config JSON if it's a string
        if isinstance(config_json, str):
            try:
                self.config_json = json.loads(config_json)
            except json.JSONDecodeError:
                self.config_json = {}
        else:
            self.config_json = config_json or {}
        
        # Setup logging
        self.logger = logging.getLogger('MentalHealthUIReports')
        self.logger.setLevel(logging.INFO)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Log file setup
        log_file = os.path.join(output_dir, "assessment.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)
        
        # Console log setup
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(console_handler)
        
        # Default assessment configuration
        self.assessment_config = {
            "color_report": True,
            "navigation_report": True,
            "button_report": True
        }
        
        # Override with config if provided
        if "assessments" in self.config_json:
            for assessment, enabled in self.config_json["assessments"].items():
                if assessment in self.assessment_config:
                    self.assessment_config[assessment] = enabled
        
        # Extract app name from APK path
        self.app_name = os.path.basename(apk_path).replace(".apk", "")
        
        # Initialize memory adapter for AutoDroid integration
        self.memory_adapter = MemoryAdapter(self.config_json, self.output_dir)
    
    def run_droidbot(self):
        """
        Run DroidBot to navigate the app and collect data.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Import DroidBot modules
            self.logger.info("Importing DroidBot modules")
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from droidbot.start import parse_args
            from droidbot.droidbot import DroidBot
            
            # Configure DroidBot options by temporarily manipulating sys.argv
            self.logger.info("Configuring DroidBot")
            import sys
            original_argv = sys.argv
            
            # Build the argument list for DroidBot with emulator-friendly defaults
            droidbot_argv = [
                sys.argv[0],  # Script name
                "-a", self.apk_path,
                "-o", self.output_dir,
                "-keep_app"  # Don't uninstall app after analysis
            ]
            
            # Don't use CV mode for emulators unless specifically requested
            if "droidbot" in self.config_json and self.config_json.get("droidbot", {}).get("use_cv", False):
                self.logger.info("Using CV mode (can be disabled in config with use_cv: false)")
                droidbot_argv.append("-cv")
            else:
                self.logger.info("CV mode disabled to avoid minicap issues")
                
            # Only try to grant permissions if requested and likely to succeed
            try:
                import subprocess
                api_cmd = subprocess.run(['adb', 'shell', 'getprop', 'ro.build.version.sdk'], 
                                         capture_output=True, text=True)
                api_level = int(api_cmd.stdout.strip())
                self.logger.info(f"Detected API level: {api_level}")
                
                if api_level < 30:
                    self.logger.info("Adding grant_perm flag (supported on this API level)")
                    droidbot_argv.append("-grant_perm")
                else:
                    self.logger.info("Skipping grant_perm flag (not reliable on API 30+)")
            except Exception as e:
                self.logger.warning(f"Could not detect API level: {str(e)}")
                # For safety, don't use grant_perm by default
            
            # Add other options from config if available
            if "droidbot" in self.config_json:
                config = self.config_json["droidbot"]
                if "timeout" in config:
                    droidbot_argv.extend(["-timeout", str(config["timeout"])])
                if "event_count" in config:
                    droidbot_argv.extend(["-count", str(config["event_count"])])
                if "interval" in config:
                    droidbot_argv.extend(["-interval", str(config["interval"])])
                if "policy" in config and config["policy"] != "task":
                    droidbot_argv.extend(["-policy", config["policy"]])
                if "device_serial" in config and config["device_serial"]:
                    droidbot_argv.extend(["-d", config["device_serial"]])
            
            # Set sys.argv temporarily to the DroidBot arguments
            self.logger.info(f"DroidBot arguments: {droidbot_argv}")
            sys.argv = droidbot_argv
            
            # Call parse_args without arguments to read from sys.argv
            try:
                args = parse_args()
                self.logger.info("Successfully parsed DroidBot arguments")
            except Exception as e:
                self.logger.error(f"Error parsing DroidBot arguments: {str(e)}")
                raise
            
            # Restore original argv
            sys.argv = original_argv
            
            # Add env_policy attribute which DroidBot needs but isn't in parse_args
            from droidbot.env_manager import POLICY_NONE
            args.env_policy = POLICY_NONE
            
            # Set defaults for other potentially missing attributes
            if not hasattr(args, 'keep_env'):
                args.keep_env = False
            if not hasattr(args, 'debug_mode'):
                args.debug_mode = False
            if not hasattr(args, 'profiling_method'):
                args.profiling_method = None
            if not hasattr(args, 'enable_accessibility_hard'):
                args.enable_accessibility_hard = False
            if not hasattr(args, 'master'):
                args.master = None
            if not hasattr(args, 'humanoid'):
                args.humanoid = None
            if not hasattr(args, 'ignore_ad'):
                args.ignore_ad = False
            if not hasattr(args, 'replay_output'):
                args.replay_output = None
            if not hasattr(args, 'is_emulator'):
                # Set is_emulator from config
                if "droidbot" in self.config_json and "is_emulator" in self.config_json["droidbot"]:
                    args.is_emulator = self.config_json["droidbot"]["is_emulator"]
                else:
                    args.is_emulator = False
                    
            # Handle explicit minicap disabling
            if not hasattr(args, 'disable_minicap'):
                args.disable_minicap = False
                
            # If config specifies to disable minicap or we're on an emulator
            if "droidbot" in self.config_json and self.config_json["droidbot"].get("disable_minicap", False):
                args.disable_minicap = True
                self.logger.info("Minicap explicitly disabled via config")
            
            # Override with config values if available
            if "droidbot" in self.config_json:
                droidbot_config = self.config_json["droidbot"]
                
                # Apply timeout if specified
                if "timeout" in droidbot_config:
                    args.timeout = int(droidbot_config["timeout"])
                
                # Apply event count if specified
                if "event_count" in droidbot_config:
                    args.count = int(droidbot_config["event_count"])
                
                # Apply policy if specified
                if "policy" in droidbot_config:
                    args.input_policy = droidbot_config["policy"]
                    
                    # Enable memory-guided policy for better app exploration
                    if args.input_policy == "memory_guided":
                        self.logger.info("Using memory-guided policy for intelligent app exploration")
                        
                # Apply random input if specified
                if "random_input" in droidbot_config:
                    args.random_input = bool(droidbot_config["random_input"])
                    
                # Apply event interval if specified
                if "interval" in droidbot_config:
                    args.interval = int(droidbot_config["interval"])
                
                # Apply device serial if specified
                if "device_serial" in droidbot_config:
                    args.device_serial = droidbot_config["device_serial"]
            
            # Check for critical sections and create a task
            task = None
            
            # Check if critical sections are all N/A or empty
            all_na = True
            has_critical_sections = False
            critical_sections = []
            
            if "critical_sections" in self.config_json and self.config_json["critical_sections"]:
                has_critical_sections = True
                
                # Filter out any critical sections marked as N/A
                for section in self.config_json["critical_sections"]:
                    # Skip if name or keywords are marked as N/A
                    if section.get("name") == "N/A" or section.get("keywords") == "N/A":
                        continue
                    # Skip if any keyword in the list is N/A
                    if isinstance(section.get("keywords"), list) and "N/A" in section.get("keywords"):
                        continue
                    
                    # If we found at least one valid section, not all are N/A
                    if section.get("name") and section.get("keywords"):
                        all_na = False
                        critical_sections.append(section)
            
            # Default to exploring 5 unique screens if all critical sections are N/A or none provided
            if (has_critical_sections and all_na) or not critical_sections:
                self.logger.info("Critical sections set to N/A or empty. Defaulting to exploring 5 unique screens.")
                task = {
                    "type": "unique_screens_exploration",
                    "target_screens": 5,
                    "memory_enabled": True,
                    "app_notes": self.memory_adapter.get_memory_context_for_gpt()
                }
            else:
                # Use standard critical sections exploration
                task = {
                    "type": "critical_sections_exploration",
                    "sections": critical_sections,
                    "memory_enabled": True,
                    "app_notes": self.memory_adapter.get_memory_context_for_gpt()
                }
                
                # Only use task policy if not using memory_guided
                if args.input_policy != "memory_guided":
                    args.input_policy = "task"  # Use task policy
            
            # Initialize and run DroidBot - with manual device detection
            self.logger.info(f"Starting DroidBot for {self.app_name}")
            
            # Setup a device state callback to track visited states with our memory adapter
            def state_callback(state):
                if state:
                    state_data = {
                        "activity": state.foreground_activity,
                        "views": [view.__dict__ for view in state.views],
                        "timestamp": state.timestamp
                    }
                    self.memory_adapter.record_state_visit(state.state_str, state_data)
            
            try:
                    # Original DroidBot initialization - no changes needed
                # DroidBot will handle this directly when bot.start() is called
                
                self.logger.info("Creating DroidBot with simplified parameters")
                bot = DroidBot(
                    app_path=args.apk_path,
                    device_serial=args.device_serial,
                    output_dir=args.output_dir,
                    env_policy="none",  # Simpler than using args.env_policy
                    policy_name=args.input_policy,
                    random_input=args.random_input,
                    script_path=None,  # Simpler than args.script_path
                    event_count=args.count,
                    event_interval=args.interval,
                    timeout=args.timeout,
                    keep_app=True,  # Simpler than args.keep_app
                    keep_env=False,  # Simpler than args.keep_env
                    cv_mode=args.cv_mode,
                    debug_mode=False,  # Simplified
                    profiling_method=None,  # Simplified
                    grant_perm=args.grant_perm,
                    enable_accessibility_hard=False,  # Simplified
                    master=None,  # Simplified
                    humanoid=None,  # Simplified
                    ignore_ad=False,  # Simplified
                    replay_output=None  # Simplified
                )
                
                # Create task policy adapter to leverage AutoDroid's native TaskPolicy
                try:
                    # Initialize the adapter with proper error handling
                    self.logger.info("Creating TaskPolicyAdapter for AutoDroid integration")
                    
                    # Pass config through the adapter for proper conversion
                    task_policy_adapter = TaskPolicyAdapter(bot.device, bot.app, self.config_json)
                    
                    # Log config details for debugging
                    self.logger.info(f"Config task type: {type(self.config_json.get('task'))}")
                    self.logger.info(f"Config task value: {self.config_json.get('task')}")
                    self.logger.info(f"Unique screens limit: {self.config_json.get('unique_screens')}")
                    
                    # If we're using memory_guided policy, handle specially
                    if args.input_policy == "memory_guided":
                        self.logger.info("Using memory_guided policy with direct task configuration")
                        # For memory_guided, we still need a string task
                        if isinstance(task_policy_adapter.task_description, str):
                            bot.task = task_policy_adapter.task_description
                        else:
                            bot.task = "Explore the app thoroughly and interact with main features"
                    else:
                        # Standard TaskPolicy integration - ENSURE we get a string from the adapter
                        task_description = task_policy_adapter.get_task_description()
                        
                        # CRITICAL: Log exactly what we're setting as the task
                        self.logger.info(f"Setting bot.task to: '{task_description}' (type: {type(task_description)})")
                        
                        # GUARANTEED string task description
                        if not isinstance(task_description, str) or not task_description.strip():
                            task_description = "Explore the app thoroughly and interact with all UI elements"
                            self.logger.warning(f"Invalid task description from adapter, using default: '{task_description}'")
                            
                        # Add unique screens limit if specified
                        if "unique_screens" in self.config_json:
                            limit = self.config_json["unique_screens"]
                            if not task_description.lower().find("unique screen") >= 0:
                                task_description += f". Stop after exploring {limit} unique screens."
                                self.logger.info(f"Added unique screens limit: {limit}")
                        
                        # Directly set the task string
                        bot.task = task_description
                        self.logger.info(f"Set task to: {bot.task}")
                        
                        # Set additional TaskPolicy parameters via reflection if needed
                        try:
                            if hasattr(bot, "input_manager") and hasattr(bot.input_manager, "policy"):
                                if hasattr(bot.input_manager.policy, "unique_screen_limit"):
                                    if "unique_screens" in self.config_json:
                                        bot.input_manager.policy.unique_screen_limit = self.config_json["unique_screens"]
                                        self.logger.info(f"Set unique_screen_limit to: {self.config_json['unique_screens']}")
                        except AttributeError:
                            self.logger.warning("Could not set additional TaskPolicy parameters")
                            
                        # Ensure proper output directories for reports
                        # This is critical for the later assessment reports to find data
                        state_dir = os.path.join(self.output_dir, "states")
                        screen_captures_dir = os.path.join(state_dir, "screen_captures")
                        if not os.path.exists(screen_captures_dir):
                            os.makedirs(screen_captures_dir, exist_ok=True)
                            self.logger.info(f"Created screenshot directory: {screen_captures_dir}")
                            
                        # Make sure NavigationReport can find states
                        utg_dir = os.path.join(self.output_dir, "utg")
                        if not os.path.exists(utg_dir):
                            os.makedirs(utg_dir, exist_ok=True)
                            self.logger.info(f"Created UTG directory: {utg_dir}")
                            
                        # Register a callback to copy screenshots to the expected location
                        def state_and_screen_callback(state):
                            if state and hasattr(state, "state_str") and hasattr(state, "screenshot_path"):
                                try:
                                    if state.screenshot_path and os.path.exists(state.screenshot_path):
                                        # Copy the screenshot to the expected location
                                        basename = os.path.basename(state.screenshot_path)
                                        dest_path = os.path.join(screen_captures_dir, basename)
                                        import shutil
                                        shutil.copy2(state.screenshot_path, dest_path)
                                        self.logger.info(f"Copied screenshot to: {dest_path}")
                                        
                                        # Record this state transition for navigation analysis
                                        self.memory_adapter.record_state_visit(state.state_str, {
                                            "activity": state.foreground_activity,
                                            "screenshot": dest_path,
                                            "timestamp": state.timestamp
                                        })
                                except Exception as e:
                                    self.logger.warning(f"Error copying screenshot: {e}")
                                    
                        # Register our callback to help build the navigation graph
                        if hasattr(bot.device, "add_state_callback"):
                            bot.device.add_state_callback(state_and_screen_callback)
                            self.logger.info("Registered state and screenshot callback")
                except Exception as e:
                    # If adapter fails completely, fall back to direct configuration
                    self.logger.error(f"Error initializing TaskPolicyAdapter: {str(e)}")
                    self.logger.info("Falling back to direct task configuration")
                    bot.task = task
                
            except Exception as e:
                self.logger.error(f"Error initializing DroidBot: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                raise
            
            # Set up state callback if DroidBot supports it
            if hasattr(bot.device, "add_state_callback"):
                bot.device.add_state_callback(state_callback)
            
            bot.start()
            self.logger.info("DroidBot analysis completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error running DroidBot: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
    
    def run_assessments(self):
        """
        Run the enabled assessment modules.
        
        Returns:
            Dictionary containing assessment results
        """
        assessment_results = {}
        
        # Ensure screenshots are in the right place for reports
        self._prepare_assessment_data()
        
        # Get memory context for GPT to include in assessment reports
        memory_context = self.memory_adapter.get_memory_context_for_gpt()
        self.logger.info(f"Using memory context for assessment: {memory_context}")
        
        # Run Color Report if enabled
        if self.assessment_config["color_report"]:
            try:
                self.logger.info("Running Color Analysis")
                # Pass memory context to color report
                config_with_memory = self.config_json.copy()
                config_with_memory["memory_context"] = memory_context
                
                color_report = ColorReport(self.output_dir, config_with_memory)
                result = color_report.analyze()
                assessment_results["color_report"] = result
                
                # Store result in assessment memory
                self.memory_adapter.add_assessment_result("color_report", result)
                
                # Add GPT insights to memory
                if "gpt_feedback" in result:
                    self.memory_adapter.add_gpt_insight(result["gpt_feedback"], "color")
                
                self.logger.info("Color Analysis completed")
            except Exception as e:
                self.logger.error(f"Error in Color Analysis: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                # Add dummy result so report doesn't break
                assessment_results["color_report"] = {"error": str(e), "analysis": "Failed to complete color analysis"}
        
        # Run Navigation Report if enabled
        if self.assessment_config["navigation_report"]:
            try:
                self.logger.info("Running Navigation Analysis")
                # Pass memory context to navigation report
                config_with_memory = self.config_json.copy()
                config_with_memory["memory_context"] = memory_context
                config_with_memory["visited_sections"] = self.memory_adapter.visited_sections
                
                navigation_report = NavigationReport(self.output_dir, config_with_memory)
                result = navigation_report.analyze()
                assessment_results["navigation_report"] = result
                
                self.logger.info("Navigation Analysis completed")
            except Exception as e:
                self.logger.error(f"Error in Navigation Analysis: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                # Add dummy result so report doesn't break
                assessment_results["navigation_report"] = {"error": str(e), "analysis": "Failed to complete navigation analysis"}
        
        # Run Button Report if enabled
        if self.assessment_config["button_report"]:
            try:
                self.logger.info("Running Button Analysis")
                button_report = ButtonReport(self.output_dir, self.config_json)
                assessment_results["button_report"] = button_report.analyze()
                self.logger.info("Button Analysis completed")
            except Exception as e:
                self.logger.error(f"Error in Button Analysis: {str(e)}")
                import traceback
                self.logger.error(traceback.format_exc())
                # Add dummy result so report doesn't break
                assessment_results["button_report"] = {"error": str(e), "analysis": "Failed to complete button analysis"}
        
        # Add memory data to assessment results with detailed debugging
        visited_states_count = len(self.memory_adapter.visited_states)
        self.logger.info(f"Adding memory data with {visited_states_count} visited states to report")
        
        # If we have no visited states but found screenshots, something's wrong with tracking
        if visited_states_count == 0:
            # Check for any screenshots as fallback
            import glob
            screenshots_dir = os.path.join(self.output_dir, "states", "screen_captures")
            any_screenshots = glob.glob(os.path.join(screenshots_dir, "*.png")) + glob.glob(os.path.join(screenshots_dir, "*.jpg"))
            fallback_count = len(any_screenshots)
            
            self.logger.info(f"No visited states recorded, but found {fallback_count} screenshots as fallback")
            if fallback_count > 0:
                visited_states_count = fallback_count
        
        assessment_results["memory_data"] = {
            "visited_states_count": visited_states_count,
            "sections_found": {name: visited for name, visited in self.memory_adapter.visited_sections.items() if visited},
            "sections_not_found": self.memory_adapter.get_unvisited_sections()
        }
        
        return assessment_results
        
    def _prepare_assessment_data(self):
        """
        Prepare data directories and files for assessment.
        Ensures screenshots are in the correct location for reports to find them.
        """
        self.logger.info("Preparing assessment data directories")
        
        # Ensure screenshot directory exists
        states_dir = os.path.join(self.output_dir, "states")
        screenshots_dir = os.path.join(states_dir, "screen_captures")
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Debug info about existing directories
        import glob
        self.logger.info(f"Output directory: {self.output_dir} - Exists: {os.path.exists(self.output_dir)}")
        self.logger.info(f"States directory: {states_dir} - Exists: {os.path.exists(states_dir)}")
        self.logger.info(f"Screenshots directory: {screenshots_dir} - Exists: {os.path.exists(screenshots_dir)}")
        
        # Check all directories for existing screenshots
        potential_locations = [
            ("Output dir", os.path.join(self.output_dir, "*.jpg"), os.path.join(self.output_dir, "*.png")),
            ("States dir", os.path.join(states_dir, "*.jpg"), os.path.join(states_dir, "*.png")),
            ("Screenshots dir", os.path.join(screenshots_dir, "*.jpg"), os.path.join(screenshots_dir, "*.png")),
            ("Views dir", os.path.join(self.output_dir, "views", "*.jpg"), os.path.join(self.output_dir, "views", "*.png"))
        ]
        
        for location_name, jpg_pattern, png_pattern in potential_locations:
            jpg_files = glob.glob(jpg_pattern)
            png_files = glob.glob(png_pattern)
            self.logger.info(f"{location_name}: {len(jpg_files)} JPG files, {len(png_files)} PNG files")
        
        # Copy all screenshots to screen_captures directory if they're not already there
        src_screenshots = []
        for path in [
            os.path.join(states_dir, "*.jpg"),
            os.path.join(states_dir, "*.png"),
            os.path.join(self.output_dir, "*.jpg"),
            os.path.join(self.output_dir, "*.png")
        ]:
            import glob
            found_files = glob.glob(path)
            if found_files:
                self.logger.info(f"Found {len(found_files)} matching {path}")
                src_screenshots.extend(found_files)
        
        if src_screenshots:
            import shutil
            self.logger.info(f"Copying {len(src_screenshots)} screenshots to {screenshots_dir}")
            for src in src_screenshots:
                dest = os.path.join(screenshots_dir, os.path.basename(src))
                if not os.path.exists(dest):
                    try:
                        shutil.copy2(src, dest)
                        self.logger.info(f"Copied screenshot {src} to {dest}")
                    except Exception as e:
                        self.logger.warning(f"Error copying screenshot: {e}")
                else:
                    self.logger.info(f"Skipping copy of {src} (already exists at destination)")
        else:
            self.logger.warning("No screenshots found to copy")
            
        # Check screenshot counts for debugging
        import glob
        all_screenshots = glob.glob(os.path.join(screenshots_dir, "*"))
        
        # List actual files for better debugging
        if len(all_screenshots) > 0:
            self.logger.info(f"Found {len(all_screenshots)} screenshots in {screenshots_dir}:")
            for screenshot in all_screenshots[:5]:  # Show first 5 to avoid log spam
                self.logger.info(f"  - {os.path.basename(screenshot)}")
            if len(all_screenshots) > 5:
                self.logger.info(f"  - ... and {len(all_screenshots) - 5} more")
        else:
            # If no screenshots, search recursively to find any images
            self.logger.warning(f"No screenshots found in {screenshots_dir}, searching recursively...")
            try:
                import subprocess
                find_cmd = subprocess.run(
                    ['find', self.output_dir, '-name', '*.png', '-o', '-name', '*.jpg'], 
                    capture_output=True, text=True
                )
                if find_cmd.stdout:
                    self.logger.info(f"Found images with recursive search:\n{find_cmd.stdout.strip()}")
                else:
                    self.logger.warning("No images found in recursive search")
            except Exception as e:
                self.logger.warning(f"Error running recursive search: {e}")
        
        # Create edges.json for navigation graph if needed
        edges_file = os.path.join(self.output_dir, "edges.json")
        if not os.path.exists(edges_file):
            try:
                # Create a default edges file from visited states
                edges = []
                prev_state = None
                visited_states = list(self.memory_adapter.visited_states.keys())
                
                for i, state in enumerate(visited_states):
                    if prev_state:
                        edges.append({
                            "from": prev_state,
                            "to": state,
                            "interaction": "tap"
                        })
                    prev_state = state
                
                with open(edges_file, 'w') as f:
                    import json
                    json.dump(edges, f)
                self.logger.info(f"Created navigation edges file at {edges_file}")
            except Exception as e:
                self.logger.error(f"Error creating edges.json: {e}")
                
        # Check if we have state data for report generation
        self.logger.info(f"Visited states: {len(self.memory_adapter.visited_states)}")
        if not self.memory_adapter.visited_states:
            self.logger.warning("No visited states recorded, reports may be incomplete")
    
    def generate_report(self, assessment_results):
        """
        Generate an HTML report from assessment results.
        
        Args:
            assessment_results: Dictionary containing assessment results
            
        Returns:
            Path to the generated report file
        """
        try:
            self.logger.info("Generating assessment report")
            
            # Add memory insights to the assessment results
            memory_context = self.memory_adapter.get_memory_context_for_gpt()
            if "memory_data" not in assessment_results:
                assessment_results["memory_data"] = {}
            assessment_results["memory_data"]["memory_context"] = memory_context
            
            report_generator = ReportGenerator(self.output_dir, self.app_name, assessment_results)
            report_path = report_generator.generate_report()
            
            if report_path:
                self.logger.info(f"Report generated successfully at {report_path}")
                return report_path
            else:
                self.logger.error("Failed to generate report")
                return None
                
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
    
    def run(self):
        """
        Run the complete assessment process: DroidBot analysis, assessments, and report generation.
        
        Returns:
            Path to the generated report file, or None if unsuccessful
        """
        self.logger.info(f"Starting assessment for {self.app_name}")
        
        # Run DroidBot to collect data
        if not self.run_droidbot():
            self.logger.error("DroidBot analysis failed, cannot continue")
            return None
        
        # Run assessments
        assessment_results = self.run_assessments()
        
        # Generate report
        report_path = self.generate_report(assessment_results)
        
        if report_path:
            self.logger.info(f"Assessment completed successfully. Report: {report_path}")
        else:
            self.logger.error("Assessment completed with errors")
        
        return report_path


# Import for use in run_assessment.py
import sys