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
import os
import time
from typing import Optional

from ai.memory_system import MemoryManager, MemoryExtractor
from ai.terminal_ui import terminal


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

        if self.context_manager is None:
            
                print("[CORE WARNING] ChatEngine received context_manager=None")
            
        else:
          
                print(f"[CORE] ContextManager attached: {type(self.context_manager).__name__}")

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
        personality: str = "normal",
        request_id: Optional[str] = None
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

        terminal.section("CHAT ENGINE MEMORY CHECK")
        terminal.dim(f"Context Manager: {self.context_manager}")
        terminal.dim(f"Memory Manager: {self.memory_manager}")
        terminal.dim(f"Memory Extractor: {self.memory_extractor}")



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

                terminal.memory("MEMORY FOUND")
                terminal.dim(mem_summary)

                



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
            terminal.available_tools([t.get('function', {}).get('name') for t in tool_specs])

        smoke_intent = None
        if self.tool_router and hasattr(self.tool_router, 'detect'):
            smoke_intent = self.tool_router.detect(text)
        if smoke_intent and smoke_intent.get('tool') == 'smoke_counter':
            read_only = bool(self.tool_router and hasattr(self.tool_router, 'is_read_only_smoke_query') and self.tool_router.is_read_only_smoke_query(text))
            terminal.info(f"[SMOKE INTENT] {'read_only' if read_only else 'log'}")
            terminal.info(f"[SMOKE ACTION] {smoke_intent.get('action')}")
            terminal.info(f"[SMOKE TYPE] {smoke_intent.get('smoke_type', 'n/a')}")
            terminal.info(f"[SMOKE SCOPE] {smoke_intent.get('scope', 'all')}")

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ]

        terminal.user(text)

        if request_id:
            terminal.ollama("OLLAMA CALL", f"id={request_id} phase=first")

        if os.environ.get("CYN_DEBUG_PROMPT") == "1":
            terminal.section("ACTUAL SYSTEM PROMPT")
            terminal.dim(messages[0]["content"])

        # Call Ollama with a real chat tool schema. If the model issues a tool call,
        # execute it in Python and then send the tool result back to Ollama.
        start = time.perf_counter()
        response = self.ollama.chat(messages=messages, tools=tool_specs or None)
        terminal.timing(f"[FIRST OLLAMA TIME] {time.perf_counter() - start:.2f}s")
        message = response.get("message", {})
        tool_calls = message.get("tool_calls") or []

        # Validate tool_calls before proceeding. If the model returned any tool name
        # that is not registered in the tool router, log and treat as if no tool was requested
        # so the flow falls back to a normal assistant response without executing tools.
        invalid_tool_names = []
        validated_tool_calls = []
        for tc in tool_calls:
            name = (tc.get("function") or {}).get("name") or tc.get("name")
            if name and self.tool_router and hasattr(self.tool_router, 'tools'):
                if name in self.tool_router.tools:
                    validated_tool_calls.append(tc)
                else:
                    invalid_tool_names.append(name)
            else:
                # If tool router missing or name absent, treat as invalid to be safe
                if name:
                    invalid_tool_names.append(name)

        if invalid_tool_names:
            terminal.model("MODEL RESPONSE", f"Invalid tool names detected from model: {invalid_tool_names}")
            terminal.warning("Falling back to a normal assistant response without executing tools.")
            # Proceed as if there were no tool calls
            tool_calls = []
            message = {"role": "assistant", "content": message.get("content", "")}
        else:
            # Use the validated tool_calls (could be empty)
            tool_calls = validated_tool_calls

        if tool_calls:
            terminal.model("MODEL RESPONSE")
            terminal.json(dict(message) if isinstance(message, dict) else message)

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

                if request_id:
                    terminal.tool("TOOL CALL", f"id={request_id} tool={name}")
                else:
                    terminal.tool("TOOL CALL", f"name={name}")
                terminal.tool_args("TOOL ARGUMENTS")
                terminal.json(arguments)

                # Additional smoke-query tracing and augmentation to ensure the tool call contains
                # explicit smoke_type when the user requested a type (e.g., 'vape', 'pen').
                if name == 'smoke_counter' and isinstance(arguments, dict):
                    parsed_from_text = None
                    try:
                        if self.tool_router and hasattr(self.tool_router, 'detect'):
                            parsed_from_text = self.tool_router.detect(text)
                    except Exception:
                        parsed_from_text = None

                    parsed_action = arguments.get('action') or (parsed_from_text or {}).get('action')
                    parsed_smoke_type = arguments.get('smoke_type') or (parsed_from_text or {}).get('smoke_type')
                    parsed_scope = arguments.get('scope') or (parsed_from_text or {}).get('scope')

                    if self.tool_router and hasattr(self.tool_router, 'is_read_only_smoke_query') and self.tool_router.is_read_only_smoke_query(text):
                        if str(arguments.get('action', '')).lower() == 'log':
                            arguments['action'] = 'stats'
                            if 'today' in text.lower() and not arguments.get('scope'):
                                arguments['scope'] = 'today'
                            terminal.info("[SMOKE INTENT] read_only")
                            terminal.info(f"[SMOKE ACTION] stats")
                            terminal.info(f"[SMOKE TYPE] {arguments.get('smoke_type', parsed_smoke_type or 'n/a')}")
                            terminal.info(f"[SMOKE SCOPE] {arguments.get('scope') or parsed_scope or ('today' if 'today' in text.lower() else 'all')}")
                     
                    terminal.info("[SMOKE QUERY]")
                    terminal.dim(text)
                    terminal.info(f"[PARSED ACTION] {parsed_action}")
                    terminal.info(f"[PARSED SMOKE TYPE] {parsed_smoke_type}")
                    terminal.info(f"[PARSED DATE/SCOPE] {parsed_scope}")

                    if not arguments.get('smoke_type') and parsed_smoke_type:
                        try:
                            arguments['smoke_type'] = parsed_smoke_type
                            terminal.info('Augmented tool arguments with smoke_type from router.detect()')
                        except Exception:
                            pass

                    st = arguments.get('smoke_type')
                    if st and hasattr(self.tool_router, 'normalize_smoke_type'):
                        try:
                            arguments['smoke_type'] = self.tool_router.normalize_smoke_type(st)
                        except Exception:
                            pass

                    amt = arguments.get('amount')
                    if isinstance(amt, str):
                        try:
                            if '.' in amt:
                                arguments['amount'] = float(amt)
                            else:
                                arguments['amount'] = int(amt)
                        except Exception:
                            try:
                                arguments['amount'] = float(amt)
                            except Exception:
                                pass

                if request_id:
                    terminal.execute("EXECUTING TOOL", f"id={request_id} tool={name}")
                else:
                    terminal.execute("EXECUTING TOOL", f"tool={name}")

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
                        merged = dict(raw_result)
                        merged.setdefault("success", raw_result.get("success", tool_result.success))
                        merged.setdefault("total_units", raw_result.get("total_units"))
                        merged.setdefault("total_cigarettes", raw_result.get("total_cigarettes"))
                        merged.setdefault("total_sessions", raw_result.get("total_sessions"))
                        merged.setdefault("today_sessions", raw_result.get("today_sessions"))
                        merged.setdefault("today_units", raw_result.get("today_units"))
                        merged.setdefault("last_session", raw_result.get("last_session"))
                        merged.setdefault("units", raw_result.get("units"))
                        merged.setdefault("sessions", raw_result.get("sessions"))
                        merged.setdefault("smoke_type", raw_result.get("smoke_type"))
                        merged.setdefault("scope", raw_result.get("scope", "all"))
                        merged["authoritative_source"] = "current_tool_result"
                        tool_result_payload = merged

                    if request_id:
                        terminal.result("TOOL RESULT", f"id={request_id}")
                    else:
                        terminal.result("TOOL RESULT")
                    terminal.json(tool_result_payload)

                display_override = None
                if name == 'smoke_counter':
                    user_specified_type = None
                    try:
                        parsed_from_text = self.tool_router.detect(text) if self.tool_router and hasattr(self.tool_router, 'detect') else None
                        user_specified_type = (parsed_from_text or {}).get('smoke_type') or arguments.get('smoke_type') or tool_result_payload.get('smoke_type')
                    except Exception:
                        user_specified_type = arguments.get('smoke_type') or tool_result_payload.get('smoke_type')

                    if not user_specified_type:
                        scope_val = arguments.get('scope') or tool_result_payload.get('scope') or 'all'
                        if str(scope_val).lower() == 'today':
                            display_units = tool_result_payload.get('today_units') if tool_result_payload.get('today_units') is not None else tool_result_payload.get('units') or tool_result_payload.get('total_units')
                        else:
                            display_units = tool_result_payload.get('total_units') if tool_result_payload.get('total_units') is not None else tool_result_payload.get('units') or tool_result_payload.get('today_units')
                        try:
                            display_units = 0 if display_units is None else display_units
                        except Exception:
                            display_units = display_units
                        display_override = f"You've smoked {display_units} smoking units."
                        tool_result_payload['display'] = display_override

                tool_message_content = {
                    "tool_name": name,
                    "result": tool_result_payload,
                    "instruction": "Use the current tool result as the authoritative source for this request. Prefer it over memory and over the current user message. For smoke_counter, use its result exactly; do not claim you lack the information if the tool already returned it."
                }
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", "call_1"),
                    "name": name,
                    "content": json.dumps(tool_message_content, ensure_ascii=False)
                }
                messages.append(tool_message)

            if request_id:
                terminal.ollama("OLLAMA CALL", f"id={request_id} phase=final")
            terminal.info("[RETURNING TOOL RESULT TO MODEL]")

            # Optimize final Ollama call for deterministic tools (small prompt)
            # Deterministic tools should not require re-sending the full system prompt.
            deterministic_tools = {"smoke_counter"}
            tool_messages = [m for m in messages if m.get("role") == "tool"]
            tool_names = [m.get("name") for m in tool_messages]
            use_minimal = False
            if tool_messages and all((n in deterministic_tools) for n in tool_names):
                use_minimal = True

            final_start = time.perf_counter()
            if use_minimal:
                # Build a minimal response prompt containing: brief identity/style, original user message,
                # and the tool result messages. Instruct the model to answer using the tool result.
                small_identity = (
                    "CYN-X identity: You are Cyn, a playful, curious AI companion. "
                    "Answer in Cyn's voice and style. Use the provided tool result as the authoritative source for this reply. "
                    "Do not call any tools, do not request external information, and do not consult memory for this response."
                )
                final_messages = [
                    {"role": "system", "content": small_identity},
                    {"role": "user", "content": text},
                ]
                # include the tool messages (they contain result + instruction)
                final_messages.extend(tool_messages)

                if request_id:
                    terminal.ollama("OLLAMA CALL", f"id={request_id} phase=final (minimal prompt)")

                final_response = self.ollama.chat(messages=final_messages, tools=None)
            else:
                final_response = self.ollama.chat(messages=messages, tools=None)

            terminal.timing(f"[FINAL OLLAMA TIME] {time.perf_counter() - final_start:.2f}s")
            assistant_text = (final_response.get("message") or {}).get("content") or str(final_response)

            terminal.model("FINAL MESSAGES")
            if use_minimal:
                terminal.json(final_messages)
            else:
                terminal.json(messages)
            terminal.model("FINAL MODEL RESPONSE")
            terminal.dim(assistant_text)
            return assistant_text

        # No tool call was requested by the model; fall back to the original generation flow.
        assistant_text = (
            (response.get("message") or {}).get("content")
            or response.get("response")
            or response.get("text")
            or str(response)
        )
        terminal.model("FINAL MODEL RESPONSE")
        terminal.dim(assistant_text)
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