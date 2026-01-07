"""
Add Survey Tool - Create systematic survey patterns for area coverage
"""

from typing import Optional, List, Union
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from .tools import MAVLinkToolBase
from config.settings import get_agent_settings
from core.parsing import parse_altitude, parse_distance, parse_radius, parse_coordinates

# Load agent settings for Field descriptions
_agent_settings = get_agent_settings()


class SurveyInput(BaseModel):
    """Create survey pattern over specified area using center+radius OR corner points"""
    
    # ===== CENTER + RADIUS SURVEY =====
    # Center location 
    coordinates: Optional[Union[str, tuple]] = Field(None, description="GPS coordinates as 'lat,lon' for survey center (e.g., '40.7128,-74.0060'). **Avoid using unless user provides exact coordinates.** Prefer distance/heading/reference_frame for more intuitive positioning.")
    mgrs: Optional[str] = Field(None, description="MGRS coordinate for survey center. Use ONLY when user provides MGRS coordinates.")
    
    # Relative positioning
    distance: Optional[Union[float, str, tuple]] = Field(None, description="Distance to survey center from reference point with optional units (e.g., '2 miles', '1000 meters', '500 ft'). Use with heading. Can set to 0.0 to survey around the reference frame.")
    heading: Optional[str] = Field(None, description="Direction to survey center: 'north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest'. Use with distance.")
    relative_reference_frame: Optional[str] = Field(None, description="Reference point for center distance: 'origin' (takeoff), 'last_waypoint'. You MUST pick one, make an educated guess if using relative positioning. Use 'origin' when user references 'start', 'takeoff', 'here', etc. Otherwise assume last_waypoint.")
    
    # Survey area size (for center+radius mode)
    radius: Optional[Union[float, str, tuple]] = Field(None, description=f"Radius of circular survey area with optional units (e.g., '1 mile', '500 meters', '1000 ft'). Default = {_agent_settings['survey_default_radius']} {_agent_settings['survey_radius_units']}")
    
    # ===== CORNER POINTS SURVEY =====
    # Corner points defining survey boundary (up to 4 corners for rectangular area)
    corner1_lat: Optional[float] = Field(None, description="Latitude of first corner point.")
    corner1_lon: Optional[float] = Field(None, description="Longitude of first corner point.")
    corner1_mgrs: Optional[str] = Field(None, description="MGRS coordinate for first corner point.")
    corner2_lat: Optional[float] = Field(None, description="Latitude of second corner point.")
    corner2_lon: Optional[float] = Field(None, description="Longitude of second corner point.")
    corner2_mgrs: Optional[str] = Field(None, description="MGRS coordinate for second corner point.")
    corner3_lat: Optional[float] = Field(None, description="Latitude of third corner point.")
    corner3_lon: Optional[float] = Field(None, description="Longitude of third corner point.")
    corner3_mgrs: Optional[str] = Field(None, description="MGRS coordinate for third corner point.")
    corner4_lat: Optional[float] = Field(None, description="Latitude of fourth corner point.")
    corner4_lon: Optional[float] = Field(None, description="Longitude of fourth corner point.")
    corner4_mgrs: Optional[str] = Field(None, description="MGRS coordinate for fourth corner point.")
    
    # ===== SURVEY PARAMETERS =====
    # Survey flight parameters
    altitude: Optional[Union[float, str, tuple]] = Field(None, description=f"Flight altitude for the survey pattern with optional units (e.g., '150 feet', '50 meters'). Default = {_agent_settings['survey_default_altitude']} {_agent_settings['survey_altitude_units']}")
    
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
    seq: Optional[int] = Field(None, description="Position to insert survey in mission (1-based index). The survey will be inserted AT this position, shifting existing items down. Omit to add at end.")
    
    # Search parameters
    search_target: Optional[str] = Field(None, description="Target description for AI to search for during survey (e.g., 'vehicles', 'people', 'buildings'). ONLY use if the user specifically request 'AI', 'detection', or specifies a target.")
    detection_behavior: Optional[str] = Field(None, description="Detection behavior: 'tag_and_continue' (mark targets and continue mission) or 'detect_and_monitor' (abort mission and circle detected target). Use with search_target")


