"""
Event hooks and logging configuration for the Personal Assistant.
This module centralizes all logging configuration and event handling for agents.
"""

import os
import sys
import json
import logging
from typing import Any, Dict, Optional

from agents import RunHooks, Agent
from agents.lifecycle import RunContextWrapper
from agents.tool import Tool

# Simple logging configuration
def setup_logging(log_file: str = 'personal_assistant.log'):
    """Set up simple centralized logging for the entire application."""
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Remove any existing handlers to avoid duplicates
    for handler in logger.handlers:
        logger.removeHandler(handler)
        
    # Suppress all non-essential logs
    suppress_loggers = ["openai", "httpx", "httpcore", "agents"]
    for logger_name in suppress_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)
    
    # Simple console handler with clean output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    
    # File handler for complete logs
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
    logger.addHandler(file_handler)
    
    return logger

# We'll use the root logger for all logging
logger = logging.getLogger()

# Helper function for consistent agent action logging
def log_agent_action(agent_name: str, action: str, message: str = None, tool_name: str = None):
    """Log agent actions with consistent formatting and emojis.
    
    Args:
        agent_name: The name of the agent
        action: Action type (init, processing, complete, tool_start, tool_end, handoff)
        message: Optional message to include with the action
        tool_name: Optional tool name for tool-related actions
    """
    emoji = ""
    if "Activity" in agent_name:
        emoji = "🎡 [Activity Agent]"
    elif "Culinary" in agent_name:
        emoji = "🍲 [Culinary Agent]"
    elif "Foodie" in agent_name:
        emoji = "🍴 [Foodie Agent]"
    elif "Planner" in agent_name:
        emoji = "📑 [Planner Agent]"
    elif "Coordinator" in agent_name:
        emoji = "👨‍💻 [Coordinator]"
    
    # If no emoji found, use generic format
    label = emoji if emoji else f"[{agent_name}]"
    
    # Log based on action type
    if action == "init":
        logger.info(f"\n{label} Initializing with tools")
    elif action == "processing":
        if message:
            logger.info(f"\n{label} Processing request: '{message[:50]}{'...' if len(message) > 50 else ''}'")
        else:
            logger.info(f"\n{label} Processing request")
    elif action == "planning":
        logger.info(f"\n{label} Creating comprehensive plan...")
    elif action == "complete":
        logger.info(f"\n{label} Completed analysis and recommendations")
    elif action == "tool_start":
        param_str = message or ""
        if param_str:
            logger.info(f"\n[tool called: {tool_name}({param_str})]")
        else:
            logger.info(f"\n[tool called: {tool_name}]")
    elif action == "tool_end":
        if tool_name:
            agent_label = message or ""
            logger.info(f"\n{label} Completed tool: {tool_name}{agent_label}")
        else:
            logger.info(f"\n{label} Tool completed")
    elif action == "handoff":
        to_agent = message or "Unknown Agent"
        logger.info(f"\n[Handoff from {agent_name} to {to_agent}]")
    else:
        logger.info(f"\n{label} {action}")


class AgentRunHooks(RunHooks):
    """
    Custom RunHooks implementation to handle streaming events from OpenAI Agent SDK.
    This allows us to capture agent state changes, tool calls, and other events
    during the agent execution.
    """
    
    def __init__(self):
        super().__init__()
        self.current_agent = "Unknown Agent"
    
    async def on_agent_start(self, context: RunContextWrapper, agent: Agent) -> None:
        """Called when an agent starts processing."""
        agent_name = agent.name if agent else "Unknown Agent"
        self.current_agent = agent_name
        
        # Log agent transition
        logger.info(f"\n[Agent updated: {agent_name}]")
        
        # Get input text if available
        input_text = None
        try:
            if hasattr(context, 'input') and context.input:
                input_text = context.input
        except Exception:
            pass
            
        # Log agent initialization with appropriate emoji
        if input_text:
            log_agent_action(agent_name, "processing", input_text)
        else:
            log_agent_action(agent_name, "init")
    
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Called when an agent completes processing."""
        agent_name = agent.name if agent else "Unknown Agent"
        
        # Only log completion for specialized agents when they're not the final agent
        # This avoids duplicate output for the Head Coordinator Agent
        if agent_name != "Head Coordinator Agent" and any(agent_type in agent_name for agent_type in ["Activity", "Culinary", "Foodie", "Planner"]):
            log_agent_action(agent_name, "complete")
    
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        """Called when a tool is about to be executed."""
        agent_name = agent.name if agent else "Unknown Agent"
        tool_name = tool.name if hasattr(tool, 'name') else "Unknown Tool"
        
        # Get parameters if available
        tool_params = {}
        try:
            if hasattr(context, 'step_state') and hasattr(context.step_state, 'current_item'):
                current_item = context.step_state.current_item
                if hasattr(current_item, 'tool_call') and current_item.tool_call:
                    if hasattr(current_item.tool_call, 'parameters'):
                        tool_params = current_item.tool_call.parameters
        except Exception:
            pass
        
        # Log tool call using the helper function
        if tool_params:
            param_str = ", ".join([f"{k}={v}" for k, v in tool_params.items()])
            log_agent_action(agent_name, "tool_start", param_str, tool_name)
        else:
            log_agent_action(agent_name, "tool_start", None, tool_name)
    
    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str) -> None:
        """Called when a tool execution completes."""
        agent_name = agent.name if agent else "Unknown Agent"
        tool_name = tool.name if hasattr(tool, 'name') else "Unknown Tool"
        
        # Process and log the result
        if result:
            try:
                # Try to parse as JSON
                result_data = json.loads(result)
                
                if isinstance(result_data, dict):
                    # Handle dict results
                    agent_label = ""
                    if "agent" in result_data:
                        agent_label = f" from {result_data['agent']}"
                    
                    # Log completion using helper function
                    log_agent_action(agent_name, "tool_end", agent_label, tool_name)
                    
                    # Log the full tool output
                    logger.info(f"[tool output: {json.dumps(result_data, indent=2)}]")
                else:
                    # Non-dict JSON result
                    log_agent_action(agent_name, "tool_end", None, tool_name)
                    logger.info(f"[tool output: {json.dumps(result_data)}]")
            except (json.JSONDecodeError, TypeError):
                # Non-JSON result
                log_agent_action(agent_name, "tool_end", None, tool_name)
                logger.info(f"[tool output: {result[:1000]}{'...' if len(result) > 1000 else ''}]")
        else:
            # No result
            log_agent_action(agent_name, "tool_end", None, tool_name)
            logger.info(f"[tool output: No result]")


    
    async def on_handoff(self, context: RunContextWrapper, from_agent: Agent, to_agent: Agent) -> None:
        """Called when one agent hands off to another."""
        from_name = from_agent.name if from_agent else "Unknown Agent"
        to_name = to_agent.name if to_agent else "Unknown Agent"
        
        # Log handoff using helper function
        log_agent_action(from_name, "handoff", to_name)
        
        # Update current agent
        self.current_agent = to_name


# Create a singleton instance that can be imported and used across the application
agent_hooks = AgentRunHooks()