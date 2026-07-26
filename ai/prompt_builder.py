"""
PromptBuilder bridges ChatEngine and PromptManager.

PromptManager handles loading:
- core.md
- personality.md
- voice.md
- conversation.md
- safety.md
- modes
- examples
"""

from typing import List, Optional

from .prompt_manager import PromptManager


class PromptBuilder:

    def __init__(self, templates_dir: Optional[str] = None):
        self.manager = PromptManager(templates_dir)


    def build_system_prompt(
        self,
        modes: Optional[List[str]] = None,
        memory: str = "",
        context: str = ""
    ) -> str:

        return self.manager.build_system_prompt(
            active_modes=modes,
            memory_summary=memory,
            additional_context=context
        )


    def build_prompt(
        self,
        user_input: str,
        mode_fragment: str = "",
        personality_fragment: str = "",
        history: Optional[List[dict]] = None,
        memory_summary: str = "",
        tools_spec: str = ""
    ) -> str:

        system = self.build_system_prompt(
            modes=None,
            memory=memory_summary,
            context=tools_spec
        )

        parts = [
            system
        ]

        if personality_fragment:
            parts.append(personality_fragment)

        if mode_fragment:
            parts.append(mode_fragment)

        if history:
            parts.append("Recent conversation:")

            for msg in history[-10:]:
                parts.append(
                    f"{msg.get('role')}: {msg.get('content')}"
                )

        parts.append(
            "User: " + user_input
        )

        return "\n\n".join(
            p for p in parts if p
        )
