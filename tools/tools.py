"""
MAVLink Mission Planning Tools - Main module
Contains base class, shared utilities, and tool registry
"""

from typing import Tuple, Optional, Any
from langchain_core.tools import BaseTool

from core.manager import MissionManager
from config.settings import get_agent_settings
from core.parsing import parse_altitude, parse_distance, parse_radius, parse_coordinates


# Shared utility functions for tools

def unpack_measurement(value: Any, default_units: str = 'meters') -> Tuple[Optional[float], str]:
    """
    Unpack a measurement value that may be a tuple (value, units) or a scalar.

    Args:
        value: Either (value, units) tuple from validator, or scalar value
        default_units: Units to use if value is not a tuple

    Returns:
        Tuple of (value, units)
    """
    if isinstance(value, tuple):
        return value
    return (value, default_units)


def unpack_coordinates(value: Any) -> Tuple[Optional[float], Optional[float]]:
    """
    Unpack coordinates that may be a tuple (lat, lon) or None.

    Args:
        value: Either (lat, lon) tuple from validator, or None

    Returns:
        Tuple of (latitude, longitude)
    """
    if isinstance(value, tuple):
        return value
    return (None, None)


# Reusable field validators for Pydantic models

def validate_distance(v):
    """Validator for distance fields - parses string values with units"""
    if v is None:
        return None
    parsed_value, units = parse_distance(v)
    if parsed_value is None:
        return v  # Let Pydantic handle validation error
    return (parsed_value, units)


def validate_altitude(v):
    """Validator for altitude fields - parses string values with units"""
    if v is None:
        return None
    parsed_value, units = parse_altitude(v)
    if parsed_value is None:
        return v  # Let Pydantic handle validation error
    return (parsed_value, units)


def validate_radius(v):
    """Validator for radius fields - parses string values with units"""
    if v is None:
        return None
    parsed_value, units = parse_radius(v)
    if parsed_value is None:
        return v  # Let Pydantic handle validation error
    return (parsed_value, units)


def validate_coordinates(v):
    """Validator for coordinates fields - parses string values"""
    if v is None:
        return None
    lat, lon = parse_coordinates(v)
    if lat is None or lon is None:
        return v  # Let Pydantic handle validation error
    return (lat, lon)


# Base class for all mission item tools
class MAVLinkToolBase(BaseTool):
    """Base class providing shared functionality for all MAVLink tools"""
    
    def __init__(self, mission_manager: MissionManager):
        super().__init__()
        self._mission_manager = mission_manager
        # Load agent settings
        self._agent_settings = get_agent_settings()
    
    @property
    def mission_manager(self):
        return self._mission_manager
    
    def _get_command_name(self, command_type: str) -> str:
        """Get human-readable command name from type"""
        command_map = {
            'takeoff': "Takeoff",
            'waypoint': "Waypoint",
            'loiter': "Loiter",
            'rtl': "Return to Launch",
            'survey': "Survey"
        }
        return command_map.get(command_type, f"Unknown {command_type}")
    
    def _validate_mission_after_action(self) -> tuple[bool, str]:
        """Validate mission after action is performed - allows rollback if invalid"""
        mission = self.mission_manager.get_mission()
        if not mission:
            return True, ""
        
        # Use the comprehensive mission validation from MissionManager with mode-specific rules
        is_valid, message_list = self.mission_manager.validate_mission()
        
        if not is_valid:
            # Return first error as primary message
            primary_error = message_list[0] if message_list else "Mission validation failed"
            return False, primary_error
        
        # Check for auto-fixes and report them
        auto_fixes = [msg for msg in message_list if msg.startswith("Auto-fix:")]
        if auto_fixes:
            return True, ". ".join(auto_fixes)
        
        return True, ""
    
    def _save_mission_state(self):
        """Save current mission state for rollback"""
        mission = self.mission_manager.get_mission()
        if mission:
            # Save a copy of all mission items
            return [item for item in mission.items]
        return []
    
    def _restore_mission_state(self, saved_state):
        """Restore mission state from saved state"""
        mission = self.mission_manager.get_mission()
        if mission:
            mission.items.clear()
            mission.items.extend(saved_state)

    def _get_mission_state_summary(self) -> str:
        """Get brief summary of current mission state - now delegates to mission manager"""
        return self.mission_manager.get_mission_state_summary()
    
    def _build_coordinate_description(self, latitude, longitude, mgrs, distance, heading, distance_units, relative_reference_frame):
        """Build coordinate description for responses"""
        if latitude is not None and longitude is not None:
            return f"lat/long ({latitude:.6f}, {longitude:.6f})"
        elif mgrs is not None:
            return f"MGRS {mgrs}"
        elif distance is not None and heading is not None:
            units_text = f" {distance_units}" if distance_units else ""
            ref_frame = relative_reference_frame or "origin"
            return f"{distance}{units_text} {heading} from {ref_frame}"
        else:
            return "coordinates not specified"

def get_command_tools(mission_manager: MissionManager) -> list:
    """Get MAVLink tools for command mode - add tools only"""
    from .add_waypoint_tool import AddWaypointTool
    from .add_takeoff_tool import AddTakeoffTool
    from .add_rtl_tool import AddRTLTool
    from .add_loiter_tool import AddLoiterTool
    from .add_survey_tool import AddSurveyTool

    return [
        AddWaypointTool(mission_manager),
        AddTakeoffTool(mission_manager),
        AddSurveyTool(mission_manager),
        AddRTLTool(mission_manager),
        AddLoiterTool(mission_manager),
    ]

def get_mission_tools(mission_manager: MissionManager) -> list:
    """Get all MAVLink mission planning tools for mission mode"""
    from .add_waypoint_tool import AddWaypointTool
    from .add_takeoff_tool import AddTakeoffTool
    from .add_rtl_tool import AddRTLTool
    from .add_loiter_tool import AddLoiterTool
    from .add_survey_tool import AddSurveyTool
    from .update_mission_item_tool import UpdateMissionItemTool
    from .delete_mission_item_tool import DeleteMissionItemTool
    from .reorder_item_tool import ReorderItemTool
    from .move_item_tool import MoveItemTool
    
    return [
        AddWaypointTool(mission_manager),
        AddTakeoffTool(mission_manager),
        AddSurveyTool(mission_manager),
        AddRTLTool(mission_manager),
        AddLoiterTool(mission_manager),
        UpdateMissionItemTool(mission_manager),
        DeleteMissionItemTool(mission_manager),
        ReorderItemTool(mission_manager),
        MoveItemTool(mission_manager),
    ]

def get_tools_for_mode(mission_manager: MissionManager, mode: str) -> list:
    """Get appropriate tools for the specified mode"""
    if mode == "command":
        return get_command_tools(mission_manager)
    else:
        return get_mission_tools(mission_manager)