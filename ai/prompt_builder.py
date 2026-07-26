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

PromptBuilder assembles:
- system prompt
- personality
- modes
- memory
- retrieved knowledge
- tools
- recent conversation
- user input
"""

from typing import List, Optional

from .prompt_manager import PromptManager


class PromptBuilder:

    def __init__(
        self,
        templates_dir: Optional[str] = None
    ):

        self.manager = PromptManager(
            templates_dir
        )


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
        knowledge_context: str = "",
        tools_spec: str = ""
    ) -> str:


        # ---------------------------------
        # Combine temporary context
        # ---------------------------------

        additional_context = []


        if knowledge_context:

            additional_context.append(
                "Relevant knowledge:\n"
                + knowledge_context
            )


        if tools_spec:

            additional_context.append(
                "Available tools:\n"
                + tools_spec
            )


        context = "\n\n".join(
            additional_context
        )



        system = self.build_system_prompt(

            modes=None,

            memory=memory_summary,

            context=context

        )



        parts = [

            system

        ]



        # ---------------------------------
        # Personality override
        # ---------------------------------

        if personality_fragment:

            parts.append(
                personality_fragment
            )



        # ---------------------------------
        # Active mode
        # ---------------------------------

        if mode_fragment:

            parts.append(
                mode_fragment
            )



        # ---------------------------------
        # Conversation history
        # ---------------------------------

        if history:

            parts.append(
                "Recent conversation:"
            )


            for msg in history[-10:]:

                role = msg.get(
                    "role",
                    "unknown"
                )

                content = msg.get(
                    "content",
                    ""
                )


                parts.append(
                    f"{role}: {content}"
                )



        # ---------------------------------
        # Current user message
        # ---------------------------------

        parts.append(
            "User: "
            + user_input
        )



        return "\n\n".join(

            p

            for p in parts

            if p

        )