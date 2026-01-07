"""
Delete Mission Item Tool - Remove specific mission item by sequence number
"""

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from .tools import MAVLinkToolBase


class DeleteMissionItemInput(BaseModel):
    """Delete/remove specific mission item by sequence number"""
    
    seq: int = Field(description="Mission item number to delete (1=first item, 2=second item, etc.). Extract from user phrases like 'remove item 3' (seq=3), 'get rid of the second loiter' (seq depends on context). Use to permantenly remove extraneous mission items.")


class DeleteMissionItemTool(MAVLinkToolBase):
    name: str = "delete_mission_item"
    description: str = "Delete specific mission item by its sequence number. Use when user wants to remove a particular item from the mission by specifying its position or when you need to correct a mistake you made. Use for commands like 'delete the second waypoint', 'remove item 1', 'get rid of that survey'. Item is permanently removed and remaining items are renumbered."
    args_schema: type = DeleteMissionItemInput
    
    def __init__(self, mission_manager):
        super().__init__(mission_manager)
    
    def _run(self, seq: int) -> str:
        # Create response
        response = ""

        # Populate response
        try:
            mission = self.mission_manager.get_mission()
            if not mission or not mission.items:
                response = "Error: No mission items to delete"
            else:
                # Save current mission state for potential rollback
                saved_state = self._save_mission_state()
                
                # Convert 1-based indexing to 0-based
                zero_based_seq = seq - 1
                if seq < 1 or zero_based_seq >= len(mission.items):
                    response = f"Error: Invalid sequence number {seq}. Mission has {len(mission.items)} items (1 to {len(mission.items)})"
                else:
                    # Get item info before deletion for confirmation message
                    item_to_delete = mission.items[zero_based_seq]
                    command_name = self._get_command_name(getattr(item_to_delete, 'command_type', 'unknown'))
                    
                    # Remove the item from the mission
                    del mission.items[zero_based_seq]
                    
                    # Resequence remaining items
                    for i, item in enumerate(mission.items):
                        item.seq = i
                    
                    # Validate mission after deletion
                    is_valid, error_msg = self._validate_mission_after_action()
                    if not is_valid:
                        # Rollback the action
                        self._restore_mission_state(saved_state)
                        return f"Planning Error: {error_msg}" + self._get_mission_state_summary()
                    else:
                        response = f"Deleted mission item {seq} ({command_name}). Mission now has {len(mission.items)} items."
                        response += self._get_mission_state_summary()
            
        except Exception as e:
            response = f"Error: {str(e)}"

        return response