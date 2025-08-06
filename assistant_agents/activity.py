"""
Activity Suggestion Agent for the Personal Assistant.
Specializes in recommending activities based on age, location, and preferences.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from agents import Agent, ModelSettings, function_tool, Runner
from assistant_agents import AgentWrapper, BaseAgent, create_error_handler
from utils import load_prompt, DISCLAIMER, get_activities


# Define Pydantic models for the tools
class ActivitySearchParams(BaseModel):
    age_min: int = Field(0, description="Minimum age for activity")
    age_max: int = Field(99, description="Maximum age for activity")
    indoor: Optional[bool] = Field(None, description="True for indoor activities, False for outdoor")
    location: Optional[str] = Field(None, description="Location name (optional)")

class ActivityDetailsParams(BaseModel):
    activity_name: str = Field(..., description="Name of the activity")

class ToddlerActivityParams(BaseModel):
    indoor: Optional[bool] = Field(None, description="True for indoor activities, False for outdoor")

class ActivityAgent(AgentWrapper, BaseAgent):
    """
    Agent specialized in suggesting activities based on user preferences,
    age groups, and other constraints using the OpenAI Agent SDK.
    """
    
    def __init__(self, system_prompt: str = None, model: str = "gpt-4"):
        # Load default prompt if none provided
        if system_prompt is None:
            system_prompt = load_prompt("activity_base.md") + DISCLAIMER
        
        super().__init__("Activity Suggestion Agent", system_prompt, model)
        
        # Set up tools for the agent
        self._setup_tools()
        
    def _setup_tools(self):
        """Set up the tools for this agent using the Agent SDK."""
        
        # Tool to search for activities based on criteria
        @function_tool(name_override="search_activities",
                     description_override="Search for activities based on age range, location, and indoor/outdoor preference",
                     failure_error_function=create_error_handler("search_activities"))
        async def search_activities(params: ActivitySearchParams) -> str:
            """Search for activities based on criteria."""
            result = await self._search_activities(
                age_min=params.age_min,
                age_max=params.age_max,
                indoor=params.indoor,
                location=params.location
            )
            return json.dumps(result)
        
        # Tool to get activity details
        @function_tool(name_override="get_activity_details",
                     description_override="Get detailed information about a specific activity",
                     failure_error_function=create_error_handler("get_activity_details"))
        async def get_activity_details(params: ActivityDetailsParams) -> str:
            """Get detailed information about a specific activity."""
            result = await self._get_activity_details(params.activity_name)
            return json.dumps(result)
        
        # Tool to get activities for toddlers
        @function_tool(name_override="get_toddler_activities",
                     description_override="Get activities suitable for toddlers (ages 1-4)",
                     failure_error_function=create_error_handler("get_toddler_activities"))
        async def get_toddler_activities(params: ToddlerActivityParams) -> str:
            """Get activities suitable for toddlers."""
            result = await self._get_toddler_activities(params.indoor)
            return json.dumps(result)
        
        # Store the tools for agent creation
        self.tools = [search_activities, get_activity_details, get_toddler_activities]
    
    async def process(self, user_input: str) -> Dict[str, Any]:
        """
        Process a user input related to activity suggestions.
        
        Args:
            user_input: The user's query about activities
            
        Returns:
            Dict containing the agent's response
        """
        # Enhanced visibility for activity agent logs
        root_logger = logging.getLogger()
        root_logger.info(f"\n🎡 [Activity Agent] Starting to process request: '{user_input[:50]}{'...' if len(user_input) > 50 else ''}'")
        logger.info(f"🎡 Activity Agent is processing: '{user_input[:50]}{'...' if len(user_input) > 50 else ''}'")
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        # Initial call to get response or tool calls
        response = await self.call_openai_api(messages)
        message = response.choices[0].message
        
        # Log initial thinking
        if message.content:
            logger.info(f"🎡 Activity Agent initial analysis: {message.content[:80]}...")
        
        # Handle any tool calls
        tool_call_count = 0
        while message.tool_calls:
            tool_call_count += 1
            logger.info(f"🎡 Activity Agent tool calls round {tool_call_count}: {len(message.tool_calls)} calls")
            
            # Execute tool calls
            tool_results = await self.execute_tool_calls(message.tool_calls)
            
            # Add tool calls and results to messages
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })
            
            for result in tool_results:
                # Summarize results in the log
                if isinstance(result.result, list):
                    logger.info(f"🎡 Activity Agent found {len(result.result)} matching activities")
                elif isinstance(result.result, dict) and 'name' in result.result:
                    logger.info(f"🎡 Activity Agent found details for: {result.result['name']}")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": message.tool_calls[tool_results.index(result)].id,
                    "content": json.dumps(result.result)
                })
            
            # Get next response
            logger.info(f"🎡 Activity Agent is analyzing data and preparing recommendations...")
            response = await self.call_openai_api(messages)
            message = response.choices[0].message
        
        # Enhanced visibility for completion logs
        root_logger = logging.getLogger()
        root_logger.info(f"\n🎡 [Activity Agent] Completed analysis and prepared recommendations")
        logger.info(f"🎡 Activity Agent has completed its analysis and prepared recommendations")
        
        # Return the final message content
        return {
            "content": message.content,
            "agent": self.name
        }
    
    # Tool implementation methods
    
    async def _search_activities(self, age_min: int = 0, age_max: int = 99, 
                               indoor: Optional[bool] = None, location: Optional[str] = None) -> List[Dict]:
        """Search for activities based on criteria."""
        filters = {}
        if age_min > 0:
            filters["age_min"] = age_min
        if age_max < 99:
            filters["age_max"] = age_max
        if indoor is not None:
            filters["indoor"] = indoor
        if location:
            filters["location"] = location
            
        activities = get_activities(**filters)
        
        # Simplify the output for the agent
        simplified = []
        for activity in activities:
            simplified.append({
                "name": activity["name"],
                "description": activity["description"],
                "location": activity.get("location", ""),
                "indoor": activity.get("indoor", False),
                "duration_minutes": activity.get("duration_minutes", 60),
                "suitable_for_toddlers": activity.get("suitable_for_toddlers", False),
                "cost": activity.get("cost", "$")
            })
            
        return simplified
    
    async def _get_activity_details(self, activity_name: str) -> Dict:
        """Get detailed information about a specific activity."""
        activities = get_activities()
        
        for activity in activities:
            if activity["name"].lower() == activity_name.lower():
                return activity
                
        return {"error": f"Activity '{activity_name}' not found"}
    
    async def _get_toddler_activities(self, indoor: Optional[bool] = None) -> List[Dict]:
        """Get activities suitable for toddlers."""
        filters = {"age_min": 1, "age_max": 4}
        if indoor is not None:
            filters["indoor"] = indoor
            
        activities = get_activities(**filters)
        
        # Filter for activities specifically marked as suitable for toddlers
        toddler_activities = [a for a in activities if a.get("suitable_for_toddlers", False)]
        
        return toddler_activities


def build_activity_agent(system_prompt: str = None, model: str = "gpt-4") -> ActivityAgent:
    """Build and return an ActivityAgent with OpenAI Agent SDK integration."""
    agent = ActivityAgent(system_prompt, model)
    # Build and return the agent with SDK
    agent.build_agent()
    return agent