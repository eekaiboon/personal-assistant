"""
Culinary Agent for the Personal Assistant.
Specializes in home cooking suggestions and recipes.
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
from utils import load_prompt, DISCLAIMER, get_recipes


# Define Pydantic models for the tools
class RecipeSearchParams(BaseModel):
    """Parameters for searching recipes."""
    cuisine: Optional[str] = Field(None, description="Type of cuisine (e.g., Chinese, Korean, Japanese, Italian)")
    meal_type: Optional[str] = Field(None, description="Type of meal (e.g., breakfast, lunch, dinner, snack)")
    max_prep_time: Optional[int] = Field(None, description="Maximum preparation time in minutes")
    
    model_config = {"extra": "forbid"}


class RecipeDetailsParams(BaseModel):
    """Parameters for getting recipe details."""
    recipe_name: str = Field(..., description="Name of the recipe to get details for")
    
    model_config = {"extra": "forbid"}


class KidFriendlyRecipesParams(BaseModel):
    """Parameters for searching kid-friendly recipes."""
    cuisine: Optional[str] = Field(None, description="Type of cuisine (optional)")
    max_prep_time: Optional[int] = Field(None, description="Maximum preparation time in minutes (optional)")
    
    model_config = {"extra": "forbid"}


class FavoriteRecipesParams(BaseModel):
    """Parameters for getting favorite recipes (no parameters needed)."""
    
    model_config = {"extra": "forbid"}


# Tool implementation methods
async def search_recipes_impl(cuisine: Optional[str] = None, 
                           meal_type: Optional[str] = None, 
                           max_prep_time: Optional[int] = None) -> List[Dict]:
    """Search for recipes based on criteria."""
    filters = {}
    if cuisine:
        filters["cuisine"] = cuisine
    if meal_type:
        filters["meal_type"] = meal_type
    if max_prep_time:
        filters["max_prep_time"] = max_prep_time
        
    recipes = get_recipes(**filters)
    
    # Simplify the output for the agent
    simplified = []
    for recipe in recipes:
        simplified.append({
            "name": recipe["name"],
            "cuisine": recipe.get("cuisine", ""),
            "meal_type": recipe.get("meal_type", ""),
            "description": recipe.get("description", ""),
            "prep_time": recipe.get("prep_time", 0),
            "cook_time": recipe.get("cook_time", 0),
            "kid_friendly": recipe.get("kid_friendly", False),
            "favorite": recipe.get("favorite", False)
        })
        
    return simplified


async def get_recipe_details_impl(recipe_name: str) -> Dict:
    """Get detailed information about a specific recipe."""
    recipes = get_recipes()
    
    for recipe in recipes:
        if recipe["name"].lower() == recipe_name.lower():
            return recipe
            
    return {"error": f"Recipe '{recipe_name}' not found"}


async def get_favorite_recipes_impl() -> List[Dict]:
    """Get a list of favorite recipes."""
    recipes = get_recipes()
    
    # Filter for favorite recipes
    favorites = [r for r in recipes if r.get("favorite", False)]
    
    return favorites


async def get_kid_friendly_recipes_impl(cuisine: Optional[str] = None, 
                                     max_prep_time: Optional[int] = None) -> List[Dict]:
    """Get kid-friendly recipes."""
    filters = {"kid_friendly": True}
    if cuisine:
        filters["cuisine"] = cuisine
    if max_prep_time:
        filters["max_prep_time"] = max_prep_time
        
    recipes = get_recipes(**filters)
    
    return [r for r in recipes if r.get("kid_friendly", False)]


def build_culinary_agent(model: str = "gpt-4") -> Agent:
    """Build and return a Culinary Agent using the OpenAI Agent SDK."""
    # Agent creation is logged via event hooks
    
    # Load the system prompt
    system_prompt = load_prompt("culinary_base.md") + DISCLAIMER
    
    # Define tools
    @function_tool(name_override="search_recipes",
                 description_override="Search for recipes based on cuisine, meal type, and prep time",
                 failure_error_function=create_error_handler("search_recipes"))
    async def search_recipes(params: RecipeSearchParams) -> str:
        """Search for recipes based on criteria."""
        result = await search_recipes_impl(
            cuisine=params.cuisine,
            meal_type=params.meal_type,
            max_prep_time=params.max_prep_time
        )
        return json.dumps(result)
    
    @function_tool(name_override="get_recipe_details",
                 description_override="Get detailed information about a specific recipe",
                 failure_error_function=create_error_handler("get_recipe_details"))
    async def get_recipe_details(params: RecipeDetailsParams) -> str:
        """Get detailed information about a specific recipe."""
        result = await get_recipe_details_impl(params.recipe_name)
        return json.dumps(result)
    
    @function_tool(name_override="get_favorite_recipes",
                 description_override="Get a list of favorite recipes",
                 failure_error_function=create_error_handler("get_favorite_recipes"))
    async def get_favorite_recipes(params: FavoriteRecipesParams) -> str:
        """Get a list of favorite recipes."""
        result = await get_favorite_recipes_impl()
        return json.dumps(result)
    
    @function_tool(name_override="get_kid_friendly_recipes",
                 description_override="Get kid-friendly recipes",
                 failure_error_function=create_error_handler("get_kid_friendly_recipes"))
    async def get_kid_friendly_recipes(params: KidFriendlyRecipesParams) -> str:
        """Get kid-friendly recipes."""
        result = await get_kid_friendly_recipes_impl(
            cuisine=params.cuisine,
            max_prep_time=params.max_prep_time
        )
        return json.dumps(result)
    
    # Create and return the agent
    return Agent(
        name="Culinary Agent",
        instructions=system_prompt,
        tools=[search_recipes, get_recipe_details, get_favorite_recipes, get_kid_friendly_recipes],
        model=model,
        model_settings=ModelSettings(
            parallel_tool_calls=True,
            tool_choice="auto",
            temperature=0
        )
    )


async def run_culinary_agent(query: str, agent: Agent = None, event_handler: Any = None) -> Dict[str, Any]:
    """Run the Culinary Agent with a specific query."""
    # Build the agent if not provided
    if agent is None:
        agent = build_culinary_agent()
    
    # Processing is logged via event hooks
    
    # Set up hooks if an event_handler was provided
    hooks = None
    if event_handler is not None:
        hooks = agent_hooks
    
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
        "agent": "Culinary Agent"
    }