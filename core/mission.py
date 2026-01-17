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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MissionItem':
        """Deserialize mission item from dict (inverse of to_dict())

        Args:
            data: Dictionary containing mission item fields

        Returns:
            MissionItem instance
        """
        # Create MissionItem with only the fields present in data
        # This handles both full serialized items and partial items
        return cls(
            seq=data.get('seq', 0),
            frame=data.get('frame', 0),
            command=data.get('command', 0),
            current=data.get('current', 0),
            command_type=data.get('command_type'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            mgrs=data.get('mgrs'),
            distance=data.get('distance'),
            heading=data.get('heading'),
            altitude=data.get('altitude'),
            radius=data.get('radius'),
            altitude_units=data.get('altitude_units'),
            distance_units=data.get('distance_units'),
            radius_units=data.get('radius_units'),
            relative_reference_frame=data.get('relative_reference_frame'),
            search_target=data.get('search_target'),
            detection_behavior=data.get('detection_behavior'),
        )

@dataclass
class Mission:
    """Represents a complete mission"""
    items: List[MissionItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)

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
        # Note: convert_to_absolute parameter is kept for API compatibility
        # but conversion now happens during validation when home_position is provided

        return mission_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Mission':
        """Deserialize mission from dict (inverse of to_dict())

        Args:
            data: Dictionary containing mission fields including items array

        Returns:
            Mission instance with items deserialized
        """
        items = [MissionItem.from_dict(item_data)
                 for item_data in data.get('items', [])]

        mission = cls()
        mission.items = items
        mission.created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        mission.modified_at = datetime.fromisoformat(data.get('modified_at', datetime.now().isoformat()))

        return mission

    def to_mavlink(self) -> List[Dict[str, Any]]:
        """Convert mission to MAVLink MISSION_ITEM_INT format"""
        from core.mavlink_format import mission_to_mavlink
        return mission_to_mavlink(self)

    @classmethod
    def from_mavlink(cls, mav_items: List[Dict[str, Any]]) -> 'Mission':
        """Create mission from MAVLink MISSION_ITEM_INT format"""
        from core.mavlink_format import mission_from_mavlink
        return mission_from_mavlink(mav_items)

