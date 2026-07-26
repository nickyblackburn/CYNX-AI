"""
MemoryExtractor: Analyzes conversations and extracts worth-remembering information.
Uses pattern matching to identify preferences, projects, goals, names, and communication styles.
"""
import logging
import re
from typing import List, Dict, Tuple
from .manager import MemoryManager


logger = logging.getLogger("cynx.memory")


class MemoryExtractor:
    """Extracts and saves important information from conversations."""

    # Patterns for different memory types
    PREFERENCE_PATTERNS = [
        r"i (?:prefer|like|enjoy|love|hate|dislike|can't stand)\s+([^.!?]+)",
        r"(?:prefer|like|enjoy|love|hate|dislike)\s+(.{5,}?)(?:\.|$)",
        r"i don't (?:like|enjoy|prefer)\s+([^.!?]+)",
        r"(?:favorite|best)\s+(?:is|are)?\s*([^.!?]+)",
    ]

    GOAL_PATTERNS = [
        r"(?:my goal|i want to|i'm trying to|aiming to|planning to)\s+([^.!?]+)",
        r"(?:i want|i need|i should)\s+([^.!?]+)",
    ]

    PROJECT_PATTERNS = [
        r"(?:working on|building|creating|developing|coding)\s+([^.!?]+)",
        r"(?:i'm (?:building|creating|working on|developing)|project\s+(?:is|called))\s+([^.!?]+)",
    ]

    NAME_PATTERNS = [
        r"(?:my name is|call me|i'm|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:name(?:'s)?|people call me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ]

    STYLE_PATTERNS = [
        r"(?:i'm|i am)\s+([\w\s]+(?:person|programmer|developer|engineer|designer|writer))",
        r"(?:i work|i (?:do|use))\s+(?:with|using)\s+([^.!?]+)",
    ]

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager

    def extract_and_save(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str = ""
    ) -> List[int]:
        """
        Analyze message pair and save worth-remembering information.

        Args:
            user_id: User identifier
            user_message: User's message
            assistant_response: Assistant's response (optional)

        Returns:
            List of saved memory IDs
        """
        saved_ids = []
        full_text = f"{user_message} {assistant_response}".lower()

        # Try each extraction method
        extracted = []

        # Preferences
        prefs = self._extract_preferences(full_text)
        extracted.extend([('preference', p, 6) for p in prefs])

        # Names
        names = self._extract_names(full_text)
        extracted.extend([('name', n, 8) for n in names])

        # Goals
        goals = self._extract_goals(full_text)
        extracted.extend([('goal', g, 7) for g in goals])

        # Projects
        projects = self._extract_projects(full_text)
        extracted.extend([('project', p, 7) for p in projects])

        # Communication style
        styles = self._extract_style(full_text)
        extracted.extend([('style', s, 5) for s in styles])

        # Save all extracted items
        for category, content, importance in extracted:
            if self._should_save(content):
                mem_id = self.memory_manager.remember(
                    user_id,
                    content=content,
                    category=category,
                    importance=importance
                )
                if mem_id:
                    saved_ids.append(mem_id)

        if saved_ids:
            logger.info(f"[EXTRACT_SAVE] Saved {len(saved_ids)} memories for {user_id}")

        return saved_ids

    def _extract_preferences(self, text: str) -> List[str]:
        """Extract user preferences."""
        prefs = []
        for pattern in self.PREFERENCE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if self._is_meaningful(match):
                    prefs.append(f"Prefers: {match}")
        return prefs[:3]  # Limit to top 3

    def _extract_goals(self, text: str) -> List[str]:
        """Extract user goals."""
        goals = []
        for pattern in self.GOAL_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if self._is_meaningful(match) and len(match) > 10:
                    goals.append(f"Goal: {match}")
        return goals[:2]  # Limit to top 2

    def _extract_projects(self, text: str) -> List[str]:
        """Extract ongoing projects."""
        projects = []
        for pattern in self.PROJECT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if self._is_meaningful(match) and len(match) > 10:
                    projects.append(f"Project: {match}")
        return projects[:2]  # Limit to top 2

    def _extract_names(self, text: str) -> List[str]:
        """Extract user's name."""
        for pattern in self.NAME_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if len(match) > 2 and len(match) < 30:
                    return [f"Name: {match}"]
        return []

    def _extract_style(self, text: str) -> List[str]:
        """Extract communication and work style."""
        styles = []
        for pattern in self.STYLE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match = match.strip()
                if self._is_meaningful(match):
                    styles.append(f"Style: {match}")
        return styles[:2]  # Limit to top 2

    def _is_meaningful(self, text: str) -> bool:
        """Check if text is meaningful (not just punctuation/emoji)."""
        # Remove punctuation and spaces
        cleaned = re.sub(r'[^\w\s]', '', text)
        # At least 3 characters
        return len(cleaned) >= 3

    def _should_save(self, content: str) -> bool:
        """Heuristic: should we save this memory?"""
        if not content or not content.strip():
            return False

        content = content.strip()

        # Too short
        if len(content) < 5:
            return False

        # All punctuation/emoji
        if not re.search(r'[a-zA-Z0-9]', content):
            return False

        # Looks like spam (repeated chars)
        if re.search(r'(.)\1{5,}', content):
            return False

        return True
