"""
Move Item Tool - Change geographical position of mission item
"""

from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator

from .tools import MAVLinkToolBase, validate_distance, validate_coordinates, unpack_measurement, unpack_coordinates


class MoveItemInput(BaseModel):
    """Move mission item to new geographical position"""
    
    seq: int = Field(description="Mission item number to move (1=first item, 2=second item, etc.)")
    
    # GPS coordinates - DISCOURAGED, prefer relative positioning
    coordinates: Optional[Union[str, tuple]] = Field(None, description="New GPS coordinates as 'lat,lon' (e.g., '40.7128,-74.0060'). **Avoid using unless user provides exact coordinates.** Prefer distance/heading/reference_frame for more intuitive positioning.")
    mgrs: Optional[str] = Field(None, description="New MGRS coordinate string like '11SMT1234567890'.")
    
    # Relative positioning - PREFERRED method for positioning
    distance: Optional[Union[float, str, tuple]] = Field(None, description="New distance value for relative positioning with optional units (e.g., '2 miles', '1000 meters', '500 ft').")
    heading: Optional[str] = Field(None, description="New compass direction as text.")
    relative_reference_frame: Optional[str] = Field(None, description="New reference point for distance measurement. Use 'origin' when user references 'start', 'takeoff', 'here', etc., 'last_waypoint' if the user references the last waypoint, or 'self' to move the item relative to its current position. Use 'self' for commands like 'move the waypoint 2 mi west' 'update the orbit point to be 1500m south of current position'. Any time you want to move an item relative to its current position, you should use 'self'")
    
    @field_validator('distance', mode='before')
    @classmethod
    def parse_distance_field(cls, v):
        return validate_distance(v)

    @field_validator('coordinates', mode='before')
    @classmethod
    def parse_coordinates_field(cls, v):
        return validate_coordinates(v)


