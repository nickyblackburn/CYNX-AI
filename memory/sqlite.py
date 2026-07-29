"""
SQLite database manager for CYN-X.

Handles:
- database connection
- schema creation
- memory storage tables
- conversation storage
- performance indexes
"""


import sqlite3

from pathlib import Path







# ---------------------------------
# Database Connection
# ---------------------------------


def connect(
    db_path=None
):


    if not db_path:


        root = Path(__file__).resolve().parents[1]


        database_dir = (

            root

            /

            "database"

        )


        database_dir.mkdir(

            parents=True,

            exist_ok=True

        )


        db_path = (

            database_dir

            /

            "cyn.db"

        )



    db_path = str(db_path)



    print(
        "DATABASE USING:",
        db_path
    )



    conn = sqlite3.connect(

        db_path,

        check_same_thread=False

    )



    ensure_schema(

        conn

    )


    return conn







# ---------------------------------
# Schema Setup
# ---------------------------------


def ensure_schema(
    conn
):


    cur = conn.cursor()





    # -----------------------------
    # Memories
    # -----------------------------


    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (

            id INTEGER PRIMARY KEY AUTOINCREMENT,


            user_id TEXT DEFAULT 'default',


            kind TEXT NOT NULL,


            content TEXT NOT NULL,


            importance INTEGER DEFAULT 5,


            tags TEXT DEFAULT '[]',


            metadata TEXT DEFAULT '{}',


            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,


            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
        """
    )

        # -----------------------------
        # Knowledge
        # -----------------------------

    cur.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                category TEXT DEFAULT 'general',

                title TEXT,

                content TEXT NOT NULL,

                importance INTEGER DEFAULT 5,

                tags TEXT DEFAULT '[]',

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

            )
            """
            )


    cur.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_knowledge_category

    ON knowledge(category)
    """
    )
    







    # -----------------------------
    # Conversations
    # -----------------------------


    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (

            id INTEGER PRIMARY KEY AUTOINCREMENT,


            user_id TEXT DEFAULT 'default',


            role TEXT NOT NULL,


            message TEXT NOT NULL,


            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
        """
    )







    # -----------------------------
    # Memory Indexes
    # -----------------------------


    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memories_user

        ON memories(user_id)
        """
    )



    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memories_importance

        ON memories(importance)
        """
    )







    # -----------------------------
    # Conversation Index
    # -----------------------------


    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_conversations_user

        ON conversations(user_id)
        """
    )






    conn.commit()






    # -----------------------------
    # Verify Database
    # -----------------------------


    cur.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        """
    )


    tables = cur.fetchall()


    print(
        "DATABASE TABLES:",
        tables
    )









# ---------------------------------
# Conversation Helper
# ---------------------------------


def save_conversation(
    conn,
    user_id,
    role,
    message
):

    print("LOADED CYN SQLITE MODULE")
    cur = conn.cursor()



    cur.execute(
        """
        INSERT INTO conversations
        (
            user_id,
            role,
            message
        )

        VALUES (?, ?, ?)

        """,

        (
            user_id,
            role,
            message
        )

    )



    conn.commit()



    return cur.lastrowid