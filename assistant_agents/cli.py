"""
Command-line interface utilities for the Personal Assistant Multi-Agent System.

This module provides command-line argument parsing and display functions for the
Personal Assistant Multi-Agent System. It handles session configuration, welcome messages,
and other CLI-related functionality.

Functions:
    parse_arguments: Parse command-line arguments for the assistant
    get_session_config: Process arguments to get session configuration
    display_welcome_message: Display a welcome message with session information
"""

import argparse
import logging
import datetime
from typing import Dict, Any, Optional, Tuple

# Use logger configured by event_hooks.py
logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for the personal assistant.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(description='Personal Assistant Multi-Agent System')
    
    # Basic functionality
    parser.add_argument('--query', '-q', type=str, 
                       help='Query to process (if not specified, runs in interactive mode)')
    
    # Session management arguments
    session_group = parser.add_argument_group('Session Management')
    session_group.add_argument('--session-id', '-s', type=str, 
                        help='Session ID to use (default: date-based session ID)')
    session_group.add_argument('--clear-session', action='store_true', 
                        help='Clear the session before starting')
    session_group.add_argument('--list-sessions', action='store_true', 
                        help='List all available sessions and exit')
    session_group.add_argument('--db-path', type=str, default='conversation_history.db',
                        help='Path to the session database file (default: conversation_history.db)')
    session_group.add_argument('--in-memory', action='store_true',
                        help='Use in-memory session (no persistence)')
    
    # Advanced options
    advanced_group = parser.add_argument_group('Advanced Options')
    advanced_group.add_argument('--model', type=str,
                        help='Override the model specified in .env')
    advanced_group.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    
    return parser.parse_args()


def get_session_config(args: argparse.Namespace) -> Tuple[str, Optional[str], bool]:
    """
    Process command-line arguments to get session configuration.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Tuple of (session_id, db_path, clear_session)
    """
    # Generate session ID if not provided
    session_id = args.session_id
    if session_id is None:
        # Create a date-based session ID
        now = datetime.datetime.now()
        session_id = f"session_{now.strftime('%Y%m%d_%H%M%S')}"
    
    # Determine database path
    db_path = None if args.in_memory else args.db_path
    
    return session_id, db_path, args.clear_session


def display_welcome_message(session_id: str, item_count: int, db_path: Optional[str]) -> None:
    """
    Display a welcome message with session information.
    
    Args:
        session_id: Current session ID
        item_count: Number of items in the session
        db_path: Database path (None for in-memory)
    """
    logger.info("\nPersonal Assistant Multi-Agent System")
    logger.info("====================================")
    logger.info(f"Session: {session_id} ({item_count} messages{' - persistent' if db_path else ''})")
    logger.info("Type your questions or requests. Type 'exit', 'quit', or Ctrl-D to end the session.")
    logger.info("Special commands: '/clear' to clear session history.\n")