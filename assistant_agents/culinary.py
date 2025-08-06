"""
Culinary Agent for the Personal Assistant.
Specializes in home cooking suggestions and recipes.
"""

import json
from typing import Dict, Any, List, Optional

from assistant_agents import BaseAgent, FunctionTool
from utils import load_prompt, DISCLAIMER, get_recipes


class CulinaryAgent(BaseAgent):
    """
    Agent specialized in suggesting recipes, cooking tips,
    and meal planning for home cooking.
    """
    
    def __init__(self, system_prompt: str = None, model: str = "gpt-4"):
        # Load default prompt if none provided
        if system_prompt is None:
            system_prompt = load_prompt("culinary_base.md") + DISCLAIMER
        
        super().__init__("Culinary Agent", system_prompt, model)
        
        # Add tools for the agent
        self._setup_tools()
        
    def _setup_tools(self):
        """Set up the tools for this agent."""
        
        # Tool to search for recipes based on criteria
        search_recipes_tool = FunctionTool(
            func=self._search_recipes,
            name="search_recipes",
            description="Search for recipes based on cuisine, meal type, and prep time"
        )
        search_recipes_tool.parameters = {
            "cuisine": {"type": "string", "description": "Type of cuisine (e.g., Chinese, Korean, Japanese)"},
            "meal_type": {"type": "string", "description": "Type of meal (e.g., breakfast, lunch, dinner, snack)"},
            "max_prep_time": {"type": "integer", "description": "Maximum preparation time in minutes"}
        }
        self.add_tool(search_recipes_tool)
        
        # Tool to get recipe details
        get_recipe_details_tool = FunctionTool(
            func=self._get_recipe_details,
            name="get_recipe_details",
            description="Get detailed information about a specific recipe"
        )
        get_recipe_details_tool.parameters = {
            "recipe_name": {"type": "string", "description": "Name of the recipe"}
        }
        self.add_tool(get_recipe_details_tool)
        
        # Tool to get favorite recipes
        get_favorite_recipes_tool = FunctionTool(
            func=self._get_favorite_recipes,
            name="get_favorite_recipes",
            description="Get a list of favorite recipes"
        )
        self.add_tool(get_favorite_recipes_tool)
        
        # Tool to get kid-friendly recipes
        get_kid_friendly_recipes_tool = FunctionTool(
            func=self._get_kid_friendly_recipes,
            name="get_kid_friendly_recipes",
            description="Get kid-friendly recipes"
        )
        get_kid_friendly_recipes_tool.parameters = {
            "cuisine": {"type": "string", "description": "Type of cuisine (optional)"},
            "max_prep_time": {"type": "integer", "description": "Maximum preparation time in minutes (optional)"}
        }
        self.add_tool(get_kid_friendly_recipes_tool)
    
    async def process(self, user_input: str) -> Dict[str, Any]:
        """
        Process a user input related to recipes and cooking.
        
        Args:
            user_input: The user's query about recipes or cooking
            
        Returns:
            Dict containing the agent's response
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        # Initial call to get response or tool calls
        response = await self.call_openai_api(messages)
        message = response.choices[0].message
        
        # Handle any tool calls
        while message.tool_calls:
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
                messages.append({
                    "role": "tool",
                    "tool_call_id": message.tool_calls[tool_results.index(result)].id,
                    "content": json.dumps(result.result)
                })
            
            # Get next response
            response = await self.call_openai_api(messages)
            message = response.choices[0].message
        
        # Return the final message content
        return {
            "content": message.content,
            "agent": self.name
        }
    
    # Tool implementation methods
    
    async def _search_recipes(self, cuisine: Optional[str] = None, 
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
    
    async def _get_recipe_details(self, recipe_name: str) -> Dict:
        """Get detailed information about a specific recipe."""
        recipes = get_recipes()
        
        for recipe in recipes:
            if recipe["name"].lower() == recipe_name.lower():
                return recipe
                
        return {"error": f"Recipe '{recipe_name}' not found"}
    
    async def _get_favorite_recipes(self) -> List[Dict]:
        """Get a list of favorite recipes."""
        recipes = get_recipes()
        
        # Filter for favorite recipes
        favorites = [r for r in recipes if r.get("favorite", False)]
        
        return favorites
    
    async def _get_kid_friendly_recipes(self, cuisine: Optional[str] = None, 
                                     max_prep_time: Optional[int] = None) -> List[Dict]:
        """Get kid-friendly recipes."""
        filters = {"kid_friendly": True}
        if cuisine:
            filters["cuisine"] = cuisine
        if max_prep_time:
            filters["max_prep_time"] = max_prep_time
            
        recipes = get_recipes(**filters)
        
        return [r for r in recipes if r.get("kid_friendly", False)]


def build_culinary_agent(system_prompt: str = None, model: str = "gpt-4") -> CulinaryAgent:
    """Build and return a CulinaryAgent."""
    return CulinaryAgent(system_prompt, model)