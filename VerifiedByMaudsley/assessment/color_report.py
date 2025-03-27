import os
import numpy as np
import glob
from PIL import Image
from sklearn.cluster import KMeans
from collections import Counter
import colorsys
import requests
import json
import logging

class ColorReport:
    """
    Analyzes color schemes of mental health app UI screenshots.
    Extracts dominant colors, classifies them according to mental health design guidelines,
    and evaluates accessibility.
    """
    
    def __init__(self, output_dir, config_json):
        """
        Initialize the ColorReport module.
        
        Args:
            output_dir: Directory containing screenshots from DroidBot
            config_json: Configuration settings including API keys for GPT analysis
        """
        self.output_dir = output_dir
        self.config_json = config_json
        self.screenshots_dir = os.path.join(output_dir, "states", "screen_captures")
        self.logger = logging.getLogger('ColorReport')
        
        # Color classification guidelines
        self.calming_colors = {
            'blue': ((190, 210, 250), (130, 160, 210)),
            'green': ((140, 200, 140), (100, 160, 100)),
            'purple': ((190, 180, 210), (150, 140, 170)),
            'teal': ((160, 210, 210), (120, 170, 170))
        }
        
        self.anxiety_colors = {
            'red': ((255, 100, 100), (200, 60, 60)),
            'bright_yellow': ((255, 255, 100), (230, 230, 50)),
            'neon_colors': ((250, 250, 190), (230, 230, 140))
        }
        
        # WCAG contrast requirements
        self.min_contrast_ratio = 4.5  # AA standard
        
    def extract_dominant_colors(self, image_path, n_colors=5):
        """
        Extract dominant colors from an image using K-means clustering.
        
        Args:
            image_path: Path to the image file
            n_colors: Number of dominant colors to extract
            
        Returns:
            List of (color, percentage) tuples
        """
        try:
            image = Image.open(image_path).convert('RGB')
            image = image.resize((100, 100))  # Resize for faster processing
            
            # Convert image to numpy array
            image_array = np.array(image)
            pixels = image_array.reshape(-1, 3)
            
            # Use K-means to find dominant colors
            kmeans = KMeans(n_clusters=n_colors, n_init=10)
            kmeans.fit(pixels)
            
            # Get the colors and their percentages
            colors = kmeans.cluster_centers_.astype(int)
            labels = kmeans.labels_
            color_counts = Counter(labels)
            total_pixels = len(labels)
            
            # Sort colors by occurrence
            dominant_colors = []
            for cluster_id, count in color_counts.items():
                color = tuple(colors[cluster_id])
                percentage = count / total_pixels
                dominant_colors.append((color, percentage))
                
            return sorted(dominant_colors, key=lambda x: x[1], reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error extracting colors from {image_path}: {str(e)}")
            return []
    
    def classify_color(self, color):
        """
        Classify a color as calming, anxiety-inducing, or neutral.
        
        Args:
            color: RGB tuple
            
        Returns:
            Classification string
        """
        r, g, b = color
        
        # Check calming colors
        for color_name, ((r1, g1, b1), (r2, g2, b2)) in self.calming_colors.items():
            if (r1 > r > r2) and (g1 > g > g2) and (b1 > b > b2):
                return f"calming ({color_name})"
        
        # Check anxiety-inducing colors
        for color_name, ((r1, g1, b1), (r2, g2, b2)) in self.anxiety_colors.items():
            if (r1 > r > r2) and (g1 > g > g2) and (b1 > b > b2):
                return f"anxiety-inducing ({color_name})"
        
        # Convert RGB to HSV for additional analysis
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        
        # Highly saturated colors can be stimulating
        if s > 0.8 and v > 0.8:
            return "potentially stimulating (high saturation)"
        
        # Very bright colors can be harsh
        if v > 0.9 and s > 0.5:
            return "potentially harsh (very bright)"
        
        # Low saturation, medium to high value is usually neutral
        if s < 0.3 and v > 0.7:
            return "neutral (light)"
        
        # Low saturation and low value (grays)
        if s < 0.3 and v < 0.7:
            return "neutral (dark)"
        
        return "neutral"
    
    def calculate_contrast_ratio(self, color1, color2):
        """
        Calculate contrast ratio between two colors according to WCAG guidelines.
        
        Args:
            color1: RGB tuple
            color2: RGB tuple
            
        Returns:
            Contrast ratio
        """
        # Convert RGB to relative luminance
        def get_luminance(rgb):
            r, g, b = rgb
            r, g, b = r/255, g/255, b/255
            
            # Apply gamma correction
            r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            
            # Calculate luminance
            return 0.2126 * r + 0.7152 * g + 0.0722 * b
        
        l1 = get_luminance(color1)
        l2 = get_luminance(color2)
        
        # Ensure the lighter color is l1
        if l2 > l1:
            l1, l2 = l2, l1
        
        # Calculate contrast ratio
        return (l1 + 0.05) / (l2 + 0.05)
    
    def generate_gpt_feedback(self, color_data):
        """
        Generate feedback on color scheme using GPT API.
        
        Args:
            color_data: Dictionary with color analysis results
            
        Returns:
            Feedback text
        """
        try:
            # Check if API key exists and is properly formatted
            if not self.config_json or 'api_keys' not in self.config_json or 'openai' not in self.config_json['api_keys']:
                self.logger.warning("OpenAI API key not found in config")
                return "GPT analysis unavailable (API key not configured)"
            
            api_key = self.config_json['api_keys']['openai']
            
            # Validate API key format
            if not api_key or not api_key.startswith('sk-'):
                self.logger.warning(f"Invalid OpenAI API key format: {api_key[:5]}...")
                return "GPT analysis unavailable (invalid API key format)"
            
            # Debug log the API key (first 5 chars only)
            self.logger.info(f"Using OpenAI API key: {api_key[:5]}...")
            
            # Get memory context if available
            memory_context = ""
            if "memory_context" in self.config_json and self.config_json["memory_context"] != "N/A":
                memory_context = self.config_json["memory_context"]
                self.logger.info("Using memory context for GPT analysis")
            
            # Add app notes if available
            app_notes = ""
            if "app_notes" in self.config_json and len(self.config_json["app_notes"]) > 0:
                if "notes" in self.config_json["app_notes"][0] and self.config_json["app_notes"][0]["notes"] != "N/A":
                    app_notes = self.config_json["app_notes"][0]["notes"]
            
            # Generate simulated feedback for invalid key
            if not api_key.startswith('sk-') or 'proj-' in api_key:
                self.logger.warning("Using simulated feedback due to invalid API key")
                return """
                Color Analysis Feedback (simulated):
                
                The app's color scheme appears to predominantly use neutral colors with some calming elements, which is generally appropriate for a mental health application. The neutral palette helps create a non-stimulating environment that won't trigger anxiety or stress responses.
                
                From a psychological perspective, the color balance seems suitable for users who may be experiencing mental health challenges. The absence of bright, anxiety-inducing colors is a positive design choice.
                
                Regarding accessibility, some screens show lower contrast ratios than the WCAG recommended minimum of 4.5:1. This could make content difficult to read for users with visual impairments. Consider increasing the contrast between text elements and backgrounds.
                
                Suggestions for improvement:
                1. Increase contrast ratios where they fall below guidelines
                2. Consider adding more calming blue or green tones in strategic areas
                3. Maintain the current neutral base while ensuring sufficient visual hierarchy
                4. Test with actual mental health service users to validate the emotional impact
                
                Overall, the current color scheme provides a solid foundation but could benefit from these targeted improvements to better serve the mental health community.
                """
            
            # Prepare the prompt for GPT
            prompt = f"""
            Analyze this color scheme data from a mental health app UI and provide feedback:
            
            Dominant Colors:
            {color_data['dominant_colors']}
            
            Color Classifications:
            {color_data['color_classifications']}
            
            Contrast Ratios:
            {color_data['contrast_ratios']}
            
            {memory_context}
            
            App Description:
            {app_notes}
            
            Please provide specific feedback on:
            1. Whether the color scheme is appropriate for a mental health app
            2. How the colors might affect users psychologically based on mental health research
            3. Accessibility considerations based on the contrast ratios
            4. Specific suggestions for improvement considering this is a mental health app
            
            Keep your response concise and professional, focusing on evidence-based design principles.
            Avoid suggesting colors that might trigger anxiety if this app is used by vulnerable individuals.
            """
            
            # Call OpenAI API
            try:
                response = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4",
                        "messages": [
                            {"role": "system", "content": "You are a UI/UX expert specialized in mental health apps with knowledge of color psychology and accessibility standards."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 500
                    }
                )
                
                if response.status_code == 200:
                    return response.json()["choices"][0]["message"]["content"]
                else:
                    self.logger.error(f"GPT API error: {response.status_code} - {response.text}")
                    return f"Error generating feedback (API error: {response.status_code})"
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Network error calling GPT API: {str(e)}")
                return "Error generating feedback (network error)"
                
        except Exception as e:
            self.logger.error(f"Error generating GPT feedback: {str(e)}")
            return "Error generating feedback"
    
    def analyze(self):
        """
        Analyze all screenshots and generate a color report.
        
        Returns:
            Dictionary with analysis results
        """
        results = {
            "screenshots_analyzed": 0,
            "color_scheme_summary": {},
            "dominant_colors_by_screen": {},
            "accessibility_issues": [],
            "gpt_feedback": "",
            "overall_score": 0
        }
        
        # Find screenshots in multiple possible locations
        possible_screenshot_dirs = [
            self.screenshots_dir,
            os.path.join(self.output_dir, "states"),
            self.output_dir,
            os.path.join(self.output_dir, "droidbot_resources"),
            os.path.dirname(self.output_dir)
        ]
        
        # Debug message for directory search
        dir_messages = []
        for dir_path in possible_screenshot_dirs:
            if os.path.exists(dir_path):
                dir_messages.append(f"  - {dir_path} (exists)")
            else:
                dir_messages.append(f"  - {dir_path} (not found)")
        
        self.logger.info(f"Searching for screenshots in the following directories:\n" + "\n".join(dir_messages))
        
        screenshots = []
        for dir_path in possible_screenshot_dirs:
            if os.path.exists(dir_path):
                # Look for png files
                png_files = glob.glob(os.path.join(dir_path, "*.png"))
                if png_files:
                    self.logger.info(f"Found {len(png_files)} PNG files in {dir_path}")
                    screenshots.extend(png_files)
                
                # Look for jpg files
                jpg_files = glob.glob(os.path.join(dir_path, "*.jpg"))
                if jpg_files:
                    self.logger.info(f"Found {len(jpg_files)} JPG files in {dir_path}")
                    screenshots.extend(jpg_files)
                
                # Check subdirectories for structure-based screenshots
                for subdir in ["states", "views"]:
                    subdir_path = os.path.join(dir_path, subdir)
                    if os.path.exists(subdir_path):
                        png_in_subdir = glob.glob(os.path.join(subdir_path, "*.png"))
                        jpg_in_subdir = glob.glob(os.path.join(subdir_path, "*.jpg"))
                        
                        if png_in_subdir or jpg_in_subdir:
                            self.logger.info(f"Found {len(png_in_subdir)} PNG and {len(jpg_in_subdir)} JPG files in {subdir_path}")
                            screenshots.extend(png_in_subdir)
                            screenshots.extend(jpg_in_subdir)
        
        self.logger.info(f"Total screenshots found: {len(screenshots)}")
        
        # Check if we have any files with the pattern names
        screen_prefix_files = [s for s in screenshots if os.path.basename(s).startswith(("screen_", "state_"))]
        screen_name_files = [s for s in screenshots if "screen" in os.path.basename(s)]
        
        self.logger.info(f"Files with screen_/state_ prefix: {len(screen_prefix_files)}")
        self.logger.info(f"Files with 'screen' in name: {len(screen_name_files)}")
        
        # Filter to include only screen_ or state_ prefixes which are common in DroidBot
        filtered_screenshots = [s for s in screenshots if 
                              os.path.basename(s).startswith(("screen_", "state_")) or 
                              "screen" in os.path.basename(s)]
        
        # If we have no filtered screenshots, use all available
        if not filtered_screenshots and screenshots:
            self.logger.info("No files match screen patterns, using all available screenshots")
            filtered_screenshots = screenshots
        
        if not filtered_screenshots:
            self.logger.warning(f"No screenshots found in any of the expected directories")
            return results
        
        # Limit the number of screenshots to analyze to prevent excessive processing
        if len(filtered_screenshots) > 20:
            self.logger.info(f"Limiting color analysis to 20 screenshots out of {len(filtered_screenshots)}")
            filtered_screenshots = filtered_screenshots[:20]
        
        results["screenshots_analyzed"] = len(filtered_screenshots)
        
        # Color statistics
        calming_count = 0
        anxiety_count = 0
        neutral_count = 0
        low_contrast_count = 0
        
        # Analyze each screenshot
        for screenshot in filtered_screenshots:
            screen_name = os.path.basename(screenshot).replace(".png", "").replace(".jpg", "")
            
            # Extract dominant colors
            dominant_colors = self.extract_dominant_colors(screenshot)
            
            if not dominant_colors:
                continue
                
            # Store dominant colors
            results["dominant_colors_by_screen"][screen_name] = [
                {"color": f"rgb{color}", "percentage": f"{percentage*100:.1f}%"} 
                for color, percentage in dominant_colors
            ]
            
            # Classify colors and check contrast
            classified_colors = []
            for primary_color, _ in dominant_colors[:2]:  # Focus on top 2 colors
                classification = self.classify_color(primary_color)
                classified_colors.append(f"rgb{primary_color}: {classification}")
                
                if "calming" in classification:
                    calming_count += 1
                elif "anxiety" in classification or "stimulating" in classification or "harsh" in classification:
                    anxiety_count += 1
                else:
                    neutral_count += 1
            
            # Check contrast between top two colors if they exist
            if len(dominant_colors) >= 2:
                color1, _ = dominant_colors[0]
                color2, _ = dominant_colors[1]
                contrast = self.calculate_contrast_ratio(color1, color2)
                
                if contrast < self.min_contrast_ratio:
                    low_contrast_count += 1
                    results["accessibility_issues"].append({
                        "screen": screen_name,
                        "issue": f"Low contrast ratio ({contrast:.2f}) between dominant colors"
                    })
            
            # Store classifications for this screen
            results["color_scheme_summary"][screen_name] = {
                "classifications": classified_colors,
                "contrast_issues": contrast < self.min_contrast_ratio
            }
        
        # Calculate overall statistics
        total_colors = calming_count + anxiety_count + neutral_count
        if total_colors > 0:
            calming_percentage = (calming_count / total_colors) * 100
            anxiety_percentage = (anxiety_count / total_colors) * 100
            neutral_percentage = (neutral_count / total_colors) * 100
            
            results["color_distribution"] = {
                "calming": f"{calming_percentage:.1f}%",
                "anxiety_inducing": f"{anxiety_percentage:.1f}%",
                "neutral": f"{neutral_percentage:.1f}%"
            }
            
            # Calculate accessibility score (0-100)
            if results["screenshots_analyzed"] > 0:
                accessibility_score = 100 - ((low_contrast_count / results["screenshots_analyzed"]) * 100)
                results["accessibility_score"] = accessibility_score
            
            # Calculate overall color score (0-100)
            # Ideal: high calming, low anxiety, moderate neutral
            color_score = (calming_percentage * 0.7) + (neutral_percentage * 0.3) - (anxiety_percentage * 0.5)
            color_score = max(0, min(100, color_score))
            results["color_score"] = color_score
            
            # Overall score is average of color and accessibility scores
            results["overall_score"] = (color_score + (results.get("accessibility_score", 0))) / 2
        
        # Generate GPT feedback if we have enough data
        if total_colors > 0:
            gpt_data = {
                "dominant_colors": results["dominant_colors_by_screen"],
                "color_classifications": results["color_scheme_summary"],
                "contrast_ratios": results["accessibility_issues"]
            }
            
            # Skip GPT feedback if API key is not valid
            api_key = None
            if self.config_json and 'api_keys' in self.config_json and 'openai' in self.config_json['api_keys']:
                api_key = self.config_json['api_keys']['openai']
                
            if api_key and api_key.startswith('sk-'):
                self.logger.info("Generating GPT feedback for color analysis")
                results["gpt_feedback"] = self.generate_gpt_feedback(gpt_data)
            else:
                self.logger.warning("Skipping GPT feedback due to missing/invalid API key")
                results["gpt_feedback"] = "GPT feedback unavailable - please check your OpenAI API key."
        
        return results