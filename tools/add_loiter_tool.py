"""
Add Loiter Tool - Create loiter/hover pattern
Two variants:
  AddLoiterTool            — multirotor/ground: hover in place, no radius
  AddLoiterWithRadiusTool  — fixed-wing/VTOL: orbit with radius
"""

from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator

from .tools import MAVLinkToolBase, validate_altitude, validate_distance, validate_radius, validate_coordinates, unpack_measurement, unpack_coordinates
from config.settings import get_agent_settings

# Load agent settings for Field descriptions
_agent_settings = get_agent_settings()


class LoiterInputNoRadius(BaseModel):
    """Loiter/hover at a location (no orbit radius — hover in place)"""

    # GPS coordinates
    coordinates: Optional[Union[str, tuple]] = Field(None, description="GPS coordinates as 'lat,lon' (e.g., '40.7128,-74.0060'). **Avoid using unless user provides exact coordinates.** Prefer distance/heading/reference_frame for more intuitive positioning.")
    mgrs: Optional[str] = Field(None, description="MGRS coordinate for loiter center. Use ONLY when user provides MGRS coordinates.")

    # Relative positioning
    distance: Optional[Union[float, str, tuple]] = Field(None, description="Distance to loiter point from reference point with optional units (e.g., '2 miles', '1000 meters', '500 ft'). Use with heading. Can set to 0.0 to hover AT the reference frame.")
    heading: Optional[str] = Field(None, description="Direction to loiter point: 'north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest'. Use with distance.")
    relative_reference_frame: Optional[str] = Field(None, description="Reference point for distance: 'origin' (takeoff), 'last_waypoint'. You MUST pick one, make an educated guess if using relative positioning. Use 'origin' when user references 'start', 'takeoff', 'here', etc. Otherwise assume last_waypoint.")

    # Optional altitude
    altitude: Optional[Union[float, str, tuple]] = Field(None, description=f"Altitude for the hover with optional units (e.g., '150 feet', '50 meters'). Specify only if user mentions height. Default = {_agent_settings['loiter_default_altitude']} {_agent_settings['loiter_altitude_units']}")

    # Insertion position
    seq: Optional[int] = Field(None, description="Position to insert loiter in mission (1-based index). The loiter will be inserted AT this position, shifting existing items down. Omit to add at end.")

    # Search parameters
    search_target: Optional[str] = Field(None, description="Target description for AI to search for during loiter (e.g., 'vehicles', 'people', 'buildings'). Do not use if user does not specify.")
    detection_behavior: Optional[str] = Field(None, description="Detection behavior: 'tag_and_continue' or 'detect_and_monitor'. Use with search_target.")

    @field_validator('distance', mode='before')
    @classmethod
    def parse_distance_field(cls, v):
        return validate_distance(v)

    @field_validator('altitude', mode='before')
    @classmethod
    def parse_altitude_field(cls, v):
        return validate_altitude(v)

    @field_validator('coordinates', mode='before')
    @classmethod
    def parse_coordinates_field(cls, v):
        return validate_coordinates(v)


class LoiterInputWithRadius(BaseModel):
    """Create circular orbit/loiter pattern at specified location with defined radius"""

    # GPS coordinates
    coordinates: Optional[Union[str, tuple]] = Field(None, description="GPS coordinates as 'lat,lon' (e.g., '40.7128,-74.0060'). **Avoid using unless user provides exact coordinates.** Prefer distance/heading/reference_frame for more intuitive positioning.")
    mgrs: Optional[str] = Field(None, description="MGRS coordinate for orbit center. Use ONLY when user provides MGRS coordinates.")

    # Relative positioning
    distance: Optional[Union[float, str, tuple]] = Field(None, description="Distance to orbit center from reference point with optional units (e.g., '2 miles', '1000 meters', '500 ft'). Use with heading. Can set to 0.0 to orbit AT the reference frame.")
    heading: Optional[str] = Field(None, description="Direction to orbit center: 'north', 'northeast', 'east', 'southeast', 'south', 'southwest', 'west', 'northwest'. Use with distance.")
    relative_reference_frame: Optional[str] = Field(None, description="Reference point for distance: 'origin' (takeoff), 'last_waypoint'. You MUST pick one, make an educated guess if using relative positioning. Use 'origin' when user references 'start', 'takeoff', 'here', etc. Otherwise assume last_waypoint.")

    # Orbit radius — required for fixed-wing/VTOL to fly circles
    radius: Optional[Union[float, str, tuple]] = Field(None, description=f"Radius of the circular orbit with optional units (e.g., '500 feet', '100 meters', '0.5 miles'). Default = {_agent_settings['loiter_default_radius']} {_agent_settings['loiter_radius_units']}")

    # Optional orbit altitude
    altitude: Optional[Union[float, str, tuple]] = Field(None, description=f"Altitude for the orbit pattern with optional units (e.g., '150 feet', '50 meters'). Specify only if user mentions height. Default = {_agent_settings['loiter_default_altitude']} {_agent_settings['loiter_altitude_units']}")

    # Insertion position
    seq: Optional[int] = Field(None, description="Position to insert loiter in mission (1-based index). The loiter will be inserted AT this position, shifting existing items down. Omit to add at end.")

    # Search parameters
    search_target: Optional[str] = Field(None, description="Target description for AI to search for during survey (e.g., 'vehicles', 'people', 'buildings'). Do not use if user does not specify.")
    detection_behavior: Optional[str] = Field(None, description="Detection behavior: 'tag_and_continue' (mark targets and continue mission) or 'detect_and_monitor' (abort mission and circle detected target). Use with search_target")

    @field_validator('distance', mode='before')
    @classmethod
    def parse_distance_field(cls, v):
        return validate_distance(v)

    @field_validator('radius', mode='before')
    @classmethod
    def parse_radius_field(cls, v):
        return validate_radius(v)

    @field_validator('altitude', mode='before')
    @classmethod
    def parse_altitude_field(cls, v):
        return validate_altitude(v)

    @field_validator('coordinates', mode='before')
    @classmethod
    def parse_coordinates_field(cls, v):
        return validate_coordinates(v)


