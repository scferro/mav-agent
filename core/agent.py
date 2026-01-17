"""
MAVLink Agent Main Class
Handles different modes: command, mission_new, mission_update
"""

from typing import Dict, Any, Optional, List
import json
from datetime import datetime

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from tools import get_tools_for_mode
from llm_backends import OllamaInterface, TensorRTInterface
from prompts import get_system_prompt
from config import get_settings, get_model_settings
from core import MissionManager

def create_model_interface():
    """Factory function to create the appropriate model interface based on configuration"""
    model_settings = get_model_settings()
    model_type = model_settings.get('type', 'ollama').lower()

    if model_type == 'tensorrt':
        return TensorRTInterface()
    elif model_type == 'ollama':
        return OllamaInterface()
    else:
        raise ValueError(f"Unsupported model type: {model_type}. Supported types: ollama, tensorrt")

class MAVLinkAgent:
    """Main MAVLink mission planning agent"""
    
    def __init__(self, verbose: bool = False):
        self.settings = get_settings()
        self.verbose = verbose or self.settings.agent.verbose_default

        # Initialize single model interface once
        self.model_interface = create_model_interface()

        # Initialize components
        self.tools = []  # Will be set when mode is selected
        self.mission_manager = None  # Will be set when mode is selected

        # Agent state
        self.current_mode = None
        self.agent_graph = None
        self.chat_history = []
    
    def _setup_tools_for_mode(self, mode: str):
        """Setup tools and mission manager for specific mode"""
        # Create mission manager first
        self.mission_manager = MissionManager(mode=mode)

        # Model interface already initialized - reuse it
        # Only recreate tools (lightweight)
        self.tools = get_tools_for_mode(self.mission_manager, mode)

        # Debug: print tool info
        if self.verbose:
            print(f"🔧 Loaded {len(self.tools)} tools for {mode} mode")

        # Initialize agent with new tools
        self._initialize_agent()
    
    
    def _initialize_agent(self):
        """Initialize the LangGraph agent"""
        try:
            # Get LLM
            if hasattr(self.model_interface, 'get_llm'):
                # Ollama interface pattern
                llm = self.model_interface.get_llm()
            else:
                # Direct LangChain BaseChatModel (TensorRT)
                llm = self.model_interface
            
            # Create the LangGraph ReAct agent with a checkpointer for state management
            checkpointer = InMemorySaver()
            
            
            # Create the agent graph - this will continue until no more tool calls
            self.agent_graph = create_react_agent(
                model=llm,
                tools=self.tools,
                checkpointer=checkpointer
            )
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize agent: {str(e)}")
    
    
    def mission_mode(self, user_input: str) -> Dict[str, Any]:
        """Execute mission mode - interactive mission building"""
        
        # Setup tools for mission mode only if not already in mission mode
        if self.current_mode != "mission":
            self.current_mode = "mission"
            self._setup_tools_for_mode("mission")
        
        # Set mission manager to mission mode for strict validation
        self.mission_manager.set_mode("mission")
        
        # Only clear chat history and create new mission if no mission exists
        if not self.mission_manager.has_mission():
            self.chat_history = []
            self.mission_manager.create_mission()
            
            # Inject system prompt only once when mission is first created
            base_system_prompt = get_system_prompt("mission")
            self.chat_history.append(SystemMessage(content=base_system_prompt))
        
        try:
            # Append current mission state to user message for context
            mission_state_summary = self.mission_manager.get_mission_state_summary()
            enhanced_user_input = f"{user_input}{mission_state_summary}"
            
            # Build messages with enhanced user input
            messages = [HumanMessage(content=enhanced_user_input)]
            
            # Add all chat history (including system message from first creation)
            all_messages = self.chat_history + messages
            
            # Let LangGraph handle the conversation flow - it will continue until no more tool calls
            config = {"configurable": {"thread_id": "mission_thread"}}
            
            result = self.agent_graph.invoke({
                "messages": all_messages
            }, config=config)
            
            # In verbose mode, print the full conversation chain
            if self.verbose:
                print("\n🔍 VERBOSE: Agent Conversation Chain")
                print("=" * 50)
                for i, msg in enumerate(result["messages"]):
                    msg_type = type(msg).__name__
                    print(f"{i}. {msg_type}:")
                    if hasattr(msg, 'content') and msg.content:
                        print(f"   Content: {msg.content}")
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        print(f"   Tool calls: {msg.tool_calls}")
                    if hasattr(msg, 'name') and msg.name:
                        print(f"   Tool name: {msg.name}")
                    print()

            # Find the last AI message (not ToolMessage)
            final_ai_message = None
            for msg in reversed(result["messages"]):
                if msg.__class__.__name__ == 'AIMessage':
                    final_ai_message = msg
                    break
            
            if final_ai_message:
                output = final_ai_message.content if hasattr(final_ai_message, 'content') else str(final_ai_message)
            else:
                output = "No AI response found"

            # Save new messages to chat history 
            new_messages = result.get("messages", [])[len(self.chat_history):]
            self.chat_history.extend(new_messages)

            # Get final mission state with automatic coordinate conversion for display
            mission = self.mission_manager.get_mission()
            
            mission_state = mission.to_dict(convert_to_absolute=True) if mission else None
            
            return {
                "success": True,
                "mode": "mission", 
                "input": user_input,
                "output": output,
                "mission_state": mission_state,
                "intermediate_steps": result.get("messages", []) if self.verbose else []
            }
            
        except Exception as e:
            # In verbose mode or on error, try to print message chain if available
            try:
                if 'result' in locals() and result.get("messages"):
                    print("\n🔍 ERROR: Agent Conversation Chain (up to failure point)")
                    print("=" * 60)
                    for i, msg in enumerate(result["messages"]):
                        msg_type = type(msg).__name__
                        print(f"{i}. {msg_type}:")
                        if hasattr(msg, 'content') and msg.content:
                            print(f"   Content: {msg.content}")
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            print(f"   Tool calls: {msg.tool_calls}")
                        if hasattr(msg, 'name') and msg.name:
                            print(f"   Tool name: {msg.name}")
                        print()
                else:
                    print("\n🔍 ERROR: No message chain available (error occurred before agent execution)")
            except:
                print("\n🔍 ERROR: Could not display message chain")
            
            return {
                "success": False,
                "mode": "mission",
                "input": user_input,
                "error": str(e),
                "output": f"Mission creation failed: {str(e)}"
            }
    
    def command_mode(self, user_input: str) -> Dict[str, Any]:
        """Execute command mode - single commands with reset"""
        self.current_mode = "command"
        
        # Setup tools for command mode (always reset for command mode)  
        self._setup_tools_for_mode("command")
        
        # Set mission manager to command mode for relaxed validation
        self.mission_manager.set_mode("command")
        
        # Always clear chat history and create fresh mission for command mode
        self.chat_history = []
        self.mission_manager.create_mission()

        system_prompt = get_system_prompt("command")
        
        try:
            # Append current action state to user message for context in command mode
            current_action_summary = self.mission_manager.get_current_action_summary()
            enhanced_user_input = f"{user_input}{current_action_summary}"
            
            # LangGraph uses messages instead of system_prompt/input format
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=enhanced_user_input)
            ]
            
            # Let LangGraph handle the conversation flow - use unique thread ID to prevent state carryover
            import time
            config = {"configurable": {"thread_id": f"command_thread_{int(time.time() * 1000)}"}}
            
            result = self.agent_graph.invoke({
                "messages": messages
            }, config=config)
            
            # In verbose mode, print the full conversation chain
            if self.verbose:
                print("\n🔍 VERBOSE: Command Conversation Chain")
                print("=" * 50)
                for i, msg in enumerate(result["messages"]):
                    msg_type = type(msg).__name__
                    print(f"{i}. {msg_type}:")
                    if hasattr(msg, 'content') and msg.content:
                        content_preview = msg.content
                        print(f"   Content: {content_preview}")
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        print(f"   Tool calls: {msg.tool_calls}")
                    if hasattr(msg, 'name') and msg.name:
                        print(f"   Tool name: {msg.name}")
                    print()

            # Find the last AI message (not ToolMessage)
            final_ai_message = None
            for msg in reversed(result["messages"]):
                if msg.__class__.__name__ == 'AIMessage':
                    final_ai_message = msg
                    break
            
            if final_ai_message:
                output = final_ai_message.content if hasattr(final_ai_message, 'content') else str(final_ai_message)
            else:
                output = "No AI response found"

            # Get final mission state with automatic coordinate conversion for display
            mission = self.mission_manager.get_mission()
            mission_state = mission.to_dict(convert_to_absolute=True) if mission else None
            
            # Reset for next command (clear mission and chat history)
            self.chat_history = []
            self.mission_manager.clear_mission()
            
            return {
                "success": True,
                "mode": "command", 
                "input": user_input,
                "output": output,
                "mission_state": mission_state,
                "intermediate_steps": result.get("messages", []) if self.verbose else []
            }
            
        except Exception as e:
            # Reset even on error
            self.chat_history = []
            self.mission_manager.clear_mission()

            # In verbose mode or on error, try to print message chain if available
            try:
                if 'result' in locals() and result.get("messages"):
                    print("\n🔍 ERROR: Agent Conversation Chain (up to failure point)")
                    print("=" * 60)
                    for i, msg in enumerate(result["messages"]):
                        msg_type = type(msg).__name__
                        print(f"{i}. {msg_type}:")
                        if hasattr(msg, 'content') and msg.content:
                            print(f"   Content: {msg.content}")
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            print(f"   Tool calls: {msg.tool_calls}")
                        if hasattr(msg, 'name') and msg.name:
                            print(f"   Tool name: {msg.name}")
                        print()
                else:
                    print("\n🔍 ERROR: No message chain available (error occurred before agent execution)")
            except:
                print("\n🔍 ERROR: Could not display message chain")
            
            return {
                "success": False,
                "mode": "command",
                "input": user_input,
                "error": str(e),
                "output": f"Command execution failed: {str(e)}"
            }
    
    def get_mission_summary(self) -> Optional[Dict[str, Any]]:
        """Get summary of current mission"""
        mission = self.mission_manager.get_mission()
        if not mission:
            return None
        
        # Validate mission
        valid, errors = self.mission_manager.validate_mission()
        
        # Count different command types
        command_counts = {}
        for item in mission.items:
            cmd_name = getattr(item, 'command_type', 'unknown').title()
            command_counts[cmd_name] = command_counts.get(cmd_name, 0) + 1
        
        return {
            "total_items": len(mission.items),
            "valid": valid,
            "errors": errors,
            "command_counts": command_counts,
            "created_at": mission.created_at.isoformat(),
            "modified_at": mission.modified_at.isoformat()
        }

    def plan(self,
             user_input: str,
             mode: str = "mission",
             mission_state: Optional[Dict] = None,
             home_position: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Unified stateless planning endpoint.

        Args:
            user_input: Natural language command
            mode: 'mission' or 'command'
            mission_state: Current mission or action state (optional)
            home_position: Dict with 'latitude', 'longitude' from GCS (optional but recommended)

        Returns:
            {
                "success": bool,
                "mode": str,
                "output": str,
                "mission_items": List[Dict],      # Full mission
                "added_items": List[Dict],         # What was new
                "modified_items": List[Dict],      # What changed
                "deleted_items": List[Dict],       # What was removed
                "validation": {
                    "valid": bool,
                    "errors": List[str],
                    "warnings": List[str]
                }
            }
        """
        from core.mission import Mission

        # Save current state
        original_mission = self.mission_manager.get_mission() if self.mission_manager else None
        original_history = self.chat_history.copy()
        original_mode = self.current_mode

        try:
            # Load request context
            if mission_state:
                loaded_mission = Mission.from_dict(mission_state)
                self.mission_manager.current_mission = loaded_mission

            # Route to appropriate mode handler
            if mode == "mission":
                result = self.mission_mode(user_input)
            elif mode == "command":
                result = self.command_mode(user_input)
            else:
                raise ValueError(f"Invalid mode: {mode}")

            # Enhance response with delta information (pass home_position for validation)
            enhanced_result = self._enhance_with_deltas(
                result,
                original_mission,
                self.mission_manager.get_mission(),
                home_position
            )

            return enhanced_result

        finally:
            # Always restore original state
            self.mission_manager.current_mission = original_mission
            self.chat_history = original_history
            self.current_mode = original_mode

    def _enhance_with_deltas(self, result: Dict,
                            old_mission,
                            new_mission,
                            home_position: Optional[Dict] = None) -> Dict:
        """Calculate what changed in the mission

        Args:
            result: Original result from mission_mode or command_mode
            old_mission: Mission state before operation
            new_mission: Mission state after operation
            home_position: Dict with 'latitude', 'longitude' from GCS (optional)

        Returns:
            Enhanced result with delta information
        """
        old_items = old_mission.items if old_mission else []
        new_items = new_mission.items if new_mission else []

        # Simple seq-based diff
        old_seqs = {item.seq: item for item in old_items}
        new_seqs = {item.seq: item for item in new_items}

        added = [item.to_dict() for seq, item in new_seqs.items()
                 if seq not in old_seqs]
        deleted = [item.to_dict() for seq, item in old_seqs.items()
                   if seq not in new_seqs]
        modified = [item.to_dict() for seq, item in new_seqs.items()
                    if seq in old_seqs and item.to_dict() != old_seqs[seq].to_dict()]

        # Add mission_items array to result
        result['mission_items'] = [item.to_dict() for item in new_items]
        result['added_items'] = added
        result['modified_items'] = modified
        result['deleted_items'] = deleted

        # Add validation information (pass home_position for coordinate conversion)
        if new_mission:
            valid, errors = self.mission_manager.validate_mission(home_position=home_position)
            result['validation'] = {
                'valid': valid,
                'errors': errors if errors else [],
                'warnings': []  # Can be populated with non-critical issues
            }
        else:
            result['validation'] = {
                'valid': True,
                'errors': [],
                'warnings': []
            }

        return result


