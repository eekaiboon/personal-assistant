"""
Personal Assistant Multi-Agent System
Base classes and shared functionality for the agent system using OpenAI Agents SDK.
"""

import json
import asyncio
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable

import openai
from pydantic import BaseModel

# Import OpenAI Agent SDK components
from agents import Agent, ModelSettings, function_tool, Runner

logger = logging.getLogger(__name__)


class ToolResult(BaseModel):
    """Result from a tool call."""
    name: str
    result: Any

# We'll use the function_tool decorator from the Agent SDK instead of our custom Tool classes

# Helper function to create tool error handlers
def create_error_handler(tool_name: str) -> Callable:
    """Create an error handler function for a specific tool."""
    def error_handler(ctx, error):
        logger.error(f"Error in tool {tool_name}: {error}")
        return json.dumps({"error": f"Error in {tool_name}: {str(error)}"})
    return error_handler


# Create wrapper for Agent SDK

class AgentWrapper:
    """Wrapper around the Agent SDK for our assistant system."""
    
    def __init__(self, name: str, system_prompt: str, model: str = "gpt-4"):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.tools = []
        self.agent = None
        
        # The OpenAI Agent SDK will use environment variables directly
        
    def build_agent(self):
        """Build the actual Agent SDK agent with configured tools."""
        # Log agent creation
        tool_names = [t.__name__ if hasattr(t, "__name__") else t.__class__.__name__ for t in self.tools]
        logger.info(f"🔧 Building {self.name} with {len(self.tools)} tools: {', '.join(tool_names) if tool_names else 'none'}")
        
        # Also log to root logger for visibility in main.py
        root_logger = logging.getLogger()
        agent_emoji = ""
        if "Activity" in self.name:
            agent_emoji = "🎡 [Activity Agent]"
        elif "Culinary" in self.name:
            agent_emoji = "🍲 [Culinary Agent]"
        elif "Foodie" in self.name:
            agent_emoji = "🍴 [Foodie Agent]"
        elif "Planner" in self.name:
            agent_emoji = "📑 [Planner Agent]"
        elif "Head Coordinator" in self.name:
            agent_emoji = "👨‍💻 [Coordinator]"
            
        if agent_emoji:
            root_logger.info(f"\n{agent_emoji} Initializing with {len(self.tools)} tools")
        
        # Set model settings for parallel tool execution
        model_settings = ModelSettings(
            parallel_tool_calls=True,
            tool_choice="auto",
            temperature=0
        )
        
        # Create Agent SDK agent
        self.agent = Agent(
            name=self.name,
            instructions=self.system_prompt,
            tools=self.tools,
            model=self.model,
            model_settings=model_settings
        )
        
        return self.agent
        
    async def process(self, user_input: str, hooks=None) -> Dict[str, Any]:
        """Process a user input using the Agent SDK."""
        # Build the agent if not already built
        if self.agent is None:
            self.build_agent()
            
        logger.info(f"🧠 {self.name} is processing: '{user_input[:50]}{'...' if len(user_input) > 50 else ''}'")
        
        # Also log to root logger for visibility in main.py
        root_logger = logging.getLogger()
        agent_emoji = ""
        if "Activity" in self.name:
            agent_emoji = "🎡 [Activity Agent]"
            root_logger.info(f"\n{agent_emoji} Processing request: '{user_input[:50]}{'...' if len(user_input) > 50 else ''}'")
        elif "Culinary" in self.name:
            agent_emoji = "🍲 [Culinary Agent]"
            root_logger.info(f"\n{agent_emoji} Processing request: '{user_input[:50]}{'...' if len(user_input) > 50 else ''}'")
        elif "Foodie" in self.name:
            agent_emoji = "🍴 [Foodie Agent]"
            root_logger.info(f"\n{agent_emoji} Processing request: '{user_input[:50]}{'...' if len(user_input) > 50 else ''}'")
        elif "Planner" in self.name:
            agent_emoji = "📑 [Planner Agent]"
            root_logger.info(f"\n{agent_emoji} Creating comprehensive plan...")
        
        # Run the agent
        run_kwargs = {"starting_agent": self.agent, "input": user_input, "max_turns": 15}
        if hooks:
            run_kwargs["hooks"] = hooks
            
        # Run the agent with or without hooks
        run_coroutine = Runner.run(**run_kwargs)
        result = await run_coroutine
        
        # Log completion
        logger.info(f"✅ {self.name} completed processing")
        if agent_emoji:
            root_logger.info(f"\n{agent_emoji} Completed analysis and recommendations")
        
        # Return the final result
        return {
            "content": result.final_output,
            "agent": self.name
        }
        
# Legacy implementation for backward compatibility
class BaseAgent:
    """Legacy BaseAgent for backward compatibility."""
    
    def __init__(self, name, system_prompt, model="gpt-4"):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.tools = []
        self.client = openai.OpenAI()
        
    def add_tool(self, tool):
        """Add a tool to the agent."""
        self.tools.append(tool)
        
    async def call_openai_api(self, messages):
        """Call OpenAI API with messages."""
        return await asyncio.to_thread(
            self.client.chat.completions.create,
            model=self.model,
            messages=messages,
            tools=[t.to_dict() for t in self.tools] if self.tools else None
        )
        
    async def execute_tool_calls(self, tool_calls):
        """Execute tool calls."""
        results = []
        for tc in tool_calls:
            tool = next((t for t in self.tools if t.name == tc.function.name), None)
            if tool:
                args = json.loads(tc.function.arguments)
                result = await tool.execute(**args)
                results.append(ToolResult(name=tc.function.name, result=result))
        return results

class FunctionTool:
    """Legacy FunctionTool for backward compatibility."""
    
    def __init__(self, func, name, description):
        self.func = func
        self.name = name
        self.description = description
        self.parameters = {}
        
    async def execute(self, **kwargs):
        """Execute the function with kwargs."""
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        return await asyncio.to_thread(self.func, **kwargs)
        
    def to_dict(self):
        """Convert to OpenAI API tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.parameters.keys())
                }
            }
        }