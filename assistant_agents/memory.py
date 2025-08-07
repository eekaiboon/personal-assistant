"""
Memory management module for the Personal Assistant Multi-Agent System.
Handles session management and conversation history persistence.

This module provides a wrapper around the OpenAI Agent SDK's SQLiteSession
with enhanced functionality for session management, listing, and diagnostics.
"""

import os
import logging
import sqlite3
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Protocol, Union

# Import OpenAI Agent SDK session components
from agents.memory import SQLiteSession, Session

# Use logger configured by event_hooks.py
logger = logging.getLogger(__name__)

# Constants
DEFAULT_DB_PATH = "conversation_history.db"


class DatabaseHelper:
    """Helper class for direct database operations."""
    
    @staticmethod
    def connect_to_db(db_path: str) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
        """
        Create a connection to the SQLite database.
        
        Args:
            db_path: Path to the database file
            
        Returns:
            Tuple containing connection and cursor objects
            
        Raises:
            sqlite3.Error: If connection fails
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        return conn, cursor
    
    @staticmethod
    def get_table_names(cursor: sqlite3.Cursor) -> List[str]:
        """
        Get all table names from the database.
        
        Args:
            cursor: SQLite cursor
            
        Returns:
            List of table names
        """
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]
    
    @staticmethod
    def count_session_items(cursor: sqlite3.Cursor, tables: List[str], session_id: str) -> int:
        """
        Count items for a specific session using appropriate table schema.
        
        Args:
            cursor: SQLite cursor
            tables: Available tables in the database
            session_id: Session ID to count items for
            
        Returns:
            Number of items in the session
        """
        count = 0
        
        if 'agent_messages' in tables:
            cursor.execute(
                "SELECT COUNT(*) FROM agent_messages JOIN agent_sessions ON agent_messages.session_id = agent_sessions.id "
                "WHERE agent_sessions.session_id = ?", 
                (session_id,)
            )
            count = cursor.fetchone()[0]
        elif 'items' in tables:
            cursor.execute("SELECT COUNT(*) FROM items WHERE session_id = ?", (session_id,))
            count = cursor.fetchone()[0]
            
        return count
    
    @staticmethod
    def get_session_ids(cursor: sqlite3.Cursor, tables: List[str]) -> List[str]:
        """
        Get all session IDs using appropriate table schema.
        
        Args:
            cursor: SQLite cursor
            tables: Available tables in the database
            
        Returns:
            List of session IDs
        """
        session_ids = []
        
        if 'agent_sessions' in tables:
            cursor.execute("SELECT DISTINCT session_id FROM agent_sessions")
            session_ids = [row[0] for row in cursor.fetchall()]
        elif 'items' in tables:
            cursor.execute("SELECT DISTINCT session_id FROM items")
            session_ids = [row[0] for row in cursor.fetchall()]
        elif 'sessions' in tables:
            cursor.execute("SELECT DISTINCT id FROM sessions")
            session_ids = [row[0] for row in cursor.fetchall()]
            
        return session_ids


class AssistantSession:
    """
    Wrapper around the SQLiteSession class from the OpenAI Agents SDK.
    Provides additional helper methods for session management.
    """
    
    def __init__(self, session_id: str, db_path: Optional[str] = None):
        """
        Initialize a new assistant session.
        
        Args:
            session_id: Unique identifier for the session
            db_path: Path to the SQLite database (None for in-memory)
        """
        self.session_id = session_id
        self.db_path = db_path
        self._session = SQLiteSession(session_id, db_path)
        logger.info(f"Initialized session: {session_id}" + 
                    (f" (persistent: {db_path})" if db_path else " (in-memory)"))
    
    @property
    def session(self) -> Session:
        """Get the underlying Session object."""
        return self._session
    
    #
    # Session Item Management Methods
    #
    
    async def get_items(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get conversation history items.
        
        Args:
            limit: Maximum number of items to retrieve (None for all)
            
        Returns:
            List of conversation items
        """
        return await self._session.get_items(limit)
    
    async def add_items(self, items: List[Dict[str, Any]]) -> None:
        """
        Add items to the conversation history.
        
        Args:
            items: List of items to add
        """
        await self._session.add_items(items)
    
    async def pop_item(self) -> Dict[str, Any]:
        """
        Remove and return the most recent item.
        
        Returns:
            The most recent conversation item
        """
        return await self._session.pop_item()
    
    async def clear_session(self) -> None:
        """Clear all items from this session."""
        await self._session.clear_session()
        logger.info(f"Cleared session: {self.session_id}")
    
    async def get_item_count(self) -> int:
        """
        Get the number of items in the session.
        
        Returns:
            Number of conversation items
        """
        try:
            items = await self.get_items()
            return len(items)
        except Exception:
            # Fallback method using direct database access if the SDK method fails
            if not self.db_path:  # In-memory sessions can't use SQLite fallback
                return 0
            
            try:
                conn, cursor = DatabaseHelper.connect_to_db(self.db_path)
                tables = DatabaseHelper.get_table_names(cursor)
                count = DatabaseHelper.count_session_items(cursor, tables, self.session_id)
                conn.close()
                return count
            except Exception as e:
                logger.error(f"Error counting session items: {str(e)}")
                return 0
    
    #
    # Static Session Management Methods
    #
    
    @staticmethod
    async def list_sessions(db_path: str) -> List[str]:
        """
        List all session IDs in a database.
        
        Args:
            db_path: Path to the SQLite database
            
        Returns:
            List of session IDs
        """
        if not os.path.exists(db_path):
            return []
        
        try:
            conn, cursor = DatabaseHelper.connect_to_db(db_path)
            tables = DatabaseHelper.get_table_names(cursor)
            session_ids = DatabaseHelper.get_session_ids(cursor, tables)
            conn.close()
            return session_ids
        except Exception as e:
            logger.error(f"Error listing sessions: {str(e)}")
            return []
            
    @staticmethod
    async def list_all_sessions(db_path: str) -> List[Dict[str, Any]]:
        """
        List all sessions in the database with their message counts.
        
        Args:
            db_path: Path to the session database
            
        Returns:
            List of dictionaries containing session_id and message_count
        """
        results = []
        
        try:
            if not os.path.exists(db_path):
                return results
                
            session_ids = await AssistantSession.list_sessions(db_path)
            
            if not session_ids:
                return results
                
            for session_id in session_ids:
                try:
                    # Create temporary session to get message count
                    temp_session = AssistantSession(session_id, db_path)
                    count = await temp_session.get_item_count()
                    results.append({
                        "session_id": session_id,
                        "message_count": count
                    })
                except Exception as e:
                    # Add session with error information
                    results.append({
                        "session_id": session_id,
                        "error": str(e)
                    })
            
            return results
        
        except Exception as e:
            logger.error(f"Error listing sessions: {str(e)}")
            # Re-raise as a dictionary with error information
            raise Exception(f"Failed to list sessions: {str(e)}")
    
    @staticmethod
    async def create_session(session_id: str, db_path: Optional[str] = None, 
                           clear_existing: bool = False) -> 'AssistantSession':
        """
        Create a new session with the given ID.
        
        Args:
            session_id: Session ID to create
            db_path: Optional database path for persistent sessions
            clear_existing: Whether to clear the session if it exists
            
        Returns:
            AssistantSession instance
        """
        session = AssistantSession(session_id, db_path)
        if clear_existing:
            await session.clear_session()
        return session
    
    def __str__(self) -> str:
        """String representation of the session."""
        return f"AssistantSession(id={self.session_id}, db={self.db_path or 'in-memory'})"