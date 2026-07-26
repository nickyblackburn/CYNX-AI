"""
PromptBuilder assembles the system prompt from modular prompt files.

Uses PromptManager to dynamically load and combine core personality,
modes, examples, recent history, and memory summaries.
"""
from pathlib import Path
from typing import List, Optional

from .prompt_manager import PromptManager


class PromptBuilder:
    """Backwards-compatible prompt builder using the new PromptManager."""

    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize PromptBuilder.

        Args:
            templates_dir: Path to prompts directory (defaults to ./prompts_new)
        """
        if templates_dir:
            prompts_dir = templates_dir
        else:
            # Try new location first, fall back to old
            new_dir = Path(__file__).resolve().parents[1] / 'prompts_new'
            old_dir = Path(__file__).resolve().parents[1] / 'prompts'
            prompts_dir = str(new_dir) if new_dir.exists() else str(old_dir)

        self.manager = PromptManager(prompts_dir)

    def build_prompt(
        self,
        user_input: str,
        mode_fragment: str = '',
        personality_fragment: str = '',
        history: Optional[List[dict]] = None,
        memory_summary: str = '',
        tools_spec: str = '',
        active_modes: Optional[List[str]] = None
    ) -> str:
        """
        Build the complete system prompt.

        Args:
            user_input: The user's input message
            mode_fragment: (Deprecated) Mode content as string
            personality_fragment: (Deprecated) Personality content as string
            history: Recent conversation history
            memory_summary: Summary of relevant memory
            tools_spec: Tools specification if applicable
            active_modes: List of mode names to activate (new approach)

        Returns:
            Complete assembled prompt
        """
        parts = []

        # Load core personality using PromptManager
        parts.append(self.manager.load_core_prompts())

        # Support legacy mode/personality fragments for backwards compatibility
        if personality_fragment:
            parts.append(personality_fragment)

        if mode_fragment:
            parts.append(mode_fragment)

        # Support new active_modes approach
        if active_modes:
            for mode_name in active_modes:
                mode_content = self.manager.load_mode(mode_name)
                if mode_content:
                    parts.append(f"# Mode: {mode_name.title()}\n\n{mode_content}")

        # Add tools spec if provided
        if tools_spec:
            parts.append(tools_spec)

        # Add memory summary if provided
        if memory_summary:
            parts.append("# Memory Summary\n\n" + memory_summary)

        # Add recent conversation history
        if history:
            history_parts = ["# Recent Conversation"]
            for msg in history[-10:]:
                role = msg.get('role', 'unknown').title()
                content = msg.get('content', '')
                history_parts.append(f"{role}: {content}")
            parts.append("\n".join(history_parts))

        # Add user input
        parts.append("User: " + user_input)

        return "\n\n".join([p for p in parts if p])
