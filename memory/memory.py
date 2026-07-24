"""
High-level MemoryStore API that uses sqlite.py under the hood.
"""
from typing import List, Dict, Optional


class MemoryStore:
    def __init__(self, conn):
        self.conn = conn

    def add_memory(self, kind: str, content: str, metadata: Optional[Dict] = None):
        cur = self.conn.cursor()
        cur.execute('INSERT INTO memories (kind, content, metadata) VALUES (?, ?, ?)',
                    (kind, content, (str(metadata) if metadata else None)))
        self.conn.commit()
        return cur.lastrowid

    def retrieve_recent(self, limit: int = 10) -> List[Dict]:
        cur = self.conn.cursor()
        cur.execute('SELECT id, created_at, kind, content, metadata FROM memories ORDER BY id DESC LIMIT ?', (limit,))
        rows = cur.fetchall()
        return [dict(id=r[0], created_at=r[1], kind=r[2], content=r[3], metadata=r[4]) for r in rows]

    def search_similar(self, query: str, top_k: int = 5):
        # Placeholder until embeddings are available; simple substring search.
        cur = self.conn.cursor()
        cur.execute("SELECT id, content FROM memories WHERE content LIKE ? LIMIT ?", (f"%{query}%", top_k))
        return cur.fetchall()

    def purge_older_than(self, days: int):
        # Placeholder: requires timestamp arithmetic depending on SQLite build
        pass
