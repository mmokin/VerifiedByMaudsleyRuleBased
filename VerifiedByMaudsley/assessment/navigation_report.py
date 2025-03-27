import os
import json
import glob
import logging
import networkx as nx
from collections import defaultdict

class NavigationReport:
    """
    Analyzes app navigation by measuring steps required to reach critical sections,
    evaluating navigation efficiency and depth.
    """
    
    def __init__(self, output_dir, config_json):
        """
        Initialize the NavigationReport module.
        
        Args:
            output_dir: Directory containing UTG data from DroidBot
            config_json: Configuration settings including critical sections to analyze
        """
        self.output_dir = output_dir
        self.config_json = config_json
        self.logger = logging.getLogger('NavigationReport')
        
        # Load critical sections from config if available
        self.critical_sections = []
        if config_json and 'critical_sections' in config_json:
            self.critical_sections = config_json['critical_sections']
        
        # Default critical sections if none specified
        self.default_critical_sections = [
            {"name": "Login/Registration", "keywords": ["login", "sign in", "register", "sign up"]},
            {"name": "Profile", "keywords": ["profile", "account", "settings"]},
            {"name": "Support/Help", "keywords": ["help", "support", "faq", "contact"]},
            {"name": "Main Features", "keywords": ["dashboard", "home", "main", "activities"]},
            {"name": "Privacy Settings", "keywords": ["privacy", "permissions", "security"]}
        ]
        
        # UTG graph paths
        self.utg_json_path = os.path.join(output_dir, "utg.json")
        self.utg_structure = None
        self.utg_graph = None
    
    def load_utg_data(self):
        """
        Load UTG (UI Transition Graph) data from DroidBot output.
        
        Returns:
            True if loading was successful, False otherwise
        """
        try:
            if os.path.exists(self.utg_json_path):
                with open(self.utg_json_path, 'r') as f:
                    self.utg_structure = json.load(f)
                self.logger.info(f"Loaded UTG from {self.utg_json_path}")
                return True
            
            # If no UTG JSON, try to build from state files
            states_dir = os.path.join(self.output_dir, "states")
            if os.path.exists(states_dir):
                state_files = glob.glob(os.path.join(states_dir, "*.json"))
                if state_files:
                    self.utg_structure = {
                        "nodes": [],
                        "edges": []
                    }
                    
                    # Load states as nodes
                    for state_file in state_files:
                        with open(state_file, 'r') as f:
                            state_data = json.load(f)
                            state_id = os.path.basename(state_file).replace(".json", "")
                            self.utg_structure["nodes"].append({
                                "id": state_id,
                                "package": state_data.get("foreground_package", ""),
                                "activity": state_data.get("foreground_activity", ""),
                                "state_str": state_data.get("state_str", ""),
                                "views": state_data.get("views", [])
                            })
                    
                    # Try to load trace.json for edges
                    trace_path = os.path.join(self.output_dir, "events", "trace.json")
                    if os.path.exists(trace_path):
                        with open(trace_path, 'r') as f:
                            trace_data = json.load(f)
                            for event in trace_data:
                                if "from_state" in event and "to_state" in event:
                                    self.utg_structure["edges"].append({
                                        "from": event["from_state"],
                                        "to": event["to_state"],
                                        "event": event.get("event_type", "")
                                    })
                    
                    self.logger.info(f"Reconstructed UTG from {len(state_files)} state files")
                    return True
            
            self.logger.error(f"Could not find UTG data at {self.utg_json_path} or in states directory")
            return False
            
        except Exception as e:
            self.logger.error(f"Error loading UTG data: {str(e)}")
            return False
    
    def build_graph(self):
        """
        Build a NetworkX graph representation of the UI states and transitions.
        
        Returns:
            True if graph building was successful, False otherwise
        """
        if not self.utg_structure:
            return False
        
        try:
            G = nx.DiGraph()
            
            # Add nodes (states)
            for node in self.utg_structure["nodes"]:
                G.add_node(node["id"], 
                           package=node.get("package", ""),
                           activity=node.get("activity", ""),
                           state_str=node.get("state_str", ""),
                           views=node.get("views", []))
            
            # Add edges (transitions)
            for edge in self.utg_structure["edges"]:
                G.add_edge(edge["from"], edge["to"], 
                           event=edge.get("event", ""))
            
            self.utg_graph = G
            self.logger.info(f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
            return True
            
        except Exception as e:
            self.logger.error(f"Error building graph: {str(e)}")
            return False
    
    def identify_critical_nodes(self, target_sections):
        """
        Identify nodes in the graph that correspond to critical sections.
        
        Args:
            target_sections: List of dictionaries with name and keywords for critical sections
            
        Returns:
            Dictionary mapping section names to lists of matching node IDs
        """
        if not self.utg_graph:
            return {}
        
        critical_nodes = defaultdict(list)
        
        # For each section, find nodes that match its keywords
        for section in target_sections:
            section_name = section["name"]
            keywords = [kw.lower() for kw in section["keywords"]]
            
            for node_id, node_data in self.utg_graph.nodes(data=True):
                # Check activity and package name
                activity = node_data.get("activity", "").lower()
                package = node_data.get("package", "").lower()
                
                # Check all view texts
                view_texts = []
                for view in node_data.get("views", []):
                    if "text" in view and view["text"]:
                        view_texts.append(view["text"].lower())
                    if "resource_id" in view and view["resource_id"]:
                        view_texts.append(view["resource_id"].lower())
                    if "content_desc" in view and view["content_desc"]:
                        view_texts.append(view["content_desc"].lower())
                
                # Check if any keyword matches
                for keyword in keywords:
                    if (keyword in activity or 
                        keyword in package or 
                        any(keyword in text for text in view_texts)):
                        critical_nodes[section_name].append(node_id)
                        break
        
        return critical_nodes
    
    def find_shortest_paths(self, target_nodes):
        """
        Find shortest paths from entry nodes to target nodes.
        
        Args:
            target_nodes: Dictionary mapping section names to lists of node IDs
            
        Returns:
            Dictionary with navigation analysis results
        """
        if not self.utg_graph or not target_nodes:
            return {}
        
        results = {}
        
        # Find potential entry nodes (typically the first few nodes in the graph)
        entry_nodes = []
        sorted_nodes = sorted(self.utg_graph.nodes())
        if sorted_nodes:
            # Consider first node and nodes with no incoming edges as entry points
            entry_nodes.append(sorted_nodes[0])
            for node in self.utg_graph.nodes():
                if self.utg_graph.in_degree(node) == 0:
                    entry_nodes.append(node)
        
        if not entry_nodes:
            self.logger.warning("No entry nodes identified")
            return results
        
        # For each critical section, find shortest paths from entry nodes
        for section_name, section_nodes in target_nodes.items():
            if not section_nodes:
                results[section_name] = {
                    "found": False,
                    "min_steps": float('inf'),
                    "avg_steps": float('inf'),
                    "reachable_percentage": 0
                }
                continue
            
            all_path_lengths = []
            reachable_count = 0
            
            for target_node in section_nodes:
                min_path_length = float('inf')
                
                for entry_node in entry_nodes:
                    try:
                        if nx.has_path(self.utg_graph, entry_node, target_node):
                            path_length = nx.shortest_path_length(
                                self.utg_graph, entry_node, target_node)
                            min_path_length = min(min_path_length, path_length)
                            reachable_count += 1
                            break  # Found at least one path
                    except nx.NetworkXNoPath:
                        continue
                
                if min_path_length < float('inf'):
                    all_path_lengths.append(min_path_length)
            
            # Calculate statistics
            if all_path_lengths:
                avg_path_length = sum(all_path_lengths) / len(all_path_lengths)
                min_path_length = min(all_path_lengths)
                reachable_percentage = (reachable_count / len(section_nodes)) * 100
            else:
                avg_path_length = float('inf')
                min_path_length = float('inf')
                reachable_percentage = 0
            
            results[section_name] = {
                "found": len(all_path_lengths) > 0,
                "min_steps": min_path_length if min_path_length < float('inf') else None,
                "avg_steps": avg_path_length if avg_path_length < float('inf') else None,
                "reachable_percentage": reachable_percentage
            }
        
        return results
    
    def calculate_navigation_scores(self, path_results):
        """
        Calculate navigation scores based on path analysis.
        
        Args:
            path_results: Dictionary with path analysis results
            
        Returns:
            Dictionary with scores
        """
        scores = {
            "overall_score": 0,
            "reachability_score": 0,
            "efficiency_score": 0,
            "section_scores": {}
        }
        
        if not path_results:
            return scores
        
        # Calculate per-section scores
        reachable_sections = 0
        total_efficiency_score = 0
        
        for section_name, result in path_results.items():
            section_score = 0
            
            # Reachability component (50%)
            if result["found"]:
                reachability = result["reachable_percentage"] / 100
                reachable_sections += 1
            else:
                reachability = 0
                
            section_score += reachability * 50
            
            # Efficiency component (50%)
            if result["min_steps"] is not None:
                # Fewer steps is better - max score for 1-2 steps, decreasing for more
                if result["min_steps"] <= 2:
                    efficiency = 1.0
                elif result["min_steps"] <= 4:
                    efficiency = 0.8
                elif result["min_steps"] <= 6:
                    efficiency = 0.6
                else:
                    efficiency = 0.4 - (min(result["min_steps"], 15) - 6) * 0.05
                    efficiency = max(0, efficiency)  # Ensure it doesn't go negative
            else:
                efficiency = 0
                
            section_score += efficiency * 50
            total_efficiency_score += efficiency
            
            scores["section_scores"][section_name] = {
                "score": section_score,
                "reachability": reachability * 100,
                "efficiency": efficiency * 100
            }
        
        # Overall reachability score
        if len(path_results) > 0:
            scores["reachability_score"] = (reachable_sections / len(path_results)) * 100
        
        # Overall efficiency score
        if reachable_sections > 0:
            scores["efficiency_score"] = (total_efficiency_score / reachable_sections) * 100
        
        # Overall navigation score (average of reachability and efficiency)
        scores["overall_score"] = (scores["reachability_score"] + scores["efficiency_score"]) / 2
        
        return scores
    
    def analyze(self):
        """
        Analyze navigation paths to critical sections.
        
        Returns:
            Dictionary with analysis results
        """
        results = {
            "success": False,
            "critical_sections": [],
            "navigation_paths": {},
            "scores": {
                "overall_score": 0,
                "reachability_score": 0,
                "efficiency_score": 0,
                "section_scores": {}
            },
            "unreachable_sections": []
        }
        
        # Load UTG data and build graph
        if not self.load_utg_data() or not self.build_graph():
            self.logger.error("Failed to build navigation graph")
            return results
        
        # Use specified critical sections or defaults
        target_sections = self.critical_sections if self.critical_sections else self.default_critical_sections
        results["critical_sections"] = [section["name"] for section in target_sections]
        
        # Identify nodes corresponding to critical sections
        critical_nodes = self.identify_critical_nodes(target_sections)
        
        # Find which sections were not found in the app
        not_found_sections = []
        for section in target_sections:
            if section["name"] not in critical_nodes or not critical_nodes[section["name"]]:
                not_found_sections.append(section["name"])
        
        results["sections_not_found"] = not_found_sections
        
        # Find shortest paths to critical sections
        path_results = self.find_shortest_paths(critical_nodes)
        results["navigation_paths"] = path_results
        
        # Calculate navigation scores
        scores = self.calculate_navigation_scores(path_results)
        results["scores"] = scores
        
        # Identify unreachable sections
        unreachable_sections = []
        for section_name, path_result in path_results.items():
            if not path_result["found"]:
                unreachable_sections.append(section_name)
        
        results["unreachable_sections"] = unreachable_sections
        
        results["success"] = True
        return results