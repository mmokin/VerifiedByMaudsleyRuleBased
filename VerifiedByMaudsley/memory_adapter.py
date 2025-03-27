import os
import json
import logging
import sys
from typing import Dict, List, Optional, Set, Any

# Add parent directory to import AutoDroid modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MemoryAdapter:
    """
    Adapts AutoDroid memory features for Verified by Maudsley.
    Provides utilities to track visited states, store app-specific knowledge,
    and help with navigation.
    
    This adapter leverages AutoDroid's built-in memory capabilities 
    while adding assessment-specific tracking.
    """
    
    def __init__(self, config_json: Dict[str, Any], output_dir: str):
        """
        Initialize the MemoryAdapter.
        
        Args:
            config_json: Configuration settings
            output_dir: Output directory for storing memory data
        """
        self.logger = logging.getLogger('MemoryAdapter')
        self.config = config_json
        self.output_dir = output_dir
        self.memory_file = os.path.join(output_dir, "memory_data.json")
        
        # Track visited states and sections
        self.visited_states: Set[str] = set()
        self.visited_sections: Dict[str, bool] = {}
        self.current_app_data: Dict[str, Any] = {}
        
        # Track assessment-specific data
        self.assessment_data: Dict[str, Any] = {
            "gpt_insights": [],
            "assessment_results": {},
            "visited_section_elements": {}
        }
        
        # Load baseline data if available
        self.baseline_data: Dict[str, Any] = {}
        if "memory_settings" in self.config and "baseline_data_path" in self.config["memory_settings"]:
            self._load_baseline_data(self.config["memory_settings"]["baseline_data_path"])
        
        # Initialize memory structure
        self._init_memory()
    
    def _load_baseline_data(self, baseline_path: str) -> None:
        """
        Load baseline data from a JSON file.
        
        Args:
            baseline_path: Path to the baseline data file
        """
        try:
            # Get AutoDroid root directory 
            autodroid_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # Try multiple possible paths in a platform-independent way
            possible_paths = [
                baseline_path,  # Original path as provided
                os.path.join(autodroid_root, baseline_path),  # Relative to AutoDroid root
                os.path.join(autodroid_root, "memory", "baseline_data.json"),  # Standard location
                os.path.join(self.output_dir, "baseline_data.json")  # In output directory
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        self.baseline_data = json.load(f)
                    self.logger.info(f"Loaded baseline data from {path}")
                    return
                
            # If we get here, none of the paths worked
            self.logger.warning(f"Baseline data file not found in any of: {possible_paths}")
            
            # Create an empty baseline file in the output directory
            empty_baseline = {}
            baseline_output_path = os.path.join(self.output_dir, "baseline_data.json")
            os.makedirs(os.path.dirname(baseline_output_path), exist_ok=True)
            with open(baseline_output_path, 'w') as f:
                json.dump(empty_baseline, f)
            self.logger.info(f"Created empty baseline data file at {baseline_output_path}")
            self.baseline_data = empty_baseline
        except Exception as e:
            self.logger.error(f"Error loading baseline data: {str(e)}")
    
    def _init_memory(self) -> None:
        """
        Initialize the memory structure.
        """
        memory_data = {
            "visited_states": [],
            "visited_sections": {},
            "app_specific_data": {},
            "navigation_history": [],
            "critical_elements": {},
            "gpt_insights": []
        }
        
        # Initialize with critical sections from config
        if "critical_sections" in self.config:
            for section in self.config["critical_sections"]:
                section_name = section["name"]
                self.visited_sections[section_name] = False
                
                # Add keywords to critical elements for easy detection
                memory_data["critical_elements"][section_name] = {
                    "keywords": section["keywords"],
                    "found_elements": []
                }
        
        # Incorporate app notes if available and enabled and not marked as N/A
        if ("memory_settings" in self.config and 
            self.config["memory_settings"].get("use_app_notes", False) and
            "app_notes" in self.config):
            
            notes = ""
            for note_obj in self.config["app_notes"]:
                if "notes" in note_obj and note_obj["notes"] != "N/A":
                    notes += note_obj["notes"] + " "
                    
            memory_data["app_specific_data"]["notes"] = notes.strip()
        
        # Save initial memory data
        self.current_app_data = memory_data
        self._save_memory_data()
    
    def record_state_visit(self, state_str: str, state_data: Dict[str, Any]) -> None:
        """
        Record a visit to a UI state.
        
        Args:
            state_str: Unique identifier for the state
            state_data: Data about the state
        """
        # Flag for first visit to this state
        is_new_state = state_str not in self.visited_states
        
        # Record state visit
        if is_new_state:
            self.logger.info(f"New state discovered: {state_str[:10]}...")
            self.visited_states.add(state_str)
            self.current_app_data["visited_states"].append(state_str)
        
            # Record navigation history
            self.current_app_data["navigation_history"].append({
                "state": state_str,
                "activity": state_data.get("activity", ""),
                "timestamp": state_data.get("timestamp", ""),
                "screenshot": state_data.get("screenshot", "")
            })
        
            # Check if this state matches any critical section
            self._check_critical_sections(state_data)
            
            # Save memory data for every new state
            self._save_memory_data()
        
        # Record state transition for navigation graph
        if hasattr(self, 'last_state') and self.last_state and self.last_state != state_str:
            self._record_state_transition(self.last_state, state_str, state_data.get("timestamp", ""))
        
        # Always update the last state
        self.last_state = state_str
        
        # Check if we've reached desired unique screen count
        unique_screens_limit = self.config.get("unique_screens", 0)
        if unique_screens_limit > 0 and len(self.visited_states) >= unique_screens_limit:
            self.logger.info(f"Reached limit of {unique_screens_limit} unique screens")
            # Set a flag that can be checked to stop exploration
            self.exploration_complete = True
    
    def _record_state_transition(self, from_state: str, to_state: str, timestamp: str = "") -> None:
        """
        Record a transition between states for building the navigation graph
        
        Args:
            from_state: Source state string
            to_state: Destination state string
            timestamp: Optional timestamp for the transition
        """
        # Initialize transitions list if it doesn't exist
        if not hasattr(self, 'state_transitions'):
            self.state_transitions = []
            
        # Add this transition
        transition = {
            'from': from_state,
            'to': to_state,
            'interaction': 'tap',
            'timestamp': timestamp
        }
        self.state_transitions.append(transition)
        
        # Write transitions to file for NavigationReport
        try:
            edges_file = os.path.join(self.output_dir, 'edges.json')
            with open(edges_file, 'w') as f:
                json.dump(self.state_transitions, f, indent=2)
            self.logger.debug(f"Wrote {len(self.state_transitions)} transitions to {edges_file}")
        except Exception as e:
            self.logger.error(f"Error writing transitions to file: {e}")
    
    def _check_critical_sections(self, state_data: Dict[str, Any]) -> None:
        """
        Check if a state corresponds to any critical section.
        
        Args:
            state_data: Data about the state
        """
        if "critical_elements" not in self.current_app_data:
            return
            
        # Extract text from views
        view_texts = []
        if "views" in state_data:
            for view in state_data["views"]:
                if "text" in view and view["text"]:
                    view_texts.append(view["text"].lower())
                if "content_desc" in view and view["content_desc"]:
                    view_texts.append(view["content_desc"].lower())
                if "resource_id" in view and view["resource_id"]:
                    view_texts.append(view["resource_id"].lower())
        
        # Check each critical section
        for section_name, section_data in self.current_app_data["critical_elements"].items():
            if self.visited_sections.get(section_name, True):
                continue  # Skip already visited sections
                
            keywords = section_data["keywords"]
            activity = state_data.get("activity", "").lower()
            
            # Check if any keyword matches
            for keyword in keywords:
                if keyword.lower() in activity or any(keyword.lower() in text for text in view_texts):
                    self.visited_sections[section_name] = True
                    self.current_app_data["visited_sections"][section_name] = True
                    
                    # Record the matching elements
                    matching_elements = []
                    for text in view_texts:
                        if any(keyword.lower() in text for keyword in keywords):
                            matching_elements.append(text)
                    
                    self.current_app_data["critical_elements"][section_name]["found_elements"] = matching_elements
                    self.logger.info(f"Found critical section: {section_name}")
                    break
    
    def _save_memory_data(self) -> None:
        """
        Save memory data to file.
        """
        try:
            # Merge assessment data into memory data
            memory_data = {
                **self.current_app_data,
                "assessment_data": self.assessment_data,
                "visited_states_count": len(self.visited_states),
                "visited_sections": self.visited_sections
            }
            
            with open(self.memory_file, 'w') as f:
                json.dump(memory_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving memory data: {str(e)}")
            
    def add_assessment_result(self, assessment_name: str, result: Dict[str, Any]) -> None:
        """
        Add assessment result to memory.
        
        Args:
            assessment_name: Name of the assessment
            result: Assessment result data
        """
        self.assessment_data["assessment_results"][assessment_name] = result
        self._save_memory_data()
    
    def should_revisit_state(self, state_str: str) -> bool:
        """
        Determine if a state should be revisited.
        
        Args:
            state_str: Unique identifier for the state
            
        Returns:
            True if the state should be revisited, False otherwise
        """
        # Check if revisit prevention is enabled
        if ("memory_settings" in self.config and 
            self.config["memory_settings"].get("avoid_revisits", False)):
            return state_str not in self.visited_states
            
        # By default, allow revisits
        return True
    
    def get_unvisited_sections(self) -> List[str]:
        """
        Get the names of critical sections that haven't been visited.
        
        Returns:
            List of section names
        """
        return [name for name, visited in self.visited_sections.items() if not visited]
    
    def get_memory_context_for_gpt(self) -> str:
        """
        Generate a context string for GPT based on memory data.
        
        Returns:
            Context string
        """
        context = "<p><strong>App Navigation History:</strong></p>"
        
        # Add visited sections
        visited_sections = [name for name, visited in self.visited_sections.items() if visited]
        if visited_sections:
            context += f"<p>Found sections: {', '.join(visited_sections)}</p>"
        
        # Add unvisited sections
        unvisited_sections = self.get_unvisited_sections()
        if unvisited_sections:
            context += f"<p>Sections not found: {', '.join(unvisited_sections)}</p>"
        
        # Add app notes if available
        if "app_specific_data" in self.current_app_data and "notes" in self.current_app_data["app_specific_data"]:
            context += f"<p><strong>App Notes:</strong> {self.current_app_data['app_specific_data']['notes']}</p>"
        
        # Add navigation statistics
        context += f"<p>Navigated through {len(self.visited_states)} unique screens.</p>"
        
        # Add GPT insights from assessment data - avoid duplication
        unique_insights = {}  # Use a dict to store unique insights by content
        
        # First, process color report insights to avoid duplication
        if self.assessment_data["gpt_insights"]:
            for insight in self.assessment_data["gpt_insights"]:
                # Create a unique key based on the insight text
                insight_text = insight['insight'].lower()
                if insight_text not in unique_insights:
                    unique_insights[insight_text] = insight
        
        if unique_insights:
            context += "<p><strong>Key Insights:</strong></p><ul>"
            for insight in unique_insights.values():
                context += f"<li><strong>{insight['category'].title()}:</strong> {insight['insight']}</li>"
            context += "</ul>"
        
        return context
        
    def get_assessment_memory_context(self) -> str:
        """
        Generate a context string based on assessment memory.
        This is an alias for get_memory_context_for_gpt for backward compatibility.
        
        Returns:
            Context string for assessment reports
        """
        return self.get_memory_context_for_gpt()
    
    def add_gpt_insight(self, insight: str, category: str) -> None:
        """
        Add an insight from GPT to the memory.
        
        Args:
            insight: The insight text
            category: Category of the insight (e.g., "color", "navigation")
        """
        if "gpt_insights" not in self.current_app_data:
            self.current_app_data["gpt_insights"] = []
            
        self.current_app_data["gpt_insights"].append({
            "category": category,
            "insight": insight
        })
        
        # Also add to assessment-specific data
        self.assessment_data["gpt_insights"].append({
            "category": category,
            "insight": insight
        })
        
        # Save after adding insights
        self._save_memory_data()
    
    def get_credentials(self) -> Dict[str, str]:
        """
        Get credentials from config.
        
        Returns:
            Dictionary with username and password
        """
        if "credentials" in self.config and len(self.config["credentials"]) > 0:
            cred = self.config["credentials"][0]
            return {
                "username": cred.get("username", ""),
                "password": cred.get("password", "")
            }
        return {"username": "", "password": ""}
    
    def should_use_credentials(self, state_data: Dict[str, Any]) -> bool:
        """
        Determine if credentials should be used on the current state.
        
        Args:
            state_data: Data about the state
            
        Returns:
            True if credentials should be used
        """
        # Extract text from views
        view_texts = []
        if "views" in state_data:
            for view in state_data["views"]:
                if "text" in view and view["text"]:
                    view_texts.append(view["text"].lower())
                if "content_desc" in view and view["content_desc"]:
                    view_texts.append(view["content_desc"].lower())
                if "resource_id" in view and view["resource_id"]:
                    view_texts.append(view["resource_id"].lower())
        
        # Keywords that indicate a login screen
        login_keywords = ["login", "sign in", "username", "email", "password"]
        
        # Check if any keyword matches
        for keyword in login_keywords:
            if any(keyword in text for text in view_texts):
                return True
                
        return False