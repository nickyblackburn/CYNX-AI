"""
ChatEngine orchestrates a single chat turn: memory retrieval, prompt building, LLM call, tool-calling, and persistence.
Keep this class thin for now; expand with async handling and retries later.
"""

import logging
from typing import Optional

from ai.memory_system import MemoryManager, MemoryExtractor


logger = logging.getLogger("cynx.chat")


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
        logger_obj=None
    ):
        self.ollama = ollama_client
        self.prompt_builder = prompt_builder
        self.memory_store = memory_store
        self.tool_router = tool_router
        self.mode_manager = mode_manager
        self.memory_manager = memory_manager
        self.memory_extractor = memory_extractor
        self.logger = logger_obj or logger


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
        1. Retrieve memories
        2. Build Cyn system prompt
        3. Send to Ollama
        4. Extract memories
        5. Save conversation info
        """

        # -----------------------------
        # 1. Memory recall
        # -----------------------------

        mem_summary = ""

        if self.memory_manager:
            memories = self.memory_manager.recall(
                user_id,
                limit=5
            )

            if memories:
                self.logger.info(
                    f"[MEMORY] Loaded {len(memories)} memories for {user_id}"
                )

                mem_summary = self.memory_manager.format_for_prompt(
                    memories
                )

                for mem in memories:
                    self.logger.debug(
                        f" - [{mem['category']}] {mem['content']}"
                    )

            else:
                self.logger.debug(
                    f"[MEMORY] No memories found for {user_id}"
                )


        # -----------------------------
        # 2. Build prompt
        # -----------------------------

        mode_content = []

        if mode:
            mode_content.append(mode)

        prompt = self.prompt_builder.build_system_prompt(
            modes=mode_content,
            memory=mem_summary,
            context=f"Personality: {personality}"
        )


        # Add current user message
        full_prompt = (
            prompt
            + "\n\nUser:\n"
            + text
            + "\n\nCyn:"
        )


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
        # 3. Ollama generation
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
        # 4. Extract memories
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


        # -----------------------------
        # 5. Legacy memory storage
        # -----------------------------

        self.memory_store.add_memory(
            kind="fact",
            content=f"Used CYN-X personality mode: {personality}",
            metadata={
                "user_id": user_id
            }
        )


        return assistant_text