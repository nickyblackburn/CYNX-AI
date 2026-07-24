"""
ChatEngine orchestrates a single chat turn: memory retrieval, prompt building, LLM call, tool-calling, and persistence.
Keep this class thin for now; expand with async handling and retries later.
"""
from typing import Optional


class ChatEngine:
    def __init__(self, ollama_client, prompt_builder, memory_store, tool_router, mode_manager, logger=None):
        self.ollama = ollama_client
        self.prompt_builder = prompt_builder
        self.memory_store = memory_store
        self.tool_router = tool_router
        self.mode_manager = mode_manager
        self.logger = logger

    def handle_user_message(self, user_id: str, text: str, mode: str = 'normal', personality: str = 'normal') -> str:
        """Process a user message and return assistant response (synchronous version).
        Flow:
          - retrieve short memory summary
          - build prompt
          - call ollama
          - detect tool calls (not implemented here)
          - persist conversation
        """

        # Retrieve recent memories
        memories = self.memory_store.retrieve_recent(limit=5)

        mem_summary = "\n".join(
            [
                f"- {memory['kind']}: {memory['content']}"
                for memory in memories
            ]
        )

        mode_spec = self.mode_manager.get_mode(mode)

        personality_frag = ''

        prompt = self.prompt_builder.build_prompt(
            text,
            mode_fragment=mode_spec.instruction_fragment,
            personality_fragment=personality_frag,
            memory_summary=mem_summary,
            history=[]
        )

        self.logger and self.logger.debug(
            "Prompt built for user %s",
            user_id
        )

        resp = self.ollama.generate(prompt)

        # For now, assume resp contains a top-level 'response' field
        assistant_text = (
            resp.get('response')
            or resp.get('text')
            or str(resp)
        )

        # Persist conversation
        self.memory_store.add_memory(
            kind="conversation",
            content=f"User: {text}\nAssistant: {assistant_text}",
            metadata={
                "user_id": user_id
            }
        )

        return assistant_text