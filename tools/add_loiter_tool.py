"""
Add Loiter Tool - Create circular orbit/loiter pattern
"""

from typing import Optional, Union
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from .tools import MAVLinkToolBase
from config.settings import get_agent_settings
from core.parsing import parse_altitude, parse_distance, parse_radius, parse_coordinates

# Load agent settings for Field descriptions
_agent_settings = get_agent_settings()

class LoiterInput(BaseModel):
    """Create circular orbit/loiter pattern at specified location with defined radius"""

    # GPS coordinates
    coordinates: Optional[Union[str, tuple]] = Field(None, description="GPS coordinates as 'lat,lon' (e.g., '40.7128,-74.0060'). **Avoid using unless user provides exact coordinates.** Prefer distance/heading/reference_frame for more intuitive positioning.")
    mgrs: Optional[str] = Field(None, description="MGRS coordinate for orbit center. Use ONLY when user provides MGRS coordinates.")
    
    # Relative positioning 
    distance: Optional[Union[float, str, tuple]] = Field(None, description="Distance to orbit center from reference point with optional units (e.g., '2 miles', '1000 meters', '500 ft'). Use with heading. Can set to 0.0 to orbit AT the reference frame.")
    heading: Optional[str] = Field(None, description="Direction to orbit center: 'north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest'. Use with distance.")
    relative_reference_frame: Optional[str] = Field(None, description="Reference point for distance: 'origin' (takeoff), 'last_waypoint'. You MUST pick one, make an educated guess if using relative positioning. Use 'origin' when user references 'start', 'takeoff', 'here', etc. Otherwise assume last_waypoint.")
    
    # Orbit radius - critical parameter often specified by user
    radius: Optional[Union[float, str, tuple]] = Field(None, description=f"Radius of the circular orbit with optional units (e.g., '500 feet', '100 meters', '0.5 miles'). Default = {_agent_settings['loiter_default_radius']} {_agent_settings['loiter_radius_units']}")
    
    # Optional orbit altitude
    altitude: Optional[Union[float, str, tuple]] = Field(None, description=f"Altitude for the orbit pattern with optional units (e.g., '150 feet', '50 meters'). Specify only if user mentions height. Default = {_agent_settings['loiter_default_altitude']} {_agent_settings['loiter_altitude_units']}")
    
    @field_validator('distance', mode='before')
    @classmethod
    def parse_distance_field(cls, v):
        if v is None:
            return None
        parsed_value, units = parse_distance(v)
        if parsed_value is None:
            return v  # Let Pydantic handle validation error
        return (parsed_value, units)
    
    @field_validator('radius', mode='before')
    @classmethod
    def parse_radius_field(cls, v):
        if v is None:
            return None
        parsed_value, units = parse_radius(v)
        if parsed_value is None:
            return v  # Let Pydantic handle validation error
        return (parsed_value, units)
    
    @field_validator('altitude', mode='before')
    @classmethod
    def parse_altitude_field(cls, v):
        if v is None:
            return None
        parsed_value, units = parse_altitude(v)
        if parsed_value is None:
            return v  # Let Pydantic handle validation error
        return (parsed_value, units)
    
    @field_validator('coordinates', mode='before')
    @classmethod
    def parse_coordinates_field(cls, v):
        if v is None:
            return None
        lat, lon = parse_coordinates(v)
        if lat is None or lon is None:
            return v  # Let Pydantic handle validation error
        return (lat, lon)
    
    # Insertion position
    seq: Optional[int] = Field(None, description="Position to insert loiter in mission (1-based index). The loiter will be inserted AT this position, shifting existing items down. Example: seq=2 means the new loiter becomes item #2, and the old item #2 becomes item #3. Omit to add at end.")
    
    # Search parameters
    search_target: Optional[str] = Field(None, description="Target description for AI to search for during survey (e.g., 'vehicles', 'people', 'buildings'). Do not use if user does not specify.")
    detection_behavior: Optional[str] = Field(None, description="Detection behavior: 'tag_and_continue' (mark targets and continue mission) or 'detect_and_monitor' (abort mission and circle detected target). Use with search_target")
    

