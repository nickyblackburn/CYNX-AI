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

import json
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


    def _ollama_tools(self):
        if not self.tool_router:
            return None
        return self.tool_router.as_ollama_tools()


    def handle_user_message(        self,
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



        # Prepare tools specification for the model so it knows available tools and
        # the concise rule: call tools when appropriate (direct action first).
        tools_list = []
        if self.tool_router:
            for t in self.tool_router.describe_tools():
                tools_list.append(f"{t['name']}: {t['description']}")
        tools_spec_str = "Available tools:\n" + "\n".join(tools_list)
        tools_spec_str += "\n\nTool-use instruction: When the user asks for information or an action that one of your available tools can perform, use the appropriate tool. Execute the tool and use its result in your response. PRIORITY: Direct response first. Personality second. Do not redirect mundane requests into unrelated topics."
        tools_spec_str += "\nSpecial rule for smoke_counter: if the user asks for smoking totals or session counts, use the tool result exactly as returned. Do not recalculate totals. Do not substitute session count for total_units. Use total_units exactly as returned by smoke_counter."

        prompt = self.prompt_builder.build_prompt(

            user_input=text,

            mode_fragment="\n".join(

                mode_content

            ),

            memory_summary=mem_summary,

            knowledge_context=knowledge_context,

            tools_spec=tools_spec_str

        )



        self.logger.info(

            f"[PROMPT SIZE] chars={len(prompt)} words={len(prompt.split())}"

        )





        # -----------------------------
        # 3. Tool-aware chat loop
        # -----------------------------
        tool_specs = self._ollama_tools()
        if tool_specs:
            print("[AVAILABLE TOOLS]", [t.get('function', {}).get('name') for t in tool_specs])

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ]

        print("[USER]", text)

        # Call Ollama with a real chat tool schema. If the model issues a tool call,
        # execute it in Python and then send the tool result back to Ollama.
        response = self.ollama.chat(messages=messages, tools=tool_specs or None)
        message = response.get("message", {})
        tool_calls = message.get("tool_calls") or []

        if tool_calls:
            print("[MODEL RESPONSE]")
            print(json.dumps(message, ensure_ascii=False, indent=2)[:2000])

            messages.append({
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": tool_calls,
            })

            for tool_call in tool_calls:
                name = (tool_call.get("function") or {}).get("name") or tool_call.get("name")
                arguments = (tool_call.get("function") or {}).get("arguments") or tool_call.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except Exception:
                        arguments = {}

                print("[TOOL CALL]")
                print("name=", name)
                print("[TOOL ARGUMENTS]")
                print(json.dumps(arguments, ensure_ascii=False, indent=2))
                print("[EXECUTING TOOL]")

                if not self.tool_router or name not in self.tool_router.tools:
                    tool_result_payload = {"success": False, "error": f"Tool '{name}' not found."}
                else:
                    tool_result = self.tool_router.call_tool(name, arguments)
                    tool_result_payload = tool_result.metadata if tool_result.metadata is not None else {
                        "success": tool_result.success,
                        "output": tool_result.output,
                    }
                    tool_result_payload = dict(tool_result_payload)
                    tool_result_payload.setdefault("success", tool_result.success)
                    tool_result_payload.setdefault("output", tool_result.output)

                    if name == "smoke_counter":
                        raw_result = {} if not isinstance(tool_result_payload, dict) else dict(tool_result_payload)
                        tool_result_payload = {
                            "success": raw_result.get("success", tool_result.success),
                            "total_units": raw_result.get("total_units"),
                            "total_cigarettes": raw_result.get("total_cigarettes"),
                            "total_sessions": raw_result.get("total_sessions"),
                            "today_sessions": raw_result.get("today_sessions"),
                            "today_units": raw_result.get("today_units"),
                            "last_session": raw_result.get("last_session"),
                        }

                    print("[TOOL RESULT]")
                    print(json.dumps(tool_result_payload, ensure_ascii=False, indent=2))

                tool_message_content = {
                    "tool_name": name,
                    "result": tool_result_payload,
                    "instruction": "Use total_units exactly as returned by the smoke_counter tool. Do not recalculate it. Do not substitute session count for total_units."
                }
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", "call_1"),
                    "name": name,
                    "content": json.dumps(tool_message_content, ensure_ascii=False)
                }
                messages.append(tool_message)

            print("[RETURNING TOOL RESULT TO MODEL]")
            final_response = self.ollama.chat(messages=messages, tools=None)
            assistant_text = (final_response.get("message") or {}).get("content") or str(final_response)
            print("[FINAL MODEL RESPONSE]")
            print(assistant_text)
            return assistant_text

        # No tool call was requested by the model; fall back to the original generation flow.
        assistant_text = (
            (response.get("message") or {}).get("content")
            or response.get("response")
            or response.get("text")
            or str(response)
        )
        print("[FINAL MODEL RESPONSE]")
        print(assistant_text)
        return assistant_text




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