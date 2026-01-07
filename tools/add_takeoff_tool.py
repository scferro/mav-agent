"""
Add Takeoff Tool - Launch drone from ground to flight altitude
"""

from typing import Optional, Union
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from .tools import MAVLinkToolBase
from config.settings import get_agent_settings
from core.parsing import parse_altitude, parse_coordinates

# Load agent settings for Field descriptions
_agent_settings = get_agent_settings()


class TakeoffInput(BaseModel):
    """Launch drone from ground to specified flight altitude"""
    
    # GPS coordinates - RARELY needed, usually takeoff from current position
    coordinates: Optional[Union[str, tuple]] = Field(None, description="GPS coordinates as 'lat,lon' (e.g., '40.7128,-74.0060'). **Usually leave empty to takeoff from current drone position.** Only use when user specifies exact takeoff coordinates.")
    mgrs: Optional[str] = Field(None, description="MGRS coordinate string. Use when user provides MGRS grid coordinates for takeoff location.")
    
    # Target altitude - required parameter
    altitude: Optional[Union[float, str, tuple]] = Field(None, description=f"Target takeoff altitude that drone will climb to with optional units (e.g., '250 feet', '100 meters'). Extract from phrases like 'takeoff to 250 feet', 'launch to 100 meters'. This sets the flight altitude for the mission. DO NOT include unless directly specified by the user. Default = {_agent_settings['takeoff_default_altitude']} {_agent_settings['takeoff_altitude_units']}")
    
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
    
    # VTOL transition heading
    heading: Optional[str] = Field(None, description="Direction VTOL will point during transition to forward flight: 'north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest'. Typically into the wind. Use ONLY when direction is specified.")


class AddTakeoffTool(MAVLinkToolBase):
    name: str = "add_takeoff"
    description: str = "Add takeoff command to launch drone from ground to flight altitude. Always inserted as the FIRST mission item. Use when user wants drone to take off, launch, or lift off. Use for commands like 'takeoff', 'launch', 'lift off', especially when altitude is specified like 'takeoff to 200 feet', 'launch to 100 meters'."
    args_schema: type = TakeoffInput
    
    def __init__(self, mission_manager):
        super().__init__(mission_manager)
    
    def _run(self, coordinates: Optional[Union[str, tuple]] = None, 
             altitude: Optional[Union[float, tuple]] = None, mgrs: Optional[str] = None, heading: Optional[str] = None) -> str:
        # Create response
        response = ""

        # Populate response
        try:
            # Parse measurement tuples from validators
            if isinstance(altitude, tuple):
                altitude_value, altitude_units = altitude
            else:
                altitude_value, altitude_units = altitude, 'meters'
            
            # Parse coordinates from validator
            if isinstance(coordinates, tuple):
                latitude, longitude = coordinates
            else:
                latitude, longitude = None, None
            
            # Save current mission state for potential rollback
            saved_state = self._save_mission_state()
            
            # Build coordinate description - for takeoff, usually just use altitude
            coord_desc = ""
            if latitude is not None and longitude is not None:
                coord_desc = f" from lat/long ({latitude:.6f}, {longitude:.6f})"
            elif mgrs is not None:
                coord_desc = f" from MGRS {mgrs}"
            else:
                coord_desc = ""
            
            # For mission manager, use lat/lon if provided, otherwise use 0 (no guessing)
            actual_lat = latitude if latitude is not None else 0.0
            actual_lon = longitude if longitude is not None else 0.0
            actual_alt = altitude_value if altitude_value is not None else 10.0  # Default takeoff altitude
            
            item = self.mission_manager.add_takeoff(
                actual_lat, actual_lon, actual_alt, 
                altitude_units=altitude_units,
                latitude=latitude,
                longitude=longitude,
                altitude=altitude_value,
                mgrs=mgrs,
                heading=heading
            )
            
            # Validate mission after adding takeoff
            is_valid, validation_msg = self._validate_mission_after_action()
            if not is_valid:
                # Rollback the action
                self._restore_mission_state(saved_state)
                return f"Planning Error: {validation_msg}" + self._get_mission_state_summary()
            else:
                # Build response message with preserved units
                altitude_msg = f"{altitude_value} {altitude_units}" if altitude_value is not None else "default altitude"
                heading_msg = f", Heading={heading}" if heading is not None else ""
                response = f"Takeoff command added to mission{coord_desc}, Alt={altitude_msg}{heading_msg} (Item {item.seq + 1})"
                
                # Include auto-fix notifications if any
                if validation_msg:
                    response += f". {validation_msg}"
                
                response += self._get_mission_state_summary()
            
        except Exception as e:
            response = f"Error: {str(e)}"

        return response