"""
Planner Agent for the Personal Assistant.
Specializes in creating comprehensive plans by synthesizing information from other agents.
"""

import json
import os
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from agents import Agent, ModelSettings, function_tool, Runner
from assistant_agents import create_error_handler
from assistant_agents.event_hooks import agent_hooks
from utils import load_prompt, DISCLAIMER, get_travel_time


# Define Pydantic models for the tools
class TravelTimeParams(BaseModel):
    origin: str = Field(..., description="Starting location name")
    destination: str = Field(..., description="Destination location name")
    
    model_config = {"extra": "forbid"}

# Define a structured activity model
class ActivityItem(BaseModel):
    name: str = Field(..., description="Name of the activity")
    location: str = Field("", description="Location of the activity")
    duration_minutes: int = Field(60, description="Duration of the activity in minutes")
    
    model_config = {"extra": "forbid"}

class ScheduleOptimizationParams(BaseModel):
    activities: List[ActivityItem] = Field(..., description="List of activities to schedule")
    start_time: str = Field(..., description="Start time in HH:MM format")
    end_time: Optional[str] = Field(None, description="End time in HH:MM format (optional)")
    
    model_config = {"extra": "forbid"}

# Define a structured schedule item model
class ScheduleItem(BaseModel):
    activity_name: str = Field(..., description="Name of the activity")
    location: str = Field("", description="Location of the activity")
    start_time: str = Field(..., description="Start time in HH:MM format")
    end_time: str = Field(..., description="End time in HH:MM format")
    travel_time_minutes: int = Field(0, description="Travel time to this location in minutes")
    
    model_config = {"extra": "forbid"}

class ItineraryCreationParams(BaseModel):
    schedule: List[ScheduleItem] = Field(..., description="Optimized schedule with timing")
    include_tips: bool = Field(True, description="Whether to include tips for each activity")
    
    model_config = {"extra": "forbid"}


# Tool implementation methods
async def calculate_travel_time_impl(origin: str, destination: str) -> Dict:
    """Calculate estimated travel time between two locations."""
    travel_info = get_travel_time(origin, destination)
    
    return {
        "origin": origin,
        "destination": destination,
        "travel_time_minutes": travel_info.get("driving_minutes", 0),
        "distance_miles": travel_info.get("driving_distance_miles", 0),
        "notes": travel_info.get("traffic_notes", "")
    }

async def optimize_schedule_impl(activities: List[ActivityItem], start_time: str, end_time: Optional[str] = None) -> Dict:
    """
    Optimize a schedule based on activities, durations, and locations.
    This is a simplified mock implementation.
    """
    # Parse start time
    try:
        start_hour, start_minute = map(int, start_time.split(':'))
        current_time = start_hour * 60 + start_minute  # Convert to minutes
    except (ValueError, AttributeError):
        return {"error": "Invalid start time format. Please use HH:MM format."}
    
    # Parse end time if provided
    end_time_minutes = None
    if end_time:
        try:
            end_hour, end_minute = map(int, end_time.split(':'))
            end_time_minutes = end_hour * 60 + end_minute
        except (ValueError, AttributeError):
            return {"error": "Invalid end time format. Please use HH:MM format."}
    
    # Create optimized schedule
    optimized_schedule = []
    last_location = "Home (Sunnyvale)"
    
    for activity in activities:
        # Add travel time from last location
        travel_info = get_travel_time(last_location, activity.get("location", ""))
        travel_time = travel_info.get("driving_minutes", 15)  # Default to 15 min if not found
        
        # Calculate activity start and end times
        activity_start_time = current_time + travel_time
        activity_end_time = activity_start_time + activity.get("duration_minutes", 60)
        
        # Check if we exceed end time
        if end_time_minutes and activity_end_time > end_time_minutes:
            break
        
        # Format times as HH:MM
        start_hour, start_minute = divmod(activity_start_time, 60)
        end_hour, end_minute = divmod(activity_end_time, 60)
        
        formatted_start = f"{start_hour:02d}:{start_minute:02d}"
        formatted_end = f"{end_hour:02d}:{end_minute:02d}"
        
        # Add to schedule
        optimized_schedule.append({
            "activity_name": activity.get("name", "Unknown Activity"),
            "location": activity.get("location", ""),
            "start_time": formatted_start,
            "end_time": formatted_end,
            "travel_time_minutes": travel_time
        })
        
        # Update for next iteration
        current_time = activity_end_time
        last_location = activity.get("location", "")
    
    return {"optimized_schedule": optimized_schedule}

