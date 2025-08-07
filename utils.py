"""Shared utilities for the multi-agent personal assistant."""

from pathlib import Path
import json
import os
import logging
from openai import AsyncOpenAI
from agents import set_default_openai_client, set_default_openai_api

# ---------------------------------------------------------------------------
# Global disclaimer for all agents
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "DISCLAIMER: I am an AI language model. Information provided is for "
    "assistance purposes only. Please use your judgment when following "
    "recommendations, especially those related to children, health, or safety.\n\n"
)

# Configure logging
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT_DIR: Path = Path(__file__).resolve().parent  # repository root


def repo_path(rel: str | Path) -> Path:
    """Return an absolute Path inside the repository given a relative string."""
    return (ROOT_DIR / rel).resolve()


def mock_data_path(filename: str) -> Path:
    """Return path to a mock data file."""
    return repo_path(f"mock_data/{filename}")


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

PROMPTS_DIR: Path = repo_path("prompts")


def load_prompt(name: str, **subs) -> str:
    """Load a Markdown prompt template and substitute <PLACEHOLDERS>."""
    content = (PROMPTS_DIR / name).read_text()
    for key, val in subs.items():
        content = content.replace(f"<{key}>", str(val))
    return content


# ---------------------------------------------------------------------------
# Mock data loaders
# ---------------------------------------------------------------------------

def load_mock_data(filename: str) -> dict:
    """Load mock data from a JSON file."""
    file_path = mock_data_path(filename)
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except UnicodeDecodeError:
            # Fallback to latin-1 encoding if UTF-8 fails
            with open(file_path, "r", encoding="latin-1") as f:
                return json.load(f)
    return {}


def get_activities(**filters) -> list:
    """
    Get activities from mock data, filtered by provided parameters.
    
    Args:
        **filters: Keyword arguments to filter activities.
            age_min: Minimum age for the activity
            age_max: Maximum age for the activity
            indoor: Boolean indicating if indoor activity is preferred
            location: String to match in location field
            
    Returns:
        list: List of matching activities
    """
    activities = load_mock_data("activities.json").get("activities", [])
    
    # Apply filters
    if filters:
        filtered = []
        for activity in activities:
            match = True
            
            # Age filter - activity is appropriate if its min age is <= our min filter and its max age is >= our max filter
            if "age_min" in filters and activity.get("age_min", 0) > filters["age_min"]:
                match = False  # Activity minimum age is too high
            
            if "age_max" in filters and activity.get("age_max", 99) < filters["age_max"]:
                match = False  # Activity maximum age is too low
                
            # Indoor/outdoor filter
            if "indoor" in filters and activity.get("indoor") != filters["indoor"]:
                match = False
                
            # Location filter (partial match)
            if "location" in filters and filters["location"].lower() not in activity.get("location", "").lower():
                match = False
                
            if match:
                filtered.append(activity)
        
        return filtered
    
    return activities


def get_recipes(**filters) -> list:
    """
    Get recipes from mock data, filtered by provided parameters.
    
    Args:
        **filters: Keyword arguments to filter recipes.
            cuisine: Cuisine type
            meal_type: Type of meal (breakfast, lunch, dinner, etc.)
            max_prep_time: Maximum preparation time in minutes
            
    Returns:
        list: List of matching recipes
    """
    recipes = load_mock_data("recipes.json").get("recipes", [])
    
    # Apply filters
    if filters:
        filtered = []
        for recipe in recipes:
            match = True
            
            # Cuisine filter
            if "cuisine" in filters and filters["cuisine"].lower() not in recipe.get("cuisine", "").lower():
                match = False
                
            # Meal type filter
            if "meal_type" in filters and filters["meal_type"].lower() not in recipe.get("meal_type", "").lower():
                match = False
                
            # Max prep time filter
            if "max_prep_time" in filters and recipe.get("prep_time", 0) > filters["max_prep_time"]:
                match = False
                
            if match:
                filtered.append(recipe)
        
        return filtered
    
    return recipes