class MoveItemTool(MAVLinkToolBase):
    name: str = "move_item"
    description: str = "Move mission item to new geographical position using GPS coordinates, MGRS, or relative positioning. For changing altitude, radius, or search parameters, use update_mission_item tool instead."
    args_schema: type = MoveItemInput
    
    def __init__(self, mission_manager):
        super().__init__(mission_manager)
    
    def _run(self, seq: int, coordinates: Optional[Union[str, tuple]] = None, mgrs: Optional[str] = None,
             distance: Optional[Union[float, tuple]] = None, heading: Optional[str] = None, 
             relative_reference_frame: Optional[str] = None) -> str:
        
        try:
            # Unpack measurement tuples from validators
            distance_value, distance_units = unpack_measurement(distance)
            latitude, longitude = unpack_coordinates(coordinates)
            
            mission = self.mission_manager.get_mission()
            if not mission or not mission.items:
                return "Error: No mission items to move"
            
            # Save current mission state for potential rollback
            saved_state = self._save_mission_state()
            
            # Convert 1-based indexing to 0-based
            zero_based_seq = seq - 1
            if seq < 1 or zero_based_seq >= len(mission.items):
                return f"Error: Invalid sequence number {seq}. Mission has {len(mission.items)} items (1 to {len(mission.items)})"
            
            item = mission.items[zero_based_seq]
            changes_made = []
            
            # Check if this item supports position updates (waypoint, loiter, survey) or heading (takeoff)
            command_type = getattr(item, 'command_type', None)
            supports_position = command_type in ['waypoint', 'loiter', 'survey']
            supports_heading = command_type in ['takeoff', 'waypoint', 'loiter', 'survey']
            
            # Update GPS coordinates if provided
            if latitude is not None and longitude is not None:
                if supports_position:
                    item.latitude = latitude
                    item.longitude = longitude
                    # Clear relative positioning when setting GPS coordinates
                    if hasattr(item, 'distance'): item.distance = None
                    if hasattr(item, 'heading'): item.heading = None
                    if hasattr(item, 'mgrs'): item.mgrs = None
                    if hasattr(item, 'relative_reference_frame'): item.relative_reference_frame = None
                    changes_made.append(f"position to lat/long ({latitude:.6f}, {longitude:.6f})")
                else:
                    return f"Error: Cannot modify GPS coordinates on item {seq} - {command_type} commands don't support positioning"
            
            # Update MGRS coordinate if provided
            if mgrs is not None:
                if supports_position:
                    item.mgrs = mgrs
                    # Clear other positioning when setting MGRS
                    if hasattr(item, 'latitude'): item.latitude = None
                    if hasattr(item, 'longitude'): item.longitude = None
                    if hasattr(item, 'distance'): item.distance = None
                    if hasattr(item, 'heading'): item.heading = None
                    if hasattr(item, 'relative_reference_frame'): item.relative_reference_frame = None
                    changes_made.append(f"position to MGRS {mgrs}")
                else:
                    return f"Error: Cannot modify MGRS coordinates on item {seq} - {command_type} commands don't support positioning"
            
            # Update relative positioning if provided
            if distance_value is not None and heading is not None:
                if supports_position:
                    # All positioning (including 'self' reference) converts to absolute coordinates
                    from core.units import calculate_absolute_coordinates

                    try:
                        # Helper to find takeoff/origin coordinates from mission
                        def get_origin_coordinates():
                            mission = self.mission_manager.get_mission()
                            if mission and mission.items:
                                # Find first takeoff item
                                for mi in mission.items:
                                    if mi.command_type == 'takeoff' and mi.latitude is not None and mi.longitude is not None:
                                        return mi.latitude, mi.longitude
                            return None, None

                        # Determine reference point
                        if relative_reference_frame == 'self':
                            # Use current item coordinates as reference (items now always have absolute coords)
                            ref_lat, ref_lon = item.latitude, item.longitude
                        elif relative_reference_frame == 'origin':
                            # Use takeoff origin from mission
                            ref_lat, ref_lon = get_origin_coordinates()
                            if ref_lat is None or ref_lon is None:
                                return "Error: Cannot use 'origin' reference - no takeoff item with coordinates found in mission."
                        elif relative_reference_frame == 'last_waypoint':
                            # Find last waypoint coordinates
                            mission = self.mission_manager.get_mission()
                            last_coords = self._find_last_waypoint_coordinates(mission, seq - 1)
                            if last_coords:
                                ref_lat, ref_lon = last_coords
                            else:
                                # Fall back to origin if no last waypoint found
                                ref_lat, ref_lon = get_origin_coordinates()
                                if ref_lat is None or ref_lon is None:
                                    return "Error: Cannot find reference point - no last waypoint and no takeoff item with coordinates found."
                        else:
                            # Default to origin
                            ref_lat, ref_lon = get_origin_coordinates()
                            if ref_lat is None or ref_lon is None:
                                return "Error: Cannot determine origin - no takeoff item with coordinates found in mission."
                        
                        # Convert relative positioning to new absolute coordinates
                        new_lat, new_lon = calculate_absolute_coordinates(
                            ref_lat, ref_lon, distance_value, heading, distance_units
                        )
                        
                        # Update item with new absolute coordinates
                        item.latitude = new_lat
                        item.longitude = new_lon
                        
                        # Clear all positioning attributes except lat/lon
                        if hasattr(item, 'mgrs'): item.mgrs = None
                        if hasattr(item, 'distance'): item.distance = None
                        if hasattr(item, 'heading'): item.heading = None
                        if hasattr(item, 'distance_units'): item.distance_units = None
                        if hasattr(item, 'relative_reference_frame'): item.relative_reference_frame = None
                        
                        units_text = f" {distance_units}" if distance_units else ""
                        ref_desc = "current location" if relative_reference_frame == 'self' else (relative_reference_frame or "origin")
                        changes_made.append(f"position to {distance_value}{units_text} {heading} from {ref_desc} (new coordinates: {new_lat:.6f}, {new_lon:.6f})")
                        
                    except Exception as e:
                        return f"Error: Failed to calculate new position - {str(e)}"
                else:
                    return f"Error: Cannot modify position on item {seq} - {command_type} commands don't support positioning"
            
            # Update heading only (for takeoff VTOL transition direction)
            if heading is not None and distance is None:
                if supports_heading:
                    item.heading = heading
                    changes_made.append(f"heading to {heading}")
                else:
                    return f"Error: Cannot modify heading on item {seq} - {command_type} commands don't support heading"
            
            # Check if we have a successful update
            if not changes_made:
                return "No position changes specified - provide GPS coordinates (lat/long), MGRS, or relative positioning (distance/heading) to move the item"
            
            # Validate mission after modifications
            is_valid, error_msg = self._validate_mission_after_action()
            if not is_valid:
                # Rollback the action
                self._restore_mission_state(saved_state)
                return f"Planning Error: {error_msg}" + self._get_mission_state_summary()
            
            changes_str = ", ".join(changes_made)
            response = f"Moved mission item {seq}: {changes_str}"
            response += self._get_mission_state_summary()
            return response
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _find_last_waypoint_coordinates(self, mission, current_index):
        """Find coordinates from last waypoint or navigation command"""
        for i in range(current_index - 1, -1, -1):
            prev_item = mission.items[i]
            if (getattr(prev_item, 'command_type', None) in ['waypoint', 'takeoff', 'loiter', 'survey'] and
                hasattr(prev_item, 'latitude') and prev_item.latitude is not None and
                hasattr(prev_item, 'longitude') and prev_item.longitude is not None):
                return (prev_item.latitude, prev_item.longitude)
        return None