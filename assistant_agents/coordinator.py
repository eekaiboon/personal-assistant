"""
Head Coordinator Agent for the Personal Assistant.
This agent orchestrates the other specialist agents, routes requests,
and synthesizes results into cohesive responses for the user.
"""

import json
import os
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import OpenAI Agent SDK components
from agents import Agent, ModelSettings, function_tool, Runner
from assistant_agents import create_error_handler
from assistant_agents.event_hooks import agent_hooks
from utils import load_prompt, DISCLAIMER

# Import agent runner functions
from assistant_agents.activity import run_activity_agent
from assistant_agents.culinary import run_culinary_agent
from assistant_agents.foodie import run_foodie_agent
from assistant_agents.planner import run_planner_agent

# Tool implementation methods

# Tool implementation methods
async def get_activity_suggestions_impl(activity_agent, query: str, age: Optional[int] = None, 
                                      indoor_preference: Optional[bool] = None,
                                      event_handler: Any = None) -> Dict:
    """Get activity suggestions from the Activity Agent."""
    # Enhance the query with age and indoor preference if provided
    enhanced_query = query
    if age is not None:
        enhanced_query += f" for a {age}-year-old"
    if indoor_preference is not None:
        enhanced_query += f" {'indoors' if indoor_preference else 'outdoors'}"
    
    # Format the query summary
    query_summary = enhanced_query[:80] + ('...' if len(enhanced_query) > 80 else '')
    
    try:
        # Process through the activity agent - Note: run_activity_agent already does its own logging
        result = await run_activity_agent(enhanced_query, activity_agent, event_handler=event_handler)
        
        return result
    except Exception as e:
        error_msg = f"Error in Activity Agent: {str(e)}"
        logger.error(f"{error_msg}")
        return {"error": error_msg}

async def get_recipe_suggestions_impl(culinary_agent, query: str, cuisine: Optional[str] = None, 
                                   meal_type: Optional[str] = None,
                                   event_handler: Any = None) -> Dict:
    """Get recipe and cooking suggestions from the Culinary Agent."""
    # Enhance the query with cuisine and meal type if provided
    enhanced_query = query
    if cuisine:
        enhanced_query += f" {cuisine} cuisine"
    if meal_type:
        enhanced_query += f" for {meal_type}"
    
    # Format the query summary
    query_summary = enhanced_query[:80] + ('...' if len(enhanced_query) > 80 else '')
    
    try:
        # Process through the culinary agent - Note: run_culinary_agent already does its own logging
        result = await run_culinary_agent(enhanced_query, culinary_agent, event_handler=event_handler)
        
        return result
    except Exception as e:
        error_msg = f"Error in Culinary Agent: {str(e)}"
        logger.error(f"{error_msg}")
        return {"error": error_msg}

async def get_restaurant_suggestions_impl(foodie_agent, query: str, cuisine: Optional[str] = None, 
                                       location: Optional[str] = None,
                                       event_handler: Any = None) -> Dict:
    """Get restaurant and dining suggestions from the Foodie Agent."""
    # Enhance the query with cuisine and location if provided
    enhanced_query = query
    if cuisine:
        enhanced_query += f" {cuisine} cuisine"
    if location:
        enhanced_query += f" in {location}"
    
    # Format the query summary
    query_summary = enhanced_query[:80] + ('...' if len(enhanced_query) > 80 else '')
    
    try:
        # Process through the foodie agent - Note: run_foodie_agent already does its own logging
        result = await run_foodie_agent(enhanced_query, foodie_agent, event_handler=event_handler)
        
        return result
    except Exception as e:
        error_msg = f"Error in Foodie Agent: {str(e)}"
        logger.error(f"{error_msg}")
        return {"error": error_msg}

async def create_plan_impl(planner_agent, query: str, activity_results: Optional[Dict] = None,
                        culinary_results: Optional[Dict] = None,
                        foodie_results: Optional[Dict] = None,
                        event_handler: Any = None) -> Dict:
    """Create a comprehensive plan using the Planner Agent."""
    try:
        if any([activity_results, culinary_results, foodie_results]):
            planner_input = {
                "user_question": query,
                "activity_results": activity_results,
                "culinary_results": culinary_results,
                "foodie_results": foodie_results
            }
            
            result = await run_planner_agent(json.dumps(planner_input), planner_agent, event_handler=event_handler)
        else:
            # Direct query to the planner
            result = await run_planner_agent(query, planner_agent, event_handler=event_handler)
        
        # Note: run_planner_agent already handles logging
        
        return result
    except Exception as e:
        error_msg = f"Error in Planner Agent: {str(e)}"
        logger.error(f"{error_msg}")
        return {"error": error_msg}

