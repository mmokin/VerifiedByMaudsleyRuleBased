#!/usr/bin/env python3
"""
Run assessment script for Verified by Maudsley.
This script is called by run_assessment.bat with the required parameters.
"""

import os
import sys
import json
import traceback
import logging
import argparse

# Fix imports based on how the script is called
try:
    from .mental_health_ui_reports import MentalHealthUIReports
    from .credential_manager import CredentialManager
except ImportError:
    # When called directly from bat file
    try:
        # Check if importing from the current directory works
        from mental_health_ui_reports import MentalHealthUIReports
        from credential_manager import CredentialManager
    except ImportError:
        # Add parent directory to path and use package name
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from VerifiedByMaudsley.mental_health_ui_reports import MentalHealthUIReports
        from VerifiedByMaudsley.credential_manager import CredentialManager

def main():
    """
    Main entry point for the assessment process.
    """
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger('run_assessment')
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Verified by Maudsley - Mental Health App UI Assessment")
    parser.add_argument("apk_path", help="Path to the APK file to assess")
    parser.add_argument("output_dir", help="Directory to save assessment results")
    parser.add_argument("-c", "--config", help="Path to a custom config.json file")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Debug info
    logger.info(f"APK Path: {args.apk_path}")
    logger.info(f"Output Directory: {args.output_dir}")
    logger.info(f"Config Path: {args.config}")
    
    apk_path = args.apk_path
    output_dir = args.output_dir
    config_path = args.config if args.config else os.path.join(os.path.dirname(__file__), "config.json")
    
    # Check if APK exists
    if not os.path.exists(apk_path):
        logger.error(f"APK file not found: {apk_path}")
        return 1
    
    # Load configuration
    config_json = None
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config_json = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return 1
    else:
        logger.warning(f"Configuration file not found: {config_path}")
        config_json = {}
    
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Configure file logging
    file_handler = logging.FileHandler(os.path.join(output_dir, "assessment.log"))
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    try:
        # Initialize the credential manager
        credential_manager = CredentialManager(config_json=json.dumps(config_json))
        
        # Initialize the assessment tool
        assessment = MentalHealthUIReports(apk_path, output_dir, config_json)
        
        # Run the assessment
        report_path = assessment.run()
        
        if report_path and os.path.exists(report_path):
            logger.info(f"Assessment completed successfully. Report: {report_path}")
            return 0
        else:
            logger.error("Assessment failed to generate report")
            return 1
    
    except Exception as e:
        logger.error(f"Error during assessment: {str(e)}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())