"""
Foodie Agent for the Personal Assistant.
Specializes in restaurant recommendations and dining options.
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
from utils import load_prompt, DISCLAIMER, get_restaurants, get_travel_time


# Define Pydantic models for the tools
class RestaurantSearchParams(BaseModel):
    cuisine: Optional[str] = Field(None, description="Type of cuisine (e.g., Italian, Chinese, etc.)")
    location: Optional[str] = Field(None, description="Location/area name")
    price_range: Optional[int] = Field(None, description="Price range (1-5, where 5 is most expensive)")
    
    model_config = {"extra": "forbid"}


class RestaurantDetailsParams(BaseModel):
    restaurant_name: str = Field(..., description="Name of the restaurant")
    
    model_config = {"extra": "forbid"}


class KidFriendlyRestaurantsParams(BaseModel):
    cuisine: Optional[str] = Field(None, description="Type of cuisine (optional)")
    location: Optional[str] = Field(None, description="Location/area name (optional)")
    
    model_config = {"extra": "forbid"}


class RestaurantTravelTimeParams(BaseModel):
    restaurant_name: str = Field(..., description="Name of the restaurant")
    starting_point: str = Field("Sunnyvale", description="Starting point (defaults to Sunnyvale)")
    
    model_config = {"extra": "forbid"}


# Tool implementation methods
async def search_restaurants_impl(cuisine: Optional[str] = None, 
                               location: Optional[str] = None, 
                               price_range: Optional[int] = None) -> List[Dict]:
    """Search for restaurants based on criteria."""
    filters = {}
    if cuisine:
        filters["cuisine"] = cuisine
    if location:
        filters["location"] = location
    if price_range is not None:
        filters["price_range"] = price_range
            
    restaurants = get_restaurants(**filters)
    
    # Simplify the output for the agent
    simplified = []
    for restaurant in restaurants:
        simplified.append({
            "name": restaurant["name"],
            "cuisine": restaurant.get("cuisine", ""),
            "location": restaurant.get("location", ""),
            "price_range": restaurant.get("price_range", "$"),
            "rating": restaurant.get("rating", 0.0),
            "description": restaurant.get("description", ""),
            "kid_friendly": restaurant.get("kid_friendly", False)
        })
            
    return simplified


async def get_restaurant_details_impl(restaurant_name: str) -> Dict:
    """Get detailed information about a specific restaurant."""
    restaurants = get_restaurants()
    
    for restaurant in restaurants:
        if restaurant["name"].lower() == restaurant_name.lower():
            return restaurant
                
    return {"error": f"Restaurant '{restaurant_name}' not found"}


async def get_favorite_restaurants_impl() -> List[Dict]:
    """Get a list of favorite restaurants."""
    restaurants = get_restaurants()
    
    # Filter for restaurants with high ratings (4.5+)
    favorites = [r for r in restaurants if r.get("rating", 0) >= 4.5]
    
    return favorites


async def get_kid_friendly_restaurants_impl(cuisine: Optional[str] = None,
                                         location: Optional[str] = None) -> List[Dict]:
    """Get kid-friendly restaurants."""
    filters = {"kid_friendly": True}
    if cuisine:
        filters["cuisine"] = cuisine
    if location:
        filters["location"] = location
            
    restaurants = get_restaurants(**filters)
    
    return [r for r in restaurants if r.get("kid_friendly", False)]


async def get_restaurant_travel_time_impl(restaurant_name: str, 
                                       starting_point: str = "Sunnyvale") -> Dict:
    """Get travel time to a specific restaurant."""
    # First, get the restaurant details to find its location
    restaurants = get_restaurants()
    
    restaurant = None
    for r in restaurants:
        if r["name"].lower() == restaurant_name.lower():
            restaurant = r
            break
                
    if not restaurant:
        return {"error": f"Restaurant '{restaurant_name}' not found"}
            
    restaurant_location = restaurant.get("location", "")
    if not restaurant_location:
        return {"error": f"Restaurant '{restaurant_name}' has no location information"}
            
    # Get travel time from starting point to restaurant location
    travel_info = get_travel_time(starting_point, restaurant_location)
    
    return {
        "restaurant_name": restaurant_name,
        "starting_point": starting_point,
        "destination": restaurant_location,
        "travel_time_minutes": travel_info.get("driving_minutes", 0),
        "distance_miles": travel_info.get("driving_distance_miles", 0),
        "notes": travel_info.get("note", "")
    }


def build_foodie_agent(model: str = "gpt-4") -> Agent:
    """Build and return a Foodie Agent using the OpenAI Agent SDK."""
    # Agent creation is logged via event hooks
    
    # Load the system prompt
    system_prompt = load_prompt("foodie_base.md") + DISCLAIMER
    
    # Define tools
    @function_tool(name_override="search_restaurants",
                 description_override="Search for restaurants based on cuisine, location, and price range",
                 failure_error_function=create_error_handler("search_restaurants"))
    async def search_restaurants(params: RestaurantSearchParams) -> str:
        """Search for restaurants based on criteria."""
        result = await search_restaurants_impl(
            cuisine=params.cuisine,
            location=params.location,
            price_range=params.price_range
        )
        return json.dumps(result)
    
    @function_tool(name_override="get_restaurant_details",
                 description_override="Get detailed information about a specific restaurant",
                 failure_error_function=create_error_handler("get_restaurant_details"))
    async def get_restaurant_details(params: RestaurantDetailsParams) -> str:
        """Get detailed information about a specific restaurant."""
        result = await get_restaurant_details_impl(params.restaurant_name)
        return json.dumps(result)
    
    @function_tool(name_override="get_favorite_restaurants",
                 description_override="Get a list of favorite restaurants",
                 failure_error_function=create_error_handler("get_favorite_restaurants"))
    async def get_favorite_restaurants() -> str:
        """Get a list of favorite restaurants."""
        result = await get_favorite_restaurants_impl()
        return json.dumps(result)
    
    @function_tool(name_override="get_kid_friendly_restaurants",
                 description_override="Get kid-friendly restaurants",
                 failure_error_function=create_error_handler("get_kid_friendly_restaurants"))
    async def get_kid_friendly_restaurants(params: KidFriendlyRestaurantsParams) -> str:
        """Get kid-friendly restaurants."""
        result = await get_kid_friendly_restaurants_impl(
            cuisine=params.cuisine,
            location=params.location
        )
        return json.dumps(result)
    
    @function_tool(name_override="get_restaurant_travel_time",
                 description_override="Get travel time to a specific restaurant",
                 failure_error_function=create_error_handler("get_restaurant_travel_time"))
    async def get_restaurant_travel_time(params: RestaurantTravelTimeParams) -> str:
        """Get travel time to a specific restaurant."""
        result = await get_restaurant_travel_time_impl(
            restaurant_name=params.restaurant_name,
            starting_point=params.starting_point
        )
        return json.dumps(result)
    
    # Create and return the agent
    return Agent(
        name="Foodie Agent",
        instructions=system_prompt,
        tools=[
            search_restaurants, 
            get_restaurant_details, 
            get_favorite_restaurants, 
            get_kid_friendly_restaurants,
            get_restaurant_travel_time
        ],
        model=model,
        model_settings=ModelSettings(
            parallel_tool_calls=True,
            tool_choice="auto",
            temperature=0
        )
    )


async def run_foodie_agent(query: str, agent: Agent = None, event_handler: Any = None) -> Dict[str, Any]:
    """Run the Foodie Agent with a specific query."""
    # Build the agent if not provided
    if agent is None:
        agent = build_foodie_agent()
    
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
        "agent": "Foodie Agent"
    }