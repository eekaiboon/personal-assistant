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
from agents import run_demo_loop

from assistant_agents.config import build_assistant_agents
from assistant_agents.event_hooks import agent_hooks, setup_logging
from assistant_agents.coordinator import run_coordinator_agent

# Load environment variables
load_dotenv()

# Set up centralized logging
logger = setup_logging()

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
    
    # Run_demo_loop is imported at the top of the file
    
    # Run the interactive demo loop with the head coordinator agent and our custom hooks
    await run_demo_loop(
        agent=head_coordinator,
        stream=True,
        hooks=agent_hooks  # Pass our custom hooks to get proper logging
    )
    
    # Note: The OpenAI SDK doesn't support passing a stream_handler to run_demo_loop
    # We'll need to implement our own event handling if needed

async def run_with_query(query: str) -> None:
    """Run the assistant with a specific query."""
    # Build and configure agents
    bundle = build_assistant_agents()
    head_coordinator = bundle.head_coordinator
    
    print("\nPersonal Assistant")
    print(f"Query: {query}\n")
    
    try:
        # Run the coordinator agent directly with our hooks
        result = await run_coordinator_agent(query, head_coordinator, event_handler=True)
        
        # Print the final result with a clear delineation
        print("\n" + "="*50)
        print("\nFinal Answer:")
        print(f"\n{result.get('content', 'No response content available')}")
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