class AddSurveyTool(MAVLinkToolBase):
    name: str = "add_survey"
    description: str = "Create survey pattern for area coverage. Two modes: CENTER+RADIUS (specify center point and radius) or CORNER POINTS (define polygon boundary). The drone can perform AI searches for specified targets with its camera while surverying. Use for survey commands like 'survey 1km radius around this point' or 'search the area bounded by these corners'. Specify Lat/Long OR MGRS OR distance/heading/reference. Do not mix location systems."
    args_schema: type = SurveyInput
    
    def __init__(self, mission_manager):
        super().__init__(mission_manager)

    def _run(self, coordinates: Optional[Union[str, tuple]] = None, mgrs: Optional[str] = None,
             distance: Optional[Union[float, tuple]] = None, heading: Optional[str] = None,
             relative_reference_frame: Optional[str] = None, radius: Optional[Union[float, tuple]] = None,
             corner1_lat: Optional[float] = None, corner1_lon: Optional[float] = None, corner1_mgrs: Optional[str] = None,
             corner2_lat: Optional[float] = None, corner2_lon: Optional[float] = None, corner2_mgrs: Optional[str] = None,
             corner3_lat: Optional[float] = None, corner3_lon: Optional[float] = None, corner3_mgrs: Optional[str] = None,
             corner4_lat: Optional[float] = None, corner4_lon: Optional[float] = None, corner4_mgrs: Optional[str] = None,
             altitude: Optional[Union[float, tuple]] = None,
             seq: Optional[int] = None, search_target: Optional[str] = None, detection_behavior: Optional[str] = None) -> str:
        try:
            # Parse measurement tuples from validators
            if isinstance(distance, tuple):
                distance_value, distance_units = distance
            else:
                distance_value, distance_units = distance, 'meters'
            
            if isinstance(radius, tuple):
                radius_value, radius_units = radius
            else:
                radius_value, radius_units = radius, 'meters'
            
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
            
            # Build corner points list from individual parameters
            corner_points = []
            if corner1_lat is not None or corner1_mgrs is not None:
                corner_points.append({'lat': corner1_lat, 'lon': corner1_lon, 'mgrs': corner1_mgrs})
            if corner2_lat is not None or corner2_mgrs is not None:
                corner_points.append({'lat': corner2_lat, 'lon': corner2_lon, 'mgrs': corner2_mgrs})
            if corner3_lat is not None or corner3_mgrs is not None:
                corner_points.append({'lat': corner3_lat, 'lon': corner3_lon, 'mgrs': corner3_mgrs})
            if corner4_lat is not None or corner4_mgrs is not None:
                corner_points.append({'lat': corner4_lat, 'lon': corner4_lon, 'mgrs': corner4_mgrs})
            
            # Determine survey mode
            if corner_points and len(corner_points) > 0:
                # Corner points mode
                survey_mode = "polygon"
                area_desc = f"polygon with {len(corner_points)} corners"
            elif latitude is not None or distance_value is not None:
                # Center-based mode
                if radius_value is not None:
                    survey_mode = "circular"
                    area_desc = f"circular area (radius: {radius_value} {radius_units or 'meters'})"
                else:
                    return "Planning Error: Survey area size not specified. Provide radius for center-based survey" + self._get_mission_state_summary()
            else:
                return "Planning Error: Survey area not defined. Provide center coordinates OR corner points" + self._get_mission_state_summary()
            
            # Build coordinate description for center (if applicable)
            if survey_mode != "polygon":
                center_desc = self._build_coordinate_description(latitude, longitude, mgrs, 
                                                               distance_value, heading, distance_units, 
                                                               relative_reference_frame)
            else:
                center_desc = "defined by corner points"
            
            # Set defaults
            actual_altitude = altitude_value or 100.0
            actual_altitude_units = altitude_units or "meters"
            
            # Create a survey mission item
            item = self.mission_manager.add_survey(
                mode=survey_mode,
                center_lat=latitude or 0.0,
                center_lon=longitude or 0.0,
                radius=radius_value or 0.0,
                corners=corner_points,
                altitude=actual_altitude,
                radius_units=radius_units,
                altitude_units=actual_altitude_units,
                insert_at=seq,
                center_latitude=latitude,
                center_longitude=longitude,
                survey_radius=radius_value,
                survey_altitude=altitude_value,
                center_mgrs=mgrs,
                center_distance=distance_value,
                center_heading=heading,
                center_distance_units=distance_units,
                center_relative_reference_frame=relative_reference_frame,
                search_target=search_target,
                detection_behavior=detection_behavior
            )
            
            # Validate mission after adding survey
            is_valid, validation_msg = self._validate_mission_after_action()
            if not is_valid:
                # Rollback the action
                self._restore_mission_state(saved_state)
                return f"Planning Error: {validation_msg}" + self._get_mission_state_summary()
            
            # Build response with preserved units
            response = f"Survey pattern created for {area_desc} at {center_desc}, Alt={altitude_value} {altitude_units} (Item {item.seq + 1})"
            
            # Include auto-fix notifications if any
            if validation_msg:
                response += f". {validation_msg}"
            
            response += self._get_mission_state_summary()
            return response
            
        except Exception as e:
            response = f"Error: {str(e)}"
            
        return response