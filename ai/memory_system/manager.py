"""
MemoryManager: Stores and retrieves long-term user memories.
Scoped by user_id and categorized by memory type.
"""
import sqlite3
import logging
from typing import List, Dict, Optional
from datetime import datetime


logger = logging.getLogger("cynx.memory")


class MemoryManager:
    """Manages user-scoped long-term memories with importance scoring."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def remember(
        self,
        user_id: str,
        content: str,
        category: str = "general",
        importance: int = 5
    ) -> int:
        """
        Save a memory for a user.

        Args:
            user_id: User identifier
            content: Memory content
            category: Memory type (preference, project, goal, name, style)
            importance: 1-10 scale, higher = more important

        Returns:
            Memory ID if successful, None if duplicate
        """
        if not content or not content.strip():
            return None

        try:
            cur = self.conn.cursor()
            cur.execute(
                '''INSERT INTO user_memories
                   (user_id, category, content, importance, created_at, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))''',
                (user_id, category, content.strip(), max(1, min(10, importance)))
            )
            self.conn.commit()
            memory_id = cur.lastrowid
            logger.info(f"[MEMORY_SAVE] user_id={user_id} category={category} memory_id={memory_id}")
            return memory_id
        except sqlite3.IntegrityError:
            # Duplicate memory (same user, category, content)
            logger.debug(f"[MEMORY_SKIP] Duplicate memory for {user_id}: {content[:50]}")
            return None
        except Exception as e:
            logger.error(f"[MEMORY_ERROR] Failed to save: {e}")
            return None

    def recall(
        self,
        user_id: str,
        limit: int = 5,
        min_importance: int = 1,
        categories: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Retrieve top memories for a user.

        Args:
            user_id: User identifier
            limit: Max memories to return
            min_importance: Filter by minimum importance (1-10)
            categories: Filter by categories (None = all)

        Returns:
            List of memory dicts: {id, user_id, category, content, importance, created_at}
        """
        try:
            cur = self.conn.cursor()

            # Build query
            query = '''SELECT id, user_id, category, content, importance, created_at
                      FROM user_memories
                      WHERE user_id = ? AND importance >= ?'''
            params = [user_id, min_importance]

            if categories:
                placeholders = ','.join('?' * len(categories))
                query += f' AND category IN ({placeholders})'
                params.extend(categories)

            # Sort by importance (desc), then recency (desc)
            query += ' ORDER BY importance DESC, created_at DESC LIMIT ?'
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()

            memories = []
            for row in rows:
                memories.append({
                    'id': row[0],
                    'user_id': row[1],
                    'category': row[2],
                    'content': row[3],
                    'importance': row[4],
                    'created_at': row[5]
                })

            if memories:
                logger.info(f"[MEMORY_RECALL] user_id={user_id} recalled {len(memories)} memories")

            return memories
        except Exception as e:
            logger.error(f"[MEMORY_ERROR] Recall failed: {e}")
            return []

    def search(
        self,
        user_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search memories by keyword (substring match).

        Args:
            user_id: User identifier
            query: Search term
            limit: Max results

        Returns:
            List of matching memory dicts
        """
        try:
            cur = self.conn.cursor()
            cur.execute(
                '''SELECT id, user_id, category, content, importance, created_at
                   FROM user_memories
                   WHERE user_id = ? AND content LIKE ?
                   ORDER BY importance DESC LIMIT ?''',
                (user_id, f'%{query}%', limit)
            )
            rows = cur.fetchall()

            memories = []
            for row in rows:
                memories.append({
                    'id': row[0],
                    'user_id': row[1],
                    'category': row[2],
                    'content': row[3],
                    'importance': row[4],
                    'created_at': row[5]
                })

            return memories
        except Exception as e:
            logger.error(f"[MEMORY_ERROR] Search failed: {e}")
            return []

    def delete_memory(self, memory_id: int) -> bool:
        """
        Delete a specific memory.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found or error
        """
        try:
            cur = self.conn.cursor()
            cur.execute('DELETE FROM user_memories WHERE id = ?', (memory_id,))
            self.conn.commit()

            if cur.rowcount > 0:
                logger.info(f"[MEMORY_DELETE] Deleted memory_id={memory_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"[MEMORY_ERROR] Delete failed: {e}")
            return False

    def get_all_memories(self, user_id: str) -> List[Dict]:
        """
        Get ALL memories for a user (admin/debug).

        Args:
            user_id: User identifier

        Returns:
            All memory dicts for user, sorted by importance desc
        """
        try:
            cur = self.conn.cursor()
            cur.execute(
                '''SELECT id, user_id, category, content, importance, created_at
                   FROM user_memories
                   WHERE user_id = ?
                   ORDER BY importance DESC, created_at DESC''',
                (user_id,)
            )
            rows = cur.fetchall()

            memories = []
            for row in rows:
                memories.append({
                    'id': row[0],
                    'user_id': row[1],
                    'category': row[2],
                    'content': row[3],
                    'importance': row[4],
                    'created_at': row[5]
                })

            return memories
        except Exception as e:
            logger.error(f"[MEMORY_ERROR] Get all failed: {e}")
            return []

    def update_memory(
        self,
        memory_id: int,
        importance: Optional[int] = None,
        content: Optional[str] = None
    ) -> bool:
        """
        Update an existing memory.

        Args:
            memory_id: Memory ID to update
            importance: New importance (1-10)
            content: New content

        Returns:
            True if updated, False if not found or error
        """
        try:
            updates = []
            params = []

            if importance is not None:
                updates.append('importance = ?')
                params.append(max(1, min(10, importance)))

            if content is not None:
                updates.append('content = ?')
                params.append(content.strip())

            if not updates:
                return False

            updates.append('updated_at = datetime("now")')
            params.append(memory_id)

            query = f"UPDATE user_memories SET {', '.join(updates)} WHERE id = ?"
            cur = self.conn.cursor()
            cur.execute(query, params)
            self.conn.commit()

            if cur.rowcount > 0:
                logger.info(f"[MEMORY_UPDATE] Updated memory_id={memory_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"[MEMORY_ERROR] Update failed: {e}")
            return False

    def format_for_prompt(self, memories: List[Dict]) -> str:
        """
        Format memories into readable prompt section.

        Args:
            memories: List of memory dicts from recall()

        Returns:
            Formatted string ready for system prompt, empty if no memories
        """
        if not memories:
            return ""

        lines = []
        for mem in memories:
            category = mem.get('category', 'general')
            content = mem.get('content', '')
            importance = mem.get('importance', 5)
            lines.append(f"- [{category} #{importance}] {content}")

        return "\n".join(lines)