def build_coordinator_agent(activity_agent, culinary_agent, foodie_agent, planner_agent, 
                           model: str = "gpt-4",
                           event_handler: Any = None) -> Agent:
    """Build and return a Coordinator Agent using the OpenAI Agent SDK."""
    # Agent creation is logged via event hooks
    
    # Load the system prompt
    system_prompt = load_prompt("coordinator_base.md") + DISCLAIMER
    
    # Define tools
    @function_tool
    async def get_activity_suggestions(query: str, age: Optional[int] = None, indoor_preference: Optional[bool] = None) -> str:
        """Get activity suggestions from the Activity Agent.
        
        Args:
            query: The activity-related query
            age: Age of the person for whom activities are being suggested (optional)
            indoor_preference: True for indoor activities, False for outdoor (optional)
        """
        result = await get_activity_suggestions_impl(
            activity_agent,
            query,
            age,
            indoor_preference,
            event_handler=event_handler
        )
        return json.dumps(result)
    
    @function_tool
    async def get_recipe_suggestions(query: str, cuisine: Optional[str] = None, meal_type: Optional[str] = None) -> str:
        """Get recipe and cooking suggestions from the Culinary Agent.
        
        Args:
            query: The cooking-related query
            cuisine: Type of cuisine (optional)
            meal_type: Type of meal (e.g., breakfast, lunch, dinner) (optional)
        """
        result = await get_recipe_suggestions_impl(
            culinary_agent,
            query,
            cuisine,
            meal_type,
            event_handler=event_handler
        )
        return json.dumps(result)
    
    @function_tool
    async def get_restaurant_suggestions(query: str, cuisine: Optional[str] = None, location: Optional[str] = None) -> str:
        """Get restaurant and dining suggestions from the Foodie Agent.
        
        Args:
            query: The dining-related query
            cuisine: Type of cuisine (optional)
            location: Location preference (optional)
        """
        result = await get_restaurant_suggestions_impl(
            foodie_agent,
            query,
            cuisine,
            location,
            event_handler=event_handler
        )
        return json.dumps(result)
    
    @function_tool
    async def create_plan(query: str, activity_results: Optional[str] = None,
                         culinary_results: Optional[str] = None,
                         foodie_results: Optional[str] = None) -> str:
        """Create a comprehensive plan using the Planner Agent.
        
        Args:
            query: The planning-related query
            activity_results: Results from the Activity Agent as JSON string (optional)
            culinary_results: Results from the Culinary Agent as JSON string (optional)
            foodie_results: Results from the Foodie Agent as JSON string (optional)
        """
        # Parse JSON strings to dictionaries if provided
        activity_dict = json.loads(activity_results) if activity_results else None
        culinary_dict = json.loads(culinary_results) if culinary_results else None
        foodie_dict = json.loads(foodie_results) if foodie_results else None
        
        result = await create_plan_impl(
            planner_agent,
            query,
            activity_dict,
            culinary_dict,
            foodie_dict,
            event_handler=event_handler
        )
        return json.dumps(result)
    
    # Create and return the agent
    return Agent(
        name="Head Coordinator Agent",
        instructions=system_prompt,
        tools=[get_activity_suggestions, get_recipe_suggestions, get_restaurant_suggestions, create_plan],
        model=model,
        model_settings=ModelSettings(
            parallel_tool_calls=True,
            tool_choice="auto",
            temperature=0
        )
    )

async def run_coordinator_agent(query: str, agent: Agent = None, 
                               activity_agent=None, culinary_agent=None, 
                               foodie_agent=None, planner_agent=None,
                               event_handler: Any = None) -> Dict[str, Any]:
    """Run the Coordinator Agent with a specific query."""
    # Build the agent if not provided
    if agent is None and all([activity_agent, culinary_agent, foodie_agent, planner_agent]):
        agent = build_coordinator_agent(
            activity_agent,
            culinary_agent,
            foodie_agent,
            planner_agent,
            event_handler=event_handler
        )
    elif agent is None:
        raise ValueError("Either agent or all specialist agents must be provided")
    
    # Processing is logged via event hooks
    
    # Set up hooks if an event_handler was provided
    hooks = None
    if event_handler is not None:
        hooks = agent_hooks
    
    try:
        # Get max_turns from environment
        max_turns = int(os.environ.get("MAX_TURNS", 2))
        
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
            "agent": "Head Coordinator Agent"
        }
    except Exception as e:
        return {
            "content": f"I apologize, but I encountered an error while processing your request: {str(e)}",
            "agent": "Head Coordinator Agent"
        }