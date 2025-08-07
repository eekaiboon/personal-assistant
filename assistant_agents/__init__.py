"""
Personal Assistant Multi-Agent System
Package for agent implementations using OpenAI Agent SDK.
"""

import json
import logging
from typing import Callable

# Import necessary utilities
logger = logging.getLogger(__name__)

# Helper function to create tool error handlers
def create_error_handler(tool_name: str) -> Callable:
    """Create an error handler function for a specific tool."""
    def error_handler(ctx, error):
        logger.error(f"Error in tool {tool_name}: {error}")
        return json.dumps({"error": f"Error in {tool_name}: {str(error)}"})
    return error_handler

# Note: log_agent_action function was moved to event_hooks.py

# Make the AssistantSession class available
from assistant_agents.memory import AssistantSession