#!/usr/bin/env python3
"""
Personal Assistant Multi-Agent System

This script provides an interactive personal assistant that uses a multi-agent system
built on the OpenAI Agent SDK to answer questions, provide information, and help with
various tasks. The assistant maintains conversation history across sessions.

Features:
- Hub-and-spoke multi-agent architecture
- Session management for conversation persistence
- Interactive and single-query modes
- Streaming responses with real-time feedback
- Error handling and recovery
- Configurable through command-line arguments

Usage:
    # Run in interactive mode
    python main.py
    
    # Run with a single query
    python main.py --query "Help me plan a day trip"
    
    # Run with session management
    python main.py --session-id "my_session"
    
    # List all available sessions
    python main.py --list-sessions
"""

# Standard library imports
import os
import sys
import asyncio
import json
import logging
from typing import Optional, Any, Dict, List

# Third-party imports
from dotenv import load_dotenv

# OpenAI Agent SDK imports
from agents import Runner, ItemHelpers
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent, RunItemStreamEvent
from openai.types.responses import ResponseTextDeltaEvent

# Personal Assistant module imports
from assistant_agents.config import build_assistant_agents
from assistant_agents.event_hooks import agent_hooks, setup_logging
from assistant_agents.coordinator import run_coordinator_agent
from assistant_agents.memory import AssistantSession
from assistant_agents.cli import parse_arguments, get_session_config, display_welcome_message
from assistant_agents.errors import (
    handle_error, log_error, AssistantError, SessionError, 
    ConfigurationError, check_environment
)

# Load environment variables
load_dotenv()

# Set up centralized logging
logger = setup_logging()


# ============================================================================
# CORE INTERACTION FUNCTIONALITY
# ============================================================================

