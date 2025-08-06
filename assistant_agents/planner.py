"""
Planner Agent for the Personal Assistant.
Specializes in creating comprehensive plans by synthesizing information from other agents.
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from assistant_agents import BaseAgent, FunctionTool
from utils import load_prompt, DISCLAIMER, get_travel_time


class PlannerAgent(BaseAgent):
    """
    Agent specialized in creating comprehensive plans by integrating information
    from other specialized agents and adding timing, logistics, and organization.
    """
    
    def __init__(self, system_prompt: str = None, model: str = "gpt-4"):
        # Load default prompt if none provided
        if system_prompt is None:
            system_prompt = load_prompt("planner_base.md") + DISCLAIMER
        
        super().__init__("Planner Agent", system_prompt, model)
        
        # Add tools for the agent
        self._setup_tools()
        
    def _setup_tools(self):
        """Set up the tools for this agent."""
        
        # Tool to calculate travel time between locations
        calculate_travel_time_tool = FunctionTool(
            func=self._calculate_travel_time,
            name="calculate_travel_time",
            description="Calculate estimated travel time between two locations"
        )
        calculate_travel_time_tool.parameters = {
            "origin": {"type": "string", "description": "Starting location name"},
            "destination": {"type": "string", "description": "Destination location name"}
        }
        self.add_tool(calculate_travel_time_tool)
        
        # Tool to optimize schedule timing
        optimize_schedule_tool = FunctionTool(
            func=self._optimize_schedule,
            name="optimize_schedule",
            description="Optimize a schedule based on activities, durations, and locations"
        )
        optimize_schedule_tool.parameters = {
            "activities": {
                "type": "array",
                "description": "List of activities to schedule",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the activity"},
                        "location": {"type": "string", "description": "Location of the activity"},
                        "duration_minutes": {"type": "integer", "description": "Duration of the activity in minutes"}
                    }
                }
            },
            "start_time": {"type": "string", "description": "Start time in HH:MM format"},
            "end_time": {"type": "string", "description": "End time in HH:MM format (optional)"}
        }
        self.add_tool(optimize_schedule_tool)
        
        # Tool to create a narrative itinerary
        create_itinerary_tool = FunctionTool(
            func=self._create_itinerary,
            name="create_itinerary",
            description="Create a narrative itinerary based on a schedule"
        )
        create_itinerary_tool.parameters = {
            "schedule": {
                "type": "array",
                "description": "Optimized schedule with timing",
                "items": {
                    "type": "object",
                    "properties": {
                        "activity_name": {"type": "string", "description": "Name of the activity"},
                        "start_time": {"type": "string", "description": "Start time in HH:MM format"},
                        "end_time": {"type": "string", "description": "End time in HH:MM format"},
                        "location": {"type": "string", "description": "Location of the activity"}
                    }
                }
            },
            "include_tips": {"type": "boolean", "description": "Whether to include tips for each activity"}
        }
        self.add_tool(create_itinerary_tool)
    
    async def process(self, user_input: str) -> Dict[str, Any]:
        """
        Process user inputs or specialist agent outputs to create a comprehensive plan.
        
        Args:
            user_input: Either direct user query or a JSON string containing specialist outputs
            
        Returns:
            Dict containing the agent's response with a comprehensive plan
        """
        logger.info(f"📑 Planner Agent is analyzing input ({len(user_input)} chars)")
        
        # Check if input is a JSON string with specialist outputs
        try:
            input_data = json.loads(user_input)
            if isinstance(input_data, dict) and any(key in input_data for key in ["activity_results", "culinary_results", "foodie_results"]):
                # This is a request from the coordinator with specialist results
                logger.info(f"📑 Planner Agent detected specialist outputs to synthesize")
                if 'user_question' in input_data:
                    logger.info(f"📑 Planning for user query: {input_data.get('user_question')}")
                
                # Log what specialists provided input
                specialists_input = []
                if 'activity_results' in input_data:
                    specialists_input.append('Activity')
                if 'culinary_results' in input_data:
                    specialists_input.append('Culinary')
                if 'foodie_results' in input_data:
                    specialists_input.append('Foodie')
                    
                logger.info(f"📑 Synthesizing inputs from: {', '.join(specialists_input)} agents")
                
                plan_request = f"""
                Please create a comprehensive plan based on the following specialist outputs:
                
                USER QUERY: {input_data.get('user_question', '')}
                
                ACTIVITY SUGGESTIONS: {json.dumps(input_data.get('activity_results', {}), indent=2)}
                
                CULINARY SUGGESTIONS: {json.dumps(input_data.get('culinary_results', {}), indent=2)}
                
                RESTAURANT SUGGESTIONS: {json.dumps(input_data.get('foodie_results', {}), indent=2)}
                
                Create a well-structured plan that integrates these suggestions with appropriate timing,
                transitions, and logistics. Include both a narrative description and a structured itinerary.
                """
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": plan_request}
                ]
            else:
                # Just a regular user input
                logger.info(f"📑 Planner Agent processing direct user input: {user_input[:50]}...")
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_input}
                ]
        except (json.JSONDecodeError, TypeError):
            # Not a JSON string, treat as direct user input
            logger.info(f"📑 Planner Agent processing direct user input: {user_input[:50]}...")
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_input}
            ]
        
        logger.info(f"📑 Planner Agent is starting to design the plan")
        
        # Initial call to get response or tool calls
        response = await self.call_openai_api(messages)
        message = response.choices[0].message
        
        # Log initial thinking
        if message.content:
            logger.info(f"📑 Planner Agent initial thoughts: {message.content[:80]}...")
            
        # Handle any tool calls
        tool_call_count = 0
        while message.tool_calls:
            tool_call_count += 1
            logger.info(f"📑 Planner Agent is calculating timing and logistics (step {tool_call_count})")
            
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
                # Log what the planner is doing with tools
                tool_name = result.name
                if 'calculate_travel_time' in tool_name:
                    if isinstance(result.result, dict):
                        logger.info(f"📑 Calculated travel time from {result.result.get('origin', 'unknown')} to {result.result.get('destination', 'unknown')}: {result.result.get('travel_time_minutes', '?')} minutes")
                elif 'optimize_schedule' in tool_name:
                    logger.info(f"📑 Optimizing activity schedule and timing")
                elif 'create_itinerary' in tool_name:
                    logger.info(f"📑 Creating detailed itinerary narrative")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": message.tool_calls[tool_results.index(result)].id,
                    "content": json.dumps(result.result)
                })
            
            # Get next response
            logger.info(f"📑 Planner Agent is refining the plan based on calculated logistics")
            response = await self.call_openai_api(messages)
            message = response.choices[0].message
        
        logger.info(f"📑 Planner Agent has completed the comprehensive plan")
        
        # Return the final message content
        return {
            "content": message.content,
            "agent": self.name
        }
    
    # Tool implementation methods
    
    async def _calculate_travel_time(self, origin: str, destination: str) -> Dict:
        """Calculate estimated travel time between two locations."""
        travel_info = get_travel_time(origin, destination)
        
        return {
            "origin": origin,
            "destination": destination,
            "travel_time_minutes": travel_info.get("driving_minutes", 0),
            "distance_miles": travel_info.get("driving_distance_miles", 0),
            "notes": travel_info.get("traffic_notes", "")
        }
    
    async def _optimize_schedule(self, activities: List[Dict], start_time: str, end_time: Optional[str] = None) -> Dict:
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
    
    async def _create_itinerary(self, schedule: List[Dict], include_tips: bool = True) -> Dict:
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


def build_planner_agent(system_prompt: str = None, model: str = "gpt-4") -> PlannerAgent:
    """Build and return a PlannerAgent."""
    return PlannerAgent(system_prompt, model)