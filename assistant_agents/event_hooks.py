"""
Event hooks and logging configuration for the Personal Assistant.
This module centralizes all logging configuration and event handling for agents.
"""

import os
import sys
import logging
from typing import Any, Dict, Optional

from agents import RunHooks, Agent
from agents.lifecycle import RunContextWrapper
from agents.tool import Tool

# Core logging configuration function
def setup_logging(log_file: str = 'personal_assistant.log'):
    """Set up centralized logging for the entire application."""
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
        
    # Suppress all non-essential logs
    suppress_loggers = [
        "openai", "httpx", "httpcore", "agents", 
        "agents.agent", "assistant_agents"
    ]
    
    for logger_name in suppress_loggers:
        level = logging.CRITICAL if logger_name == "agents.agent" else logging.ERROR
        logging.getLogger(logger_name).setLevel(level)
    
    # Set up a simple console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(console_handler)
    
    # Create a separate file handler for detailed logs
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s'))
    root_logger.addHandler(file_handler)
    
    # Ensure propagation of logs from subagents
    subagent_loggers = [
        "assistant_agents", "assistant_agents.activity", 
        "assistant_agents.culinary", "assistant_agents.foodie", 
        "assistant_agents.planner"
    ]
    
    for name in subagent_loggers:
        sub_logger = logging.getLogger(name)
        sub_logger.setLevel(logging.INFO)
        # Ensure propagation is True (default) so logs go to root logger
        sub_logger.propagate = True
    
    return root_logger

# Configure this module's logger - will be set up properly when setup_logging is called
logger = logging.getLogger(__name__)

# Logging helper function moved from __init__.py
def log_agent_action(agent_name: str, action: str, message: str = None):
    """Log agent actions with consistent formatting and emojis."""
    root_logger = logging.getLogger()
    
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
    
    if not emoji:
        return
        
    if action == "init":
        root_logger.info(f"\n{emoji} Initializing with tools")
    elif action == "processing":
        if message:
            root_logger.info(f"\n{emoji} Processing request: '{message[:50]}{'...' if len(message) > 50 else ''}'")
        else:
            root_logger.info(f"\n{emoji} Processing request")
    elif action == "planning":
        root_logger.info(f"\n{emoji} Creating comprehensive plan...")
    elif action == "complete":
        root_logger.info(f"\n{emoji} Completed analysis and recommendations")

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
        
        logger.info(f"\n[Agent updated: {agent_name}]\n")
        
        # When an agent is updated, we can use this to show initialization messages
        if any(agent_type in agent_name for agent_type in ["Activity", "Culinary", "Foodie", "Planner", "Coordinator"]):
            log_agent_action(agent_name, "init")
    
    async def on_agent_end(self, context: RunContextWrapper, agent: Agent, output: Any) -> None:
        """Called when an agent completes processing."""
        agent_name = agent.name if agent else "Unknown Agent"
        
        if any(agent_type in agent_name for agent_type in ["Activity", "Culinary", "Foodie", "Planner", "Coordinator"]):
            log_agent_action(agent_name, "complete")
    
    async def on_tool_start(self, context: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        """Called when a tool is about to be executed."""
        agent_name = agent.name if agent else "Unknown Agent"
        tool_name = tool.name if hasattr(tool, 'name') else "Unknown Tool"
        logger.info(f"\n[{agent_name} called tool: {tool_name}]")
    
    async def on_tool_end(self, context: RunContextWrapper, agent: Agent, tool: Tool, result: str) -> None:
        """Called when a tool execution completes."""
        agent_name = agent.name if agent else "Unknown Agent"
        tool_name = tool.name if hasattr(tool, 'name') else "Unknown Tool"
        
        # Log the tool completion
        logger.debug(f"{agent_name} completed tool: {tool_name}")
        
        # Log completion message
        if "Activity" in agent_name:
            logger.info(f"🎡 [Activity Agent] Completed tool: {tool_name}")
        elif "Culinary" in agent_name:
            logger.info(f"🍲 [Culinary Agent] Completed tool: {tool_name}")
        elif "Foodie" in agent_name:
            logger.info(f"🍴 [Foodie Agent] Completed tool: {tool_name}")
        elif "Planner" in agent_name:
            logger.info(f"📑 [Planner Agent] Completed tool: {tool_name}")
        elif "Coordinator" in agent_name:
            logger.info(f"👨‍💻 [Coordinator] Completed tool: {tool_name}")
        else:
            logger.info(f"\n[{agent_name} completed tool: {tool_name}]")
    
    async def on_handoff(self, context: RunContextWrapper, from_agent: Agent, to_agent: Agent) -> None:
        """Called when one agent hands off to another."""
        from_name = from_agent.name if from_agent else "Unknown Agent"
        to_name = to_agent.name if to_agent else "Unknown Agent"
        
        logger.info(f"\n[Handoff from {from_name} to {to_name}]")
        self.current_agent = to_name

# Create a singleton instance that can be imported and used across the application
agent_hooks = AgentRunHooks()