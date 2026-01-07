"""
MAVLink Mission State Management
Handles mission creation, validation, and state tracking
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class MissionItem:
    """Represents a single mission item"""
    seq: int
    frame: int = 0
    command: int = 0
    current: int = 0
    
    # Command type for tracking what each mission item is
    command_type: Optional[str] = None

    # Raw input values
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    mgrs: Optional[str] = None
    distance: Optional[float] = None
    heading: Optional[str] = None  # Text direction like 'north', 'east', etc.
    altitude: Optional[float] = None
    radius: Optional[float] = None
    
    # Unit specifications and reference frame - store EXACTLY what model provided
    altitude_units: Optional[str] = None
    distance_units: Optional[str] = None
    radius_units: Optional[str] = None
    relative_reference_frame: Optional[str] = None
    
    # Search parameters (for waypoint, loiter, survey)
    search_target: Optional[str] = None
    detection_behavior: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            'seq': self.seq,
            'frame': self.frame,
            'command': self.command,
            'current': self.current,
            'command_type': self.command_type,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'mgrs': self.mgrs,
            'distance': self.distance,
            'heading': self.heading,
            'altitude': self.altitude,
            'radius': self.radius,
            'altitude_units': self.altitude_units,
            'distance_units': self.distance_units,
            'radius_units': self.radius_units,
            'relative_reference_frame': self.relative_reference_frame,
            'search_target': self.search_target,
            'detection_behavior': self.detection_behavior,
        }

@dataclass
class Mission:
    """Represents a complete mission"""
    items: List[MissionItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    
    def add_item(self, item: MissionItem) -> MissionItem:
        """Add mission item to end of mission"""
        item.seq = len(self.items)
        self.items.append(item)
        self.modified_at = datetime.now()
        return item
    
    def clear_items(self):
        """Remove all mission items"""
        self.items.clear()
        self.modified_at = datetime.now()
    
    def to_dict(self, convert_to_absolute: bool = False) -> Dict[str, Any]:
        """Convert to dictionary format
        
        Args:
            convert_to_absolute: If True, convert relative coordinates to absolute for display
        """
        mission_dict = {
            'items': [item.to_dict() for item in self.items],
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat()
        }
        
        # Apply coordinate conversion if requested
        if convert_to_absolute and self.items:
            from core.units import convert_mission_to_absolute_coordinates
            from config.settings import get_current_takeoff_settings
            
            try:
                takeoff_settings = get_current_takeoff_settings()
                converted_dict = convert_mission_to_absolute_coordinates(self, takeoff_settings)
                if converted_dict:
                    mission_dict = converted_dict
            except Exception as e:
                # If conversion fails, return original mission dict
                # This ensures the system is robust even if conversion has issues
                pass
        
        return mission_dict

