"""
MAVLink Mission Manager
Manages single current mission and validation
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from config import get_settings
from core.mission import Mission, MissionItem
from core.validator import MissionValidator
import json


class MissionManager:
    """Manages single current mission and validation"""
    
    def __init__(self, mode: str = "mission"):
        self.current_mission: Optional[Mission] = None
        self.current_action: Optional[MissionItem] = None  # For command mode
        self.mode = mode
        self.validator = MissionValidator(get_settings())
    
    def create_mission(self) -> Mission:
        """Create a new current mission"""
        mission = Mission()
        self.current_mission = mission
        return mission
    
    def get_mission(self) -> Optional[Mission]:
        """Get current mission"""
        return self.current_mission
    
    def clear_mission(self) -> bool:
        """Clear current mission"""
        if self.current_mission:
            self.current_mission = None
            return True
        return False
    
    def has_mission(self) -> bool:
        """Check if current mission exists"""
        return self.current_mission is not None
    
    def set_mode(self, mode: str):
        """Set the validation mode"""
        self.mode = mode
    
    def insert_item_at(self, item: MissionItem, position: Optional[int] = None) -> MissionItem:
        """Insert mission item at specific position or append to end"""
        mission = self._get_current_mission_or_raise()
        
        if position is None or position <= 0:
            # Append to end (default behavior)
            item.seq = len(mission.items)
            mission.items.append(item)
        else:
            # Insert at specific position (1-based)
            insert_index = position - 1  # Convert to 0-based index
            
            if insert_index > len(mission.items):
                # If position is beyond current length, append to end
                item.seq = len(mission.items)
                mission.items.append(item)
            else:
                # Insert at specified position
                item.seq = insert_index
                mission.items.insert(insert_index, item)
                
                # Resequence all items after insertion
                for i, mission_item in enumerate(mission.items):
                    mission_item.seq = i
        
        mission.modified_at = datetime.now()
        return item
    
    def add_takeoff(self, lat: float, lon: float, alt: float, 
                   altitude_units: Optional[str] = None, 
                   latitude: Optional[float] = None, longitude: Optional[float] = None, 
                   altitude: Optional[float] = None, mgrs: Optional[str] = None,
                   heading: Optional[str] = None,
                   search_target: Optional[str] = None, detection_behavior: Optional[str] = None) -> MissionItem:
        """Add takeoff command - always goes at the beginning"""
        mission = self._get_current_mission_or_raise()
        
        item = MissionItem(
            seq=0,  # Will be set by insert_item_at
            command_type='takeoff',  # Track what type of command this is
            # Store model parameters directly
            altitude=altitude,
            altitude_units=altitude_units,
            latitude=latitude,
            longitude=longitude,
            mgrs=mgrs,
            heading=heading,
            search_target=search_target,
            detection_behavior=detection_behavior
        )
        return self.insert_item_at(item, 1)  # Always insert at position 1 (first)
    
    def add_waypoint(self, lat: float, lon: float, alt: float,
                    altitude_units: Optional[str] = None, insert_at: Optional[int] = None, 
                    latitude: Optional[float] = None, longitude: Optional[float] = None, 
                    altitude: Optional[float] = None, mgrs: Optional[str] = None,
                    distance: Optional[float] = None, heading: Optional[str] = None,
                    distance_units: Optional[str] = None, relative_reference_frame: Optional[str] = None,
                    search_target: Optional[str] = None, detection_behavior: Optional[str] = None) -> MissionItem:
        """Add waypoint command"""
        mission = self._get_current_mission_or_raise()
        
        item = MissionItem(
            seq=0,  # Will be set by insert_item_at
            command_type='waypoint',  # Track what type of command this is
            # Store model parameters directly
            altitude=altitude,
            altitude_units=altitude_units,
            latitude=latitude,
            longitude=longitude,
            mgrs=mgrs,
            distance=distance,
            heading=heading,
            distance_units=distance_units,
            relative_reference_frame=relative_reference_frame,
            search_target=search_target,
            detection_behavior=detection_behavior
        )
        return self.insert_item_at(item, insert_at)
    
    
    def add_return_to_launch(self, altitude: Optional[float] = None, 
                            altitude_units: Optional[str] = None,
                            search_target: Optional[str] = None, detection_behavior: Optional[str] = None) -> MissionItem:
        """Add return to launch command - always goes at the end"""
        mission = self._get_current_mission_or_raise()
        
        item = MissionItem(
            seq=0,  # Will be set by insert_item_at
            command_type='rtl',  # Track what type of command this is
            altitude=altitude,
            altitude_units=altitude_units,
            search_target=search_target,
            detection_behavior=detection_behavior
        )
        return self.insert_item_at(item, None)  # None = add at end
    
    def add_loiter(self, lat: float, lon: float, alt: float,
                  radius: float, radius_units: Optional[str] = None, insert_at: Optional[int] = None,
                  latitude: Optional[float] = None, longitude: Optional[float] = None, 
                  altitude: Optional[float] = None, altitude_units: Optional[str] = None,
                  mgrs: Optional[str] = None, distance: Optional[float] = None, 
                  heading: Optional[str] = None, distance_units: Optional[str] = None,
                  relative_reference_frame: Optional[str] = None,
                  search_target: Optional[str] = None, detection_behavior: Optional[str] = None) -> MissionItem:
        """Add loiter command"""
        mission = self._get_current_mission_or_raise()
        
        
        item = MissionItem(
            seq=0,  # Will be set by insert_item_at
            command_type='loiter',  # Track what type of command this is
            # Store model parameters directly
            radius=radius,
            radius_units=radius_units,
            altitude=altitude,
            altitude_units=altitude_units,
            latitude=latitude,
            longitude=longitude,
            mgrs=mgrs,
            distance=distance,
            heading=heading,
            distance_units=distance_units,
            relative_reference_frame=relative_reference_frame,
            search_target=search_target,
            detection_behavior=detection_behavior
        )
        return self.insert_item_at(item, insert_at)
    
    def add_survey(self, mode: str, center_lat: float, center_lon: float, 
                  radius: Optional[float] = None, corners: Optional[List[Dict]] = None,
                  altitude: float = 100.0, radius_units: Optional[str] = None, 
                  altitude_units: Optional[str] = None, insert_at: Optional[int] = None,
                  center_latitude: Optional[float] = None, center_longitude: Optional[float] = None,
                  survey_radius: Optional[float] = None, survey_altitude: Optional[float] = None,
                  center_mgrs: Optional[str] = None, center_distance: Optional[float] = None,
                  center_heading: Optional[str] = None, center_distance_units: Optional[str] = None,
                  center_relative_reference_frame: Optional[str] = None,
                  search_target: Optional[str] = None, detection_behavior: Optional[str] = None) -> MissionItem:
        """Add survey command"""
        mission = self._get_current_mission_or_raise()
        
        item = MissionItem(
            seq=0,  # Will be set by insert_item_at
            command_type='survey',  # Track what type of command this is
            # Store model parameters directly
            radius=survey_radius,
            radius_units=radius_units,
            altitude=survey_altitude,
            altitude_units=altitude_units,
            latitude=center_latitude,
            longitude=center_longitude,
            mgrs=center_mgrs,
            distance=center_distance,
            heading=center_heading,
            distance_units=center_distance_units,
            relative_reference_frame=center_relative_reference_frame,
            search_target=search_target,
            detection_behavior=detection_behavior
        )
        
        # Store survey-specific data as attributes
        item.survey_mode = mode
        item.corners = corners
        
        return self.insert_item_at(item, insert_at)
    
    
    def validate_mission(self, home_position: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        """Validate mission for safety and completeness

        Args:
            home_position: Dict with 'latitude', 'longitude' from GCS (optional but recommended)
        """
        mission = self._get_current_mission_or_raise()
        is_valid, errors, fixes_applied = self.validator.validate_mission(
            mission,
            self.mode,
            home_position=home_position
        )

        # Combine errors and fixes for reporting
        all_messages = errors.copy()
        if fixes_applied:
            all_messages.extend([f"Auto-fix: {fix}" for fix in fixes_applied])

        return is_valid, all_messages
    
    def _get_current_mission_or_raise(self) -> Mission:
        """Get current mission or raise error if not found"""
        if not self.current_mission:
            raise ValueError("No current mission available")
        return self.current_mission
    
    
    def get_mission_state_summary(self) -> str:
        """Get brief summary of current mission state in JSON format"""
        
        mission = self.get_mission()
        mission_state = {
            "total_mission_items": len(mission.items)
        }

        if mission and mission.items:
            # Items already have absolute coordinates after validation conversion
            items_to_display = mission.items
            
            items = {}
            for i, item in enumerate(items_to_display):
                command_type = getattr(item, 'command_type', 'unknown')
                
                item_data = {
                    "type": command_type
                }
                
                # Add key parameters
                if (hasattr(item, 'altitude') and item.altitude is not None) or (hasattr(item, 'altitude_units') and item.altitude_units is not None):
                    altitude_val = item.altitude if item.altitude is not None else "(altitude)"
                    alt_units = item.altitude_units if item.altitude_units is not None else "(altitude_units)"
                    item_data["altitude"] = f"{altitude_val} {alt_units}"
                
                # Show radius if either radius or radius_units is specified
                if (hasattr(item, 'radius') and item.radius is not None) or (hasattr(item, 'radius_units') and item.radius_units is not None):
                    radius_val = item.radius if item.radius is not None else "(radius)"
                    radius_units = item.radius_units if item.radius_units is not None else "(radius_units)"
                    item_data["radius"] = f"{radius_val} {radius_units}"
                
                # Add position info - prioritize absolute coordinates from conversion
                if (hasattr(item, 'latitude') and item.latitude is not None) and (hasattr(item, 'longitude') and item.longitude is not None):
                    lat_val = f"{item.latitude:.6f}"
                    lon_val = f"{item.longitude:.6f}"
                    item_data["position"] = f"lat/lon ({lat_val}, {lon_val})"
                elif hasattr(item, 'mgrs') and item.mgrs is not None:
                    item_data["position"] = f"MGRS {item.mgrs}"
                elif (hasattr(item, 'distance') and item.distance is not None) or (hasattr(item, 'heading') and item.heading is not None and item.command_type != 'takeoff') or (hasattr(item, 'distance_units') and item.distance_units is not None) or (hasattr(item, 'relative_reference_frame') and item.relative_reference_frame is not None):
                    distance = item.distance if item.distance is not None else "(distance)"
                    dist_units = item.distance_units if item.distance_units is not None else "(distance_units)"
                    heading = item.heading if item.heading is not None else "(heading)"
                    ref_frame = item.relative_reference_frame if item.relative_reference_frame is not None else "(relative_reference_frame)"
                    item_data["position"] = f"{distance} {dist_units} {heading} from {ref_frame}"
                
                # Always show heading for takeoff commands (VTOL transition direction)
                if item.command_type == 'takeoff' and hasattr(item, 'heading') and item.heading is not None:
                    item_data["heading"] = item.heading
                
                # Show search parameters if any are specified (for all command types)
                if ((hasattr(item, 'search_target') and item.search_target is not None) or (hasattr(item, 'detection_behavior') and item.detection_behavior is not None)):
                    search_target = item.search_target if item.search_target is not None else "(search_target)"
                    detection_behavior = item.detection_behavior if item.detection_behavior is not None else "(detection_behavior)"
                    item_data["search"] = f"target={search_target}, behavior={detection_behavior}"
                
                items[f"item_{i+1}"] = item_data
            
            mission_state["mission_state"] = items
        
        return "\n\n" + json.dumps(mission_state, indent=2)
    
    def set_current_action(self, action: MissionItem) -> None:
        """Set current action for command mode (no RTL allowed)"""
        if getattr(action, 'command_type', None) == 'rtl':
            raise ValueError("RTL commands are not allowed as current action")
        
        # Validate command type
        allowed_types = ['takeoff', 'waypoint', 'loiter', 'survey']
        command_type = getattr(action, 'command_type', None)
        if command_type not in allowed_types:
            raise ValueError(f"Invalid command type '{command_type}'. Allowed types: {', '.join(allowed_types)}")
        
        self.current_action = action
    
    def get_current_action(self) -> Optional[MissionItem]:
        """Get current action for command mode"""
        return self.current_action
    
    def get_current_action_summary(self) -> str:
        """Get brief summary of current action in JSON format"""
        if not self.current_action:
            return "\n\n{\"current_action\": null}"
        
        action = self.current_action
        command_type = getattr(action, 'command_type', 'unknown')
        
        action_data = {
            "type": command_type
        }
        
        # Add key parameters
        if (hasattr(action, 'altitude') and action.altitude is not None) or (hasattr(action, 'altitude_units') and action.altitude_units is not None):
            altitude_val = action.altitude if action.altitude is not None else "(altitude)"
            alt_units = action.altitude_units if action.altitude_units is not None else "(altitude_units)"
            action_data["altitude"] = f"{altitude_val} {alt_units}"
        
        # Show radius if either radius or radius_units is specified
        if (hasattr(action, 'radius') and action.radius is not None) or (hasattr(action, 'radius_units') and action.radius_units is not None):
            radius_val = action.radius if action.radius is not None else "(radius)"
            radius_units = action.radius_units if action.radius_units is not None else "(radius_units)"
            action_data["radius"] = f"{radius_val} {radius_units}"
        
        # Add position info
        if (hasattr(action, 'latitude') and action.latitude is not None) and (hasattr(action, 'longitude') and action.longitude is not None):
            lat_val = f"{action.latitude:.6f}"
            lon_val = f"{action.longitude:.6f}"
            action_data["position"] = f"lat/lon ({lat_val}, {lon_val})"
        elif hasattr(action, 'mgrs') and action.mgrs is not None:
            action_data["position"] = f"MGRS {action.mgrs}"
        elif (hasattr(action, 'distance') and action.distance is not None) or (hasattr(action, 'heading') and action.heading is not None and action.command_type != 'takeoff') or (hasattr(action, 'distance_units') and action.distance_units is not None) or (hasattr(action, 'relative_reference_frame') and action.relative_reference_frame is not None):
            distance = action.distance if action.distance is not None else "(distance)"
            dist_units = action.distance_units if action.distance_units is not None else "(distance_units)"
            heading = action.heading if action.heading is not None else "(heading)"
            ref_frame = action.relative_reference_frame if action.relative_reference_frame is not None else "(relative_reference_frame)"
            action_data["position"] = f"{distance} {dist_units} {heading} from {ref_frame}"
        
        # Always show heading for takeoff commands (VTOL transition direction)
        if action.command_type == 'takeoff' and hasattr(action, 'heading') and action.heading is not None:
            action_data["heading"] = action.heading
        
        # Show search parameters if any are specified
        if ((hasattr(action, 'search_target') and action.search_target is not None) or (hasattr(action, 'detection_behavior') and action.detection_behavior is not None)):
            search_target = action.search_target if action.search_target is not None else "(search_target)"
            detection_behavior = action.detection_behavior if action.detection_behavior is not None else "(detection_behavior)"
            action_data["search"] = f"target={search_target}, behavior={detection_behavior}"
        
        current_action_state = {
            "current_action": action_data
        }
        
        return "\n\n" + json.dumps(current_action_state, indent=2)