"""
Activity Suggestion Agent for the Personal Assistant.
Specializes in recommending activities based on age, location, and preferences.
"""

import json
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from agents import Agent, ModelSettings, function_tool, Runner
from assistant_agents import create_error_handler
from assistant_agents.event_hooks import agent_hooks
from utils import load_prompt, DISCLAIMER, get_activities


# Define Pydantic models for the tools
class ActivitySearchParams(BaseModel):
    age_min: int = Field(0, description="Minimum age for activity")
    age_max: int = Field(99, description="Maximum age for activity")
    indoor: Optional[bool] = Field(None, description="True for indoor activities, False for outdoor")
    location: Optional[str] = Field(None, description="Location name (optional)")
    
    model_config = {"extra": "forbid"}

class ActivityDetailsParams(BaseModel):
    activity_name: str = Field(..., description="Name of the activity")
    
    model_config = {"extra": "forbid"}

class ToddlerActivityParams(BaseModel):
    indoor: Optional[bool] = Field(None, description="True for indoor activities, False for outdoor")
    
    model_config = {"extra": "forbid"}

# Tool implementation methods
async def search_activities_impl(age_min: int = 0, age_max: int = 99, 
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

async def get_activity_details_impl(activity_name: str) -> Dict:
    """Get detailed information about a specific activity."""
    activities = get_activities()
    
    for activity in activities:
        if activity["name"].lower() == activity_name.lower():
            return activity
            
    return {"error": f"Activity '{activity_name}' not found"}

async def get_toddler_activities_impl(indoor: Optional[bool] = None) -> List[Dict]:
    """Get activities suitable for toddlers."""
    filters = {"age_min": 1, "age_max": 4}
    if indoor is not None:
        filters["indoor"] = indoor
        
    activities = get_activities(**filters)
    
    # Filter for activities specifically marked as suitable for toddlers
    toddler_activities = [a for a in activities if a.get("suitable_for_toddlers", False)]
    
    return toddler_activities

def build_activity_agent(model: str = "gpt-4") -> Agent:
    """Build and return an Activity Agent using the OpenAI Agent SDK."""
    # Agent creation is logged via event hooks
    
    # Load the system prompt
    system_prompt = load_prompt("activity_base.md") + DISCLAIMER
    
    # Define tools
    @function_tool(name_override="search_activities",
                 description_override="Search for activities based on age range, location, and indoor/outdoor preference",
                 failure_error_function=create_error_handler("search_activities"))
    async def search_activities(params: ActivitySearchParams) -> str:
        """Search for activities based on criteria."""
        result = await search_activities_impl(
            age_min=params.age_min,
            age_max=params.age_max,
            indoor=params.indoor,
            location=params.location
        )
        return json.dumps(result)
    
    @function_tool(name_override="get_activity_details",
                 description_override="Get detailed information about a specific activity",
                 failure_error_function=create_error_handler("get_activity_details"))
    async def get_activity_details(params: ActivityDetailsParams) -> str:
        """Get detailed information about a specific activity."""
        result = await get_activity_details_impl(params.activity_name)
        return json.dumps(result)
    
    @function_tool(name_override="get_toddler_activities",
                 description_override="Get activities suitable for toddlers (ages 1-4)",
                 failure_error_function=create_error_handler("get_toddler_activities"))
    async def get_toddler_activities(params: ToddlerActivityParams) -> str:
        """Get activities suitable for toddlers."""
        result = await get_toddler_activities_impl(params.indoor)
        return json.dumps(result)
    
    # Create and return the agent
    return Agent(
        name="Activity Suggestion Agent",
        instructions=system_prompt,
        tools=[search_activities, get_activity_details, get_toddler_activities],
        model=model,
        model_settings=ModelSettings(
            parallel_tool_calls=True,
            tool_choice="auto",
            temperature=0
        )
    )

async def run_activity_agent(query: str, agent: Agent = None, event_handler: Any = None) -> Dict[str, Any]:
    """Run the Activity Agent with a specific query."""
    # Build the agent if not provided
    if agent is None:
        agent = build_activity_agent()
    
    # Processing is logged via event hooks
    
    # Set up hooks if an event_handler was provided
    hooks = None
    if event_handler is not None:
        hooks = agent_hooks
    
    # Get max_turns from environment
    max_turns = int(os.environ.get("MAX_TURNS", 5))
    
    # Run the agent
    result = await Runner.run(
        starting_agent=agent,
        input=query,
        max_turns=max_turns,
        hooks=hooks
    )
    
    # Completion is logged via event hooks
    
    # Return the result
    return {
        "content": result.final_output,
        "agent": "Activity Suggestion Agent"
    }