async def interactive_loop(session: AssistantSession, agent, input_items=None) -> None:
    """
    Run the interactive conversation loop.
    
    Args:
        session: Session for storing conversation history
        agent: Initial agent to use
        input_items: Optional initial input items
    """
    if input_items is None:
        input_items = []
        
    # Current state tracking
    current_agent = agent
    
    # Main interaction loop
    while True:
        try:
            # User input via input() function
            user_input = input(" > ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        
        # Handle special commands
        user_input_lower = user_input.strip().lower()
        if user_input_lower in {"exit", "quit"}:
            break
        if not user_input:
            continue
            
        # Handle session management commands
        if user_input_lower == "/clear":
            await session.clear_session()
            input_items = []
            print("\nSession cleared.\n")
            continue
        
        # Process user input through agent
        current_agent = await process_user_input(
            user_input=user_input,
            session=session,
            current_agent=current_agent
        )


@handle_error
async def process_user_input(user_input: str, session: AssistantSession, current_agent) -> Any:
    """
    Process a single user input through the agent system.
    
    Args:
        user_input: User's input text
        session: Session for storing conversation
        current_agent: Current agent to use
        
    Returns:
        Updated current agent
    """
    try:
        # Add user input to session
        user_item = {"role": "user", "content": user_input}
        await session.add_items([user_item])
        
        # Get all items from session
        input_items = await session.get_items()
        
        # Run the agent with hooks enabled and session
        # When using session, we should pass the user input as a string, not the full history
        result = Runner.run_streamed(
            current_agent, 
            input=user_input,
            hooks=agent_hooks,
            session=session.session
        )
        
        # Process streaming output
        await process_streaming_output(result)
        
        # Add spacing for readability
        print("\n")
        
        # Return updated agent
        return result.last_agent
    
    except Exception as e:
        # Display error to user
        print(f"\nI encountered an issue processing your request: {str(e)}\n")
        
        # Log error but continue execution - don't crash on user input errors
        log_error(e, "process_user_input")
        
        # Return same agent on error
        return current_agent


async def process_streaming_output(result) -> None:
    """
    Process streaming output from the agent.
    
    Args:
        result: StreamResult from the Runner
        
    This function handles different types of streaming events:
    - Text responses from the agent (token by token)
    - Tool call results
    
    Note: We ignore message_output_created events since the token stream
    already gives us the complete response with typing effect.
    """
    full_content = ""
    plan_content = None
    has_direct_response = False
    
    try:
        async for event in result.stream_events():
            # Handle direct agent responses (token-by-token)
            if isinstance(event, RawResponsesStreamEvent) and isinstance(event.data, ResponseTextDeltaEvent):
                # This is the token-by-token streaming text from the agent
                sys.stdout.write(event.data.delta)
                sys.stdout.flush()
                full_content += event.data.delta
                has_direct_response = True
            
            # Handle tool call results
            elif isinstance(event, RunItemStreamEvent) and hasattr(event, 'content'):
                try:
                    tool_result = json.loads(event.content)
                    if isinstance(tool_result, dict) and "content" in tool_result:
                        plan_content = tool_result["content"]
                except json.JSONDecodeError:
                    logger.debug(f"Could not parse tool result as JSON: {event.content[:100]}...")
                except Exception as e:
                    logger.debug(f"Error processing tool result: {str(e)}")
                    
            # Ignore message_output_created events
            # We already get the full response from token-by-token events
    except Exception as e:
        logger.error(f"Error processing streaming output: {str(e)}")
        # Display a user-friendly error message
        sys.stdout.write("\n[Error processing response]\n")
        sys.stdout.flush()
    
    # If no direct response but we have plan content, show it
    if not has_direct_response and plan_content:
        print("\n" + plan_content)


# ============================================================================
# MAIN PROGRAM FLOW
# ============================================================================

@handle_error
async def main() -> None:
    """
    Main entry point for the personal assistant.
    Handles command-line arguments and runs the appropriate mode.
    """
    try:
        # Check environment configuration
        check_environment()
    except ConfigurationError as e:
        logger.error(str(e))
        sys.exit(1)
    
    # Parse command-line arguments
    args = parse_arguments()
    
    # Handle listing sessions
    if args.list_sessions:
        await display_session_list(args.db_path)
        return
    
    # Get session configuration from arguments
    session_id, db_path, clear_session = get_session_config(args)
    
    # Create session
    session = AssistantSession(session_id, db_path)
    
    # Clear session if requested
    if clear_session:
        await session.clear_session()
        logger.info(f"Cleared session: {session_id}")
    
    # Get current item count
    item_count = await session.get_item_count()
    
    # Build and configure agents
    bundle = build_assistant_agents()
    head_coordinator = bundle.head_coordinator
    
    if args.query:
        # Run single-query mode
        await run_single_query(
            query=args.query,
            session=session,
            agent=head_coordinator,
            item_count=item_count
        )
    else:
        # Run interactive mode
        display_welcome_message(session_id, item_count, db_path)
        
        # Initialize from session
        input_items = await session.get_items() if item_count > 0 else []
        
        # Start interactive loop
        await interactive_loop(session, head_coordinator, input_items)


# ============================================================================
# EXECUTION MODES
# ============================================================================

@handle_error
async def run_single_query(query: str, session: AssistantSession, agent, item_count: int) -> None:
    """
    Run the assistant with a single query.
    
    Args:
        query: User's query
        session: Session instance
        agent: Agent to use
        item_count: Number of items in the session
    """
    # Log header information
    logger.info("\nPersonal Assistant")
    logger.info(f"Session: {session.session_id} ({item_count} messages)")
    logger.info(f"Query: {query}\n")
    
    try:
        # Add user query to session
        await session.add_items([{"role": "user", "content": query}])
        
        # Run the coordinator agent directly with our hooks and session
        result = await run_coordinator_agent(
            query, 
            agent, 
            event_handler=True,
            session=session.session
        )
        
        # Log the final result
        logger.info("\n" + "="*50)
        logger.info("\nFinal Answer:")
        logger.info(f"\n{result.get('content', 'No response content available')}")
        logger.info("\n" + "="*50 + "\n")
    
    except AssistantError as e:
        # For our custom errors, display a friendlier message
        logger.error("\nI'm sorry, I encountered an error processing your request.")
        logger.error(f"Details: {e.message}")
    
    except Exception as e:
        # For unexpected errors, log and display a generic message
        log_error(e, "run_single_query")
        logger.error("\nI'm sorry, I encountered an unexpected error processing your request.")




# ============================================================================
# SESSION MANAGEMENT UTILITIES
# ============================================================================

@handle_error
async def display_session_list(db_path: str) -> None:
    """
    Display a formatted list of all available sessions.
    
    Args:
        db_path: Path to the session database
    """
    try:
        if not os.path.exists(db_path):
            logger.info(f"No session database found at {db_path}")
            return
            
        sessions = await AssistantSession.list_all_sessions(db_path)
        
        if not sessions:
            logger.info(f"No sessions found in {db_path}")
            return
            
        logger.info(f"\nSessions in {db_path}:")
        for session in sessions:
            session_id = session.get("session_id", "Unknown")
            if "message_count" in session:
                logger.info(f"  - {session_id}: {session['message_count']} messages")
            else:
                logger.error(f"  - {session_id}: Error retrieving message count: {session.get('error', 'Unknown error')}")
    
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        raise SessionError("Failed to list sessions", e)


if __name__ == "__main__":
    asyncio.run(main())