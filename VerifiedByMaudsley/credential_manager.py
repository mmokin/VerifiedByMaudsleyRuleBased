import json
import os
import logging
from typing import Dict, Any, Optional, List

class CredentialManager:
    """
    Manages credentials and app-specific information stored in the config file.
    Provides secure access to sensitive information needed for app testing.
    """
    
    def __init__(self, config_path: str = None, config_json: str = None):
        """
        Initialize the CredentialManager.
        
        Args:
            config_path: Path to the config JSON file (optional)
            config_json: JSON string with configuration (optional)
            
        At least one of config_path or config_json must be provided.
        """
        self.logger = logging.getLogger('CredentialManager')
        self.config: Dict[str, Any] = {}
        
        # Load configuration
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.config = json.load(f)
                self.logger.info(f"Loaded credentials from {config_path}")
            except json.JSONDecodeError:
                self.logger.error(f"Invalid JSON in config file: {config_path}")
            except Exception as e:
                self.logger.error(f"Error loading config file: {str(e)}")
        elif config_json:
            try:
                self.config = json.loads(config_json)
                self.logger.info("Loaded credentials from provided JSON")
            except json.JSONDecodeError:
                self.logger.error("Invalid JSON string provided")
            except Exception as e:
                self.logger.error(f"Error loading JSON string: {str(e)}")
                
        # Validate configuration structure
        self._validate_config()
    
    def _validate_config(self):
        """
        Validate the configuration structure.
        """
        required_sections = ["credentials", "api_keys"]
        
        for section in required_sections:
            if section not in self.config:
                self.logger.warning(f"Missing '{section}' section in configuration")
                self.config[section] = {}
    
    def get_credentials(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get credentials for a specific app or all credentials.
        
        Args:
            app_name: Name of the app to get credentials for (optional)
            
        Returns:
            Dictionary containing credentials
        """
        if "credentials" not in self.config:
            return {}
            
        if app_name:
            # Return credentials for a specific app
            for app_credentials in self.config["credentials"]:
                if app_credentials.get("app_name") == app_name:
                    # Filter out N/A values
                    return {k: v for k, v in app_credentials.items() if v != "N/A"}
            return {}
        else:
            # Return all credentials, filtering out N/A values in each credential set
            filtered_credentials = []
            for cred in self.config["credentials"]:
                filtered_cred = {k: v for k, v in cred.items() if v != "N/A"}
                if filtered_cred:  # Only add if there are non-N/A fields
                    filtered_credentials.append(filtered_cred)
            return filtered_credentials
    
    def get_api_key(self, service_name: str) -> str:
        """
        Get an API key for a specific service.
        
        Args:
            service_name: Name of the service (e.g., "openai", "azure")
            
        Returns:
            API key string or empty string if not found
        """
        if "api_keys" not in self.config or service_name not in self.config["api_keys"]:
            return ""
            
        return self.config["api_keys"][service_name]
    
    def get_critical_sections(self) -> List[Dict[str, Any]]:
        """
        Get the list of critical sections for navigation analysis.
        
        Returns:
            List of dictionaries with critical section definitions
        """
        if "critical_sections" not in self.config:
            return []
            
        return self.config["critical_sections"]
    
    def get_app_notes(self, app_name: str) -> str:
        """
        Get app-specific notes.
        
        Args:
            app_name: Name of the app
            
        Returns:
            Notes string or empty string if not found
        """
        if "app_notes" not in self.config:
            return ""
            
        for app_note in self.config["app_notes"]:
            if app_note.get("app_name") == app_name:
                return app_note.get("notes", "")
                
        return ""
    
    def save_config(self, config_path: str) -> bool:
        """
        Save the current configuration to a file.
        
        Args:
            config_path: Path to save the config file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            self.logger.info(f"Configuration saved to {config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            return False
    
    def add_credentials(self, app_name: str, username: str, password: str) -> bool:
        """
        Add or update credentials for an app.
        
        Args:
            app_name: Name of the app
            username: Username
            password: Password
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if "credentials" not in self.config:
                self.config["credentials"] = []
                
            # Check if app already exists
            for app_credentials in self.config["credentials"]:
                if app_credentials.get("app_name") == app_name:
                    app_credentials["username"] = username
                    app_credentials["password"] = password
                    self.logger.info(f"Updated credentials for {app_name}")
                    return True
            
            # Add new credentials
            self.config["credentials"].append({
                "app_name": app_name,
                "username": username,
                "password": password
            })
            self.logger.info(f"Added credentials for {app_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding credentials: {str(e)}")
            return False
    
    def add_api_key(self, service_name: str, api_key: str) -> bool:
        """
        Add or update an API key.
        
        Args:
            service_name: Name of the service
            api_key: API key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if "api_keys" not in self.config:
                self.config["api_keys"] = {}
                
            self.config["api_keys"][service_name] = api_key
            self.logger.info(f"Added/updated API key for {service_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding API key: {str(e)}")
            return False