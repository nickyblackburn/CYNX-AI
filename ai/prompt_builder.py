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
- intent
- memory
- retrieved knowledge
- tools
- recent conversation
- conversation summary
- user input

This version keeps the original structure but adds:
- context budgeting
- smart relevance selection
- memory protection
- knowledge ranking
- context priorities
- tool limits
- history limits
- conversation summaries
"""
from typing import List, Optional, Dict, Any

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


    # ---------------------------------------------
    # Context Priority
    # Higher survives trimming
    # ---------------------------------------------

    CONTEXT_PRIORITY = {

        "identity": 100,

        "personality": 90,

        "mode": 80,

        "intent": 75,

        "memory": 70,

        "knowledge": 50,

        "history": 30,

        "tools": 20

    }


    # ---------------------------------------------
    # Prompt Layers
    # ---------------------------------------------

    DEFAULT_PROMPT_LAYERS = {

        "core": True,

        "personality": True,

        "voice": True,

        "conversation": True,

        "safety": True,

        "modes": True,

        "examples": True,

        "overrides": True

    }


    # ---------------------------------------------
    # Prompt Layer Presets
    # ---------------------------------------------

    PROMPT_LAYER_PRESETS = {

        "base": {

            "core": False,

            "personality": False,

            "voice": False,

            "conversation": False,

            "safety": False,

            "modes": False,

            "examples": False,

            "overrides": False

        },

        "core_only": {

            "core": True,

            "personality": False,

            "voice": False,

            "conversation": False,

            "safety": False,

            "modes": False,

            "examples": False,

            "overrides": False

        },

        "core_safety": {

            "core": True,

            "personality": False,

            "voice": False,

            "conversation": False,

            "safety": True,

            "modes": False,

            "examples": False,

            "overrides": False

        },

        "core_personality": {

            "core": True,

            "personality": True,

            "voice": False,

            "conversation": False,

            "safety": False,

            "modes": False,

            "examples": False,

            "overrides": False

        },

        "full_cyn": {

            "core": True,

            "personality": True,

            "voice": True,

            "conversation": True,

            "safety": True,

            "modes": True,

            "examples": True,

            "overrides": True

        }

    }


    # ---------------------------------------------
    # Initialization
    # ---------------------------------------------

    def __init__(
        self,
        templates_dir: Optional[str] = None
    ):

        self.manager = PromptManager(
            templates_dir
        )

        self.prompt_layers = dict(
            self.DEFAULT_PROMPT_LAYERS
        )


    # ---------------------------------------------
    # Prompt Layer Utilities
    # ---------------------------------------------

    def normalize_prompt_layers(
        self,
        prompt_layers: Optional[Dict[str, bool]] = None
    ) -> Dict[str, bool]:

        layers = dict(
            self.DEFAULT_PROMPT_LAYERS
        )

        if prompt_layers:

            for name, enabled in prompt_layers.items():

                if name in layers:

                    layers[name] = bool(
                        enabled
                    )

        return layers


    def set_prompt_layers(
        self,
        prompt_layers: Optional[Dict[str, bool]] = None
    ) -> Dict[str, bool]:

        self.prompt_layers = (
            self.normalize_prompt_layers(
                prompt_layers
            )
        )

        return dict(
            self.prompt_layers
        )


    def get_prompt_layers(
        self
    ) -> Dict[str, bool]:

        return dict(
            self.prompt_layers
        )


    def apply_prompt_preset(
        self,
        preset: str
    ) -> Dict[str, bool]:

        if preset not in self.PROMPT_LAYER_PRESETS:

            raise ValueError(
                f"Unknown prompt preset: {preset}"
            )

        return self.set_prompt_layers(
            self.PROMPT_LAYER_PRESETS[preset]
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

            and

            text.strip()

        )


    # ---------------------------------------------
    # Smart Context Selection
    # ---------------------------------------------

    def score_context(
        self,
        chunk: str,
        query: str
    ) -> int:


        if not chunk:

            return 0


        score = 0


        query_words = (

            query.lower()

            .split()

        )


        chunk_lower = chunk.lower()


        for word in query_words:

            if word in chunk_lower:

                score += 1


        return score


    def select_context(
        self,
        chunks: List[str],
        query: str,
        limit: int
    ) -> str:


        if not chunks:

            return ""


        scored = []


        for chunk in chunks:

            scored.append(

                (

                    self.score_context(

                        chunk,

                        query

                    ),

                    chunk

                )

            )


        scored.sort(

            key=lambda x: x[0],

            reverse=True

        )


        output = ""


        for _, chunk in scored:


            if len(output + chunk) > limit:

                break


            output += (

                chunk

                +

                "\n\n"

            )


        return output.strip()


    # ---------------------------------------------
    # System Prompt
    # ---------------------------------------------

    def build_system_prompt(
        self,
        modes: Optional[List[str]] = None,
        memory: str = "",
        context: str = "",
        prompt_layers: Optional[Dict[str, bool]] = None
    ) -> str:


        memory = self.trim_context(

            memory,

            self.MAX_MEMORY_CHARS

        )


        context = self.trim_context(

            context,

            self.MAX_KNOWLEDGE_CHARS

        )


        layers = self.normalize_prompt_layers(

            prompt_layers

            if prompt_layers is not None

            else self.prompt_layers

        )


        return self.manager.build_system_prompt(

            active_modes=(

                modes

                if layers["modes"]

                else None

            ),

            memory_summary=(

                memory

                if layers["conversation"]

                else ""

            ),

            additional_context=(

                context

                if layers["conversation"]

                else ""

            ),

            enabled_layers=layers

        )


    # ---------------------------------------------
    # Context Budget Manager
    # ---------------------------------------------

    def budget_context(
        self,
        sections: List[Dict[str, Any]]
    ) -> List[str]:


        sections.sort(

            key=lambda x:

            x["priority"],

            reverse=True

        )


        output = []

        size = 0


        for section in sections:


            content = section["content"]


            if not content:

                continue


            if (

                size == 0

                and section.get("priority", 0) >= 90

            ):

                budgeted = (

                    content[

                        :self.MAX_FINAL_PROMPT_CHARS

                    ]

                )

                output.append(

                    budgeted

                )

                size += len(

                    budgeted

                )

                continue


            if (

                size + len(content)

                >

                self.MAX_FINAL_PROMPT_CHARS

            ):

                if (

                    not output

                    and section.get(

                        "priority",

                        0

                    ) >= 90

                ):

                    budgeted = (

                        content[

                            :self.MAX_FINAL_PROMPT_CHARS

                        ]

                    )

                    output.append(

                        budgeted

                    )

                    size += len(

                        budgeted

                    )

                    continue

                continue


            output.append(

                content

            )

            size += len(

                content

            )


        return output


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
        tools_spec: str = "",
        intent: str = "",
        conversation_summary: str = "",
        prompt_layers: Optional[Dict[str, bool]] = None
    ) -> str:


        layers = self.normalize_prompt_layers(

            prompt_layers

            if prompt_layers is not None

            else self.prompt_layers

        )


        sections = []


        # ---------------------------------
        # System Identity
        # ---------------------------------

        system = self.build_system_prompt(

            modes=None,

            memory=memory_summary,

            context=knowledge_context,

            prompt_layers=layers

        )


        sections.append({

            "priority":

                self.CONTEXT_PRIORITY["identity"],

            "content":

                system

        })


        # ---------------------------------
        # Intent
        # ---------------------------------

        if (

            intent

            and

            layers["conversation"]

        ):


            sections.append({

                "priority":

                    self.CONTEXT_PRIORITY["intent"],

                "content":

                    "Intent:\n"

                    +

                    intent

            })


        # ---------------------------------
        # Personality Override
        # ---------------------------------

        if (

            personality_fragment

            and

            layers["personality"]

        ):


            sections.append({

                "priority":

                    self.CONTEXT_PRIORITY["personality"],

                "content":

                    self.trim_context(

                        personality_fragment,

                        self.MAX_PERSONALITY_CHARS

                    )

            })


        # ---------------------------------
        # Mode
        # ---------------------------------

        if (

            mode_fragment

            and

            layers["modes"]

        ):


            sections.append({

                "priority":

                    self.CONTEXT_PRIORITY["mode"],

                "content":

                    self.trim_context(

                        mode_fragment,

                        self.MAX_MODE_CHARS

                    )

            })


        # ---------------------------------
        # Memory
        # ---------------------------------

        if (

            memory_summary

            and

            layers["conversation"]

        ):


            sections.append({

                "priority":

                    self.CONTEXT_PRIORITY["memory"],

                "content":

                    "Memory:\n"

                    +

                    self.trim_context(

                        memory_summary,

                        self.MAX_MEMORY_CHARS

                    )

            })


        # ---------------------------------
        # Knowledge
        # ---------------------------------

        if (

            knowledge_context

            and

            layers["conversation"]

        ):


            sections.append({

                "priority":

                    self.CONTEXT_PRIORITY["knowledge"],

                "content":

                    "Relevant knowledge:\n"

                    +

                    self.trim_context(

                        knowledge_context,

                        self.MAX_KNOWLEDGE_CHARS

                    )

            })


        # ---------------------------------
        # Tools
        # ---------------------------------

        if (

            tools_spec

            and

            layers["conversation"]

        ):


            sections.append({

                "priority":

                    self.CONTEXT_PRIORITY["tools"],

                "content":

                    "Available tools:\n"

                    +

                    self.trim_context(

                        tools_spec,

                        self.MAX_TOOL_CHARS

                    )

            })


        # ---------------------------------
        # Conversation Summary
        # ---------------------------------

        if (

            conversation_summary

            and

            layers["conversation"]

        ):


            sections.append({

                "priority":

                    self.CONTEXT_PRIORITY["history"],

                "content":

                    "Conversation summary:\n"

                    +

                    conversation_summary

            })


        # ---------------------------------
        # History
        # ---------------------------------

        if (

            history

            and

            layers["conversation"]

        ):


            history_text = [

                "Recent conversation:"

            ]


            for msg in (

                history[

                    -self.MAX_HISTORY_MESSAGES:

                ]

            ):


                role = msg.get(

                    "role",

                    "unknown"

                )


                content = msg.get(

                    "content",

                    ""

                )


                history_text.append(

                    f"{role}: {content}"

                )


            sections.append({

                "priority":

                    self.CONTEXT_PRIORITY["history"],

                "content":

                    "\n".join(

                        history_text

                    )

            })


        # ---------------------------------
        # User Input is kept separate from the system prompt.
        # It is sent as the actual user message in ChatEngine.
        # ---------------------------------


        # ---------------------------------
        # Final Assembly
        # ---------------------------------

        final_prompt = "\n\n".join(

            self.budget_context(

                sections

            )

        )


        return self.trim_context(

            final_prompt,

            self.MAX_FINAL_PROMPT_CHARS

        )