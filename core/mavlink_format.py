"""
MAVLink format conversion utilities
Converts between internal MissionItem format and MAVLink MISSION_ITEM_INT format
"""

from typing import Dict, List, Any, Optional

# MAVLink command constants
MAV_CMD_NAV_WAYPOINT = 16
MAV_CMD_NAV_LOITER_UNLIM = 17
MAV_CMD_NAV_LOITER_TURNS = 18
MAV_CMD_NAV_LOITER_TIME = 19
MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
MAV_CMD_NAV_LAND = 21
MAV_CMD_NAV_TAKEOFF = 22
MAV_CMD_NAV_VTOL_TAKEOFF = 84
MAV_CMD_NAV_VTOL_LAND = 85
MAV_CMD_DO_SET_ROI = 201
MAV_CMD_DO_VTOL_TRANSITION = 3000

# Frame constants
MAV_FRAME_GLOBAL = 0
MAV_FRAME_GLOBAL_RELATIVE_ALT = 3
MAV_FRAME_GLOBAL_INT = 5
MAV_FRAME_GLOBAL_RELATIVE_ALT_INT = 6

# MAV_VTOL_STATE enum for transition commands
MAV_VTOL_STATE_MC = 3
MAV_VTOL_STATE_FW = 4

# Command type mapping (default / multicopter)
COMMAND_TYPE_TO_MAVLINK = {
    'takeoff': MAV_CMD_NAV_TAKEOFF,
    'waypoint': MAV_CMD_NAV_WAYPOINT,
    'loiter': MAV_CMD_NAV_LOITER_UNLIM,
    'rtl': MAV_CMD_NAV_RETURN_TO_LAUNCH,
    'land': MAV_CMD_NAV_LAND,
    'survey': MAV_CMD_NAV_WAYPOINT,  # Survey is waypoint with detection params
    'transition': MAV_CMD_DO_VTOL_TRANSITION,
}

# VTOL-specific command overrides
VTOL_COMMAND_OVERRIDES = {
    'takeoff': MAV_CMD_NAV_VTOL_TAKEOFF,
    'land': MAV_CMD_NAV_VTOL_LAND,
}

# Reverse mapping: MAVLink command ID -> command_type
MAVLINK_TO_COMMAND_TYPE = {v: k for k, v in COMMAND_TYPE_TO_MAVLINK.items()}
# Add VTOL-specific reverse mappings
MAVLINK_TO_COMMAND_TYPE[MAV_CMD_NAV_VTOL_TAKEOFF] = 'takeoff'
MAVLINK_TO_COMMAND_TYPE[MAV_CMD_NAV_VTOL_LAND] = 'land'
MAVLINK_TO_COMMAND_TYPE[MAV_CMD_DO_VTOL_TRANSITION] = 'transition'


def _get_mavlink_command(command_type: str, vehicle_type: Optional[str] = None) -> int:
    """Get the MAVLink command ID for a command type, accounting for vehicle type.

    Args:
        command_type: Internal command type string
        vehicle_type: Vehicle category (e.g., 'vtol', 'multicopter')

    Returns:
        MAVLink command integer
    """
    if vehicle_type == 'vtol' and command_type in VTOL_COMMAND_OVERRIDES:
        return VTOL_COMMAND_OVERRIDES[command_type]
    return COMMAND_TYPE_TO_MAVLINK.get(command_type, MAV_CMD_NAV_WAYPOINT)


def item_to_mavlink_dict(item: 'MissionItem', vehicle_type: Optional[str] = None) -> Dict[str, Any]:
    """Convert internal MissionItem to common MAVLink fields.

    This is the shared conversion used by both COMMAND_INT and MISSION_ITEM_INT.

    Args:
        item: Internal MissionItem with command_type, lat/lon, altitude, etc.
        vehicle_type: Vehicle category for command selection (e.g., 'vtol', 'multicopter')

    Returns:
        Dict with common MAVLink fields
    """
    from core.units import convert_to_meters

    # Get MAVLink command number (vehicle-type-aware)
    command = _get_mavlink_command(item.command_type, vehicle_type)

    # Convert coordinates
    x = int((item.latitude or 0) * 1e7)
    y = int((item.longitude or 0) * 1e7)

    # Convert altitude to meters (ground vehicles always z=0)
    if vehicle_type == 'ground':
        z = 0.0
    else:
        z = convert_to_meters(item.altitude or 0, item.altitude_units or 'feet')

    # Frame: use GLOBAL_RELATIVE_ALT_INT for relative altitude
    frame = MAV_FRAME_GLOBAL_RELATIVE_ALT_INT

    # Parameters depend on command type
    param1 = param2 = param3 = param4 = 0.0

    if item.command_type == 'takeoff':
        if vehicle_type == 'vtol':
            # VTOL takeoff: param2 = transition heading enum
            param1 = 0.0
            param2 = 0.0  # VEHICLE_DEFAULT transition heading
        else:
            param1 = 0.0  # Min pitch (used by fixed wing)
        heading_value = item.heading or 0
        if isinstance(heading_value, str):
            param4 = 0.0
        else:
            param4 = float(heading_value)

    elif item.command_type == 'land':
        if vehicle_type == 'vtol':
            # VTOL land: param1=land_options, param3=approach_alt
            param1 = 0.0  # Land options (bitmask)
            approach_alt = getattr(item, 'approach_altitude', None) or 0
            param3 = convert_to_meters(approach_alt, item.altitude_units or 'feet')
        else:
            # Regular land: param1=abort_alt
            param1 = 0.0
        heading_value = item.heading or 0
        if isinstance(heading_value, str):
            param4 = 0.0
        else:
            param4 = float(heading_value)

    elif item.command_type == 'transition':
        # DO_VTOL_TRANSITION: param1 = target state
        transition_state = getattr(item, 'transition_state', None) or 'fw'
        param1 = float(MAV_VTOL_STATE_FW if transition_state == 'fw' else MAV_VTOL_STATE_MC)
        # Transition is a DO command - no coordinates
        x = 0
        y = 0
        z = 0.0

    elif item.command_type == 'loiter':
        param3 = item.radius or 0  # Loiter radius
        param3 = convert_to_meters(param3, item.radius_units or 'feet')

    elif item.command_type == 'waypoint' or item.command_type == 'survey':
        param1 = 0.0  # Hold time
        param2 = 2.0  # Acceptance radius (meters)
        param3 = 0.0  # Pass through
        heading_value = item.heading or 0
        if isinstance(heading_value, str):
            param4 = 0.0
        else:
            param4 = float(heading_value)

    return {
        'frame': frame,
        'command': command,
        'param1': param1,
        'param2': param2,
        'param3': param3,
        'param4': param4,
        'x': x,
        'y': y,
        'z': z
    }


def to_command_int(item: 'MissionItem', target_system: int = 1, target_component: int = 1,
                   vehicle_type: Optional[str] = None) -> Dict[str, Any]:
    """Convert a MissionItem to a COMMAND_INT dict for sending a single command.

    Args:
        item: Internal MissionItem
        target_system: MAVLink target system ID
        target_component: MAVLink target component ID
        vehicle_type: Vehicle category for command selection

    Returns:
        Dict with COMMAND_INT fields
    """
    base = item_to_mavlink_dict(item, vehicle_type=vehicle_type)
    base['target_system'] = target_system
    base['target_component'] = target_component
    base['current'] = 0
    base['autocontinue'] = 0
    return base


def to_mission_item_int(item: 'MissionItem', seq: int = None,
                        vehicle_type: Optional[str] = None) -> Dict[str, Any]:
    """Convert a MissionItem to a MISSION_ITEM_INT dict for mission upload.

    Args:
        item: Internal MissionItem
        seq: Sequence number override (uses item.seq if None)
        vehicle_type: Vehicle category for command selection

    Returns:
        Dict with MISSION_ITEM_INT fields
    """
    base = item_to_mavlink_dict(item, vehicle_type=vehicle_type)
    base['seq'] = seq if seq is not None else item.seq
    base['current'] = item.current
    base['autocontinue'] = 1
    return base


def mission_item_from_mavlink(mav_item: Dict[str, Any]) -> 'MissionItem':
    """Convert MAVLink MISSION_ITEM_INT to internal MissionItem format

    Args:
        mav_item: Dict with MAVLink MISSION_ITEM_INT fields

    Returns:
        Internal MissionItem with command_type, lat/lon, altitude, etc.
    """
    from core.mission import MissionItem

    # Get command type
    command = mav_item['command']
    command_type = MAVLINK_TO_COMMAND_TYPE.get(command, 'waypoint')

    # Convert coordinates
    latitude = mav_item['x'] / 1e7
    longitude = mav_item['y'] / 1e7
    altitude = mav_item['z']  # Already in meters

    # Extract parameters
    item = MissionItem(
        seq=mav_item['seq'],
        frame=mav_item['frame'],
        command=command,
        current=mav_item['current'],
        command_type=command_type,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        altitude_units='meters'
    )

    # Command-specific parameters
    if command_type == 'takeoff':
        item.heading = mav_item.get('param4', 0)

    elif command_type == 'land':
        item.heading = mav_item.get('param4', 0)
        # Check if this was a VTOL land (has approach altitude in param3)
        if command == MAV_CMD_NAV_VTOL_LAND:
            item.approach_altitude = mav_item.get('param3', 0)

    elif command_type == 'transition':
        # DO_VTOL_TRANSITION: param1 = target state
        state_val = int(mav_item.get('param1', MAV_VTOL_STATE_FW))
        item.transition_state = 'fw' if state_val == MAV_VTOL_STATE_FW else 'mc'
        # Transition has no coordinates
        item.latitude = None
        item.longitude = None
        item.altitude = None
        item.altitude_units = None

    elif command_type == 'loiter':
        item.radius = mav_item.get('param3', 0)
        item.radius_units = 'meters'

    elif command_type in ['waypoint', 'survey']:
        item.heading = mav_item.get('param4', 0)

    return item


def mission_to_mavlink(mission: 'Mission', vehicle_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """Convert Mission to list of MAVLink MISSION_ITEM_INT dicts"""
    return [to_mission_item_int(item, seq=i, vehicle_type=vehicle_type)
            for i, item in enumerate(mission.items)]


def mission_from_mavlink(mav_items: List[Dict[str, Any]]) -> 'Mission':
    """Convert list of MAVLink MISSION_ITEM_INT dicts to Mission"""
    from core.mission import Mission
    mission = Mission()
    for mav_item in mav_items:
        item = mission_item_from_mavlink(mav_item)
        mission.items.append(item)
    return mission
