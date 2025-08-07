"""
Error handling utilities for the Personal Assistant.
"""

import logging
import sys
import traceback
import os
import functools
import asyncio
from typing import Optional, Dict, Any, Callable, TypeVar, ParamSpec

# Use logger configured by event_hooks.py
logger = logging.getLogger(__name__)

# Type definitions for better type hints
P = ParamSpec('P')
R = TypeVar('R')


class AssistantError(Exception):
    """Base exception class for all assistant-related errors."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)


class SessionError(AssistantError):
    """Exception raised for session-related errors."""
    pass


class DatabaseError(AssistantError):
    """Exception raised for database-related errors."""
    pass


class AgentError(AssistantError):
    """Exception raised for agent-related errors."""
    pass


class ConfigurationError(AssistantError):
    """Exception raised for configuration-related errors."""
    pass


def format_error(e: Exception) -> Dict[str, Any]:
    """
    Format an exception into a structured error response.
    
    Args:
        e: The exception to format
        
    Returns:
        Dictionary containing error information
    """
    # Get error type
    error_type = type(e).__name__
    
    # Get error message
    error_message = str(e)
    
    # Get original error if it's our custom error class
    original_error = None
    if isinstance(e, AssistantError) and e.original_error:
        original_error = str(e.original_error)
    
    # Create error response
    error_response = {
        "error": True,
        "error_type": error_type,
        "message": error_message
    }
    
    if original_error:
        error_response["original_error"] = original_error
    
    return error_response


def log_error(e: Exception, context: str = "") -> None:
    """
    Log an exception with context information.
    
    Args:
        e: The exception to log
        context: Optional context string describing where the error occurred
    """
    if context:
        logger.error(f"Error in {context}: {str(e)}")
    else:
        logger.error(f"Error: {str(e)}")
        
    # Log traceback for debugging
    if logger.level <= logging.DEBUG:
        logger.debug("".join(traceback.format_exception(None, e, e.__traceback__)))


def handle_error(func: Callable[P, R]) -> Callable[P, R]:
    """
    Decorator for handling errors in async functions.
    
    Args:
        func: The async function to wrap with error handling
        
    Returns:
        Wrapped function with error handling
    """
    
    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await func(*args, **kwargs)
        except AssistantError as e:
            # Log our known error types
            log_error(e, func.__name__)
            raise
        except Exception as e:
            # Wrap unknown errors in our base exception
            wrapped_error = AssistantError(f"Unexpected error in {func.__name__}", e)
            log_error(wrapped_error, func.__name__)
            raise wrapped_error
    
    return wrapper


def check_environment() -> None:
    """
    Check that required environment variables are set.
    
    Raises:
        ConfigurationError: If any required environment variables are missing
    """
    
    required_vars = ["OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )