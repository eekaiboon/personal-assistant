#!/usr/bin/env python3
"""
Personal Assistant Multi-Agent System
Main script using OpenAI agents run_demo_loop with custom logging.
"""

import os
import sys
import asyncio
import argparse
import logging
from dotenv import load_dotenv

# Import OpenAI Agent SDK components
from agents import run_demo_loop, RunHooks

from assistant_agents.config import build_assistant_agents

# Load environment variables
load_dotenv()

# Configure basic logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Remove any existing handlers
for handler in logger.handlers:
    logger.removeHandler(handler)
    
# Suppress HTTP request logs from OpenAI and httpx
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Create colored formatter for different agents
class ColoredAgentFormatter(logging.Formatter):
    CYAN = "\033[96m"     # Coordinator
    MAGENTA = "\033[95m"  # Activity
    YELLOW = "\033[93m"   # Culinary
    GREEN = "\033[92m"    # Foodie
    BLUE = "\033[94m"     # Planner
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    def format(self, record):
        # Extract agent name from message if possible
        message = record.getMessage()
        module_name = record.name
        
        # Apply color coding based on agent name or message content
        if "[Activity Agent]" in message or "activity_agent" in module_name or "🎡" in message:
            return f"{self.MAGENTA}{message}{self.RESET}"
        elif "[Culinary Agent]" in message or "culinary_agent" in module_name or "🍲" in message:
            return f"{self.YELLOW}{message}{self.RESET}"
        elif "[Foodie Agent]" in message or "foodie_agent" in module_name or "🍴" in message:
            return f"{self.GREEN}{message}{self.RESET}"
        elif "[Planner Agent]" in message or "planner_agent" in module_name or "📑" in message:
            return f"{self.BLUE}{message}{self.RESET}"
        elif "[Coordinator]" in message or "coordinator" in module_name:
            return f"{self.CYAN}{message}{self.RESET}"
        else:
            return message

# Set up a console handler with the custom color formatter
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColoredAgentFormatter())
logger.addHandler(console_handler)

# Create a separate file handler for detailed logs
file_handler = logging.FileHandler('personal_assistant.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s'))
logger.addHandler(file_handler)

# Ensure propagation of logs from subagents
for name in ["assistant_agents", "assistant_agents.activity", "assistant_agents.culinary", 
             "assistant_agents.foodie", "assistant_agents.planner"]:
    sub_logger = logging.getLogger(name)
    sub_logger.setLevel(logging.INFO)
    # Ensure propagation is True (default) so logs go to root logger
    sub_logger.propagate = True

# Helper functions to create formatted output
def coordinator_msg(msg):
    return f"\n👨‍💻 [Coordinator] {msg}"

def activity_msg(msg):
    return f"\n🎡 [Activity Agent] {msg}"

def culinary_msg(msg):
    return f"\n🍲 [Culinary Agent] {msg}"

def foodie_msg(msg):
    return f"\n🍴 [Foodie Agent] {msg}"

def planner_msg(msg):
    return f"\n📑 [Planner Agent] {msg}"

# Configure Agent SDK callback for real-time console output
def configure_agent_callbacks():
    """Configure SDK agent callbacks for real-time console output."""
    # Custom callback handler for Agent SDK events
    class ConsoleCallbacks(RunHooks):
        def on_agent_start(self, agent, *args, **kwargs):
            agent_name = agent.name if hasattr(agent, 'name') else str(agent)
            if "Activity" in agent_name:
                print(activity_msg(f"Processing request..."))
            elif "Culinary" in agent_name:
                print(culinary_msg(f"Processing request..."))
            elif "Foodie" in agent_name:
                print(foodie_msg(f"Processing request..."))
            elif "Planner" in agent_name:
                print(planner_msg(f"Creating comprehensive plan..."))
            elif "Coordinator" in agent_name:
                print(coordinator_msg(f"Analyzing request..."))
        
        def on_agent_end(self, agent, *args, **kwargs):
            agent_name = agent.name if hasattr(agent, 'name') else str(agent)
            if "Activity" in agent_name:
                print(activity_msg("Completed analysis and recommendations"))
            elif "Culinary" in agent_name:
                print(culinary_msg("Completed analysis and recommendations"))
            elif "Foodie" in agent_name:
                print(foodie_msg("Completed restaurant recommendations"))
            elif "Planner" in agent_name:
                print(planner_msg("Completed comprehensive plan"))
            elif "Coordinator" in agent_name:
                print(coordinator_msg(f"Completed processing request"))
        
        def on_tool_start(self, agent, tool_name, *args, **kwargs):
            agent_name = agent.name if hasattr(agent, 'name') else str(agent)
            if "Activity" in agent_name:
                print(activity_msg(f"Using tool: {tool_name}"))
            elif "Culinary" in agent_name:
                print(culinary_msg(f"Using tool: {tool_name}"))
            elif "Foodie" in agent_name:
                print(foodie_msg(f"Using tool: {tool_name}"))
            elif "Planner" in agent_name:
                print(planner_msg(f"Using tool: {tool_name}"))
            elif "Coordinator" in agent_name:
                print(coordinator_msg(f"Using tool: {tool_name}"))
        
        def on_tool_end(self, agent, tool_name, *args, **kwargs):
            agent_name = agent.name if hasattr(agent, 'name') else str(agent)
            if "Activity" in agent_name:
                print(activity_msg(f"Completed tool: {tool_name}"))
            elif "Culinary" in agent_name:
                print(culinary_msg(f"Completed tool: {tool_name}"))
            elif "Foodie" in agent_name:
                print(foodie_msg(f"Completed tool: {tool_name}"))
            elif "Planner" in agent_name:
                print(planner_msg(f"Completed tool: {tool_name}"))
            elif "Coordinator" in agent_name:
                print(coordinator_msg(f"Completed tool: {tool_name}"))
    
    # Return the callback instance for use with run_demo_loop
    return ConsoleCallbacks()

# Check if OpenAI API key is set
if not os.environ.get("OPENAI_API_KEY"):
    logger.error(
        "OPENAI_API_KEY environment variable not set. "
        "Please set it before running the assistant."
    )
    sys.exit(1)

async def main() -> None:
    """Run the personal assistant using OpenAI agents run_demo_loop."""
    print("\nPersonal Assistant Multi-Agent System")
    print("====================================")
    print("Type your questions or requests. Type 'exit', 'quit', or Ctrl-D to end the session.\n")
    
    # Build and configure agents
    bundle = build_assistant_agents()
    head_coordinator = bundle.head_coordinator
    
    # Configure callback system
    hooks = configure_agent_callbacks()
    
    # Use direct Runner approach
    from agents import run_demo_loop
    
    # Ensure agent is built before using it
    if head_coordinator.agent is None:
        head_coordinator.build_agent()
        
    # Run the interactive demo loop with the agent directly
    await run_demo_loop(
        agent=head_coordinator.agent,
        stream=True
    )

async def run_with_query(query: str) -> None:
    """Run the assistant with a specific query."""
    # Build and configure agents
    bundle = build_assistant_agents()
    head_coordinator = bundle.head_coordinator
    
    # Configure callback system
    hooks = configure_agent_callbacks()
    
    print("\nPersonal Assistant Multi-Agent System")
    print("====================================")
    print(f"Processing query: {query}\n")
    
    try:
        # Use a direct approach with the Runner module
        from agents import Runner
        
        # Ensure agent is built before using it
        if head_coordinator.agent is None:
            head_coordinator.build_agent()
            
        # Run the coordinator agent directly
        result = await Runner.run(
            starting_agent=head_coordinator.agent,
            input=query,
            max_turns=20,
            hooks=hooks
        )
        
        # Print the final result with a clear delineation
        print("\n" + "="*50)
        print("\nFinal Answer:")
        print(f"\n{result.final_output}")
        print("\n" + "="*50 + "\n")
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        print("\nI'm sorry, I encountered an error processing your request.")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Personal Assistant Multi-Agent System')
    parser.add_argument('--query', '-q', type=str, help='Query to process (if not specified, runs in interactive mode)')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    
    if args.query:
        # Run with specific query
        asyncio.run(run_with_query(args.query))
    else:
        # Run in interactive mode
        asyncio.run(main())