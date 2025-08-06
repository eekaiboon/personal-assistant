"""
Head Coordinator Agent for the Personal Assistant.
This agent orchestrates the other specialist agents, routes requests,
and synthesizes results into cohesive responses for the user.
"""

import json
import asyncio
import logging
import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Import OpenAI Agent SDK components
from agents import Agent, ModelSettings, function_tool, Runner
from assistant_agents import AgentWrapper, create_error_handler
from utils import load_prompt, DISCLAIMER


# Define Pydantic models for structured inputs
class ActivityRequestInput(BaseModel):
    query: str = Field(description="The activity-related query")
    age: Optional[int] = Field(None, description="Age of the person for whom activities are being suggested (optional)")
    indoor_preference: Optional[bool] = Field(None, description="True for indoor activities, False for outdoor (optional)")

class CulinaryRequestInput(BaseModel):
    query: str = Field(description="The cooking-related query")
    cuisine: Optional[str] = Field(None, description="Type of cuisine (optional)")
    meal_type: Optional[str] = Field(None, description="Type of meal (e.g., breakfast, lunch, dinner) (optional)")

class FoodieRequestInput(BaseModel):
    query: str = Field(description="The dining-related query")
    cuisine: Optional[str] = Field(None, description="Type of cuisine (optional)")
    location: Optional[str] = Field(None, description="Location preference (optional)")

class PlannerRequestInput(BaseModel):
    query: str = Field(description="The planning-related query")
    activity_results: Optional[Dict[str, Any]] = Field(None, description="Results from the Activity Agent (optional)")
    culinary_results: Optional[Dict[str, Any]] = Field(None, description="Results from the Culinary Agent (optional)")
    foodie_results: Optional[Dict[str, Any]] = Field(None, description="Results from the Foodie Agent (optional)")

