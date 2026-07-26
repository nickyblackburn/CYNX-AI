"""
SQLite helpers: connect and ensure schema.
"""
import sqlite3
from pathlib import Path
from typing import Optional


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    if not db_path:
        root = Path(__file__).resolve().parents[1]
        db_path = str(root / 'database' / 'cyn.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    # memories table (legacy)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        kind TEXT,
        content TEXT,
        metadata TEXT
    )
    ''')
    # conversations
    cur.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT,
        message TEXT,
        ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    # tool calls
    cur.execute('''
    CREATE TABLE IF NOT EXISTS tool_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        args TEXT,
        result TEXT,
        ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    # user_memories table (long-term memory system)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user_memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        category TEXT NOT NULL,
        content TEXT NOT NULL,
        importance INTEGER DEFAULT 5,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, category, content)
    )
    ''')
    conn.commit()
