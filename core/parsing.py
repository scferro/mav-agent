"""
Measurement Parsing Utilities
Handles parsing of measurements with embedded units from LLM outputs
"""

import re
from typing import Union, Tuple, Optional


# Unit normalization patterns
UNIT_PATTERNS = {
    # Distance/Radius units (most common first for efficiency)
    r'(feet|ft|foot|\')$': 'feet',
    r'(meters?|m)$': 'meters', 
    r'(miles?|mi)$': 'miles',
    r'(kilometers?|km|kms?)$': 'kilometers',
    r'(nautical_?miles?|nm|nmi)$': 'nautical_miles',
}


def parse_measurement(value: Union[str, int, float, None], default_units: str = 'meters') -> Tuple[Optional[float], Optional[str]]:
    """
    Parse measurement string into (float_value, units) tuple.
    
    Args:
        value: Input value - can be number, string with units, or None
        default_units: Units to use when none specified
        
    Returns:
        Tuple of (parsed_number, normalized_units) or (None, None) if invalid
        
    Examples:
        "150.0 feet" -> (150.0, "feet")
        "500 ft" -> (500.0, "feet") 
        "100" -> (100.0, "meters")  # using default
        100.0 -> (100.0, "meters")  # using default
        "2 miles" -> (2.0, "miles")
        None -> (None, None)
        "invalid" -> (None, None)
    """
    if value is None:
        return (None, None)
    
    # Handle numeric inputs (int/float)
    if isinstance(value, (int, float)):
        return (float(value), default_units)
    
    # Handle string inputs
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return (None, None)
        
        # Try to extract number and optional units
        # Regex matches: number (int or float) + optional whitespace + optional units
        match = re.match(r'^(\d+(?:\.\d+)?)\s*(.*)$', value)
        if not match:
            return (None, None)
        
        try:
            number = float(match.group(1))
            unit_text = match.group(2).lower().strip()
            
            # If no unit text, use default
            if not unit_text:
                return (number, default_units)
            
            # Normalize units using patterns
            for pattern, normalized_unit in UNIT_PATTERNS.items():
                if re.search(pattern, unit_text):
                    return (number, normalized_unit)
            
            # If we found unit text but no pattern matched, still return the number with default units
            # This handles cases like "150 xyz" where xyz isn't a recognized unit
            return (number, default_units)
            
        except (ValueError, AttributeError):
            return (None, None)
    
    # For any other type, return None
    return (None, None)


def parse_altitude(value: Union[str, int, float, None]) -> Tuple[Optional[float], Optional[str]]:
    """Parse altitude measurement (defaults to meters)"""
    return parse_measurement(value, default_units='meters')


def parse_distance(value: Union[str, int, float, None]) -> Tuple[Optional[float], Optional[str]]:
    """Parse distance measurement (defaults to meters)"""
    return parse_measurement(value, default_units='meters')


def parse_radius(value: Union[str, int, float, None]) -> Tuple[Optional[float], Optional[str]]:
    """Parse radius measurement (defaults to meters)"""
    return parse_measurement(value, default_units='meters')


def parse_coordinates(value: Union[str, tuple, None]) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse coordinate string into (latitude, longitude) tuple.
    
    Args:
        value: Input value - can be string with coordinates, tuple, or None
        
    Returns:
        Tuple of (latitude, longitude) or (None, None) if invalid
        
    Examples:
        "40.7128, -74.0060" -> (40.7128, -74.0060)
        "40.7128,-74.0060" -> (40.7128, -74.0060)
        "lat: 40.7128, lon: -74.0060" -> (40.7128, -74.0060)
        "40.7128" -> (40.7128, None)  # incomplete
        (40.7128, -74.0060) -> (40.7128, -74.0060)
        None -> (None, None)
        "invalid" -> (None, None)
    """
    if value is None:
        return (None, None)
    
    # Handle tuple inputs
    if isinstance(value, tuple):
        if len(value) == 2:
            try:
                lat = float(value[0]) if value[0] is not None else None
                lon = float(value[1]) if value[1] is not None else None
                return (lat, lon)
            except (ValueError, TypeError):
                return (None, None)
        return (None, None)
    
    # Handle string inputs
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return (None, None)
        
        # Remove common labels/prefixes
        value = re.sub(r'lat(itude)?:\s*', '', value, flags=re.IGNORECASE)
        value = re.sub(r'lon(gitude)?:\s*', '', value, flags=re.IGNORECASE)
        value = value.strip()
        
        # Try to extract two decimal numbers separated by comma
        # Regex matches: float, optional whitespace, comma, optional whitespace, float
        match = re.match(r'^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$', value)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                return (lat, lon)
            except ValueError:
                return (None, None)
        
        # Try single number (incomplete coordinate)
        match = re.match(r'^(-?\d+(?:\.\d+)?)$', value)
        if match:
            try:
                lat = float(match.group(1))
                return (lat, None)
            except ValueError:
                return (None, None)
    
    # For any other type, return None
    return (None, None)