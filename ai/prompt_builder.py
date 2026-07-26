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

This version keeps the original structure but adds:
- context budgeting
- smart trimming
- memory protection
- knowledge limits
- tool limits
- history limits
"""


from typing import List, Optional

from .prompt_manager import PromptManager



class PromptBuilder:


    # ---------------------------------------------
    # Context Limits
    # ---------------------------------------------

    MAX_MEMORY_CHARS = 3000

    MAX_KNOWLEDGE_CHARS = 4000

    MAX_TOOL_CHARS = 2000

    MAX_PERSONALITY_CHARS = 2500

    MAX_MODE_CHARS = 2500

    MAX_HISTORY_MESSAGES = 6

    MAX_FINAL_PROMPT_CHARS = 24000



    def __init__(
        self,
        templates_dir: Optional[str] = None
    ):

        self.manager = PromptManager(
            templates_dir
        )



    # ---------------------------------------------
    # Context Utilities
    # ---------------------------------------------

    def trim_context(
        self,
        text: str,
        limit: int
    ) -> str:


        if not text:

            return ""


        if len(text) <= limit:

            return text


        return (
            text[:limit]
            +
            "\n\n[Context shortened]"
        )



    def should_include_context(
        self,
        text: str
    ) -> bool:


        return bool(
            text
            and text.strip()
        )



    # ---------------------------------------------
    # System Prompt
    # ---------------------------------------------

    def build_system_prompt(
        self,
        modes: Optional[List[str]] = None,
        memory: str = "",
        context: str = ""
    ) -> str:


        memory = self.trim_context(
            memory,
            self.MAX_MEMORY_CHARS
        )


        context = self.trim_context(
            context,
            self.MAX_KNOWLEDGE_CHARS
        )



        return self.manager.build_system_prompt(

            active_modes=modes,

            memory_summary=memory,

            additional_context=context

        )



    # ---------------------------------------------
    # Full Prompt Builder
    # ---------------------------------------------

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
        # Temporary Context
        # ---------------------------------

        additional_context = []



        if self.should_include_context(
            knowledge_context
        ):


            additional_context.append(

                "Relevant knowledge:\n"
                +
                self.trim_context(

                    knowledge_context,

                    self.MAX_KNOWLEDGE_CHARS

                )

            )



        if self.should_include_context(
            tools_spec
        ):


            additional_context.append(

                "Available tools:\n"
                +
                self.trim_context(

                    tools_spec,

                    self.MAX_TOOL_CHARS

                )

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
        # Personality Override
        # ---------------------------------

        if personality_fragment:


            parts.append(

                self.trim_context(

                    personality_fragment,

                    self.MAX_PERSONALITY_CHARS

                )

            )



        # ---------------------------------
        # Mode
        # ---------------------------------

        if mode_fragment:


            parts.append(

                self.trim_context(

                    mode_fragment,

                    self.MAX_MODE_CHARS

                )

            )



        # ---------------------------------
        # History
        # ---------------------------------

        if history:


            parts.append(
                "Recent conversation:"
            )



            for msg in history[-self.MAX_HISTORY_MESSAGES:]:


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
        # User Input
        # ---------------------------------

        parts.append(

            "User: "
            +
            user_input

        )



        final_prompt = "\n\n".join(

            part

            for part in parts

            if part

        )



        # ---------------------------------
        # Final Protection
        # ---------------------------------

        return self.trim_context(

            final_prompt,

            self.MAX_FINAL_PROMPT_CHARS

        )