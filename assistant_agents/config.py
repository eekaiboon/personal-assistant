"""
Configuration module for the Personal Assistant Multi-Agent System.
This module handles the creation and bundling of all agents using OpenAI Agent SDK.
"""

from dataclasses import dataclass
import os
import asyncio
import logging
from dotenv import load_dotenv
from typing import Dict, Any

# Import OpenAI Agent SDK components
from agents import Agent, ModelSettings, Runner

# Import utility functions
from utils import configure_openai_client

# Import our agent builders
from assistant_agents.activity import build_activity_agent
from assistant_agents.culinary import build_culinary_agent
from assistant_agents.foodie import build_foodie_agent
from assistant_agents.planner import build_planner_agent
from assistant_agents.coordinator import build_coordinator_agent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class AssistantAgentBundle:
    """Bundle containing all agent instances."""
    head_coordinator: object
    activity: object
    culinary: object
    foodie: object
    planner: object


def build_assistant_agents() -> AssistantAgentBundle:
    """
    Build and configure all agents for the personal assistant using the OpenAI Agent SDK.
    
    Returns:
        AssistantAgentBundle: Bundle containing all configured agents
    """
    # Configure OpenAI client (handles API keys, alternative endpoints, etc.)
    configure_openai_client()
        
    # Get model configuration from environment
    model = os.environ.get("MODEL", "gpt-4")
    logger.info(f"Using model: {model}")
    
    logger.info("Building assistant agents with OpenAI Agent SDK...")
    
    # Build specialist agents
    activity_agent = build_activity_agent(model=model)
    culinary_agent = build_culinary_agent(model=model)
    foodie_agent = build_foodie_agent(model=model)
    planner_agent = build_planner_agent(model=model)
    
    # Build head coordinator agent with references to all specialists
    head_coordinator = build_coordinator_agent(
        activity_agent=activity_agent,
        culinary_agent=culinary_agent,
        foodie_agent=foodie_agent,
        planner_agent=planner_agent,
        model=model
    )
    
    # Return the complete bundle
    return AssistantAgentBundle(
        head_coordinator=head_coordinator,
        activity=activity_agent,
        culinary=culinary_agent,
        foodie=foodie_agent,
        planner=planner_agent
    )


async def run_assistant_with_query(query: str) -> dict:
    """
    Run the assistant with a specific query using the Agent SDK.
    
    Args:
        query: The user's query
        
    Returns:
        dict: The assistant's response
    """
    bundle = build_assistant_agents()
    
    logger.info(f"Processing query: {query}")
    try:
        # Use the Agent SDK Runner to execute the query
        response = await bundle.head_coordinator.process(query)
        logger.info("Query processing complete")
        return response
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return {"content": f"I apologize, but an error occurred while processing your request: {str(e)}", "agent": "System Error"}