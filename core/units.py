"""
Universal Unit Conversion System for MAVLink Agent
Supports conversion between meters, feet, kilometers, miles with easy extensibility

Main function: convert_units(value, from_unit, to_unit)
  - Universal converter: supports any unit to any unit
  - Examples: convert_units(100, 'ft', 'm'), convert_units(1, 'km', 'miles')
"""

from typing import Optional, Dict
import math


# Conversion factors to meters (base unit)
UNIT_CONVERSIONS: Dict[str, float] = {
    'meters': 1.0,              # Base unit
    'feet': 0.3048,             # 1 foot = 0.3048 meters
    'kilometers': 1000.0,       # 1 kilometer = 1000 meters
    'miles': 1609.344           # 1 mile = 1609.344 meters
}

# Unit aliases for normalization
UNIT_ALIASES: Dict[str, str] = {
    # Meters
    'meter': 'meters',
    'm': 'meters',
    
    # Feet  
    'foot': 'feet',
    'ft': 'feet',
    "'": 'feet',
    
    # Kilometers
    'kilometer': 'kilometers', 
    'km': 'kilometers',
    'kms': 'kilometers',
    
    # Miles
    'mile': 'miles',
    'mi': 'miles',
    'mil': 'miles'
}


def normalize_unit(unit: Optional[str]) -> str:
    """
    Normalize unit string to standard format
    
    Args:
        unit: Unit string to normalize (e.g., 'ft', 'feet', 'm', 'meters')
        
    Returns:
        Normalized unit string (e.g., 'feet', 'meters')
        Defaults to 'meters' for None or unknown units
    """
    if not unit:
        return 'meters'
    
    unit_lower = unit.lower().strip()
    
    # Check if it's already a standard unit
    if unit_lower in UNIT_CONVERSIONS:
        return unit_lower
    
    # Check aliases
    if unit_lower in UNIT_ALIASES:
        return UNIT_ALIASES[unit_lower]
    
    # Default to meters for unknown units
    return 'meters'


def get_conversion_factor(from_unit: Optional[str], to_unit: Optional[str]) -> float:
    """
    Get conversion factor from one unit to another
    
    Args:
        from_unit: Source unit
        to_unit: Target unit
        
    Returns:
        Conversion factor to multiply source value by
    """
    from_normalized = normalize_unit(from_unit)
    to_normalized = normalize_unit(to_unit)
    
    if from_normalized == to_normalized:
        return 1.0
    
    # Convert from source unit to meters, then to target unit
    from_to_meters = UNIT_CONVERSIONS[from_normalized]
    to_from_meters = UNIT_CONVERSIONS[to_normalized]
    
    return from_to_meters / to_from_meters


def convert_units(value: float, from_unit: Optional[str], to_unit: Optional[str]) -> float:
    """
    Convert a value from one unit to another
    
    Args:
        value: Numeric value to convert
        from_unit: Source unit (e.g., 'feet', 'ft', 'm')
        to_unit: Target unit (e.g., 'meters', 'km', 'miles')
        
    Returns:
        Converted value in target units
        Returns original value if conversion fails
        
    Examples:
        convert_units(100, 'feet', 'meters') -> 30.48
        convert_units(1, 'km', 'miles') -> 0.621371
        convert_units(5280, 'ft', 'miles') -> 1.0
    """
    if value is None:
        return None
    
    try:
        conversion_factor = get_conversion_factor(from_unit, to_unit)
        result = value * conversion_factor
        # Round to avoid floating point precision errors
        return round(result, 6)  # 6 decimal places should be sufficient
    except (KeyError, ValueError):
        # Return original value if conversion fails
        return value


# Convenience wrapper functions for common conversions
# These use the universal convert_units() method internally

def convert_to_meters(value: float, from_unit: Optional[str]) -> float:
    """
    Convenience wrapper: Convert any unit to meters
    Uses the universal convert_units() method internally
    """
    return convert_units(value, from_unit, 'meters')


# Heading / compass direction utilities

HEADING_MAP: Dict[str, float] = {
    'north': 0.0, 'n': 0.0,
    'northeast': 45.0, 'ne': 45.0,
    'east': 90.0, 'e': 90.0,
    'southeast': 135.0, 'se': 135.0,
    'south': 180.0, 's': 180.0,
    'southwest': 225.0, 'sw': 225.0,
    'west': 270.0, 'w': 270.0,
    'northwest': 315.0, 'nw': 315.0,
}


def heading_to_degrees(heading) -> float:
    """Convert a heading value to degrees.

    Accepts:
      - numeric (int/float): returned as-is
      - string compass direction: 'north', 'ne', 'southwest', etc.
      - numeric string: '180', '45.5', etc.

    Returns:
        Heading in degrees (0-360). Defaults to 0.0 for unrecognised values.
    """
    if isinstance(heading, (int, float)):
        return float(heading)
    if isinstance(heading, str):
        lookup = heading.lower().strip()
        if lookup in HEADING_MAP:
            return HEADING_MAP[lookup]
        try:
            return float(lookup)
        except ValueError:
            return 0.0
    return 0.0


# Coordinate conversion utilities
def calculate_absolute_coordinates(ref_lat: float, ref_lon: float, distance: float, heading: str, distance_units: str = 'meters') -> tuple[float, float]:
    """
    Calculate absolute lat/long coordinates from a reference point using distance and compass heading
    
    Args:
        ref_lat: Reference latitude in decimal degrees
        ref_lon: Reference longitude in decimal degrees
        distance: Distance from reference point
        heading: Compass direction ('north', 'northeast', 'east', etc.)
        distance_units: Units of distance (converted to meters internally)
        
    Returns:
        Tuple of (calculated_lat, calculated_lon) in decimal degrees
    """
    if distance is None or heading is None:
        return ref_lat, ref_lon
    
    # Convert distance to meters
    distance_meters = convert_to_meters(distance, distance_units)
    
    # Convert heading to bearing in degrees
    bearing_degrees = heading_to_degrees(heading)
    bearing_radians = math.radians(bearing_degrees)
    
    # Earth radius in meters
    earth_radius = 6378137.0
    
    # Convert reference coordinates to radians
    ref_lat_rad = math.radians(ref_lat)
    ref_lon_rad = math.radians(ref_lon)
    
    # Calculate new latitude
    new_lat_rad = math.asin(
        math.sin(ref_lat_rad) * math.cos(distance_meters / earth_radius) +
        math.cos(ref_lat_rad) * math.sin(distance_meters / earth_radius) * math.cos(bearing_radians)
    )
    
    # Calculate new longitude
    new_lon_rad = ref_lon_rad + math.atan2(
        math.sin(bearing_radians) * math.sin(distance_meters / earth_radius) * math.cos(ref_lat_rad),
        math.cos(distance_meters / earth_radius) - math.sin(ref_lat_rad) * math.sin(new_lat_rad)
    )
    
    # Convert back to degrees
    new_lat = math.degrees(new_lat_rad)
    new_lon = math.degrees(new_lon_rad)
    
    return new_lat, new_lon