class CoordinatorAgent(AgentWrapper):
    """
    The Head Coordinator Agent that orchestrates all other specialist agents
    and manages the overall conversation flow using the OpenAI Agent SDK.
    """
    
    def __init__(self, activity_agent, culinary_agent, foodie_agent, planner_agent,
                 system_prompt: str = None, model: str = "gpt-4"):
        # Store references to specialist agents
        self.activity_agent = activity_agent
        self.culinary_agent = culinary_agent
        self.foodie_agent = foodie_agent
        self.planner_agent = planner_agent
        
        # Load default prompt if none provided
        if system_prompt is None:
            system_prompt = load_prompt("coordinator_base.md") + DISCLAIMER
        
        # Initialize using the AgentWrapper
        super().__init__("Head Coordinator Agent", system_prompt, model)
        
        # Create and register tools
        self._setup_tools()
        
    def _setup_tools(self):
        """Set up the tools for this agent using the Agent SDK."""
        
        # Activity suggestions tool
        @function_tool
        async def get_activity_suggestions(query: str, age: Optional[int] = None, indoor_preference: Optional[bool] = None) -> str:
            """Get activity suggestions from the Activity Agent.
            
            Args:
                query: The activity-related query
                age: Age of the person for whom activities are being suggested (optional)
                indoor_preference: True for indoor activities, False for outdoor (optional)
            """
            result = await self._get_activity_suggestions(query, age, indoor_preference)
            return json.dumps(result)
        
        # Recipe suggestions tool
        @function_tool
        async def get_recipe_suggestions(query: str, cuisine: Optional[str] = None, meal_type: Optional[str] = None) -> str:
            """Get recipe and cooking suggestions from the Culinary Agent.
            
            Args:
                query: The cooking-related query
                cuisine: Type of cuisine (optional)
                meal_type: Type of meal (e.g., breakfast, lunch, dinner) (optional)
            """
            result = await self._get_recipe_suggestions(query, cuisine, meal_type)
            return json.dumps(result)
        
        # Restaurant suggestions tool
        @function_tool
        async def get_restaurant_suggestions(query: str, cuisine: Optional[str] = None, location: Optional[str] = None) -> str:
            """Get restaurant and dining suggestions from the Foodie Agent.
            
            Args:
                query: The dining-related query
                cuisine: Type of cuisine (optional)
                location: Location preference (optional)
            """
            result = await self._get_restaurant_suggestions(query, cuisine, location)
            return json.dumps(result)
        
        # Comprehensive planning tool
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
            
            result = await self._create_plan(
                query, 
                activity_dict, 
                culinary_dict, 
                foodie_dict
            )
            return json.dumps(result)
        
        # Store tools for agent creation
        self.tools = [get_activity_suggestions, get_recipe_suggestions, get_restaurant_suggestions, create_plan]
        
    
    async def process(self, user_input: str, hooks=None) -> Dict[str, Any]:
        """
        Process a user input, route to appropriate specialist agents,
        and synthesize results using the Agent SDK.
        
        Args:
            user_input: The user's query
            hooks: Optional RunHooks for event handling
            
        Returns:
            Dict containing the agent's response
        """
        logger.info(f"\n\n💬 User: {user_input}")
        logger.info(f"👨‍💻 Head Coordinator is analyzing the query and determining which specialists to consult...")
        
        # Ensure the agent is built
        if self.agent is None:
            self.build_agent()
        
        # Run the agent using the Agent SDK Runner
        try:
            run_kwargs = {"starting_agent": self.agent, "input": user_input, "max_turns": 20}
            if hooks:
                run_kwargs["hooks"] = hooks
                
            # Make sure to await the coroutine properly
            run_coroutine = Runner.run(**run_kwargs)
            result = await run_coroutine
            
            # Log final response creation
            logger.info(f"🌟 Head Coordinator has completed processing and prepared the final response")
            
            # Return the final message content
            return {
                "content": result.final_output,
                "agent": self.name
            }
            
        except Exception as e:
            logger.error(f"❌ Error in Head Coordinator: {str(e)}")
            return {
                "content": f"I apologize, but I encountered an error while processing your request: {str(e)}",
                "agent": self.name
            }
    
    # Tool implementation methods
    
    async def _get_activity_suggestions(self, query: str, age: Optional[int] = None, 
                                     indoor_preference: Optional[bool] = None) -> Dict:
        """Get activity suggestions from the Activity Agent."""
        # Enhance the query with age and indoor preference if provided
        enhanced_query = query
        if age is not None:
            enhanced_query += f" for a {age}-year-old"
        if indoor_preference is not None:
            enhanced_query += f" {'indoors' if indoor_preference else 'outdoors'}"
        
        # Get root logger for direct visibility
        root_logger = logging.getLogger()
        
        # Format the query summary
        query_summary = enhanced_query[:80] + ('...' if len(enhanced_query) > 80 else '')
        
        # Log both to module logger and root logger
        logger.info(f"\n\n🎡 Activating Activity Agent with query: '{query_summary}'")
        logger.info(f"\n🎡 Activity Agent is analyzing the request...")
        
        # Direct logs to root logger for main.py visibility
        root_logger.info(f"\n\n🎡 [Activity Agent] Starting with query: '{query_summary}'")
        root_logger.info(f"\n🎡 [Activity Agent] Analyzing the request...")
        
        try:
            # Process through the activity agent
            result = await self.activity_agent.process(enhanced_query)
            
            # Log completion
            logger.info(f"\n🎡 Activity Agent has completed its analysis")
            logger.info(f"\n💬 Coordinator is receiving activity suggestions")
            
            # Direct completion log to root
            root_logger.info(f"\n🎡 [Activity Agent] Completed analysis and returning suggestions")
            
            return result
        except Exception as e:
            error_msg = f"Error in Activity Agent: {str(e)}"
            logger.error(f"\n❌ {error_msg}")
            root_logger.error(f"\n❌ [Activity Agent] {error_msg}")
            return {"error": error_msg}
    
    async def _get_recipe_suggestions(self, query: str, cuisine: Optional[str] = None, 
                                    meal_type: Optional[str] = None) -> Dict:
        """Get recipe and cooking suggestions from the Culinary Agent."""
        # Enhance the query with cuisine and meal type if provided
        enhanced_query = query
        if cuisine:
            enhanced_query += f" {cuisine} cuisine"
        if meal_type:
            enhanced_query += f" for {meal_type}"
        
        # Get root logger for direct visibility
        root_logger = logging.getLogger()
        
        # Format the query summary
        query_summary = enhanced_query[:80] + ('...' if len(enhanced_query) > 80 else '')
        
        # Log both to module logger and root logger
        logger.info(f"\n\n🍲 Activating Culinary Agent with query: '{query_summary}'")
        logger.info(f"\n🍲 Culinary Agent is analyzing your food preferences and requirements...")
        
        # Direct logs to root logger for main.py visibility
        root_logger.info(f"\n\n🍲 [Culinary Agent] Starting with query: '{query_summary}'")
        root_logger.info(f"\n🍲 [Culinary Agent] Analyzing food preferences and requirements...")
        
        # Process through the culinary agent
        result = await self.culinary_agent.process(enhanced_query)
        
        # Log completion
        logger.info(f"\n🍲 Culinary Agent has completed its analysis")
        logger.info(f"\n💬 Coordinator is receiving cooking suggestions")
        
        # Direct completion log to root
        root_logger.info(f"\n🍲 [Culinary Agent] Completed analysis and returning recipe suggestions")
        
        return result
    
    async def _get_restaurant_suggestions(self, query: str, cuisine: Optional[str] = None, 
                                        location: Optional[str] = None) -> Dict:
        """Get restaurant and dining suggestions from the Foodie Agent."""
        # Enhance the query with cuisine and location if provided
        enhanced_query = query
        if cuisine:
            enhanced_query += f" {cuisine} cuisine"
        if location:
            enhanced_query += f" in {location}"
        
        # Get root logger for direct visibility
        root_logger = logging.getLogger()
        
        # Format the query summary
        query_summary = enhanced_query[:80] + ('...' if len(enhanced_query) > 80 else '')
        
        # Log both to module logger and root logger
        logger.info(f"\n\n🍴 Activating Foodie Agent with query: '{query_summary}'")
        logger.info(f"\n🍴 Foodie Agent is searching for restaurant recommendations...")
        
        # Direct logs to root logger for main.py visibility
        root_logger.info(f"\n\n🍴 [Foodie Agent] Starting with query: '{query_summary}'")
        root_logger.info(f"\n🍴 [Foodie Agent] Searching for restaurant recommendations...")
        
        # Process through the foodie agent
        result = await self.foodie_agent.process(enhanced_query)
        
        # Log completion
        logger.info(f"\n🍴 Foodie Agent has completed its search")
        logger.info(f"\n💬 Coordinator is receiving restaurant suggestions")
        
        # Direct completion log to root
        root_logger.info(f"\n🍴 [Foodie Agent] Completed search and returning restaurant suggestions")
        
        return result
    
    async def _create_plan(self, query: str, activity_results: Optional[Dict] = None,
                         culinary_results: Optional[Dict] = None,
                         foodie_results: Optional[Dict] = None) -> Dict:
        """Create a comprehensive plan using the Planner Agent."""
        # Get root logger for direct visibility
        root_logger = logging.getLogger()
        
        # If we have specialist results, package them for the planner
        logger.info(f"\n\n📑 Activating Planner Agent to create a comprehensive plan")
        root_logger.info(f"\n\n📑 [Planner Agent] Starting to create a comprehensive plan")
        
        if any([activity_results, culinary_results, foodie_results]):
            planner_input = {
                "user_question": query,
                "activity_results": activity_results,
                "culinary_results": culinary_results,
                "foodie_results": foodie_results
            }
            
            # Log what information we're giving to the planner
            specialists_used = []
            if activity_results:
                specialists_used.append("Activity")
            if culinary_results:
                specialists_used.append("Culinary")
            if foodie_results:
                specialists_used.append("Foodie")
            
            specialists_str = ", ".join(specialists_used)
            logger.info(f"\n📑 Planner Agent is synthesizing results from: {specialists_str}")
            root_logger.info(f"\n📑 [Planner Agent] Synthesizing results from: {specialists_str}")
            
            result = await self.planner_agent.process(json.dumps(planner_input))
        else:
            # Direct query to the planner
            logger.info(f"\n📑 Planner Agent is creating a plan directly from query")
            root_logger.info(f"\n📑 [Planner Agent] Creating a plan directly from query")
            result = await self.planner_agent.process(query)
        
        logger.info(f"\n📑 Planner Agent has completed the comprehensive plan")
        logger.info(f"\n💬 Coordinator is receiving the finalized plan")
        root_logger.info(f"\n📑 [Planner Agent] Completed the comprehensive plan")
            
        return result
    


def build_coordinator_agent(activity_agent, culinary_agent, foodie_agent, planner_agent, 
                           system_prompt: str = None, model: str = "gpt-4") -> CoordinatorAgent:
    """Build and return a CoordinatorAgent."""
    return CoordinatorAgent(
        activity_agent=activity_agent,
        culinary_agent=culinary_agent,
        foodie_agent=foodie_agent,
        planner_agent=planner_agent,
        system_prompt=system_prompt,
        model=model
    )