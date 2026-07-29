"""
ChatEngine orchestrates a single chat turn:
- context retrieval
- prompt building
- LLM call
- tool-calling
- memory extraction
- persistence

Keep this class thin for now;
expand with async handling and retries later.
"""

import logging
from typing import Optional

from ai.memory_system import MemoryManager, MemoryExtractor


logger = logging.getLogger("cynx.chat")



# ---------------------------------
# Context Limits
# ---------------------------------

MAX_MEMORY_CONTEXT = 3000
MAX_KNOWLEDGE_CONTEXT = 5000
MAX_TOOL_CONTEXT = 6000



class ChatEngine:


    def __init__(
        self,
        ollama_client,
        prompt_builder,
        memory_store,
        tool_router,
        mode_manager,
        memory_manager: Optional[MemoryManager] = None,
        memory_extractor: Optional[MemoryExtractor] = None,
        context_manager=None,
        logger_obj=None
    ):


        self.ollama = ollama_client

        self.prompt_builder = prompt_builder

        self.memory_store = memory_store

        self.tool_router = tool_router

        self.mode_manager = mode_manager

        self.memory_manager = memory_manager

        self.memory_extractor = memory_extractor

        self.context_manager = context_manager

        self.logger = logger_obj or logger




    # ---------------------------------
    # Context Safety
    # ---------------------------------

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





    def handle_user_message(
        self,
        user_id: str,
        text: str,
        mode: str = "normal",
        personality: str = "normal"
    ) -> str:



        """
        Process a user message.

        Flow:

        1. Retrieve relevant context
        2. Build Cyn prompt
        3. Detect tools
        4. Execute tools
        5. Generate response
        6. Extract memories
        7. Save conversation info

        """

        print("===== CHAT ENGINE MEMORY CHECK =====")
        print("Context Manager:", self.context_manager)
        print("Memory Manager:", self.memory_manager)
        print("Memory Extractor:", self.memory_extractor)
        print("====================================")



        # -----------------------------
        # 1. Context retrieval
        # -----------------------------


        mem_summary = ""

        knowledge_context = ""



        if self.context_manager:


            try:


                context = self.context_manager.build_context(

                    user_id,

                    text

                )



                mem_summary = self.trim_context(

                    context.get(
                        "memory",
                        ""
                    ),

                    MAX_MEMORY_CONTEXT

                )

                print(
                    f"[MEMORY FOUND]\n{mem_summary}"
                )

                



                knowledge_context = self.trim_context(

                    context.get(
                        "knowledge",
                        ""
                    ),

                    MAX_KNOWLEDGE_CONTEXT

                )



                self.logger.info(

                    "[CONTEXT] Loaded dynamic context"

                )


                self.logger.info(

                    f"[CONTEXT SIZE] memory={len(mem_summary)} knowledge={len(knowledge_context)}"

                )



            except Exception as e:


                self.logger.error(

                    f"[CONTEXT ERROR] {e}"

                )




        else:


            # Legacy memory fallback

            if self.memory_manager:


                memories = self.memory_manager.recall(

                    user_id,

                    limit=5

                )



                if memories:


                    self.logger.info(

                        f"[MEMORY] Loaded {len(memories)} memories"

                    )



                    mem_summary = self.trim_context(

                        self.memory_manager.format_for_prompt(

                            memories

                        ),

                        MAX_MEMORY_CONTEXT

                    )





        # -----------------------------
        # 2. Build Cyn prompt
        # -----------------------------


        mode_content = []



        if mode:


            mode_content.append(

                mode

            )



        prompt = self.prompt_builder.build_prompt(


            user_input=text,


            mode_fragment="\n".join(

                mode_content

            ),


            memory_summary=mem_summary,


            knowledge_context=knowledge_context,


            tools_spec=(

                f"Personality: {personality}"

            )

        )



        self.logger.info(

            f"[PROMPT SIZE] chars={len(prompt)} words={len(prompt.split())}"

        )





        # -----------------------------
        # 3. Tool detection
        # -----------------------------


        tool_result = None

        tool_request = None



        if self.tool_router:


            try:


                tool_request = self.tool_router.detect(

                    text

                )



                if tool_request:


                    self.logger.info(

                        f"[TOOL] Requested: {tool_request}"

                    )



                    tool_result = self.tool_router.call_tool(

                        tool_request["tool"],

                        tool_request

                    )



                    print(
                        "!!!!! TOOL RETURNED !!!!!"
                    )


                    print(

                        repr(tool_result)

                    )



            except Exception as e:


                self.logger.error(

                    f"[TOOL ERROR] {e}"

                )





        # -----------------------------
        # 4. Add tool results
        # -----------------------------


        full_prompt = prompt



        if tool_result:


            if hasattr(

                tool_result,

                "output"

            ):


                tool_text = tool_result.output


            else:


                tool_text = str(

                    tool_result

                )



            tool_text = self.trim_context(

                tool_text,

                MAX_TOOL_CONTEXT

            )



            full_prompt += (

                "\n\n"

                "[TOOL RESULTS]\n"

                +

                tool_text

                +

                "\n\n"

                "Respond as Cyn.\n"

                "Use the information provided.\n"

                "Present lists clearly when requested.\n"

                "Do not mention internal tools.\n"

                "Do not explain the search process.\n"

                "Keep Cyn's personality.\n"

            )





        full_prompt += "\n\nCyn:"



        self.logger.debug(

            "====== CYN-X PROMPT ======"

        )


        self.logger.debug(

            full_prompt[:500]

        )


        self.logger.debug(

            "=========================="

        )





        # -----------------------------
        # 5. Ollama generation
        # -----------------------------


        resp = self.ollama.generate(

            full_prompt

        )



        assistant_text = (

            resp.get("response")

            or resp.get("text")

            or str(resp)

        )





        # -----------------------------
        # 6. Extract memories
        # -----------------------------


        if self.memory_extractor:


            saved_ids = self.memory_extractor.extract_and_save(

                user_id,

                text,

                assistant_text

            )


            if saved_ids:


                self.logger.info(

                    f"[MEMORY_SAVE] Saved {len(saved_ids)} memories"

                )





        return assistant_text