def _run_loiter(tool_instance, coordinates, mgrs, distance, heading,
                relative_reference_frame, altitude, radius, seq,
                search_target, detection_behavior) -> str:
    """Shared implementation for both loiter tool variants."""
    try:
        distance_value, distance_units = unpack_measurement(distance)
        altitude_value, altitude_units = unpack_measurement(altitude)
        radius_value, radius_units = unpack_measurement(radius) if radius is not None else (None, None)
        latitude, longitude = unpack_coordinates(coordinates)

        saved_state = tool_instance._save_mission_state()

        coord_desc = tool_instance._build_coordinate_description(
            latitude, longitude, mgrs, distance_value, heading, distance_units, relative_reference_frame
        )

        actual_lat = latitude if latitude is not None else 0.0
        actual_lon = longitude if longitude is not None else 0.0
        actual_alt = altitude_value if altitude_value is not None else 0.0
        actual_radius = radius_value if radius_value is not None else 50.0

        item = tool_instance.mission_manager.add_loiter(
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

        is_valid, validation_msg = tool_instance._validate_mission_after_action()
        if not is_valid:
            tool_instance._restore_mission_state(saved_state)
            return f"Planning Error: {validation_msg}" + tool_instance._get_mission_state_summary()

        altitude_msg = f"{altitude_value} {altitude_units}" if altitude_value is not None else "not specified"
        if radius_value is not None:
            radius_msg = f"{radius_value} {radius_units}"
        else:
            radius_msg = "hover in place"

        response = f"Loiter command added to mission: {coord_desc}, Alt={altitude_msg}, Radius={radius_msg}, (Item {item.seq + 1})"

        if validation_msg:
            response += f". {validation_msg}"

        response += tool_instance._get_mission_state_summary()
        return response

    except Exception as e:
        return f"Error: {str(e)}"


class AddLoiterTool(MAVLinkToolBase):
    """Loiter tool for multirotor/ground — hover in place, no radius."""
    name: str = "add_loiter"
    description: str = (
        "Loiter/hold at a point (hover in place for multirotors). "
        "Use for 'hold', 'loiter', 'wait here', 'hover'. "
        "Specify Lat/Long OR MGRS OR distance/heading/reference. Do not mix location systems."
    )
    args_schema: type = LoiterInputNoRadius

    def __init__(self, mission_manager):
        super().__init__(mission_manager)

    def _run(self, coordinates=None, mgrs=None, distance=None, heading=None,
             relative_reference_frame=None, altitude=None, seq=None,
             search_target=None, detection_behavior=None) -> str:
        return _run_loiter(
            self, coordinates, mgrs, distance, heading,
            relative_reference_frame, altitude, None, seq,
            search_target, detection_behavior
        )


class AddLoiterWithRadiusTool(MAVLinkToolBase):
    """Loiter tool for fixed-wing/VTOL — orbits at a location with a circular radius."""
    name: str = "add_loiter"
    description: str = (
        "Loiter/orbit at a location with a circular radius (fixed-wing flies circles). "
        "Use for 'orbit', 'circle', 'loiter', or when a radius is mentioned like 'circle 2 miles north with 200m radius'. "
        "Specify Lat/Long OR MGRS OR distance/heading/reference. Do not mix location systems."
    )
    args_schema: type = LoiterInputWithRadius

    def __init__(self, mission_manager):
        super().__init__(mission_manager)

    def _run(self, coordinates=None, mgrs=None, distance=None, heading=None,
             relative_reference_frame=None, altitude=None, radius=None, seq=None,
             search_target=None, detection_behavior=None) -> str:
        return _run_loiter(
            self, coordinates, mgrs, distance, heading,
            relative_reference_frame, altitude, radius, seq,
            search_target, detection_behavior
        )