def get_restaurants(**filters) -> list:
    """
    Get restaurants from mock data, filtered by provided parameters.
    
    Args:
        **filters: Keyword arguments to filter restaurants.
            cuisine: Cuisine type
            location: Location name (partial match)
            price_range: Maximum price range (1-5)
            
    Returns:
        list: List of matching restaurants
    """
    restaurants = load_mock_data("restaurants.json").get("restaurants", [])
    
    # Apply filters
    if filters:
        filtered = []
        for restaurant in restaurants:
            match = True
            
            # Cuisine filter
            if "cuisine" in filters and filters["cuisine"].lower() not in restaurant.get("cuisine", "").lower():
                match = False
                
            # Location filter (partial match)
            if "location" in filters and filters["location"].lower() not in restaurant.get("location", "").lower():
                match = False
                
            # Price range filter
            if "price_range" in filters and len(restaurant.get("price_range", "$")) > filters["price_range"]:
                match = False
                
            if match:
                filtered.append(restaurant)
        
        return filtered
    
    return restaurants


def get_travel_time(origin: str, destination: str) -> dict:
    """
    Get estimated travel time between locations from mock data.
    
    Args:
        origin: Starting location name
        destination: Ending location name
        
    Returns:
        dict: Travel time information
    """
    locations = load_mock_data("locations.json")
    travel_times = locations.get("travel_times", [])
    
    # Try to find a match for the origin-destination pair
    for entry in travel_times:
        if (entry.get("origin").lower() == origin.lower() and 
            entry.get("destination").lower() == destination.lower()):
            return entry
    
    # If no exact match, return a default estimate
    return {
        "origin": origin,
        "destination": destination,
        "driving_minutes": 30,  # Default estimate
        "driving_distance_miles": 15,  # Default estimate
        "note": "Estimated time based on average travel speed."
    }


# ---------------------------------------------------------------------------
# OpenAI client configuration
# ---------------------------------------------------------------------------

def configure_openai_client():
    """
    Configure the OpenAI client based on environment variables.
    This supports both standard OpenAI API and alternative providers.
    
    Environment Variables:
    - OPENAI_API_KEY: API key (required)
    - OPENAI_ORG_ID: Organization ID (optional)
    - OPENAI_BASE_URL: Custom base URL for alternative providers (optional)
    - USE_CHAT_COMPLETIONS: Set to 'true' to use chat completions API (optional)
    
    Returns:
        AsyncOpenAI client instance
    """
    # Get environment variables
    api_key = os.environ.get("OPENAI_API_KEY")
    org_id = os.environ.get("OPENAI_ORG_ID")
    base_url = os.environ.get("OPENAI_BASE_URL")
    use_chat_completions = os.environ.get("USE_CHAT_COMPLETIONS", "").lower() in ("true", "1", "yes")
    
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable not set. "
            "Please set it before running the assistant."
        )
    
    # Create client with appropriate configuration
    client_kwargs = {
        "api_key": api_key
    }
    
    # Add optional parameters if provided
    if org_id:
        client_kwargs["organization"] = org_id
    
    if base_url:
        client_kwargs["base_url"] = base_url
        logger.info(f"Using custom API endpoint: {base_url}")
    
    # Create the OpenAI client
    client = AsyncOpenAI(**client_kwargs)
    
    # Set as default client for all agent calls
    # When using custom API endpoints, disable tracing to prevent auth errors
    if base_url:
        set_default_openai_client(client=client, use_for_tracing=False)
    else:
        set_default_openai_client(client=client)
    
    # Set API preference if specified
    if use_chat_completions:
        logger.info("Using Chat Completions API (alternative provider compatibility)")
        set_default_openai_api("chat_completions")
    
    return client


__all__ = [
    "ROOT_DIR",
    "repo_path",
    "mock_data_path",
    "load_prompt",
    "DISCLAIMER",
    "load_mock_data",
    "get_activities",
    "get_recipes",
    "get_restaurants",
    "get_travel_time",
    "configure_openai_client",
]