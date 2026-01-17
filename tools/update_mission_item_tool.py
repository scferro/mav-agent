"""
Update Mission Item Tool - Modify specific mission item by sequence number
"""

from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator

from .tools import MAVLinkToolBase, validate_altitude, validate_radius, unpack_measurement


class UpdateMissionItemInput(BaseModel):
    """Update specific mission item by its sequence number in the mission"""
    
    seq: int = Field(description="Mission item number to update (1=first item, 2=second item, etc.)")
    
    
    # Altitude specification
    altitude: Optional[Union[float, str, tuple]] = Field(None, description="New altitude for the specified item with optional units (e.g., '150 feet', '50 meters').")
    
    # Orbit radius (loiter only)
    radius: Optional[Union[float, str, tuple]] = Field(None, description="New radius for orbit/loiter items only with optional units (e.g., '500 feet', '100 meters'). Only works on loiter commands.")
    
    
    @field_validator('altitude', mode='before')
    @classmethod
    def parse_altitude_field(cls, v):
        return validate_altitude(v)

    @field_validator('radius', mode='before')
    @classmethod
    def parse_radius_field(cls, v):
        return validate_radius(v)
    
    
    # Search parameters
    search_target: Optional[str] = Field(None, description="Target description for AI to search for during this mission item (e.g., 'vehicles', 'people', 'buildings').")
    detection_behavior: Optional[str] = Field(None, description="Detection behavior: 'tag_and_continue' (mark targets and continue mission) or 'detect_and_monitor' (abort mission and circle detected target).")


class UpdateMissionItemTool(MAVLinkToolBase):
    name: str = "update_mission_item"
    description: str = "Update mission item altitude, radius, and search parameters by sequence number. Use when user wants to modify item properties like height, orbit size, or search behavior. For position changes, use move_item tool. You CANNOT update a mission item TYPE - delete and recreate instead."
    args_schema: type = UpdateMissionItemInput
    
    def __init__(self, mission_manager):
        super().__init__(mission_manager)
    
    def _run(self, seq: int, altitude: Optional[Union[float, tuple]] = None, 
             radius: Optional[Union[float, tuple]] = None,
             search_target: Optional[str] = None, detection_behavior: Optional[str] = None) -> str:
        # Create response
        response = ""

        # Populate response
        try:
            # Unpack measurement tuples from validators
            altitude_value, altitude_units = unpack_measurement(altitude)
            radius_value, radius_units = unpack_measurement(radius)
            
            mission = self.mission_manager.get_mission()
            if not mission or not mission.items:
                response = "Error: No mission items to update"
            else:
                # Save current mission state for potential rollback
                saved_state = self._save_mission_state()
                
                # Convert 1-based indexing to 0-based
                zero_based_seq = seq - 1
                if seq < 1 or zero_based_seq >= len(mission.items):
                    response = f"Error: Invalid sequence number {seq}. Mission has {len(mission.items)} items (1 to {len(mission.items)})"
                else:
                    item = mission.items[zero_based_seq]
                    changes_made = []
                    command_type = getattr(item, 'command_type', None)
                    
                    # Update altitude if provided
                    if altitude_value is not None:
                        if hasattr(item, 'altitude'):
                            item.altitude = altitude_value
                        if altitude_units and hasattr(item, 'altitude_units'):
                            item.altitude_units = altitude_units
                        changes_made.append(f"altitude to {altitude_value} {altitude_units or 'meters'}")
                    
                    # Update radius if provided (for loiter and survey items)
                    if radius_value is not None:
                        if command_type in ['loiter', 'survey']:
                            if hasattr(item, 'radius'):
                                item.radius = radius_value
                            if radius_units and hasattr(item, 'radius_units'):
                                item.radius_units = radius_units
                            changes_made.append(f"radius to {radius_value} {radius_units or 'meters'}")
                        else:
                            response = f"Error: Cannot modify radius on item {seq} - not a loiter/survey command"
                    
                    # Update search parameters if provided
                    if search_target is not None:
                        if hasattr(item, 'search_target'):
                            item.search_target = search_target
                        changes_made.append(f"search_target to {search_target}")
                    
                    if detection_behavior is not None:
                        if hasattr(item, 'detection_behavior'):
                            item.detection_behavior = detection_behavior
                        changes_made.append(f"detection_behavior to {detection_behavior}")
                    
                    # Check if we have a successful update
                    if not response.startswith("Error:"):
                        if not changes_made:
                            response = "No changes specified - provide altitude, radius, search_target, or detection_behavior parameters to modify. For position changes, use move_item tool."
                        else:
                            # Validate mission after modifications
                            is_valid, error_msg = self._validate_mission_after_action()
                            if not is_valid:
                                # Rollback the action
                                self._restore_mission_state(saved_state)
                                return f"Planning Error: {error_msg}" + self._get_mission_state_summary()
                            else:
                                changes_str = ", ".join(changes_made)
                                response = f"Updated mission item {seq}: {changes_str}"
                                response += self._get_mission_state_summary()
            
        except Exception as e:
            response = f"Error: {str(e)}"

        return response