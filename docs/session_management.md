# Session Management

This document provides an overview of the session management system in the Personal Assistant Multi-Agent System, which allows the assistant to maintain conversation history across multiple interactions.

## Overview

The session management system allows the assistant to remember previous conversations, enabling more natural multi-turn interactions. Sessions can be either in-memory (temporary) or persistent (stored in a SQLite database).

## Key Features

- **Persistent Memory**: Conversations are stored and can be recalled across multiple runs
- **Session Identification**: Each conversation can have a unique session ID
- **Session Listing**: View all available sessions and their message counts
- **Session Clearing**: Clear a session's history to start fresh
- **Memory Operations**: Add, retrieve, and remove conversation items

## Architecture

The session management system consists of:

1. **AssistantSession Class**: A wrapper around the OpenAI Agent SDK's SQLiteSession class
2. **DatabaseHelper Class**: Utilities for direct database operations
3. **CLI Module**: Command-line interface for session management
4. **Error Handling**: Robust error handling for session operations

## Usage

### Command-line Options

The assistant supports various command-line options for session management:

```bash
# Use a specific session ID
python main.py --session-id "my_session"

# Use in-memory session (no persistence)
python main.py --in-memory

# Clear a session before starting
python main.py --session-id "my_session" --clear-session

# List all available sessions
python main.py --list-sessions

# Specify a custom database path
python main.py --db-path "custom_sessions.db"
```

### Interactive Commands

While in interactive mode, you can use these special commands:

- `/clear`: Clear the current session history

### Session Creation

Sessions are automatically created with a timestamp-based ID if not specified:

```python
# Default session creation (timestamp-based ID)
session = AssistantSession("session_20250807_123045")

# Persistent session with custom ID
session = AssistantSession("work_planning", "conversation_history.db")

# In-memory session (temporary)
session = AssistantSession("quick_session", None)
```

### Session Operations

The `AssistantSession` class provides these operations:

```python
# Get all items in a session
items = await session.get_items()

# Add new items to a session
await session.add_items([
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!"}
])

# Get the number of items in a session
count = await session.get_item_count()

# Remove and return the most recent item
last_item = await session.pop_item()

# Clear all items from a session
await session.clear_session()
```

### Session Database Schema

The SQLite database schema supports multiple table structures for compatibility:

1. **Modern Schema** (OpenAI Agent SDK 0.1.11+):
   - `agent_sessions`: Stores session metadata
   - `agent_messages`: Stores individual messages linked to sessions

2. **Legacy Schema**:
   - `items`: Stores messages with session_id field
   - `sessions`: Stores session metadata

The system automatically detects and works with both schema types.

## Implementation Details

### Session Initialization

```python
session_id, db_path, clear_session = get_session_config(args)

# Create session
session = AssistantSession(session_id, db_path)

# Clear if requested
if clear_session:
    await session.clear_session()
```

### Session Integration with Agents

The OpenAI Agent SDK's Runner is used with the session parameter:

```python
result = Runner.run_streamed(
    agent, 
    input=input_items,
    hooks=agent_hooks,
    session=session.session  # Pass the underlying Session object
)
```

### Error Handling

The session system includes robust error handling:

1. **Database Access**: Graceful fallbacks when direct database access fails
2. **Session Listing**: Resilient to individual session errors
3. **Item Counts**: Alternative methods for counting when primary method fails

## Database Storage

Sessions are stored in a SQLite database with these characteristics:

1. **Default Location**: `conversation_history.db` in the project directory
2. **Custom Location**: Can be specified with `--db-path`
3. **In-Memory Option**: Temporary sessions with `--in-memory`

## Extending the Session System

To extend the session system:

1. **Custom Storage**: Create a class following the `Session` protocol
2. **Additional Commands**: Add more interactive commands in `main.py`
3. **Advanced Functionality**: Add session search, filtering, or tagging

## Security Considerations

1. **Data Storage**: Session data is stored in plaintext in SQLite
2. **No Encryption**: Database files are not encrypted by default
3. **Local Only**: Sessions are designed for local use only

## Troubleshooting

1. **Missing Sessions**: Verify the database path with `--list-sessions`
2. **Database Errors**: Check file permissions on the database file
3. **Session Confusion**: Use descriptive session IDs for better organization

## Viewing Conversation History

To inspect the conversation history stored in the database:

```bash
# Install sqlite3 command-line tool if not already installed
# Most systems have it pre-installed

# Open the database
sqlite3 conversation_history.db

# List all tables to see the schema
.tables

# View conversation history from modern schema (OpenAI Agent SDK 0.1.11+)
SELECT s.session_id, m.message_data, m.created_at 
FROM agent_sessions s 
JOIN agent_messages m ON s.session_id = m.session_id 
ORDER BY s.session_id, m.created_at;

# View conversation history from legacy schema
SELECT session_id, data 
FROM items 
ORDER BY session_id, id;

# View specific session history
SELECT m.message_data, m.created_at 
FROM agent_sessions s 
JOIN agent_messages m ON s.session_id = m.session_id 
WHERE s.session_id = 'your_session_id' 
ORDER BY m.created_at;

# Exit SQLite
.exit
```

### Using DB Browser for SQLite (Recommended)

For a more user-friendly experience, use DB Browser for SQLite to explore the conversation history:

1. **Install DB Browser for SQLite**:
   - **macOS**: `brew install --cask db-browser-for-sqlite` or download from the [official website](https://sqlitebrowser.org/)
   - **Windows**: Download the installer from the [official website](https://sqlitebrowser.org/dl/)
   - **Linux**: Use your package manager (e.g., `sudo apt install sqlitebrowser`) or download from the website

2. **Open the database**:
   - Launch DB Browser for SQLite
   - Click "Open Database" and navigate to your `conversation_history.db` file
   - Click "Open"

3. **Browse conversation history**:
   - Click on the "Browse Data" tab
   - Select the "agent_messages" table from the dropdown
   - You'll see all messages across all sessions
   - Use the filter button (funnel icon) to filter by session_id

4. **Examine message content**:
   - Each row represents one message
   - The `message_data` column contains JSON with the conversation content
   - Double-click on a cell to see the full content

5. **Run custom queries**:
   - Click on the "Execute SQL" tab
   - Enter SQL queries (like those shown above)
   - Click the play button to run the query
   - Results display in a grid format

This visual interface makes it much easier to explore and understand the conversation history compared to the command line.