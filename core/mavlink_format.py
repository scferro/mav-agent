"""
MAVLink format conversion utilities
Converts between internal MissionItem format and MAVLink MISSION_ITEM_INT format
"""

from typing import Dict, List, Any

# MAVLink command constants
MAV_CMD_NAV_WAYPOINT = 16
MAV_CMD_NAV_LOITER_UNLIM = 17
MAV_CMD_NAV_LOITER_TURNS = 18
MAV_CMD_NAV_LOITER_TIME = 19
MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
MAV_CMD_NAV_LAND = 21
MAV_CMD_NAV_TAKEOFF = 22
MAV_CMD_DO_SET_ROI = 201

# Frame constants
MAV_FRAME_GLOBAL = 0
MAV_FRAME_GLOBAL_RELATIVE_ALT = 3
MAV_FRAME_GLOBAL_INT = 5
MAV_FRAME_GLOBAL_RELATIVE_ALT_INT = 6

# Command type mapping
COMMAND_TYPE_TO_MAVLINK = {
    'takeoff': MAV_CMD_NAV_TAKEOFF,
    'waypoint': MAV_CMD_NAV_WAYPOINT,
    'loiter': MAV_CMD_NAV_LOITER_UNLIM,
    'rtl': MAV_CMD_NAV_RETURN_TO_LAUNCH,
    'land': MAV_CMD_NAV_LAND,
    'survey': MAV_CMD_NAV_WAYPOINT,  # Survey is waypoint with detection params
}

MAVLINK_TO_COMMAND_TYPE = {v: k for k, v in COMMAND_TYPE_TO_MAVLINK.items()}


def item_to_mavlink_dict(item: 'MissionItem') -> Dict[str, Any]:
    """Convert internal MissionItem to common MAVLink fields.

    This is the shared conversion used by both COMMAND_INT and MISSION_ITEM_INT.

    Args:
        item: Internal MissionItem with command_type, lat/lon, altitude, etc.

    Returns:
        Dict with common MAVLink fields:
        {
            'frame': int,
            'command': int,
            'param1': float,
            'param2': float,
            'param3': float,
            'param4': float,
            'x': int,  # latitude * 1e7
            'y': int,  # longitude * 1e7
            'z': float  # altitude in meters
        }
    """
    from core.units import convert_to_meters

    # Get MAVLink command number
    command = COMMAND_TYPE_TO_MAVLINK.get(item.command_type, MAV_CMD_NAV_WAYPOINT)

    # Convert coordinates
    x = int((item.latitude or 0) * 1e7)
    y = int((item.longitude or 0) * 1e7)

    # Convert altitude to meters
    z = convert_to_meters(item.altitude or 0, item.altitude_units or 'feet')

    # Frame: use GLOBAL_RELATIVE_ALT_INT for relative altitude
    frame = MAV_FRAME_GLOBAL_RELATIVE_ALT_INT

    # Parameters depend on command type
    param1 = param2 = param3 = param4 = 0.0

    if item.command_type == 'takeoff':
        param1 = 0.0  # Min pitch
        heading_value = item.heading or 0
        if isinstance(heading_value, str):
            param4 = 0.0
        else:
            param4 = float(heading_value)

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


def to_command_int(item: 'MissionItem', target_system: int = 1, target_component: int = 1) -> Dict[str, Any]:
    """Convert a MissionItem to a COMMAND_INT dict for sending a single command.

    Args:
        item: Internal MissionItem
        target_system: MAVLink target system ID
        target_component: MAVLink target component ID

    Returns:
        Dict with COMMAND_INT fields
    """
    base = item_to_mavlink_dict(item)
    base['target_system'] = target_system
    base['target_component'] = target_component
    base['current'] = 0
    base['autocontinue'] = 0
    return base


def to_mission_item_int(item: 'MissionItem', seq: int = None) -> Dict[str, Any]:
    """Convert a MissionItem to a MISSION_ITEM_INT dict for mission upload.

    Args:
        item: Internal MissionItem
        seq: Sequence number override (uses item.seq if None)

    Returns:
        Dict with MISSION_ITEM_INT fields
    """
    base = item_to_mavlink_dict(item)
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

    elif command_type == 'loiter':
        item.radius = mav_item.get('param3', 0)
        item.radius_units = 'meters'

    elif command_type in ['waypoint', 'survey']:
        item.heading = mav_item.get('param4', 0)

    return item


def mission_to_mavlink(mission: 'Mission') -> List[Dict[str, Any]]:
    """Convert Mission to list of MAVLink MISSION_ITEM_INT dicts"""
    return [to_mission_item_int(item, seq=i) for i, item in enumerate(mission.items)]


def mission_from_mavlink(mav_items: List[Dict[str, Any]]) -> 'Mission':
    """Convert list of MAVLink MISSION_ITEM_INT dicts to Mission"""
    from core.mission import Mission
    mission = Mission()
    for mav_item in mav_items:
        item = mission_item_from_mavlink(mav_item)
        mission.items.append(item)
    return mission
