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

                size + len(content)

                >

                self.MAX_FINAL_PROMPT_CHARS

            ):


                continue



            output.append(

                content

            )


            size += len(content)



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
        conversation_summary: str = ""
    ) -> str:



        sections = []



        # ---------------------------------
        # System Identity
        # ---------------------------------

        system = self.build_system_prompt(

            modes=None,

            memory=memory_summary,

            context=knowledge_context

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

        if intent:


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

        if personality_fragment:


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

        if mode_fragment:


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

        if memory_summary:


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

        if knowledge_context:


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

        if tools_spec:


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

        if conversation_summary:


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

        if history:


            history_text = [

                "Recent conversation:"

            ]


            for msg in history[-self.MAX_HISTORY_MESSAGES:]:


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
                    "\n".join(history_text)

            })



        # ---------------------------------
        # User Input
        # ---------------------------------

        sections.append({

            "priority": 110,

            "content":

                "User: "

                +

                user_input

        })



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