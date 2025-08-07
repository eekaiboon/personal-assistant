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
import json
from dotenv import load_dotenv

# Import OpenAI Agent SDK components
from agents import Runner
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent, RunItemStreamEvent
from agents import ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent

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
    """Run the personal assistant using a custom interactive loop with hooks."""
    # Welcome message
    logger.info("\nPersonal Assistant Multi-Agent System")
    logger.info("====================================")
    logger.info("Type your questions or requests. Type 'exit', 'quit', or Ctrl-D to end the session.\n")
    
    # Build and configure agents
    bundle = build_assistant_agents()
    head_coordinator = bundle.head_coordinator
    
    # Interactive loop with hooks
    input_items = []
    current_agent = head_coordinator
    
    # Track the most recent plan for display
    recent_plan_content = None
    
    while True:
        try:
            # User input via input() function
            user_input = input(" > ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        
        if user_input.strip().lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue
        
        input_items.append({"role": "user", "content": user_input})
        
        # Run the agent with hooks enabled
        result = Runner.run_streamed(
            current_agent, 
            input=input_items,
            hooks=agent_hooks
        )
        
        # Process stream events
        full_content = ""
        plan_content = None
        has_direct_response = False
        
        # Process the stream of events from the agent
        async for event in result.stream_events():
            # Handle direct agent responses (text responses from the agent)
            if isinstance(event, RawResponsesStreamEvent):
                if isinstance(event.data, ResponseTextDeltaEvent):
                    # This is the token-by-token streaming text from the agent
                    sys.stdout.write(event.data.delta)
                    sys.stdout.flush()
                    full_content += event.data.delta
                    has_direct_response = True
            # Handle message output events (final responses) from the agent
            elif isinstance(event, RunItemStreamEvent) and event.name == "message_output_created":
                # Use the ItemHelpers class from the OpenAI Agent SDK to extract text properly
                if hasattr(event, 'item'):
                    # Get the text content using the SDK's helper method
                    message_text = ItemHelpers.text_message_output(event.item)
                    if message_text:
                        # Display the message text to the user
                        sys.stdout.write(message_text)
                        sys.stdout.flush()
                        full_content = message_text  # Replace any partial content
                        has_direct_response = True
            # Handle other RunItemStreamEvent events
            elif isinstance(event, RunItemStreamEvent):
                # Try to extract content from tool responses
                try:
                    if hasattr(event, 'content'):
                        tool_result = json.loads(event.content)
                        if isinstance(tool_result, dict) and "content" in tool_result:
                            plan_content = tool_result["content"]
                except Exception:
                    pass
        
        # If no direct response but we have plan content, show it
        if not has_direct_response and plan_content:
            print("\n" + plan_content)
        
        # Add newlines for readability
        print("\n")
        
        # Update state for next iteration
        current_agent = result.last_agent
        input_items = result.to_input_list()

async def run_with_query(query: str) -> None:
    """Run the assistant with a specific query."""
    # Build and configure agents
    bundle = build_assistant_agents()
    head_coordinator = bundle.head_coordinator
    
    # Log header information
    logger.info("\nPersonal Assistant")
    logger.info(f"Query: {query}\n")
    
    try:
        # Run the coordinator agent directly with our hooks
        result = await run_coordinator_agent(query, head_coordinator, event_handler=True)
        
        # Log the final result
        logger.info("\n" + "="*50)
        logger.info("\nFinal Answer:")
        logger.info(f"\n{result.get('content', 'No response content available')}")
        logger.info("\n" + "="*50 + "\n")
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        logger.error("\nI'm sorry, I encountered an error processing your request.")

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