async def create_itinerary_impl(schedule: List[ScheduleItem], include_tips: bool = True) -> Dict:
    """
    Create a narrative itinerary based on a schedule.
    This is a simplified mock implementation.
    """
    # Format the schedule into a narrative
    narrative = []
    
    # Add introduction
    if schedule:
        first_start = schedule[0]["start_time"]
        last_end = schedule[-1]["end_time"]
        narrative.append(f"# Itinerary ({first_start} - {last_end})\n")
    else:
        narrative.append("# Itinerary\n")
        
    narrative.append("Here's your plan for the day:\n")
    
    # Add each activity
    for i, item in enumerate(schedule):
        activity_name = item.get("activity_name", "Activity")
        start_time = item.get("start_time", "")
        end_time = item.get("end_time", "")
        location = item.get("location", "")
        
        narrative.append(f"## {start_time} - {end_time}: {activity_name}\n")
        narrative.append(f"**Location**: {location}\n")
        
        # Add travel info if it's not the first activity
        if i > 0:
            travel_time = item.get("travel_time_minutes", 0)
            if travel_time > 0:
                narrative.append(f"**Travel Time**: {travel_time} minutes from previous location\n")
        
        # Add tips if requested
        if include_tips:
            # This would be more sophisticated in a real implementation
            tips = []
            
            # Example location-based tips
            if "Park" in activity_name:
                tips.append("Bring sunscreen and water")
            if "Museum" in activity_name:
                tips.append("Check for any special exhibits")
            if "Zoo" in activity_name:
                tips.append("The animal feeding times are usually mid-morning")
            
            # Add some generic tips if we don't have specific ones
            if not tips:
                if "lunch" in activity_name.lower() or "dinner" in activity_name.lower():
                    tips.append("Consider making a reservation ahead of time")
                elif i == 0:
                    tips.append("Plan to arrive on time to make the most of your day")
            
            if tips:
                narrative.append("\n**Tips:**\n")
                for tip in tips:
                    narrative.append(f"- {tip}\n")
        
        narrative.append("\n")
    
    # Add conclusion
    narrative.append("## Notes\n")
    narrative.append("- All times include travel time from the previous location\n")
    narrative.append("- Keep your phone charged and have maps available for directions\n")
    narrative.append("- Have a great day!\n")
    
    return {
        "narrative_itinerary": "\n".join(narrative),
        "schedule_summary": f"Plan includes {len(schedule)} activities spanning from {schedule[0]['start_time'] if schedule else 'N/A'} to {schedule[-1]['end_time'] if schedule else 'N/A'}"
    }


def build_planner_agent(model: str = "gpt-4") -> Agent:
    """Build and return a Planner Agent using the OpenAI Agent SDK."""
    # Agent creation is logged via event hooks
    
    # Load the system prompt
    system_prompt = load_prompt("planner_base.md") + DISCLAIMER
    
    # Define tools
    @function_tool(name_override="calculate_travel_time",
                 description_override="Calculate estimated travel time between two locations",
                 failure_error_function=create_error_handler("calculate_travel_time"))
    async def calculate_travel_time(params: TravelTimeParams) -> str:
        """Calculate estimated travel time between two locations."""
        result = await calculate_travel_time_impl(params.origin, params.destination)
        return json.dumps(result)
    
    @function_tool(name_override="optimize_schedule",
                 description_override="Optimize a schedule based on activities, durations, and locations",
                 failure_error_function=create_error_handler("optimize_schedule"))
    async def optimize_schedule(params: ScheduleOptimizationParams) -> str:
        """Optimize a schedule based on activities, durations, and locations."""
        result = await optimize_schedule_impl(
            activities=params.activities,
            start_time=params.start_time,
            end_time=params.end_time
        )
        return json.dumps(result)
    
    @function_tool(name_override="create_itinerary",
                 description_override="Create a narrative itinerary based on a schedule",
                 failure_error_function=create_error_handler("create_itinerary"))
    async def create_itinerary(params: ItineraryCreationParams) -> str:
        """Create a narrative itinerary based on a schedule."""
        result = await create_itinerary_impl(
            schedule=params.schedule,
            include_tips=params.include_tips
        )
        return json.dumps(result)
    
    # Create and return the agent
    return Agent(
        name="Planner Agent",
        instructions=system_prompt,
        tools=[calculate_travel_time, optimize_schedule, create_itinerary],
        model=model,
        model_settings=ModelSettings(
            parallel_tool_calls=True,
            tool_choice="auto",
            temperature=0
        )
    )

async def run_planner_agent(query: str, agent: Agent = None, event_handler: Any = None) -> Dict[str, Any]:
    """Run the Planner Agent with a specific query."""
    # Build the agent if not provided
    if agent is None:
        agent = build_planner_agent()
    
    # Log processing - handle both direct queries and JSON specialist outputs
    try:
        input_data = json.loads(query)
        if isinstance(input_data, dict) and any(key in input_data for key in ["activity_results", "culinary_results", "foodie_results"]):
            # This is specialist outputs to synthesize
            # Planning is logged via event hooks
            
            # Format the request for the agent
            plan_request = f"""
            Please create a comprehensive plan based on the following specialist outputs:
            
            USER QUERY: {input_data.get('user_question', '')}
            
            ACTIVITY SUGGESTIONS: {json.dumps(input_data.get('activity_results', {}), indent=2)}
            
            CULINARY SUGGESTIONS: {json.dumps(input_data.get('culinary_results', {}), indent=2)}
            
            RESTAURANT SUGGESTIONS: {json.dumps(input_data.get('foodie_results', {}), indent=2)}
            
            Create a well-structured plan that integrates these suggestions with appropriate timing,
            transitions, and logistics. Include both a narrative description and a structured itinerary.
            """
            query_to_run = plan_request
        else:
            # Direct user input
            # Processing is logged via event hooks
            query_to_run = query
    except (json.JSONDecodeError, TypeError):
        # Not a JSON string, treat as direct user input
        # Processing is logged via event hooks
        query_to_run = query
    
    # Set up hooks if an event_handler was provided
    hooks = None
    if event_handler is not None:
        hooks = agent_hooks
    
    # Get max_turns from environment
    max_turns = int(os.environ.get("MAX_TURNS", 2))
    
    # Run the agent
    result = await Runner.run(
        starting_agent=agent,
        input=query_to_run,
        max_turns=max_turns,
        hooks=hooks
    )
    
    # Completion is logged via event hooks
    
    # Return the result
    return {
        "content": result.final_output,
        "agent": "Planner Agent"
    }