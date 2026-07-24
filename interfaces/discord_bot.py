"""
Discord adapter stub. Implement event handlers and map messages to ChatEngine.
Keep token and config out of source; load from environment variables.
"""
from typing import Any


class DiscordAdapter:
    def __init__(self, chat_engine, logger=None):
        self.chat_engine = chat_engine
        self.logger = logger

    def start(self):
        # Implement discord.py bot startup here when ready
        raise NotImplementedError("Discord adapter not implemented in scaffold")
