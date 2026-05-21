"""
MAVLink connection management for the agent server.
Extracted from gcs_tool/gcs_server.py — no WebSocket broadcast (agent has no UI clients).
"""

import os
# Must set MAVLINK20 before importing pymavlink so it uses MAVLink v2 protocol
os.environ['MAVLINK20'] = '1'

import time
import threading
import queue
from pymavlink import mavutil
from typing import Dict, Any, List


# Vehicle type sets (MAV_TYPE values)
MULTIROTOR_TYPES = {2, 3, 4, 13, 14, 15}   # quad, coax heli, heli, hex, octo, tri
FIXED_WING_TYPES = {1}
VTOL_TYPES = {19, 20, 21, 22, 23, 24, 25}
GROUND_TYPES = {10, 11}                      # rover, boat


def _vehicle_class(vehicle_type):
    """Map a MAV_TYPE integer to a vehicle class string."""
    if vehicle_type in VTOL_TYPES:
        return 'vtol'
    if vehicle_type in FIXED_WING_TYPES:
        return 'fixed_wing'
    if vehicle_type in MULTIROTOR_TYPES:
        return 'multirotor'
    if vehicle_type in GROUND_TYPES:
        return 'ground'
    return 'multirotor'  # safe default


class MAVLinkConnection:
    """Manages MAVLink connection and telemetry state (agent server, no WebSocket broadcast)"""

    def __init__(self, connection_string='udp:127.0.0.1:14550'):
        self.connection_string = connection_string
        self.mav = None
        self.connected = False

        # Lock only for send operations (not recv)
        self.send_lock = threading.Lock()

        # Protocol message queue: telemetry loop forwards ACKs/requests here
        self.protocol_queue = queue.Queue()
        self._command_active = threading.Event()

        # Vehicle type (MAV_TYPE from heartbeat)
        self.vehicle_type = None

        # Heartbeat-based connection tracking
        self.last_heartbeat = None

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
            self.mav.mav.srcSystem = 255
            self.mav.mav.srcComponent = 190
            # Wait for heartbeat
            self.mav.wait_heartbeat(timeout=5)
            self.connected = True
            self.last_heartbeat = time.time()
            print(f"Connected to MAVLink on {self.connection_string}")
            return True
        except Exception as e:
            print(f"MAVLink connection failed: {e}")
            self.connected = False
            return False

    def start_telemetry_loop(self):
        """Start background thread to receive MAVLink messages"""
        self.running = True
        self.thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self.thread.start()
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def _heartbeat_loop(self):
        """Send GCS heartbeat to PX4 at 1 Hz"""
        while self.running:
            if self.mav:
                try:
                    with self.send_lock:
                        self.mav.mav.heartbeat_send(
                            18,  # MAV_TYPE_ONBOARD_CONTROLLER
                            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                            0,
                            0,
                            mavutil.mavlink.MAV_STATE_ACTIVE,
                        )
                except Exception as e:
                    print(f"Heartbeat send error: {e}")
            time.sleep(1)

    def _telemetry_loop(self):
        """Background loop to process MAVLink messages.

        This is the sole reader of the MAVLink connection. When a command
        operation is active (_command_active is set), protocol messages
        (MISSION_REQUEST_INT, MISSION_REQUEST, MISSION_ACK, COMMAND_ACK) are
        forwarded to protocol_queue instead of being handled as telemetry.
        """
        PROTOCOL_TYPES = {'MISSION_REQUEST_INT', 'MISSION_REQUEST', 'MISSION_ACK', 'COMMAND_ACK'}

        while self.running:
            if not self.mav:
                break

            try:
                msg = self.mav.recv_match(blocking=True, timeout=0.1)
                if msg:
                    msg_type = msg.get_type()
                    if self._command_active.is_set() and msg_type in PROTOCOL_TYPES:
                        self.protocol_queue.put(msg)
                    else:
                        self._handle_message(msg)

                # Heartbeat timeout check
                if self.last_heartbeat is not None:
                    if time.time() - self.last_heartbeat > 5.0:
                        if self.connected:
                            self.connected = False
                            print("Heartbeat timeout - marking disconnected")
                elif not self.connected:
                    # Never received a heartbeat
                    pass

            except Exception as e:
                print(f"Error in telemetry loop: {e}")
                break

    def _handle_message(self, msg):
        """Process MAVLink message and update state"""
        msg_type = msg.get_type()

        if msg_type == 'HEARTBEAT':
            self.last_heartbeat = time.time()
            self.connected = True
            self.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            if msg.type != mavutil.mavlink.MAV_TYPE_GCS:
                self.vehicle_type = msg.type

        elif msg_type == 'HOME_POSITION':
            new_home = {
                'latitude': msg.latitude / 1e7,
                'longitude': msg.longitude / 1e7,
                'altitude': msg.altitude / 1000.0
            }
            if new_home != self.home_position:
                self.home_position = new_home
                print(f"Home position: {self.home_position}")

        elif msg_type == 'GLOBAL_POSITION_INT':
            self.current_position = {
                'latitude': msg.lat / 1e7,
                'longitude': msg.lon / 1e7
            }
            self.altitude = msg.relative_alt / 1000.0  # mm to m

        elif msg_type == 'ATTITUDE':
            import math
            yaw_deg = msg.yaw * (180 / math.pi)
            if yaw_deg < 0:
                yaw_deg += 360
            self.heading = yaw_deg

    def upload_mission(self, mavlink_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Upload mission to drone via MAVLink mission protocol.

        Implements:
        1. Send MISSION_COUNT
        2. Wait for MISSION_REQUEST_INT for each seq
        3. Send MISSION_ITEM_INT for each requested seq
        4. Wait for MISSION_ACK

        Args:
            mavlink_items: List of MAVLink MISSION_ITEM_INT format dicts

        Returns:
            Dict with 'success', 'message', and optionally 'items_sent'
        """
        if not self.mav or not self.connected:
            return {'success': False, 'message': 'MAVLink not connected'}

        count = len(mavlink_items)
        if count == 0:
            return {'success': False, 'message': 'No mission items to upload'}

        self._command_active.set()
        # Drain stale protocol messages
        while not self.protocol_queue.empty():
            try:
                self.protocol_queue.get_nowait()
            except queue.Empty:
                break

        try:
            target_system = self.mav.target_system
            target_component = self.mav.target_component

            # Step 1: Send MISSION_COUNT
            with self.send_lock:
                self.mav.mav.mission_count_send(
                    target_system, target_component, count
                )
            print(f"Sending MISSION_COUNT: {count} items")

            # Build seq-keyed lookup for safe item access
            items_by_seq = {item['seq']: item for item in mavlink_items}

            # Step 2-4: Respond to requests and wait for ACK in one loop
            items_sent = 0
            timeout = 15  # seconds total
            start = time.time()

            while (time.time() - start) < timeout:
                try:
                    remaining = timeout - (time.time() - start)
                    if remaining <= 0:
                        break
                    msg = self.protocol_queue.get(timeout=min(remaining, 3.0))
                except queue.Empty:
                    if items_sent >= count:
                        return {'success': False, 'message': f'Timeout waiting for mission ACK (sent {items_sent}/{count})'}
                    return {'success': False, 'message': f'Timeout waiting for mission request (sent {items_sent}/{count})'}

                msg_type = msg.get_type()

                if msg_type == 'MISSION_ACK':
                    print(f"Mission ACK received: type={msg.type}")
                    if msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                        return {'success': True, 'message': f'Mission uploaded: {items_sent} items', 'items_sent': items_sent}
                    else:
                        return {'success': False, 'message': f'Mission rejected: ACK type {msg.type}'}

                if msg_type in ('MISSION_REQUEST_INT', 'MISSION_REQUEST'):
                    seq = msg.seq
                    if seq >= count:
                        return {'success': False, 'message': f'Drone requested invalid seq {seq}'}

                    item = items_by_seq.get(seq)
                    if item is None:
                        return {'success': False, 'message': f'No item for requested seq {seq}'}
                    print(f"PX4 requested seq {seq}, sending item")
                    with self.send_lock:
                        self.mav.mav.mission_item_int_send(
                            target_system, target_component,
                            item['seq'],
                            item['frame'],
                            item['command'],
                            item['current'],
                            item['autocontinue'],
                            item['param1'] if item['param1'] is not None else float('nan'),
                            item['param2'] if item['param2'] is not None else float('nan'),
                            item['param3'] if item['param3'] is not None else float('nan'),
                            item['param4'] if item['param4'] is not None else float('nan'),
                            item['x'],
                            item['y'],
                            item['z']
                        )
                    items_sent += 1

            return {'success': False, 'message': f'Timeout waiting for mission ACK (sent {items_sent}/{count})'}

        except Exception as e:
            return {'success': False, 'message': f'Upload failed: {str(e)}'}
        finally:
            self._command_active.clear()

    def send_command(self, mavlink_item: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single command for immediate execution.

        Position-based NAV commands use COMMAND_INT (preserves int32 lat/lon).
        Other commands use COMMAND_LONG.

        Args:
            mavlink_item: MAVLink MISSION_ITEM_INT format dict

        Returns:
            Dict with 'success' and 'message'
        """
        if not self.mav or not self.connected:
            return {'success': False, 'message': 'MAVLink not connected'}

        self._command_active.set()
        while not self.protocol_queue.empty():
            try:
                self.protocol_queue.get_nowait()
            except queue.Empty:
                break

        try:
            target_system = self.mav.target_system
            target_component = self.mav.target_component
            command = mavlink_item['command']

            # Position-based NAV commands use COMMAND_INT
            nav_commands = {16, 17, 18, 19, 20, 21, 22}  # WAYPOINT, LOITER_UNLIM, LOITER_TURNS, LOITER_TIME, RTL, LAND, TAKEOFF

            with self.send_lock:
                if command in nav_commands:
                    self.mav.mav.command_int_send(
                        target_system, target_component,
                        mavlink_item['frame'],
                        command,
                        0,  # current
                        mavlink_item.get('autocontinue', 0),
                        mavlink_item['param1'] if mavlink_item['param1'] is not None else float('nan'),
                        mavlink_item['param2'] if mavlink_item['param2'] is not None else float('nan'),
                        mavlink_item['param3'] if mavlink_item['param3'] is not None else float('nan'),
                        mavlink_item['param4'] if mavlink_item['param4'] is not None else float('nan'),
                        mavlink_item['x'],
                        mavlink_item['y'],
                        mavlink_item['z']
                    )
                else:
                    # COMMAND_LONG for non-position commands
                    self.mav.mav.command_long_send(
                        target_system, target_component,
                        command,
                        0,  # confirmation
                        mavlink_item['param1'] if mavlink_item['param1'] is not None else float('nan'),
                        mavlink_item['param2'] if mavlink_item['param2'] is not None else float('nan'),
                        mavlink_item['param3'] if mavlink_item['param3'] is not None else float('nan'),
                        mavlink_item['param4'] if mavlink_item['param4'] is not None else float('nan'),
                        mavlink_item['x'] / 1e7 if mavlink_item.get('x') is not None else 0,
                        mavlink_item['y'] / 1e7 if mavlink_item.get('y') is not None else 0,
                        mavlink_item['z']
                    )

            # Wait for COMMAND_ACK from protocol queue
            try:
                ack = self.protocol_queue.get(timeout=5.0)
            except queue.Empty:
                ack = None

            if ack and ack.get_type() == 'COMMAND_ACK' and ack.command == command:
                if ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                    return {'success': True, 'message': f'Command {command} accepted'}
                else:
                    return {'success': False, 'message': f'Command {command} rejected: result {ack.result}'}
            elif ack and ack.get_type() == 'COMMAND_ACK':
                return {'success': False, 'message': f'Command {command} failed (ACK for different command {ack.command})'}
            else:
                return {'success': False, 'message': f'Command {command} failed (no ACK received within timeout)'}

        except Exception as e:
            return {'success': False, 'message': f'Command failed: {str(e)}'}
        finally:
            self._command_active.clear()

    def set_mode(self, main_mode: int, sub_mode: int, label: str = '') -> Dict[str, Any]:
        """Set PX4 flight mode via MAV_CMD_DO_SET_MODE.

        Args:
            main_mode: PX4 custom main mode (e.g. 4 = AUTO)
            sub_mode: PX4 custom sub mode (e.g. 2 = TAKEOFF, 3 = LOITER, 4 = MISSION, 5 = RTL, 6 = LAND)
            label: Human-readable label for log messages

        Returns:
            Dict with 'success' and 'message'
        """
        if not self.mav or not self.connected:
            return {'success': False, 'message': 'MAVLink not connected'}

        self._command_active.set()
        while not self.protocol_queue.empty():
            try:
                self.protocol_queue.get_nowait()
            except queue.Empty:
                break

        try:
            with self.send_lock:
                self.mav.mav.command_long_send(
                    self.mav.target_system,
                    self.mav.target_component,
                    mavutil.mavlink.MAV_CMD_DO_SET_MODE,
                    0,  # confirmation
                    mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,  # param1
                    main_mode,                                          # param2
                    sub_mode,                                           # param3
                    0, 0, 0, 0                                          # param4-7
                )

            # Wait for ACK from protocol queue
            try:
                ack = self.protocol_queue.get(timeout=5.0)
            except queue.Empty:
                ack = None

            mode_label = label or f'main={main_mode} sub={sub_mode}'
            if ack and ack.get_type() == 'COMMAND_ACK' and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                return {'success': True, 'message': f'PX4 mode set: {mode_label}'}
            elif ack and ack.get_type() == 'COMMAND_ACK':
                return {'success': False, 'message': f'Mode change rejected ({mode_label}): result {ack.result}'}
            else:
                return {'success': False, 'message': f'Mode change timeout ({mode_label}): no ACK received'}

        except Exception as e:
            return {'success': False, 'message': f'Set mode failed: {str(e)}'}
        finally:
            self._command_active.clear()

    def set_mode_auto(self) -> Dict[str, Any]:
        """Set drone to PX4 Mission mode (AUTO/MISSION) after mission upload."""
        return self.set_mode(4, 4, 'AUTO/MISSION')

    def set_mode_rtl(self) -> Dict[str, Any]:
        """Set drone to PX4 RTL mode (AUTO/RTL) for immediate return."""
        return self.set_mode(4, 5, 'AUTO/RTL')

    def send_rtl_command(self) -> Dict[str, Any]:
        """Send MAV_CMD_NAV_RETURN_TO_LAUNCH (20) as COMMAND_LONG for immediate RTL."""
        if not self.mav or not self.connected:
            return {'success': False, 'message': 'MAVLink not connected'}

        self._command_active.set()
        while not self.protocol_queue.empty():
            try:
                self.protocol_queue.get_nowait()
            except queue.Empty:
                break

        try:
            with self.send_lock:
                self.mav.mav.command_long_send(
                    self.mav.target_system,
                    self.mav.target_component,
                    mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,  # 20
                    0,           # confirmation
                    0, 0, 0, 0, 0, 0, 0  # param1-7 all 0
                )

            try:
                ack = self.protocol_queue.get(timeout=5.0)
            except queue.Empty:
                ack = None

            if ack and ack.get_type() == 'COMMAND_ACK' and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                return {'success': True, 'message': 'RTL command accepted'}
            elif ack and ack.get_type() == 'COMMAND_ACK':
                return {'success': False, 'message': f'RTL command rejected: result {ack.result}'}
            else:
                return {'success': False, 'message': 'RTL command: no ACK received'}

        except Exception as e:
            return {'success': False, 'message': f'RTL command failed: {str(e)}'}
        finally:
            self._command_active.clear()

    def arm(self, force=False) -> Dict[str, Any]:
        """Arm the drone.

        Args:
            force: If True, bypass safety checks (param2=21196)

        Returns:
            Dict with 'success' and 'message'
        """
        if not self.mav or not self.connected:
            return {'success': False, 'message': 'MAVLink not connected'}

        self._command_active.set()
        while not self.protocol_queue.empty():
            try:
                self.protocol_queue.get_nowait()
            except queue.Empty:
                break

        try:
            with self.send_lock:
                self.mav.mav.command_long_send(
                    self.mav.target_system,
                    self.mav.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0,      # confirmation
                    1,      # param1: 1=arm
                    21196 if force else 0,  # param2: 21196=force
                    0, 0, 0, 0, 0
                )

            try:
                ack = self.protocol_queue.get(timeout=5.0)
            except queue.Empty:
                ack = None

            if ack and ack.get_type() == 'COMMAND_ACK' and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                return {'success': True, 'message': 'Drone armed'}
            elif ack and ack.get_type() == 'COMMAND_ACK':
                return {'success': False, 'message': f'Arm rejected: result {ack.result}'}
            else:
                return {'success': False, 'message': 'Arm timeout (no ACK received)'}

        except Exception as e:
            return {'success': False, 'message': f'Arm failed: {str(e)}'}
        finally:
            self._command_active.clear()

    def disarm(self, force=False) -> Dict[str, Any]:
        """Disarm the drone.

        Args:
            force: If True, bypass safety checks (param2=21196)

        Returns:
            Dict with 'success' and 'message'
        """
        if not self.mav or not self.connected:
            return {'success': False, 'message': 'MAVLink not connected'}

        self._command_active.set()
        while not self.protocol_queue.empty():
            try:
                self.protocol_queue.get_nowait()
            except queue.Empty:
                break

        try:
            with self.send_lock:
                self.mav.mav.command_long_send(
                    self.mav.target_system,
                    self.mav.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0,      # confirmation
                    0,      # param1: 0=disarm
                    21196 if force else 0,  # param2: 21196=force
                    0, 0, 0, 0, 0
                )

            try:
                ack = self.protocol_queue.get(timeout=5.0)
            except queue.Empty:
                ack = None

            if ack and ack.get_type() == 'COMMAND_ACK' and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                return {'success': True, 'message': 'Drone disarmed'}
            elif ack and ack.get_type() == 'COMMAND_ACK':
                return {'success': False, 'message': f'Disarm rejected: result {ack.result}'}
            else:
                return {'success': False, 'message': 'Disarm timeout (no ACK received)'}

        except Exception as e:
            return {'success': False, 'message': f'Disarm failed: {str(e)}'}
        finally:
            self._command_active.clear()

    def stop(self):
        """Stop telemetry loop"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
