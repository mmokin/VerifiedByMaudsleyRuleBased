import os
import json
import datetime
import glob
import base64
import logging
import shutil
from jinja2 import Template

class ReportGenerator:
    """
    Generates HTML reports from assessment results.
    """
    
    def __init__(self, output_dir, app_name, assessment_results):
        """
        Initialize the ReportGenerator.
        
        Args:
            output_dir: Directory to save the report to
            app_name: Name of the app being assessed
            assessment_results: Dictionary containing results from various assessments
        """
        self.output_dir = output_dir
        self.app_name = app_name
        self.assessment_results = assessment_results
        self.logger = logging.getLogger('ReportGenerator')
        self.template_html = self._get_default_template()
        
    def _get_default_template(self):
        """
        Returns the default HTML template for the report.
        
        Returns:
            String containing HTML template
        """
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report_title }}</title>
    <style>
        :root {
            --primary-color: #3366cc;
            --secondary-color: #6699cc;
            --accent-color: #99ccff;
            --text-color: #333;
            --light-gray: #f5f5f5;
            --medium-gray: #ddd;
            --dark-gray: #888;
            --success-color: #4CAF50;
            --warning-color: #FFC107;
            --danger-color: #F44336;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            margin: 0;
            padding: 0;
            background-color: #f9f9f9;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            background-color: var(--primary-color);
            color: white;
            padding: 20px;
            border-radius: 8px 8px 0 0;
            margin-bottom: 20px;
        }
        
        header h1 {
            margin: 0;
            font-size: 28px;
        }
        
        .report-meta {
            display: flex;
            justify-content: space-between;
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .report-meta-item {
            display: flex;
            align-items: center;
        }
        
        .report-meta-item i {
            margin-right: 8px;
            color: var(--primary-color);
        }
        
        .score-overview {
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .score-card {
            flex: 1;
            min-width: 200px;
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .score-card h3 {
            margin-top: 0;
            color: var(--primary-color);
        }
        
        .score-value {
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .score-excellent {
            color: var(--success-color);
        }
        
        .score-good {
            color: #2196F3;
        }
        
        .score-moderate {
            color: var(--warning-color);
        }
        
        .score-poor {
            color: var(--danger-color);
        }
        
        .report-section {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .report-section h2 {
            margin-top: 0;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--medium-gray);
            color: var(--primary-color);
        }
        
        .subsection {
            margin-bottom: 15px;
        }
        
        .subsection h3 {
            color: var(--secondary-color);
        }
        
        .color-sample {
            display: inline-block;
            width: 20px;
            height: 20px;
            border-radius: 4px;
            margin-right: 5px;
            vertical-align: middle;
            border: 1px solid var(--medium-gray);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        
        table, th, td {
            border: 1px solid var(--medium-gray);
        }
        
        th {
            background-color: var(--light-gray);
            padding: 10px;
            text-align: left;
        }
        
        td {
            padding: 10px;
        }
        
        .progress-bar-container {
            width: 100%;
            background-color: var(--light-gray);
            border-radius: 4px;
            height: 20px;
            margin: 5px 0;
        }
        
        .progress-bar {
            height: 100%;
            border-radius: 4px;
            background-color: var(--primary-color);
        }
        
        .screenshot-gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .screenshot-item {
            border: 1px solid var(--medium-gray);
            border-radius: 8px;
            overflow: hidden;
            background-color: white;
        }
        
        .screenshot-item img {
            width: 100%;
            height: auto;
            display: block;
        }
        
        .screenshot-caption {
            padding: 10px;
            text-align: center;
            font-size: 14px;
            background-color: var(--light-gray);
        }
        
        .feedback-box {
            background-color: #f0f7ff;
            border-left: 4px solid var(--primary-color);
            padding: 15px;
            margin: 15px 0;
            border-radius: 0 8px 8px 0;
        }
        
        footer {
            text-align: center;
            padding: 20px;
            color: var(--dark-gray);
            font-size: 14px;
        }
        
        .ui-graph {
            width: 100%;
            height: 500px;
            border: 1px solid var(--medium-gray);
            border-radius: 8px;
            margin: 20px 0;
        }
        
        /* For the UTG visualization */
        #utg-visualization {
            width: 100%;
            height: 600px;
            border: 1px solid var(--medium-gray);
            border-radius: 8px;
        }
    </style>
    <!-- Include Vis.js for graph visualization -->
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
</head>
<body>
    <div class="container">
        <header>
            <h1>{{ report_title }}</h1>
        </header>
        
        <div class="report-meta">
            <div class="report-meta-item">
                <i>📱</i>
                <div>
                    <strong>App:</strong> {{ app_name }}
                </div>
            </div>
            <div class="report-meta-item">
                <i>📅</i>
                <div>
                    <strong>Date:</strong> {{ report_date }}
                </div>
            </div>
            <div class="report-meta-item">
                <i>🧪</i>
                <div>
                    <strong>Assessments:</strong> {{ enabled_assessments|join(", ") }}
                </div>
            </div>
        </div>
        
        <div class="score-overview">
            {% for score in scores %}
            <div class="score-card">
                <h3>{{ score.name }}</h3>
                <div class="score-value {{ score.class }}">{{ score.value }}</div>
                <div class="score-description">{{ score.description }}</div>
            </div>
            {% endfor %}
        </div>
        
        <!-- Color Analysis Section -->
        {% if color_report %}
        <div class="report-section">
            <h2>Color Analysis</h2>
            
            <div class="subsection">
                <h3>Color Distribution</h3>
                <p>Analysis of {{ color_report.screenshots_analyzed }} screens.</p>
                
                <table>
                    <tr>
                        <th>Color Type</th>
                        <th>Percentage</th>
                        <th>Distribution</th>
                    </tr>
                    {% if color_report.color_distribution %}
                    <tr>
                        <td>Calming Colors</td>
                        <td>{{ color_report.color_distribution.calming }}</td>
                        <td>
                            <div class="progress-bar-container">
                                <div class="progress-bar" style="width: {{ color_report.color_distribution.calming }}; background-color: #4CAF50;"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Anxiety-Inducing Colors</td>
                        <td>{{ color_report.color_distribution.anxiety_inducing }}</td>
                        <td>
                            <div class="progress-bar-container">
                                <div class="progress-bar" style="width: {{ color_report.color_distribution.anxiety_inducing }}; background-color: #F44336;"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td>Neutral Colors</td>
                        <td>{{ color_report.color_distribution.neutral }}</td>
                        <td>
                            <div class="progress-bar-container">
                                <div class="progress-bar" style="width: {{ color_report.color_distribution.neutral }}; background-color: #9E9E9E;"></div>
                            </div>
                        </td>
                    </tr>
                    {% endif %}
                </table>
            </div>
            
            <div class="subsection">
                <h3>Accessibility Issues</h3>
                {% if color_report.accessibility_issues and color_report.accessibility_issues|length > 0 %}
                <table>
                    <tr>
                        <th>Screen</th>
                        <th>Issue</th>
                    </tr>
                    {% for issue in color_report.accessibility_issues %}
                    <tr>
                        <td>{{ issue.screen }}</td>
                        <td>{{ issue.issue }}</td>
                    </tr>
                    {% endfor %}
                </table>
                {% else %}
                <p>No major accessibility issues detected in the color scheme.</p>
                {% endif %}
            </div>
            
            {% if color_report.gpt_feedback %}
            <div class="subsection">
                <h3>AI Color Analysis</h3>
                <div class="feedback-box">
                    {{ color_report.gpt_feedback|safe }}
                </div>
            </div>
            {% endif %}
        </div>
        {% endif %}
        
        <!-- Navigation Analysis Section -->
        {% if navigation_report %}
        <div class="report-section">
            <h2>Navigation Analysis</h2>
            
            <div class="subsection">
                <h3>Critical Sections</h3>
                <p>Analysis of paths to important app sections:</p>
                
                <table>
                    <tr>
                        <th>Section</th>
                        <th>Found</th>
                        <th>Min Steps</th>
                        <th>Avg Steps</th>
                        <th>Score</th>
                    </tr>
                    {% for section_name, path_data in navigation_report.navigation_paths.items() %}
                    <tr>
                        <td>{{ section_name }}</td>
                        <td>{{ "Yes" if path_data.found else "No" }}</td>
                        <td>{{ path_data.min_steps if path_data.min_steps else "N/A" }}</td>
                        <td>{{ path_data.avg_steps if path_data.avg_steps else "N/A" }}</td>
                        <td>
                            {% if navigation_report.scores.section_scores[section_name] %}
                            {{ navigation_report.scores.section_scores[section_name].score|round(1) }}/100
                            {% else %}
                            N/A
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </table>
            </div>
            
            {% if navigation_report.unreachable_sections and navigation_report.unreachable_sections|length > 0 %}
            <div class="subsection">
                <h3>Unreachable Sections</h3>
                <p>The following sections could not be reached during the assessment:</p>
                <ul>
                    {% for section in navigation_report.unreachable_sections %}
                    <li>{{ section }}</li>
                    {% endfor %}
                </ul>
                <p class="feedback-box">
                    These sections might require specific user input (like login credentials) or may not exist in this app.
                    Consider providing credentials in the configuration or adjusting the critical sections list.
                </p>
            </div>
            {% endif %}
            
            <div class="subsection">
                <h3>Navigation Map</h3>
                <div id="utg-visualization"></div>
                <script type="text/javascript">
                    document.addEventListener('DOMContentLoaded', function() {
                        // UTG data will be injected here
                        const nodes = {{ utg_nodes|safe }};
                        const edges = {{ utg_edges|safe }};
                        
                        const container = document.getElementById('utg-visualization');
                        const data = {
                            nodes: nodes,
                            edges: edges
                        };
                        const options = {
                            nodes: {
                                shape: 'box',
                                margin: 10,
                                font: {
                                    size: 14
                                }
                            },
                            edges: {
                                arrows: 'to',
                                smooth: {
                                    type: 'discrete',
                                    forceDirection: 'none'
                                }
                            },
                            layout: {
                                hierarchical: {
                                    direction: 'LR',
                                    sortMethod: 'directed',
                                    nodeSpacing: 120,
                                    levelSeparation: 150
                                }
                            },
                            physics: false
                        };
                        
                        new vis.Network(container, data, options);
                    });
                </script>
            </div>
        </div>
        {% endif %}
        
        <!-- Button Analysis Section -->
        {% if button_report %}
        <div class="report-section">
            <h2>Button Analysis</h2>
            
            <div class="subsection">
                <h3>Implementation Status</h3>
                <p>{{ button_report.implementation_status }}</p>
                <p>{{ button_report.summary.message }}</p>
            </div>
            
            {% if button_report.placeholder_analysis %}
            <div class="subsection">
                <h3>Future Analysis Metrics</h3>
                <ul>
                    {% for metric in button_report.placeholder_analysis.future_metrics %}
                    <li>{{ metric }}</li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
        </div>
        {% endif %}
        
        <!-- Memory Insights Section -->
        {% if memory_data %}
        <div class="report-section">
            <h2>Memory-Guided Analysis</h2>
            
            <div class="subsection">
                <h3>App Navigation Coverage</h3>
                <p>Explored {{ memory_data.visited_states_count|default(0) }} unique app states during assessment.</p>
                
                {% if memory_data.sections_found %}
                <h4>Critical Sections Found:</h4>
                <ul>
                    {% for section_name, found in memory_data.sections_found.items() %}
                    <li>{{ section_name }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
                
                {% if memory_data.sections_not_found %}
                <h4>Critical Sections Not Found:</h4>
                <ul>
                    {% for section_name in memory_data.sections_not_found %}
                    <li>{{ section_name }}</li>
                    {% endfor %}
                </ul>
                <div class="feedback-box">
                    The sections above were not found during automatic exploration. This could indicate either:
                    <ul>
                        <li>These features don't exist in this app</li>
                        <li>They require specific login credentials or actions to access</li>
                        <li>The navigation sequence to reach them is complex</li>
                    </ul>
                </div>
                {% endif %}
            </div>
            
            {% if memory_data.memory_context %}
            <div class="subsection">
                <h3>Memory Context</h3>
                <div class="feedback-box" style="overflow-wrap: break-word; white-space: normal;">
                    {{ memory_data.memory_context|safe }}
                </div>
            </div>
            {% endif %}
        </div>
        {% endif %}
        
        <!-- Screenshots Gallery -->
        <div class="report-section">
            <h2>App Screenshots</h2>
            <div class="screenshot-gallery">
                {% for screenshot in screenshots %}
                <div class="screenshot-item">
                    <img src="data:image/png;base64,{{ screenshot.data }}" alt="{{ screenshot.name }}">
                    <div class="screenshot-caption">{{ screenshot.name }}</div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <footer>
            <p>Generated by Verified by Maudsley on {{ report_date }}</p>
        </footer>
    </div>
</body>
</html>
'''

    def _load_screenshots(self):
        """
        Load screenshots as base64 encoded strings.
        
        Returns:
            List of dictionaries with screenshot data, filtered to avoid duplicates
        """
        screenshots = []
        unique_structures = set()  # Track unique structure_str to avoid duplicate screens
        
        # First, try to load utg.js to identify unique states by structure_str
        utg_js_paths = [
            os.path.join(self.output_dir, "utg.js"),
            os.path.join(os.path.dirname(self.output_dir), "utg.js")
        ]
        
        structure_to_image_map = {}
        
        # Try to extract structure information from utg.js
        for utg_js_path in utg_js_paths:
            if os.path.exists(utg_js_path):
                try:
                    with open(utg_js_path, 'r') as f:
                        utg_js_content = f.read()
                        # Extract the JSON part (after "var utg = ")
                        if "var utg = " in utg_js_content:
                            json_part = utg_js_content.split("var utg = ", 1)[1].strip()
                            utg_data = json.loads(json_part)
                            
                            # Map structure_str to screenshot paths
                            for node in utg_data.get("nodes", []):
                                if "structure_str" in node and "image" in node:
                                    structure_str = node["structure_str"]
                                    image_path = node["image"]
                                    
                                    # Add to the map, preferring the first image for each structure
                                    if structure_str not in structure_to_image_map:
                                        structure_to_image_map[structure_str] = image_path
                    
                    self.logger.info(f"Found {len(structure_to_image_map)} unique screen structures in UTG data")
                    break
                except Exception as e:
                    self.logger.warning(f"Failed to extract structure information from {utg_js_path}: {e}")
        
        # Search for screenshots in multiple possible locations
        possible_screenshot_dirs = [
            os.path.join(self.output_dir, "states", "screen_captures"),
            os.path.join(self.output_dir, "states"),
            self.output_dir,
            os.path.join(self.output_dir, "screenshots"),
            os.path.join(self.output_dir, "img"),
            os.path.dirname(self.output_dir)  # Parent directory
        ]
        
        # If we have structure information, preferentially use those images
        if structure_to_image_map:
            for structure_str, image_path in structure_to_image_map.items():
                # Fix path separators for the current OS
                image_path = image_path.replace("\\", os.path.sep)
                
                # Try different base directories
                for base_dir in possible_screenshot_dirs:
                    full_path = os.path.join(base_dir, image_path)
                    if os.path.exists(full_path):
                        try:
                            with open(full_path, "rb") as image_file:
                                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                                name = f"Structure_{structure_str[:8]}"
                                screenshots.append({
                                    "name": name,
                                    "data": encoded_string,
                                    "structure_str": structure_str
                                })
                                unique_structures.add(structure_str)
                                break
                        except Exception as e:
                            self.logger.warning(f"Failed to load screenshot {full_path}: {e}")
        
        # If we couldn't load from structure map, fall back to loading all screenshots
        if not screenshots:
            found_screenshots = False
            for screenshots_dir in possible_screenshot_dirs:
                if os.path.exists(screenshots_dir):
                    try:
                        # Support both PNG and JPG files
                        screenshot_files = []
                        screenshot_files.extend(glob.glob(os.path.join(screenshots_dir, "*.png")))
                        screenshot_files.extend(glob.glob(os.path.join(screenshots_dir, "*.jpg")))
                        
                        # Include screen_* files and state_*.png files (common DroidBot naming patterns)
                        filtered_files = [f for f in screenshot_files if 
                                        os.path.basename(f).startswith(("screen_", "state_")) or 
                                        os.path.basename(f).isdigit() or  # For numbered screenshots
                                        "screen" in os.path.basename(f)]
                        
                        self.logger.info(f"Found {len(filtered_files)} screenshot files in {screenshots_dir}")
                        
                        if filtered_files:
                            found_screenshots = True
                            for screenshot_file in filtered_files:
                                try:
                                    with open(screenshot_file, "rb") as image_file:
                                        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                                        name = os.path.basename(screenshot_file).replace(".png", "").replace(".jpg", "")
                                        screenshots.append({
                                            "name": name,
                                            "data": encoded_string
                                        })
                                except Exception as e:
                                    self.logger.warning(f"Failed to load screenshot {screenshot_file}: {e}")
                    except Exception as e:
                        self.logger.warning(f"Error processing screenshots in {screenshots_dir}: {str(e)}")
            
            if not found_screenshots:
                self.logger.warning("No screenshots found in any of the expected directories")
            else:
                self.logger.info(f"Successfully loaded {len(screenshots)} screenshots")
        
        # If we have many screenshots, limit to a reasonable number to avoid excessive report size
        if len(screenshots) > 20:
            self.logger.info(f"Limiting screenshots from {len(screenshots)} to 20 for report clarity")
            return screenshots[:20]
            
        return screenshots
    
    def _check_droidbot_visualization(self):
        """
        Check if DroidBot visualization is available in the output directory.
        
        Returns:
            str: Path to index.html if found, None otherwise
        """
        # Check if index.html exists in the output directory
        index_path = os.path.join(self.output_dir, "index.html")
        if os.path.exists(index_path):
            # Also verify that utg.js exists
            utg_js_path = os.path.join(self.output_dir, "utg.js")
            if os.path.exists(utg_js_path):
                return index_path
        
        # Check in parent directory (common DroidBot output structure)
        parent_dir = os.path.dirname(self.output_dir)
        parent_index_path = os.path.join(parent_dir, "index.html")
        parent_utg_js_path = os.path.join(parent_dir, "utg.js")
        if os.path.exists(parent_index_path) and os.path.exists(parent_utg_js_path):
            return parent_index_path
        
        return None
    
    def _copy_droidbot_resources(self):
        """
        Copy necessary DroidBot visualization resources for embedded UTG view.
        
        Returns:
            Dictionary with resource paths or None if resources not available
        """
        resources = {}
        
        # First check if utg.js exists in output directory
        utg_js_path = os.path.join(self.output_dir, "utg.js")
        if not os.path.exists(utg_js_path):
            # Try to find it in parent directories
            parent_utg_js_path = os.path.join(os.path.dirname(self.output_dir), "utg.js")
            if os.path.exists(parent_utg_js_path):
                utg_js_path = parent_utg_js_path
            else:
                # Search for utg.js recursively
                found_utg_js = glob.glob(os.path.join(self.output_dir, "**", "utg.js"), recursive=True)
                if found_utg_js:
                    utg_js_path = found_utg_js[0]
                else:
                    self.logger.warning("Could not find utg.js file for DroidBot visualization")
                    return None
        
        # Find DroidBot resources
        droidbot_resources = None
        for path in [
            "/mnt/c/Projects/FinalDroid/AutoDroid/droidbot/resources",
            os.path.join(os.path.dirname(os.path.dirname(self.output_dir)), "droidbot", "resources")
        ]:
            if os.path.exists(path):
                droidbot_resources = path
                break
        
        if not droidbot_resources:
            self.logger.warning("Could not find DroidBot resources directory")
            return None
        
        # Create resources directory in output folder
        report_resources_dir = os.path.join(self.output_dir, "droidbot_resources")
        os.makedirs(report_resources_dir, exist_ok=True)
        
        # Copy necessary files
        resources_map = {
            "utg.js": utg_js_path,
            "vis.js": os.path.join(droidbot_resources, "stylesheets", "vis.min.js"),
            "vis.css": os.path.join(droidbot_resources, "stylesheets", "vis.min.css"),
            "droidbotUI.js": os.path.join(droidbot_resources, "stylesheets", "droidbotUI.js"),
            "droidbotUI.css": os.path.join(droidbot_resources, "stylesheets", "droidbotUI.css"),
            "jquery.js": os.path.join(droidbot_resources, "stylesheets", "jquery.min.js")
        }
        
        # Copy files and update resources dictionary with relative paths
        for resource_name, source_path in resources_map.items():
            if os.path.exists(source_path):
                dest_path = os.path.join(report_resources_dir, os.path.basename(source_path))
                try:
                    shutil.copy2(source_path, dest_path)
                    resources[resource_name] = os.path.relpath(dest_path, self.output_dir)
                except Exception as e:
                    self.logger.warning(f"Failed to copy {resource_name} from {source_path}: {e}")
            else:
                self.logger.warning(f"Resource not found: {source_path}")
        
        # If we successfully copied the essential files, return the resources map
        if "utg.js" in resources and "droidbotUI.js" in resources and "vis.js" in resources:
            return resources
        return None
    
    def _prepare_utg_data(self):
        """
        Prepare UTG data for visualization.
        
        Returns:
            Dictionary with UTG data and resources
        """
        utg_data = {
            "has_droidbot_utg": False,
            "embedded_visualization": False,
            "resources": None,
            "utg_nodes": json.dumps([]),
            "utg_edges": json.dumps([])
        }
        
        # Check if we have DroidBot UTG data
        utg_js_path = os.path.join(self.output_dir, "utg.js")
        parent_utg_js_path = os.path.join(os.path.dirname(self.output_dir), "utg.js")
        
        if os.path.exists(utg_js_path) or os.path.exists(parent_utg_js_path):
            utg_data["has_droidbot_utg"] = True
            
            # Try to copy necessary resources for embedded visualization
            resources = self._copy_droidbot_resources()
            if resources:
                utg_data["embedded_visualization"] = True
                utg_data["resources"] = resources
                return utg_data
        
        # If we can't use embedded DroidBot visualization, try to generate our own
        nodes = []
        edges = []
        
        # Try to load UTG from file (either JSON or extract from JS)
        utg_path = os.path.join(self.output_dir, "utg.json")
        if not os.path.exists(utg_path):
            # Try to extract data from utg.js
            if os.path.exists(utg_js_path):
                try:
                    with open(utg_js_path, 'r') as f:
                        utg_js_content = f.read()
                        # Extract the JSON part (after "var utg = ")
                        json_part = utg_js_content.split("var utg = ", 1)[1].strip()
                        utg_data_dict = json.loads(json_part)
                        
                        # Process the data
                        for node in utg_data_dict.get("nodes", []):
                            activity = node.get("activity", "").split('.')[-1]
                            image_path = node.get("image", "")
                            
                            # Try to get the image
                            image_full_path = os.path.join(self.output_dir, image_path.replace("\\", "/"))
                            image_data = None
                            if os.path.exists(image_full_path):
                                with open(image_full_path, "rb") as img_file:
                                    image_data = base64.b64encode(img_file.read()).decode('utf-8')
                            
                            nodes.append({
                                "id": node["id"],
                                "label": node.get("label", activity),
                                "title": node.get("title", f"State: {node['id']}"),
                                "image": f"data:image/png;base64,{image_data}" if image_data else None,
                                "shape": "image" if image_data else "box"
                            })
                        
                        # Process edges
                        for edge in utg_data_dict.get("edges", []):
                            edges.append({
                                "from": edge["from"],
                                "to": edge["to"],
                                "arrows": "to",
                                "title": edge.get("title", ""),
                                "label": edge.get("label", "")
                            })
                        
                        utg_data["utg_nodes"] = json.dumps(nodes)
                        utg_data["utg_edges"] = json.dumps(edges)
                        return utg_data
                        
                except Exception as e:
                    self.logger.error(f"Error extracting UTG data from utg.js: {str(e)}")
            
            # If we couldn't extract from utg.js, try parent directory
            if os.path.exists(parent_utg_js_path):
                try:
                    with open(parent_utg_js_path, 'r') as f:
                        utg_js_content = f.read()
                        # Extract the JSON part (after "var utg = ")
                        json_part = utg_js_content.split("var utg = ", 1)[1].strip()
                        utg_data_dict = json.loads(json_part)
                        
                        # Process nodes and edges similar to above
                        # (code omitted for brevity but is the same)
                        
                        # Process the data
                        for node in utg_data_dict.get("nodes", []):
                            activity = node.get("activity", "").split('.')[-1]
                            image_path = node.get("image", "")
                            
                            # Try to get the image
                            parent_dir = os.path.dirname(self.output_dir)
                            image_full_path = os.path.join(parent_dir, image_path.replace("\\", "/"))
                            image_data = None
                            if os.path.exists(image_full_path):
                                with open(image_full_path, "rb") as img_file:
                                    image_data = base64.b64encode(img_file.read()).decode('utf-8')
                            
                            nodes.append({
                                "id": node["id"],
                                "label": node.get("label", activity),
                                "title": node.get("title", f"State: {node['id']}"),
                                "image": f"data:image/png;base64,{image_data}" if image_data else None,
                                "shape": "image" if image_data else "box"
                            })
                        
                        # Process edges
                        for edge in utg_data_dict.get("edges", []):
                            edges.append({
                                "from": edge["from"],
                                "to": edge["to"],
                                "arrows": "to",
                                "title": edge.get("title", ""),
                                "label": edge.get("label", "")
                            })
                        
                        utg_data["utg_nodes"] = json.dumps(nodes)
                        utg_data["utg_edges"] = json.dumps(edges)
                        return utg_data
                        
                except Exception as e:
                    self.logger.error(f"Error extracting UTG data from parent utg.js: {str(e)}")
        
        # If we reach here, we either use utg.json or have no UTG data
        try:
            if os.path.exists(utg_path):
                with open(utg_path, 'r') as f:
                    utg_data_dict = json.load(f)
                
                # Process nodes and edges similar to above
                # (code omitted for brevity)
        except Exception as e:
            self.logger.error(f"Error processing UTG data: {str(e)}")
        
        utg_data["utg_nodes"] = json.dumps(nodes)
        utg_data["utg_edges"] = json.dumps(edges)
        return utg_data
    
    def _calculate_score_class(self, score):
        """
        Determine the CSS class for a score based on its value.
        
        Args:
            score: Numeric score value
            
        Returns:
            CSS class name
        """
        if score >= 80:
            return "score-excellent"
        elif score >= 60:
            return "score-good"
        elif score >= 40:
            return "score-moderate"
        else:
            return "score-poor"
    
    def generate_report(self):
        """
        Generate the HTML report.
        
        Returns:
            Path to the generated report file
        """
        try:
            # Prepare data for the template
            template_data = {
                "report_title": f"Mental Health UI Assessment: {self.app_name}",
                "app_name": self.app_name,
                "report_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "enabled_assessments": [],
                "scores": [],
                "screenshots": self._load_screenshots()
            }
            
            # Add enabled assessments
            if 'color_report' in self.assessment_results:
                template_data["enabled_assessments"].append("Color Analysis")
                template_data["color_report"] = self.assessment_results['color_report']
                
                # Add color score
                if 'overall_score' in self.assessment_results['color_report']:
                    score_value = round(self.assessment_results['color_report']['overall_score'], 1)
                    template_data["scores"].append({
                        "name": "Color Score",
                        "value": f"{score_value}/100",
                        "class": self._calculate_score_class(score_value),
                        "description": "Evaluation of color scheme appropriateness for mental health"
                    })
            
            if 'navigation_report' in self.assessment_results:
                template_data["enabled_assessments"].append("Navigation Analysis")
                template_data["navigation_report"] = self.assessment_results['navigation_report']
                
                # Add navigation score
                if 'scores' in self.assessment_results['navigation_report'] and 'overall_score' in self.assessment_results['navigation_report']['scores']:
                    score_value = round(self.assessment_results['navigation_report']['scores']['overall_score'], 1)
                    template_data["scores"].append({
                        "name": "Navigation Score",
                        "value": f"{score_value}/100",
                        "class": self._calculate_score_class(score_value),
                        "description": "Evaluation of navigation paths to critical sections"
                    })
            
            if 'button_report' in self.assessment_results:
                template_data["enabled_assessments"].append("Button Analysis")
                template_data["button_report"] = self.assessment_results['button_report']
            
            # Calculate overall score if we have at least one score
            if template_data["scores"]:
                total_score = sum(float(score["value"].split("/")[0]) for score in template_data["scores"])
                avg_score = total_score / len(template_data["scores"])
                template_data["scores"].insert(0, {
                    "name": "Overall Score",
                    "value": f"{round(avg_score, 1)}/100",
                    "class": self._calculate_score_class(avg_score),
                    "description": "Combined score across all assessments"
                })
            
            # Add memory data if available
            if 'memory_data' in self.assessment_results:
                template_data["memory_data"] = self.assessment_results['memory_data']
            
            # Prepare UTG data for visualization
            utg_data = self._prepare_utg_data()
            template_data["utg_nodes"] = utg_data["utg_nodes"]
            template_data["utg_edges"] = utg_data["utg_edges"]
            template_data["has_droidbot_utg"] = utg_data["has_droidbot_utg"]
            
            # Create the template
            template = Template(self.template_html)
            report_html = template.render(**template_data)
            
            # If we have DroidBot UTG data, embed the visualization directly
            if utg_data["embedded_visualization"] and utg_data["resources"]:
                # Create HTML for embedded UTG visualization
                resources = utg_data["resources"]
                
                # Define the embedded DroidBot UTG HTML
                droidbot_utg_html = f'''
                <!-- Embedded DroidBot UTG Visualization -->
                <link rel="stylesheet" type="text/css" href="{resources.get('vis.css', 'droidbot_resources/vis.min.css')}" />
                <link rel="stylesheet" type="text/css" href="{resources.get('droidbotUI.css', 'droidbot_resources/droidbotUI.css')}" />
                
                <div class="subsection">
                    <h3>App Navigation Map</h3>
                    <p>Below is the interactive visualization of all app screens discovered during testing:</p>
                    
                    <div style="margin-bottom: 10px;">
                        <button class="btn btn-primary" onclick="showOriginalUTG()">Show All States</button>
                        <button class="btn btn-success" onclick="clusterStructures()">Cluster by Structures</button>
                        <button class="btn btn-info" onclick="clusterActivities()">Cluster by Activities</button>
                    </div>
                    
                    <div class="row" style="height: 700px; border: 1px solid #ddd; margin: 0;">
                        <div class="col-md-8" style="height: 100%; padding: 0; background-color: #f5f5f5;" id="utg_div"></div>
                        <div class="col-md-4" style="height: 100%; overflow: auto; padding: 10px; border-left: 1px solid #ddd;" id="utg_details">
                            <h4>Details</h4>
                            <p>Click on any state or transition in the graph to see details here.</p>
                        </div>
                    </div>
                    
                    <div style="margin-top: 10px;">
                        <p><strong>How to use:</strong></p>
                        <ul>
                            <li><strong>Show All States</strong>: Shows all unique screens found during testing</li>
                            <li><strong>Cluster by Structures</strong>: Groups screens with the same UI structure (ignoring content)</li>
                            <li><strong>Cluster by Activities</strong>: Groups screens by their Android activity</li>
                            <li>Click on any state to see a larger screenshot and details</li>
                            <li>Click on any arrow to see what action causes the transition</li>
                        </ul>
                    </div>
                </div>
                
                <script type="text/javascript" src="{resources.get('jquery.js', 'droidbot_resources/jquery.min.js')}"></script>
                <script type="text/javascript" src="{resources.get('vis.js', 'droidbot_resources/vis.min.js')}"></script>
                <script type="text/javascript" src="{resources.get('utg.js', 'droidbot_resources/utg.js')}"></script>
                <script type="text/javascript" src="{resources.get('droidbotUI.js', 'droidbot_resources/droidbotUI.js')}"></script>
                
                <script type="text/javascript">
                    // Override the default vis.js options to make the layout more compact
                    document.addEventListener('DOMContentLoaded', function() {{
                        // Override the options before calling draw
                        var originalDraw = window.draw;
                        window.draw = function() {{
                            // Get the original draw function
                            if (typeof originalDraw === 'function') {{
                                // Define custom network options
                                window.customNetworkOptions = {{
                                    nodes: {{
                                        shapeProperties: {{ useBorderWithImage: true }},
                                        borderWidth: 0,
                                        borderWidthSelected: 5,
                                        color: {{
                                            border: '#FFFFFF',
                                            background: '#FFFFFF',
                                            highlight: {{ border: '#0000FF', background: '#0000FF' }}
                                        }},
                                        font: {{ size: 12, color: '#000' }}
                                    }},
                                    edges: {{
                                        color: 'black',
                                        arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }},
                                        font: {{ size: 12, color: '#000' }}
                                    }},
                                    layout: {{
                                        // More compact layout
                                        improvedLayout: true,
                                        hierarchical: {{
                                            enabled: false  // Using physics instead of hierarchical for better spacing
                                        }}
                                    }},
                                    physics: {{
                                        enabled: true,
                                        solver: 'forceAtlas2Based',
                                        forceAtlas2Based: {{
                                            gravitationalConstant: -50,  // More negative = closer nodes
                                            centralGravity: 0.01,
                                            springLength: 100,  // Shorter = closer nodes
                                            springConstant: 0.08,
                                            damping: 0.4,
                                            avoidOverlap: 0.8  // Higher = less overlap
                                        }},
                                        stabilization: {{
                                            enabled: true,
                                            iterations: 1000
                                        }}
                                    }}
                                }};
                                
                                // Call the original draw function
                                originalDraw();
                                
                                // Apply custom options to network
                                if (window.network) {{
                                    window.network.setOptions(window.customNetworkOptions);
                                    
                                    // Force a redraw after a short delay to ensure proper layout
                                    setTimeout(function() {{
                                        window.network.fit({scale: 0.9});  // Fit view to contain all nodes with some padding
                                    // Stabilize and improve layout
                                    window.network.stabilize(300);
                                    }}, 800);
                                }}
                            }}
                        }};
                        
                        // Call the modified draw function
                        if (typeof window.draw === 'function') {{
                            window.draw();
                        }}
                    }});
                </script>
                '''
                
                # Replace the default visualization with DroidBot's version
                if '<div class="subsection">\n                <h3>Navigation Map</h3>' in report_html:
                    report_html = report_html.replace(
                        '<div class="subsection">\n                <h3>Navigation Map</h3>',
                        droidbot_utg_html
                    )
                    
                    # Remove the default visualization div and script if they exist
                    if '<div id="utg-visualization"></div>' in report_html:
                        # Find the start and end of the script block
                        script_start = report_html.find('<script type="text/javascript">', 
                                                        report_html.find('<div id="utg-visualization"></div>'))
                        script_end = report_html.find('</script>', script_start) + 9
                        
                        if script_start > 0 and script_end > script_start:
                            # Remove the visualization div and script
                            report_html = report_html.replace(
                                report_html[report_html.find('<div id="utg-visualization"></div>'):script_end],
                                ''
                            )
            
            # Write the report to file
            report_path = os.path.join(self.output_dir, "maudsley_report.html")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_html)
            
            self.logger.info(f"Report generated at {report_path}")
            return report_path
            
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            return None