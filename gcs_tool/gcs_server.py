"""
GCS Server - Ground Control Station with MAVLink integration
Calls LLM Server for AI-powered mission planning
"""

import sys
import os
import threading
import requests
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from pymavlink import mavutil
from typing import Dict, Any, Optional
import logging

class MAVLinkConnection:
    """Manages MAVLink connection and telemetry state"""

    def __init__(self, connection_string='udp:127.0.0.1:14550', socketio=None):
        self.connection_string = connection_string
        self.socketio = socketio
        self.mav = None
        self.connected = False

        # Telemetry state
        self.home_position = None
        self.current_position = None
        self.altitude = None
        self.heading = None
        self.armed = False

        self.running = False
        self.thread = None

    def connect(self):
        """Connect to MAVLink"""
        try:
            self.mav = mavutil.mavlink_connection(self.connection_string)
            # Wait for heartbeat
            self.mav.wait_heartbeat(timeout=5)
            self.connected = True
            print(f"✅ Connected to MAVLink on {self.connection_string}")
            return True
        except Exception as e:
            print(f"❌ MAVLink connection failed: {e}")
            self.connected = False
            return False

    def start_telemetry_loop(self):
        """Start background thread to receive MAVLink messages"""
        self.running = True
        self.thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self.thread.start()

    def _telemetry_loop(self):
        """Background loop to process MAVLink messages"""
        while self.running:
            if not self.mav:
                break

            try:
                msg = self.mav.recv_match(blocking=True, timeout=1.0)
                if msg:
                    self._handle_message(msg)
            except Exception as e:
                print(f"Error in telemetry loop: {e}")
                break

    def _handle_message(self, msg):
        """Process MAVLink message and update state"""
        msg_type = msg.get_type()

        if msg_type == 'HEARTBEAT':
            self.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            self._broadcast_telemetry()

        elif msg_type == 'HOME_POSITION':
            self.home_position = {
                'latitude': msg.latitude / 1e7,
                'longitude': msg.longitude / 1e7,
                'altitude': msg.altitude / 1000.0
            }
            print(f"🏠 Home position: {self.home_position}")
            self._broadcast_telemetry()

        elif msg_type == 'GLOBAL_POSITION_INT':
            self.current_position = {
                'latitude': msg.lat / 1e7,
                'longitude': msg.lon / 1e7
            }
            self.altitude = msg.relative_alt / 1000.0  # mm to m
            self._broadcast_telemetry()

        elif msg_type == 'ATTITUDE':
            import math
            yaw_deg = msg.yaw * (180 / math.pi)
            if yaw_deg < 0:
                yaw_deg += 360
            self.heading = yaw_deg
            self._broadcast_telemetry()

    def _broadcast_telemetry(self):
        """Broadcast telemetry to all connected WebSocket clients"""
        if self.socketio:
            telemetry = {
                'connected': self.connected,
                'home': self.home_position,
                'position': self.current_position,
                'altitude': self.altitude,
                'heading': self.heading,
                'armed': self.armed
            }
            self.socketio.emit('telemetry', telemetry, namespace='/ws/telemetry')

    def stop(self):
        """Stop telemetry loop"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)


class GCSServer:
    """Ground Control Station Server with MAVLink integration"""

    def __init__(self, mavlink_connection='udp:127.0.0.1:14550', llm_server_url='http://localhost:5000'):
        self.app = Flask(__name__)
        CORS(self.app)

        # Flask-SocketIO for WebSocket telemetry
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # MAVLink connection
        self.mavlink = MAVLinkConnection(mavlink_connection, self.socketio) if mavlink_connection else None

        # LLM Server URL
        self.llm_server_url = llm_server_url

        self._setup_routes()
        self._setup_socketio()
        if self.mavlink:
            self._connect_mavlink()

    def _connect_mavlink(self):
        """Connect to MAVLink and start telemetry loop"""
        if self.mavlink.connect():
            self.mavlink.start_telemetry_loop()
        else:
            print("⚠️  MAVLink not connected - GCS will run without telemetry")

    def _setup_socketio(self):
        """Setup WebSocket handlers"""
        @self.socketio.on('connect', namespace='/ws/telemetry')
        def handle_connect():
            print("Browser connected to telemetry")
            # Send current state immediately
            if self.mavlink and self.mavlink.connected:
                telemetry = {
                    'connected': True,
                    'home': self.mavlink.home_position,
                    'position': self.mavlink.current_position,
                    'altitude': self.mavlink.altitude,
                    'heading': self.mavlink.heading,
                    'armed': self.mavlink.armed
                }
                emit('telemetry', telemetry)

    def _setup_routes(self):
        """Setup HTTP routes"""

        @self.app.route('/', methods=['GET'])
        def index():
            return send_file('static/index.html')

        @self.app.route('/static/<path:filename>', methods=['GET'])
        def static_files(filename):
            return send_from_directory('static', filename)

        @self.app.route('/api/status', methods=['GET'])
        def status():
            return jsonify({
                "status": "running",
                "agent_initialized": True,  # GCS is always ready when running
                "mavlink_connected": self.mavlink.connected if self.mavlink else False,
                "llm_server": self.llm_server_url
            })

        @self.app.route('/api/plan', methods=['POST'])
        def plan():
            """Proxy planning request to LLM Server"""
            try:
                data = request.get_json()

                # Add home_position from GCS telemetry
                if self.mavlink and self.mavlink.home_position:
                    data['home_position'] = self.mavlink.home_position

                # Forward to LLM Server
                response = requests.post(
                    f"{self.llm_server_url}/api/plan",
                    json=data,
                    timeout=120  # 2 minute timeout for LLM inference
                )

                return jsonify(response.json()), response.status_code

            except requests.exceptions.ConnectionError:
                return jsonify({
                    "success": False,
                    "error": f"Cannot connect to LLM Server at {self.llm_server_url}"
                }), 503
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500

    def run(self, host='0.0.0.0', port=8080):
        print(f"🌐 Starting GCS Server on http://{host}:{port}")
        print(f"📡 Telemetry WebSocket: ws://{host}:{port}/ws/telemetry")
        print(f"🤖 LLM Server: {self.llm_server_url}")
        if self.mavlink and self.mavlink.connected:
            print(f"✅ MAVLink connected: {self.mavlink.connection_string}")
        self.socketio.run(self.app, host=host, port=port, allow_unsafe_werkzeug=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GCS Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to (default: 8080)")
    parser.add_argument("--mavlink", default="udp:127.0.0.1:14550", help="MAVLink connection string (default: udp:127.0.0.1:14550)")
    parser.add_argument("--llm-server", default="http://localhost:5000", help="LLM Server URL (default: http://localhost:5000)")
    parser.add_argument("--no-mavlink", action="store_true", help="Run without MAVLink connection (testing only)")
    args = parser.parse_args()

    mavlink = None if args.no_mavlink else args.mavlink
    server = GCSServer(mavlink_connection=mavlink, llm_server_url=args.llm_server)
    server.run(port=args.port)


if __name__ == "__main__":
    main()
