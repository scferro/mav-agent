"""
MAVLink Agent Flask Server
Hosts the complete MAVLinkAgent with LLM and mission management via HTTP APIs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from typing import Dict, Any, Optional
import traceback
import logging

from core import MAVLinkAgent
from config import get_settings, reload_settings


class MAVLinkAgentServer:
    """Flask server hosting MAVLinkAgent"""
    
    def __init__(self, verbose: bool = False):
        self.app = Flask(__name__)
        CORS(self.app)  # Enable CORS for all routes
        
        # Initialize MAVLinkAgent
        self.agent: Optional[MAVLinkAgent] = None
        self.verbose = verbose
        
        # Setup logging
        if not verbose:
            logging.getLogger('werkzeug').setLevel(logging.WARNING)
        
        self._setup_routes()
        self._initialize_agent()
    
    def _clean_result_for_json(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Clean result dictionary to ensure JSON serialization"""
        if not isinstance(result, dict):
            return result
        
        cleaned = {}
        for key, value in result.items():
            if key == 'intermediate_steps':
                # Convert LangChain messages to serializable format in verbose mode
                if self.verbose and isinstance(value, list):
                    cleaned[key] = []
                    for item in value:
                        if hasattr(item, 'content'):
                            cleaned[key].append({
                                'type': type(item).__name__,
                                'content': str(item.content) if item.content else None
                            })
                        else:
                            cleaned[key].append(str(item))
                else:
                    # Skip intermediate_steps if not verbose
                    continue
            else:
                cleaned[key] = value
        
        return cleaned
    
    def _initialize_agent(self):
        """Initialize the MAVLinkAgent instance"""
        try:
            self.agent = MAVLinkAgent(verbose=self.verbose)
            print(f"🚁 MAVLinkAgent initialized (verbose={self.verbose})")
        except Exception as e:
            print(f"❌ Failed to initialize MAVLinkAgent: {e}")
            self.agent = None
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/', methods=['GET'])
        def index():
            """Serve the main web chat interface"""
            return send_file('static/index.html')
        
        @self.app.route('/static/<path:filename>', methods=['GET'])
        def static_files(filename):
            """Serve static files (CSS, JS, etc.)"""
            return send_from_directory('static', filename)
        
        @self.app.route('/api/status', methods=['GET'])
        def status():
            """Server health check"""
            return jsonify({
                "status": "running",
                "agent_initialized": self.agent is not None,
                "verbose": self.verbose
            })

        @self.app.route('/api/plan', methods=['POST'])
        def plan():
            """Unified stateless planning endpoint - accepts MAVLink format"""
            if not self.agent:
                return jsonify({
                    "success": False,
                    "error": "MAVLinkAgent not initialized",
                    "output": "Server error: Agent not available"
                }), 500

            try:
                data = request.get_json()

                # Validate required fields
                if not data or 'user_input' not in data:
                    return jsonify({
                        "success": False,
                        "error": "Missing required field: user_input"
                    }), 400

                # Extract parameters
                user_input = data['user_input']
                mode = data.get('mode', 'mission')  # Default to mission mode
                mission_state_mavlink = data.get('mission_state', None)
                home_position = data.get('home_position', None)  # NEW: from GCS

                # Validate mode
                if mode not in ['mission', 'command']:
                    return jsonify({
                        "success": False,
                        "error": f"Invalid mode: {mode}. Must be 'mission' or 'command'"
                    }), 400

                # Validate: require either mission_state or home_position
                if not mission_state_mavlink and not home_position:
                    return jsonify({
                        "success": False,
                        "error": "Missing required data: Either 'mission_state' or 'home_position' required. Connect to GCS or provide mission state."
                    }), 400

                # Convert MAVLink mission to internal format if provided
                mission_state_internal = None
                if mission_state_mavlink:
                    from core.mission import Mission
                    mission_state_internal = Mission.from_mavlink(mission_state_mavlink)
                    mission_state_internal = mission_state_internal.to_dict()

                # Execute planning with internal format
                result = self.agent.plan(
                    user_input=user_input,
                    mode=mode,
                    mission_state=mission_state_internal,
                    home_position=home_position
                )

                # Convert result mission to MAVLink format ONLY (no custom format)
                if result.get('success') and result.get('mission_state'):
                    from core.mission import Mission
                    mission = Mission.from_dict(result['mission_state'])

                    # Replace mission_state with mission_items (MAVLink format)
                    result['mission_items'] = mission.to_mavlink()
                    del result['mission_state']  # Remove old format

                # Clean for JSON serialization
                clean_result = self._clean_result_for_json(result)

                return jsonify(clean_result)

            except ValueError as e:
                return jsonify({
                    "success": False,
                    "error": f"Validation error: {str(e)}"
                }), 400
            except Exception as e:
                error_msg = str(e)
                if self.verbose:
                    error_msg += f"\n{traceback.format_exc()}"

                return jsonify({
                    "success": False,
                    "error": error_msg,
                    "output": f"Planning request failed: {str(e)}"
                }), 500

        @self.app.route('/api/config', methods=['POST'])
        def update_config():
            """Reload configuration"""
            try:
                data = request.get_json()
                config_path = data.get('config_path') if data else None
                
                if config_path:
                    reload_settings(config_path)
                
                # Reinitialize agent with new settings
                self._initialize_agent()
                
                return jsonify({
                    "success": True,
                    "message": "Configuration reloaded"
                })
                
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500

    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Run the Flask server"""
        print(f"🌐 Starting MAVLinkAgent server on http://{host}:{port}")
        print(f"🚁 Planning endpoint: POST http://{host}:{port}/api/plan")
        print(f"💚 Status endpoint: GET http://{host}:{port}/api/status")

        self.app.run(host=host, port=port, debug=debug)


def main():
    """Main server entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MAVLink Agent Flask Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    parser.add_argument("--config", "-c", type=str, help="Path to configuration file")
    
    args = parser.parse_args()

    # Load configuration if specified
    if args.config:
        try:
            reload_settings(args.config)
            print(f"📝 Loaded configuration from {args.config}")
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return 1

    # Support environment variable for verbose mode (useful for Docker)
    verbose = args.verbose or os.getenv('VERBOSE', '').lower() in ('true', '1', 'yes')

    # Create and run server
    try:
        server = MAVLinkAgentServer(verbose=verbose)
        server.run(host=args.host, port=args.port, debug=args.debug)
    except Exception as e:
        print(f"❌ Server failed to start: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())