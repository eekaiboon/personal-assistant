"""
Foodie Agent for the Personal Assistant.
Specializes in restaurant recommendations and dining out suggestions.
"""

import json
from typing import Dict, Any, List, Optional

from assistant_agents import BaseAgent, FunctionTool
from utils import load_prompt, DISCLAIMER, get_restaurants, get_travel_time


class FoodieAgent(BaseAgent):
    """
    Agent specialized in suggesting restaurants and dining options
    based on cuisine preferences, location, and other factors.
    """
    
    def __init__(self, system_prompt: str = None, model: str = "gpt-4"):
        # Load default prompt if none provided
        if system_prompt is None:
            system_prompt = load_prompt("foodie_base.md") + DISCLAIMER
        
        super().__init__("Foodie Agent", system_prompt, model)
        
        # Add tools for the agent
        self._setup_tools()
        
    def _setup_tools(self):
        """Set up the tools for this agent."""
        
        # Tool to search for restaurants based on criteria
        search_restaurants_tool = FunctionTool(
            func=self._search_restaurants,
            name="search_restaurants",
            description="Search for restaurants based on cuisine, location, and price range"
        )
        search_restaurants_tool.parameters = {
            "cuisine": {"type": "string", "description": "Type of cuisine"},
            "location": {"type": "string", "description": "Location or city name"},
            "price_range": {"type": "integer", "description": "Maximum price range (1-5, where 5 is most expensive)"}
        }
        self.add_tool(search_restaurants_tool)
        
        # Tool to get restaurant details
        get_restaurant_details_tool = FunctionTool(
            func=self._get_restaurant_details,
            name="get_restaurant_details",
            description="Get detailed information about a specific restaurant"
        )
        get_restaurant_details_tool.parameters = {
            "restaurant_name": {"type": "string", "description": "Name of the restaurant"}
        }
        self.add_tool(get_restaurant_details_tool)
        
        # Tool to get favorite restaurants
        get_favorite_restaurants_tool = FunctionTool(
            func=self._get_favorite_restaurants,
            name="get_favorite_restaurants",
            description="Get a list of favorite restaurants"
        )
        self.add_tool(get_favorite_restaurants_tool)
        
        # Tool to get kid-friendly restaurants
        get_kid_friendly_restaurants_tool = FunctionTool(
            func=self._get_kid_friendly_restaurants,
            name="get_kid_friendly_restaurants",
            description="Get kid-friendly restaurants"
        )
        get_kid_friendly_restaurants_tool.parameters = {
            "cuisine": {"type": "string", "description": "Type of cuisine (optional)"},
            "location": {"type": "string", "description": "Location or city name (optional)"}
        }
        self.add_tool(get_kid_friendly_restaurants_tool)
        
        # Tool to get travel time to restaurant
        get_restaurant_travel_time_tool = FunctionTool(
            func=self._get_restaurant_travel_time,
            name="get_restaurant_travel_time",
            description="Get estimated travel time to a restaurant from Sunnyvale"
        )
        get_restaurant_travel_time_tool.parameters = {
            "restaurant_name": {"type": "string", "description": "Name of the restaurant"}
        }
        self.add_tool(get_restaurant_travel_time_tool)
    
    async def process(self, user_input: str) -> Dict[str, Any]:
        """
        Process a user input related to restaurant recommendations.
        
        Args:
            user_input: The user's query about restaurants or dining
            
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
    
    async def _search_restaurants(self, cuisine: Optional[str] = None, 
                               location: Optional[str] = None, 
                               price_range: Optional[int] = None) -> List[Dict]:
        """Search for restaurants based on criteria."""
        filters = {}
        if cuisine:
            filters["cuisine"] = cuisine
        if location:
            filters["location"] = location
        if price_range:
            filters["price_range"] = price_range
            
        restaurants = get_restaurants(**filters)
        
        # Simplify the output for the agent
        simplified = []
        for restaurant in restaurants:
            simplified.append({
                "name": restaurant["name"],
                "cuisine": restaurant.get("cuisine", ""),
                "location": restaurant.get("location", ""),
                "address": restaurant.get("address", ""),
                "price_range": restaurant.get("price_range", "$"),
                "rating": restaurant.get("rating", 0),
                "kid_friendly": restaurant.get("kid_friendly", False),
                "signature_dishes": restaurant.get("signature_dishes", []),
                "favorite": restaurant.get("favorite", False)
            })
            
        return simplified
    
    async def _get_restaurant_details(self, restaurant_name: str) -> Dict:
        """Get detailed information about a specific restaurant."""
        restaurants = get_restaurants()
        
        for restaurant in restaurants:
            if restaurant["name"].lower() == restaurant_name.lower():
                return restaurant
                
        return {"error": f"Restaurant '{restaurant_name}' not found"}
    
    async def _get_favorite_restaurants(self) -> List[Dict]:
        """Get a list of favorite restaurants."""
        restaurants = get_restaurants()
        
        # Filter for favorite restaurants
        favorites = [r for r in restaurants if r.get("favorite", False)]
        
        return favorites
    
    async def _get_kid_friendly_restaurants(self, cuisine: Optional[str] = None, 
                                         location: Optional[str] = None) -> List[Dict]:
        """Get kid-friendly restaurants."""
        filters = {}
        if cuisine:
            filters["cuisine"] = cuisine
        if location:
            filters["location"] = location
            
        restaurants = get_restaurants(**filters)
        
        # Filter for kid-friendly restaurants
        kid_friendly = [r for r in restaurants if r.get("kid_friendly", False)]
        
        return kid_friendly
    
    async def _get_restaurant_travel_time(self, restaurant_name: str) -> Dict:
        """Get estimated travel time to a restaurant from Sunnyvale."""
        restaurants = get_restaurants()
        
        # Find the restaurant
        restaurant = None
        for r in restaurants:
            if r["name"].lower() == restaurant_name.lower():
                restaurant = r
                break
                
        if not restaurant:
            return {"error": f"Restaurant '{restaurant_name}' not found"}
            
        # Get the location of the restaurant
        location = restaurant.get("location", "").split(",")[0].strip()
        
        # Get travel time from Sunnyvale to the restaurant location
        travel_info = get_travel_time("Sunnyvale", location)
        
        return {
            "restaurant_name": restaurant_name,
            "location": location,
            "travel_time_minutes": travel_info.get("driving_minutes", 0),
            "distance_miles": travel_info.get("driving_distance_miles", 0),
            "notes": travel_info.get("traffic_notes", "")
        }


def build_foodie_agent(system_prompt: str = None, model: str = "gpt-4") -> FoodieAgent:
    """Build and return a FoodieAgent."""
    return FoodieAgent(system_prompt, model)