class AddLoiterTool(MAVLinkToolBase):
    name: str = "add_loiter"
    description: str = "Add circular orbit/loiter pattern at specified location. Use when user wants drone to fly in circles, orbit, or loiter. The drone can perform AI searches with its camera while loitering. Use for commands like 'orbit', 'circle', 'loiter', or when radius is mentioned like 'circle 2 miles north with 200m radius'. Specify Lat/Long OR MGRS OR distance/heading/reference. Do not mix location systems."
    args_schema: type = LoiterInput
    
    def __init__(self, mission_manager):
        super().__init__(mission_manager)

    def _run(self, coordinates: Optional[Union[str, tuple]] = None, mgrs: Optional[str] = None,
             distance: Optional[Union[float, tuple]] = None, heading: Optional[str] = None,
             relative_reference_frame: Optional[str] = None, altitude: Optional[Union[float, tuple]] = None,
             radius: Optional[Union[float, tuple]] = None, seq: Optional[int] = None,
             search_target: Optional[str] = None, detection_behavior: Optional[str] = None) -> str:
        try:
            # Parse measurement tuples from validators
            if isinstance(distance, tuple):
                distance_value, distance_units = distance
            else:
                distance_value, distance_units = distance, 'meters'
            
            if isinstance(altitude, tuple):
                altitude_value, altitude_units = altitude
            else:
                altitude_value, altitude_units = altitude, 'meters'
            
            if isinstance(radius, tuple):
                radius_value, radius_units = radius
            else:
                radius_value, radius_units = radius, 'meters'
            
            # Parse coordinates from validator
            if isinstance(coordinates, tuple):
                latitude, longitude = coordinates
            else:
                latitude, longitude = None, None
            
            # Save current mission state for potential rollback
            saved_state = self._save_mission_state()
            
            # Build coordinate description following wx-agent pattern
            coord_desc = self._build_coordinate_description(latitude, longitude, mgrs, distance_value, heading, distance_units, relative_reference_frame)
            
            # For mission manager, use lat/lon if provided, otherwise use 0 (no guessing)
            actual_lat = latitude if latitude is not None else 0.0
            actual_lon = longitude if longitude is not None else 0.0
            actual_alt = altitude_value if altitude_value is not None else 0.0
            actual_radius = radius_value if radius_value is not None else 50.0  # Default radius
            
            item = self.mission_manager.add_loiter(
                actual_lat, actual_lon, actual_alt, actual_radius,
                radius_units=radius_units,
                insert_at=seq,
                latitude=latitude,
                longitude=longitude,
                altitude=altitude_value,
                altitude_units=altitude_units,
                mgrs=mgrs,
                distance=distance_value,
                heading=heading,
                distance_units=distance_units,
                relative_reference_frame=relative_reference_frame,
                search_target=search_target,
                detection_behavior=detection_behavior
            )
            
            # Validate mission after adding loiter
            is_valid, validation_msg = self._validate_mission_after_action()
            if not is_valid:
                # Rollback the action
                self._restore_mission_state(saved_state)
                return f"Planning Error: {validation_msg}" + self._get_mission_state_summary()
            
            # Build response with preserved units
            altitude_msg = f"{altitude_value} {altitude_units}" if altitude_value is not None else "not specified"
            radius_msg = f"{radius_value} {radius_units}" if radius_value is not None else "not specified"
            
            response = f"Loiter command added to mission: {coord_desc}, Alt={altitude_msg}, Radius={radius_msg}, (Item {item.seq + 1})"
            
            # Include auto-fix notifications if any
            if validation_msg:
                response += f". {validation_msg}"
            
            response += self._get_mission_state_summary()
            return response
            
        except Exception as e:
            return f"Error: {str(e)}"