"""
Color scheme analysis for mental health app UI assessment.
"""

import os
import logging
import numpy as np
from collections import Counter
import traceback

# Set up logging
logger = logging.getLogger(__name__)

# Handle potential import errors more gracefully
try:
    import cv2
except ImportError:
    logger.error("OpenCV (cv2) is not installed. Please install it with: pip install opencv-python")
    cv2 = None

try:
    from sklearn.cluster import KMeans
except ImportError:
    logger.error("scikit-learn is not installed. Please install it with: pip install scikit-learn")
    KMeans = None

class ColorAnalyzer:
    """
    Analyzes UI screenshots for color schemes and evaluates them based on
    mental health design guidelines and WCAG accessibility standards.
    """
    
    # Color psychology references for mental health apps
    CALMING_COLORS = {
        'blue': [(0, 0, 128), (0, 0, 255)],        # Dark to light blue
        'green': [(0, 128, 0), (144, 238, 144)],   # Dark to light green
        'purple': [(128, 0, 128), (221, 160, 221)] # Purple to lavender
    }
    
    ANXIETY_INDUCING_COLORS = {
        'red': [(128, 0, 0), (255, 0, 0)],         # Dark to light red
        'neon': [(0, 255, 255), (255, 0, 255)]     # Bright/neon colors
    }
    
    def __init__(self, screenshot_dir):
        """
        Initialize the color analyzer with the directory containing screenshots.
        
        Args:
            screenshot_dir (str): Path to directory containing UI screenshots
        """
        self.screenshot_dir = screenshot_dir
        self.screenshots = []
        self.results = {
            'color_scheme': {
                'dominant_colors': [],
                'contrast_issues': [],
                'mental_health_assessment': '',
                'score': 0
            }
        }
    
    def load_screenshots(self):
        """Load all screenshots from the specified directory."""
        if not os.path.exists(self.screenshot_dir):
            raise FileNotFoundError(f"Screenshot directory not found: {self.screenshot_dir}")
            
        self.screenshots = []
        for filename in os.listdir(self.screenshot_dir):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                img_path = os.path.join(self.screenshot_dir, filename)
                img = cv2.imread(img_path)
                if img is not None:
                    self.screenshots.append({
                        'path': img_path,
                        'image': img
                    })
        
        return len(self.screenshots)
    
    def extract_dominant_colors(self, img, k=5):
        """
        Extract k dominant colors from an image using K-means clustering.
        
        Args:
            img (numpy.ndarray): The image to analyze
            k (int): Number of dominant colors to extract
            
        Returns:
            list: List of (color, percentage) tuples
        """
        # Reshape image to be a list of pixels
        pixels = img.reshape(-1, 3)
        
        # Convert from BGR to RGB (OpenCV loads as BGR)
        pixels = pixels[:, ::-1]
        
        # Cluster colors using K-means
        kmeans = KMeans(n_clusters=k, n_init=10)
        kmeans.fit(pixels)
        
        # Get cluster centers (the dominant colors)
        colors = kmeans.cluster_centers_
        
        # Convert to integer RGB values
        colors = colors.astype(int)
        
        # Get the counts of each cluster
        labels = kmeans.labels_
        counts = Counter(labels)
        
        # Calculate percentages
        total_count = sum(counts.values())
        percentages = [count / total_count for count in counts.values()]
        
        # Return as (color, percentage) tuples, sorted by percentage
        return sorted(list(zip(colors, percentages)), key=lambda x: x[1], reverse=True)
    
    def calculate_contrast_ratio(self, color1, color2):
        """
        Calculate contrast ratio between two colors according to WCAG guidelines.
        
        Args:
            color1 (tuple): RGB color tuple
            color2 (tuple): RGB color tuple
            
        Returns:
            float: Contrast ratio (1:1 to 21:1)
        """
        # Convert RGB to relative luminance
        def get_luminance(rgb):
            # Convert RGB values to range [0, 1]
            r, g, b = [x / 255 for x in rgb]
            
            # gamma correction
            r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            
            # Calculate luminance
            return 0.2126 * r + 0.7152 * g + 0.0722 * b
        
        # Get luminance 
        lum1 = get_luminance(color1)
        lum2 = get_luminance(color2)
        
        # Calculate contrast
        if lum1 > lum2:
            return (lum1 + 0.05) / (lum2 + 0.05)
        else:
            return (lum2 + 0.05) / (lum1 + 0.05)
    
    def is_color_in_range(self, color, color_range):
        """
        Check if a color falls within a specified range.
        
        Args:
            color (tuple): RGB color tuple to check
            color_range (list): List containing [min_color, max_color] RGB tuples
            
        Returns:
            bool: True if the color is in range
        """
        min_color, max_color = color_range
        
        # Check each RGB component
        for i in range(3):
            if color[i] < min_color[i] or color[i] > max_color[i]:
                return False
        
        return True
    
    def classify_color(self, color):
        """
        Classify a color as calming, anxiety-inducing, or neutral.
        
        Args:
            color (tuple): RGB color tuple
            
        Returns:
            str: Classification ('calming', 'anxiety_inducing', or 'neutral')
        """
        # Check if color is in calming ranges
        for color_type, ranges in self.CALMING_COLORS.items():
            if self.is_color_in_range(color, ranges):
                return 'calming'
        
        # Check if color is in anxiety-inducing ranges
        for color_type, ranges in self.ANXIETY_INDUCING_COLORS.items():
            if self.is_color_in_range(color, ranges):
                return 'anxiety_inducing'
        
        # If not in any range, it's neutral
        return 'neutral'
    
    def analyze_colors(self):
        """
        Analyze the color schemes of all loaded screenshots.
        
        Returns:
            dict: Analysis results
        """
        if not self.screenshots:
            self.load_screenshots()
            
        if not self.screenshots:
            return {'error': 'No screenshots available for analysis'}
        
        # Process each screenshot
        all_colors = []
        contrast_issues = []
        
        for screenshot in self.screenshots:
            img = screenshot['image']
            path = screenshot['path']
            
            # Extract dominant colors
            dominant_colors = self.extract_dominant_colors(img)
            
            # Store colors with metadata
            colors_with_metadata = []
            for color, percentage in dominant_colors:
                classification = self.classify_color(color)
                colors_with_metadata.append({
                    'color': color.tolist(),
                    'percentage': percentage,
                    'classification': classification,
                    'screenshot': os.path.basename(path)
                })
            
            all_colors.extend(colors_with_metadata)
            
            # Check contrast between top colors
            if len(dominant_colors) >= 2:
                bg_color, _ = dominant_colors[0]  # Assume most dominant is background
                for fg_color, _ in dominant_colors[1:]:
                    contrast = self.calculate_contrast_ratio(bg_color, fg_color)
                    if contrast < 4.5:  # WCAG AA standard for normal text
                        contrast_issues.append({
                            'colors': [bg_color.tolist(), fg_color.tolist()],
                            'contrast_ratio': contrast,
                            'screenshot': os.path.basename(path)
                        })
        
        
        calming_count = sum(1 for color in all_colors if color['classification'] == 'calming')
        anxiety_count = sum(1 for color in all_colors if color['classification'] == 'anxiety_inducing')
        neutral_count = sum(1 for color in all_colors if color['classification'] == 'neutral')
        total_count = len(all_colors)
        
        # Calculate score (0-100)
        # Higher score means better for mental health
        score = int(((calming_count * 1.5) + (neutral_count * 0.8)) / total_count * 100 - 
                   (anxiety_count / total_count * 50) - 
                   (len(contrast_issues) * 10))
        
        # Clamp score to 0-100 range
        score = max(0, min(100, score))
        
        # Create assessment text
        if score >= 80:
            assessment = "Excellent color scheme for mental health applications. The UI uses primarily calming colors with good contrast."
        elif score >= 60:
            assessment = "Good color scheme for mental health applications, but with some areas for improvement."
        elif score >= 40:
            assessment = "Moderate color scheme that could be improved for mental health applications."
        else:
            assessment = "Poor color scheme for mental health applications. The UI uses colors that may induce anxiety or stress."
        
        # Store results
        self.results['color_scheme'] = {
            'dominant_colors': all_colors,
            'contrast_issues': contrast_issues,
            'color_distribution': {
                'calming': calming_count / total_count,
                'neutral': neutral_count / total_count,
                'anxiety_inducing': anxiety_count / total_count
            },
            'mental_health_assessment': assessment,
            'score': score
        }
        
        return self.results


def analyze_colors(screenshot_dir):
    """
    Analyze screenshots in the given directory for color schemes.
    
    Args:
        screenshot_dir (str): Directory containing screenshots
        
    Returns:
        dict: Analysis results
    """
    analyzer = ColorAnalyzer(screenshot_dir)
    return analyzer.analyze_colors()