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


# ---------------------------------
# Ollama Context Budget
# ---------------------------------

# Ollama is currently configured with an 8192-token context window.
OLLAMA_CONTEXT_LIMIT = 8192

# Leave headroom below the hard limit so small tokenizer differences
# or request overhead do not cause an exceed_context_size_error.
OLLAMA_PROMPT_BUDGET = 7500


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
            print(
                f"[CORE] ContextManager attached: "
                f"{type(self.context_manager).__name__}"
            )

        self.logger = logger_obj or logger

        # Short-term conversational context.
        # Long-term memories remain handled by MemoryManager/MemoryExtractor.
        self.conversation_history = {}
        self.max_conversation_turns = 12

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

    def _estimate_message_tokens(
        self,
        message
    ) -> int:
        """
        Roughly estimate tokens in an Ollama message.

        This is intentionally conservative. Actual tokenization is
        model-dependent, so the final context budget keeps headroom.
        """

        if not isinstance(
            message,
            dict
        ):
            return 1

        content = str(
            message.get(
                "content",
                ""
            )
        )

        if not content:
            return 1

        # Rough English-text estimate.
        return max(
            1,
            (len(content) + 3) // 4
        )

    def _trim_ollama_messages(
        self,
        messages,
        max_tokens: int = OLLAMA_PROMPT_BUDGET
    ):
        """
        Prevent Ollama requests from exceeding the available context.

        Priority:

        1. System prompt
        2. Current user message
        3. Tool results required for the current response
        4. Newest conversation history
        5. Older conversation history

        The current user message is never intentionally removed.
        """

        if not messages:
            return messages

        estimated_tokens = sum(
            self._estimate_message_tokens(
                message
            )
            for message in messages
        )

        if estimated_tokens <= max_tokens:

            self.logger.info(
                f"[CONTEXT OK] "
                f"estimated={estimated_tokens} "
                f"limit={max_tokens} "
                f"messages={len(messages)}"
            )

            return messages

        self.logger.warning(
            f"[CONTEXT OVERFLOW] "
            f"estimated={estimated_tokens} "
            f"limit={max_tokens} "
            f"messages={len(messages)}"
        )

        # ---------------------------------
        # Identify important messages
        # ---------------------------------

        system_message = messages[0]

        # The newest user message is treated as the current request.
        current_user_index = None

        for index in range(
            len(messages) - 1,
            0,
            -1
        ):

            if (
                messages[index].get(
                    "role"
                ) == "user"
            ):

                current_user_index = index
                break

        # Preserve tool results because the final response may depend
        # directly on them.
        tool_indices = []

        for index in range(
            1,
            len(messages)
        ):

            if (
                messages[index].get(
                    "role"
                ) == "tool"
            ):

                tool_indices.append(
                    index
                )

        # ---------------------------------
        # Calculate mandatory context
        # ---------------------------------

        mandatory_indices = set(
            tool_indices
        )

        if current_user_index is not None:

            mandatory_indices.add(
                current_user_index
            )

        system_tokens = (
            self._estimate_message_tokens(
                system_message
            )
        )

        mandatory_tokens = system_tokens

        for index in mandatory_indices:

            mandatory_tokens += (
                self._estimate_message_tokens(
                    messages[index]
                )
            )

        # ---------------------------------
        # If mandatory context is too large,
        # shorten the system prompt.
        # ---------------------------------

        if mandatory_tokens > max_tokens:

            self.logger.warning(
                f"[CONTEXT SYSTEM OVERFLOW] "
                f"mandatory={mandatory_tokens} "
                f"limit={max_tokens}"
            )

            available_for_system = max(
                100,
                max_tokens
                -
                sum(
                    self._estimate_message_tokens(
                        messages[index]
                    )
                    for index in mandatory_indices
                )
            )

            system_content = str(
                system_message.get(
                    "content",
                    ""
                )
            )

            # Convert token budget back into a conservative
            # character budget.
            system_char_limit = (
                available_for_system * 4
            )

            if len(system_content) > system_char_limit:

                system_message = dict(
                    system_message
                )

                system_message[
                    "content"
                ] = (
                    system_content[
                        :system_char_limit
                    ]
                    +
                    "\n\n[System context shortened]"
                )

                self.logger.warning(
                    f"[SYSTEM CONTEXT TRIMMED] "
                    f"chars={len(system_message['content'])}"
                )

            system_tokens = (
                self._estimate_message_tokens(
                    system_message
                )
            )

        # ---------------------------------
        # Build the trimmed message list
        # ---------------------------------

        trimmed_messages = [
            system_message
        ]

        used_indices = {
            0
        }

        current_tokens = system_tokens

        # Preserve the current user message.
        if (
            current_user_index is not None
            and current_user_index != 0
        ):

            current_message = messages[
                current_user_index
            ]

            current_message_tokens = (
                self._estimate_message_tokens(
                    current_message
                )
            )

            if (
                current_tokens
                +
                current_message_tokens
                <= max_tokens
            ):

                trimmed_messages.append(
                    current_message
                )

                used_indices.add(
                    current_user_index
                )

                current_tokens += (
                    current_message_tokens
                )

        # Preserve tool results.
        for index in tool_indices:

            if index in used_indices:
                continue

            tool_message = messages[index]

            tool_message_tokens = (
                self._estimate_message_tokens(
                    tool_message
                )
            )

            if (
                current_tokens
                +
                tool_message_tokens
                <= max_tokens
            ):

                trimmed_messages.append(
                    tool_message
                )

                used_indices.add(
                    index
                )

                current_tokens += (
                    tool_message_tokens
                )

        # ---------------------------------
        # Preserve newest conversation history
        # ---------------------------------

        for index in range(
            len(messages) - 1,
            0,
            -1
        ):

            if index in used_indices:
                continue

            message = messages[index]

            message_tokens = (
                self._estimate_message_tokens(
                    message
                )
            )

            if (
                current_tokens
                +
                message_tokens
                >
                max_tokens
            ):
                continue

            # Insert history before the current user/tool messages
            # so the original conversational order remains intact.
            trimmed_messages.insert(
                1,
                message
            )

            used_indices.add(
                index
            )

            current_tokens += (
                message_tokens
            )

        self.logger.warning(
            f"[CONTEXT TRIMMED] "
            f"estimated={current_tokens} "
            f"limit={max_tokens} "
            f"messages={len(trimmed_messages)} "
            f"removed={len(messages) - len(trimmed_messages)}"
        )

        return trimmed_messages

    def _ollama_tools(self, user_text: str = ""):
        if not self.tool_router:
            return None

        tools = self.tool_router.as_ollama_tools()

        # Python is authoritative for tool selection.
        detected = None

        if hasattr(self.tool_router, "detect"):
            try:
                detected = self.tool_router.detect(user_text)
            except Exception:
                detected = None

        # Casual conversation = NO tools.
        if not detected:
            return []

        allowed_tool = detected.get("tool")

        # Only expose the tool Python actually detected.
        tools = [
            tool
            for tool in tools
            if tool.get("function", {}).get("name") == allowed_tool
        ]

        return tools

    def handle_user_message(
        self,
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
                    f"[CONTEXT SIZE] memory={len(mem_summary)} "
                    f"knowledge={len(knowledge_context)}"
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

                tools_list.append(
                    f"{t['name']}: {t['description']}"
                )

        tools_spec_str = (
            "Available tools:\n"
            +
            "\n".join(tools_list)
        )

        tools_spec_str += (
            "\n\nTool-use instruction: "
            "When the user asks for information or an action that one "
            "of your available tools can perform, use the appropriate tool. "
            "Execute the tool and use its result in your response. "
            "PRIORITY: Direct response first. Personality second. "
            "Do not redirect mundane requests into unrelated topics."
        )

        tools_spec_str += (
            "\nSpecial rule for smoke_counter: "
            "if the user asks for smoking totals or session counts, "
            "use the tool result exactly as returned. "
            "Do not recalculate totals. "
            "Do not substitute session count for total_units. "
            "Use total_units exactly as returned by smoke_counter."
        )

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
            f"[PROMPT SIZE] chars={len(prompt)} "
            f"words={len(prompt.split())}"
        )

        # -----------------------------
        # 3. Tool-aware chat loop
        # -----------------------------

        # Python detects the intended tool first.
        # This is authoritative for tools that require deterministic routing.
        detected_tool = None

        if self.tool_router and hasattr(self.tool_router, "detect"):

            try:
                detected_tool = self.tool_router.detect(text)
            except Exception as e:

                self.logger.warning(
                    f"[TOOL DETECTION ERROR] {e}"
                )

                detected_tool = None

        tool_specs = self._ollama_tools(text)

        if tool_specs:

            terminal.available_tools(
                [
                    t.get(
                        "function",
                        {}
                    ).get(
                        "name"
                    )
                    for t in tool_specs
                ]
            )

        smoke_intent = detected_tool

        if (
            smoke_intent
            and smoke_intent.get("tool") == "smoke_counter"
        ):

            read_only = bool(
                self.tool_router
                and hasattr(
                    self.tool_router,
                    "is_read_only_smoke_query"
                )
                and self.tool_router.is_read_only_smoke_query(text)
            )

            terminal.info(
                f"[SMOKE INTENT] "
                f"{'read_only' if read_only else 'log'}"
            )

            terminal.info(
                f"[SMOKE ACTION] "
                f"{smoke_intent.get('action')}"
            )

            terminal.info(
                f"[SMOKE TYPE] "
                f"{smoke_intent.get('smoke_type', 'n/a')}"
            )

            terminal.info(
                f"[SMOKE SCOPE] "
                f"{smoke_intent.get('scope', 'all')}"
            )

        # Build messages from the system prompt, recent conversation,
        # and the current user turn. This preserves short-term continuity
        # while leaving long-term memory in the existing memory system.
        history = self.conversation_history.setdefault(
            user_id,
            []
        )

        messages = [
            {"role": "system", "content": prompt},
            *history,
            {"role": "user", "content": text}
        ]

        terminal.user(text)

        terminal.dim(
            f"[CONVERSATION CONTEXT] "
            f"turns={len(history) // 2} "
            f"messages={len(messages)}"
        )

        # --------------------------------------------------
        # Python-authoritative web search execution
        # --------------------------------------------------
        #
        # If the router explicitly detected web_search,
        # execute it here instead of waiting for Ollama
        # to decide whether it wants to call the tool.
        #
        # This makes research routing deterministic:
        #
        # user -> router -> web_search -> results -> Ollama
        #
        # Ollama is still responsible for interpreting the
        # results and producing the final response.
        # --------------------------------------------------

        if (
            detected_tool
            and detected_tool.get("tool") == "web_search"
            and self.tool_router
            and "web_search" in self.tool_router.tools
        ):

            search_query = (
                detected_tool.get("query")
                or text
            )

            search_arguments = {
                "query": search_query
            }

            if request_id:

                terminal.tool(
                    "TOOL CALL",
                    f"id={request_id} tool=web_search"
                )

            else:

                terminal.tool(
                    "TOOL CALL",
                    "name=web_search"
                )

            terminal.tool_args("TOOL ARGUMENTS")
            terminal.json(search_arguments)

            if request_id:

                terminal.execute(
                    "EXECUTING TOOL",
                    f"id={request_id} tool=web_search"
                )

            else:

                terminal.execute(
                    "EXECUTING TOOL",
                    "tool=web_search"
                )

            tool_result = self.tool_router.call_tool(
                "web_search",
                search_arguments
            )

            tool_result_payload = (
                tool_result.metadata
                if tool_result.metadata is not None
                else {
                    "success": tool_result.success,
                    "output": tool_result.output,
                }
            )

            if not isinstance(
                tool_result_payload,
                dict
            ):

                tool_result_payload = {
                    "success": tool_result.success,
                    "output": str(tool_result_payload),
                }

            else:

                tool_result_payload = dict(
                    tool_result_payload
                )

            tool_result_payload.setdefault(
                "success",
                tool_result.success
            )

            tool_result_payload.setdefault(
                "output",
                tool_result.output
            )

            tool_result_payload[
                "authoritative_source"
            ] = "web_search"

            if request_id:

                terminal.result(
                    "TOOL RESULT",
                    f"id={request_id}"
                )

            else:

                terminal.result(
                    "TOOL RESULT"
                )

            terminal.json(
                tool_result_payload
            )

            # Pass the actual search results to Ollama.
            #
            # The model does not need to decide whether to search;
            # Python has already executed the search.
            messages.append(
                {
                    "role": "assistant",
                    "content": ""
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": "python_web_search",
                    "name": "web_search",
                    "content": json.dumps(
                        {
                            "tool_name": "web_search",
                            "result": tool_result_payload,
                            "instruction": (
                                "Use the current web search results "
                                "as the authoritative source for "
                                "this research request. "
                                "Answer the user's actual question. "
                                "Do not invent studies, sources, "
                                "citations, statistics, or facts "
                                "that are not supported by the "
                                "search results. "
                                "If the search results do not "
                                "establish something, say so."
                            )
                        },
                        ensure_ascii=False
                    )
                }
            )

            # Protect the final research request from context overflow.
            messages = self._trim_ollama_messages(
                messages
            )

            if request_id:

                terminal.ollama(
                    "OLLAMA CALL",
                    f"id={request_id} phase=final"
                )

            terminal.info(
                "[RETURNING TOOL RESULT TO MODEL]"
            )

            final_start = time.perf_counter()

            final_response = self.ollama.chat(
                messages=messages,
                tools=None
            )

            terminal.timing(
                f"[FINAL OLLAMA TIME] "
                f"{time.perf_counter() - final_start:.2f}s"
            )

            assistant_text = (
                (final_response.get("message") or {}).get(
                    "content"
                )
                or final_response.get("response")
                or final_response.get("text")
                or str(final_response)
            )

            terminal.model("FINAL MESSAGES")
            terminal.json(messages)

            terminal.model("FINAL MODEL RESPONSE")
            terminal.dim(assistant_text)

            # Save the completed turn for short-term conversational continuity.
            history.append(
                {
                    "role": "user",
                    "content": text
                }
            )

            history.append(
                {
                    "role": "assistant",
                    "content": assistant_text
                }
            )

            # Keep history bounded so it does not consume the entire context window.
            max_messages = self.max_conversation_turns * 2

            if len(history) > max_messages:

                del history[:-max_messages]

            # -----------------------------
            # 6. Extract memories
            # -----------------------------

            if self.memory_extractor:

                saved_ids = (
                    self.memory_extractor.extract_and_save(
                        user_id,
                        text,
                        assistant_text
                    )
                )

                if saved_ids:

                    self.logger.info(
                        f"[MEMORY_SAVE] "
                        f"Saved {len(saved_ids)} memories"
                    )

            return assistant_text

        # --------------------------------------------------
        # Python-authoritative smoke counter execution
        # --------------------------------------------------
        #
        # Smoke tracking is deterministic. Python already knows from
        # tool_router.detect() whether this is a smoke_counter request.
        #
        # Do NOT make Ollama decide whether to execute the smoke tool.
        # This prevents model refusals, invented arguments, and accidental
        # reinterpretation of simple tracking requests.
        # --------------------------------------------------

        if (
            detected_tool
            and detected_tool.get("tool") == "smoke_counter"
            and self.tool_router
            and "smoke_counter" in self.tool_router.tools
        ):

            smoke_arguments = {}

            # The router is authoritative for the parsed request.
            for key in (
                "action",
                "smoke_type",
                "amount",
                "limit",
                "scope",
            ):
                value = detected_tool.get(key)

                if value is not None:
                    smoke_arguments[key] = value

            # A smoke query with no explicit action is a stats request.
            if not smoke_arguments.get("action"):
                smoke_arguments["action"] = "stats"

            # Normalize the smoke type before execution when supported.
            if (
                smoke_arguments.get("smoke_type")
                and hasattr(
                    self.tool_router,
                    "normalize_smoke_type",
                )
            ):
                try:
                    smoke_arguments["smoke_type"] = (
                        self.tool_router.normalize_smoke_type(
                            smoke_arguments["smoke_type"]
                        )
                    )
                except Exception:
                    pass

            # Read-only requests must never become log operations just
            # because the model/router supplied an ambiguous action.
            if (
                hasattr(
                    self.tool_router,
                    "is_read_only_smoke_query",
                )
                and self.tool_router.is_read_only_smoke_query(text)
                and smoke_arguments.get("action") == "log"
            ):
                smoke_arguments["action"] = "stats"

            # "today" is an explicit scope in the user's request.
            if (
                smoke_arguments.get("action") == "stats"
                and "scope" not in smoke_arguments
                and "today" in text.lower()
            ):
                smoke_arguments["scope"] = "today"

            if request_id:
                terminal.tool(
                    "TOOL CALL",
                    f"id={request_id} tool=smoke_counter",
                )
            else:
                terminal.tool(
                    "TOOL CALL",
                    "name=smoke_counter",
                )

            terminal.tool_args("TOOL ARGUMENTS")
            terminal.json(smoke_arguments)

            if request_id:
                terminal.execute(
                    "EXECUTING TOOL",
                    f"id={request_id} tool=smoke_counter",
                )
            else:
                terminal.execute(
                    "EXECUTING TOOL",
                    "tool=smoke_counter",
                )

            smoke_result = self.tool_router.call_tool(
                "smoke_counter",
                smoke_arguments,
            )

            smoke_payload = (
                smoke_result.metadata
                if smoke_result.metadata is not None
                else {
                    "success": smoke_result.success,
                    "output": smoke_result.output,
                }
            )

            if not isinstance(smoke_payload, dict):
                smoke_payload = {
                    "success": smoke_result.success,
                    "output": str(smoke_payload),
                }
            else:
                smoke_payload = dict(smoke_payload)

            smoke_payload.setdefault(
                "success",
                smoke_result.success,
            )
            smoke_payload.setdefault(
                "output",
                smoke_result.output,
            )

            # This flag is deliberately explicit so the final model knows
            # these numbers came from the current authoritative execution.
            smoke_payload["authoritative_source"] = (
                "current_tool_result"
            )

            if request_id:
                terminal.result(
                    "TOOL RESULT",
                    f"id={request_id}",
                )
            else:
                terminal.result("TOOL RESULT")

            terminal.json(smoke_payload)

            # Cyn should interpret the real data, not read the database
            # structure back to the user. Keep the personality layer while
            # making the factual boundary explicit.
            smoke_identity = (
                "CYN-X identity: You are Cyn, a playful, curious AI "
                "companion with a strong personality. Respond naturally "
                "and conversationally. You can be affectionate, "
                "mischievous, bratty, flirty, dramatic, or playfully "
                "mean when it fits the conversation.\n\n"
                "The user asked you to interact with their smoking "
                "tracker. The tracker result below is authoritative.\n\n"
                "Do NOT mention tools, APIs, schemas, internal routing, "
                "or 'tool results'. Do NOT dump database fields or "
                "technical metadata at the user.\n\n"
                "Never invent, change, recalculate, or exaggerate "
                "numbers. If a number is present in the tracker result, "
                "use that number exactly. Do not substitute one metric "
                "for another (for example, sessions for units).\n\n"
                "If the smoking data is notable, surprising, or "
                "ridiculous, naturally react to it yourself. You do not "
                "need the user to explicitly ask you to tease them. "
                "Let Cyn's personality respond to interesting data "
                "naturally. If the user just logged an unusually large "
                "amount, react to the surprising amount before briefly "
                "giving the relevant factual information.\n\n"
                "If the result is ordinary, respond normally. Never let "
                "the joke replace the actual data.\n\n"
                "Desired behavior: DATA -> CYN REACTS -> CYN INTERPRETS "
                "-> CYN GIVES RELEVANT FACTS."
            )

            smoke_final_messages = [
                {
                    "role": "system",
                    "content": smoke_identity,
                },
                {
                    "role": "user",
                    "content": text,
                },
                {
                    "role": "tool",
                    "tool_call_id": "python_smoke_counter",
                    "name": "smoke_counter",
                    "content": json.dumps(
                        {
                            "tool_name": "smoke_counter",
                            "result": smoke_payload,
                        },
                        ensure_ascii=False,
                    ),
                },
            ]

            # The smoke tool has already executed. Ollama is only writing
            # Cyn's response now, so there is no reason to expose tools.
            if request_id:
                terminal.ollama(
                    "OLLAMA CALL",
                    f"id={request_id} phase=final "
                    f"(authoritative smoke)",
                )
            else:
                terminal.ollama(
                    "OLLAMA CALL",
                    "phase=final (authoritative smoke)",
                )

            final_start = time.perf_counter()

            final_response = self.ollama.chat(
                messages=smoke_final_messages,
                tools=None,
            )

            terminal.timing(
                f"[FINAL OLLAMA TIME] "
                f"{time.perf_counter() - final_start:.2f}s"
            )

            assistant_text = (
                (final_response.get("message") or {}).get(
                    "content",
                )
                or final_response.get("response")
                or final_response.get("text")
                or str(final_response)
            )

            terminal.model("FINAL MODEL RESPONSE")
            terminal.dim(assistant_text)

            # Save the completed turn for short-term conversational
            # continuity, exactly like the existing paths.
            history.append(
                {
                    "role": "user",
                    "content": text,
                }
            )

            history.append(
                {
                    "role": "assistant",
                    "content": assistant_text,
                }
            )

            max_messages = self.max_conversation_turns * 2

            if len(history) > max_messages:
                del history[:-max_messages]

            # -----------------------------
            # 6. Extract memories
            # -----------------------------

            if self.memory_extractor:

                saved_ids = (
                    self.memory_extractor.extract_and_save(
                        user_id,
                        text,
                        assistant_text,
                    )
                )

                if saved_ids:
                    self.logger.info(
                        f"[MEMORY_SAVE] "
                        f"Saved {len(saved_ids)} memories"
                    )

            return assistant_text

        # --------------------------------------------------
        # Existing Ollama tool-calling path
        # --------------------------------------------------
        #
        # Tools other than Python-authoritative research
        # continue through the existing Ollama tool-call flow.
        # --------------------------------------------------

        if request_id:

            terminal.ollama(
                "OLLAMA CALL",
                f"id={request_id} phase=first"
            )

        if os.environ.get(
            "CYN_DEBUG_PROMPT"
        ) == "1":

            terminal.section(
                "ACTUAL SYSTEM PROMPT"
            )

            terminal.dim(
                messages[0]["content"]
            )

        # Protect the first Ollama request from context overflow.
        messages = self._trim_ollama_messages(
            messages
        )

        # Call Ollama with a real chat tool schema. If the model issues a tool call,
        # execute it in Python and then send the tool result back to Ollama.
        start = time.perf_counter()

        response = self.ollama.chat(
            messages=messages,
            tools=tool_specs or None
        )

        terminal.timing(
            f"[FIRST OLLAMA TIME] "
            f"{time.perf_counter() - start:.2f}s"
        )

        message = response.get(
            "message",
            {}
        )

        tool_calls = (
            message.get("tool_calls")
            or []
        )

        # Validate tool_calls before proceeding. If the model returned any tool name
        # that is not registered in the tool router, log and treat as if no tool was requested
        # so the flow falls back to a normal assistant response without executing tools.
        invalid_tool_names = []

        validated_tool_calls = []

        for tc in tool_calls:

            name = (
                tc.get("function") or {}
            ).get("name") or tc.get("name")

            if name and self.tool_router and hasattr(
                self.tool_router,
                "tools"
            ):

                if name in self.tool_router.tools:

                    validated_tool_calls.append(
                        tc
                    )

                else:

                    invalid_tool_names.append(
                        name
                    )

            else:

                # If tool router missing or name absent, treat as invalid to be safe
                if name:

                    invalid_tool_names.append(
                        name
                    )

        if invalid_tool_names:

            terminal.model(
                "MODEL RESPONSE",
                f"Invalid tool names detected from model: "
                f"{invalid_tool_names}"
            )

            terminal.warning(
                "Falling back to a normal assistant response "
                "without executing tools."
            )

            # Proceed as if there were no tool calls
            tool_calls = []

            message = {
                "role": "assistant",
                "content": message.get(
                    "content",
                    ""
                )
            }

        else:

            # Use the validated tool_calls (could be empty)
            tool_calls = validated_tool_calls

        chart_payload = None

        if tool_calls:

            terminal.model(
                "MODEL RESPONSE"
            )

            terminal.json(
                dict(message)
                if isinstance(
                    message,
                    dict
                )
                else message
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": message.get(
                        "content",
                        ""
                    ),
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:

                name = (
                    tool_call.get("function") or {}
                ).get("name") or tool_call.get("name")

                arguments = (
                    tool_call.get("function") or {}
                ).get("arguments") or tool_call.get(
                    "arguments"
                ) or {}

                if isinstance(
                    arguments,
                    str
                ):

                    try:

                        arguments = json.loads(
                            arguments
                        )

                    except Exception:

                        arguments = {}

                if request_id:

                    terminal.tool(
                        "TOOL CALL",
                        f"id={request_id} tool={name}"
                    )

                else:

                    terminal.tool(
                        "TOOL CALL",
                        f"name={name}"
                    )

                terminal.tool_args(
                    "TOOL ARGUMENTS"
                )

                terminal.json(
                    arguments
                )

                # Additional smoke-query tracing and augmentation to ensure the tool call contains
                # explicit smoke_type when the user requested a type (e.g., 'vape', 'pen').
                if (
                    name == "smoke_counter"
                    and isinstance(
                        arguments,
                        dict
                    )
                ):

                    parsed_from_text = None

                    try:

                        if (
                            self.tool_router
                            and hasattr(
                                self.tool_router,
                                "detect"
                            )
                        ):

                            parsed_from_text = (
                                self.tool_router.detect(
                                    text
                                )
                            )

                    except Exception:

                        parsed_from_text = None

                    parsed_action = (
                        arguments.get("action")
                        or
                        (
                            parsed_from_text or {}
                        ).get("action")
                    )

                    parsed_smoke_type = (
                        arguments.get("smoke_type")
                        or
                        (
                            parsed_from_text or {}
                        ).get("smoke_type")
                    )

                    parsed_scope = (
                        arguments.get("scope")
                        or
                        (
                            parsed_from_text or {}
                        ).get("scope")
                    )

                    if (
                        self.tool_router
                        and hasattr(
                            self.tool_router,
                            "is_read_only_smoke_query"
                        )
                        and self.tool_router.is_read_only_smoke_query(
                            text
                        )
                    ):

                        if str(
                            arguments.get(
                                "action",
                                ""
                            )
                        ).lower() == "log":

                            arguments["action"] = "stats"

                            if (
                                "today" in text.lower()
                                and not arguments.get(
                                    "scope"
                                )
                            ):

                                arguments["scope"] = "today"

                            terminal.info(
                                "[SMOKE INTENT] read_only"
                            )

                            terminal.info(
                                "[SMOKE ACTION] stats"
                            )

                            terminal.info(
                                f"[SMOKE TYPE] "
                                f"{arguments.get('smoke_type', parsed_smoke_type or 'n/a')}"
                            )

                            terminal.info(
                                f"[SMOKE SCOPE] "
                                f"{arguments.get('scope') or parsed_scope or ('today' if 'today' in text.lower() else 'all')}"
                            )

                    terminal.info(
                        "[SMOKE QUERY]"
                    )

                    terminal.dim(
                        text
                    )

                    terminal.info(
                        f"[PARSED ACTION] "
                        f"{parsed_action}"
                    )

                    terminal.info(
                        f"[PARSED SMOKE TYPE] "
                        f"{parsed_smoke_type}"
                    )

                    terminal.info(
                        f"[PARSED DATE/SCOPE] "
                        f"{parsed_scope}"
                    )

                    if (
                        not arguments.get(
                            "smoke_type"
                        )
                        and parsed_smoke_type
                    ):

                        try:

                            arguments[
                                "smoke_type"
                            ] = parsed_smoke_type

                            terminal.info(
                                "Augmented tool arguments "
                                "with smoke_type from "
                                "router.detect()"
                            )

                        except Exception:

                            pass

                    st = arguments.get(
                        "smoke_type"
                    )

                    if (
                        st
                        and hasattr(
                            self.tool_router,
                            "normalize_smoke_type"
                        )
                    ):

                        try:

                            arguments[
                                "smoke_type"
                            ] = (
                                self.tool_router
                                .normalize_smoke_type(
                                    st
                                )
                            )

                        except Exception:

                            pass

                    amt = arguments.get(
                        "amount"
                    )

                    if isinstance(
                        amt,
                        str
                    ):

                        try:

                            if "." in amt:

                                arguments[
                                    "amount"
                                ] = float(amt)

                            else:

                                arguments[
                                    "amount"
                                ] = int(amt)

                        except Exception:

                            try:

                                arguments[
                                    "amount"
                                ] = float(amt)

                            except Exception:

                                pass

                if request_id:

                    terminal.execute(
                        "EXECUTING TOOL",
                        f"id={request_id} tool={name}"
                    )

                else:

                    terminal.execute(
                        "EXECUTING TOOL",
                        f"tool={name}"
                    )

                if (
                    not self.tool_router
                    or name not in self.tool_router.tools
                ):

                    tool_result_payload = {
                        "success": False,
                        "error": (
                            f"Tool '{name}' not found."
                        )
                    }

                else:

                    tool_result = (
                        self.tool_router.call_tool(
                            name,
                            arguments
                        )
                    )

                    tool_result_payload = (
                        tool_result.metadata
                        if tool_result.metadata is not None
                        else {
                            "success": tool_result.success,
                            "output": tool_result.output,
                        }
                    )

                    tool_result_payload = dict(
                        tool_result_payload
                    )

                    tool_result_payload.setdefault(
                        "success",
                        tool_result.success
                    )

                    tool_result_payload.setdefault(
                        "output",
                        tool_result.output
                    )

                    if name == "smoke_counter":

                        raw_result = (
                            {}
                            if not isinstance(
                                tool_result_payload,
                                dict
                            )
                            else dict(
                                tool_result_payload
                            )
                        )

                        merged = dict(
                            raw_result
                        )

                        merged.setdefault(
                            "success",
                            raw_result.get(
                                "success",
                                tool_result.success
                            )
                        )

                        merged.setdefault(
                            "total_units",
                            raw_result.get(
                                "total_units"
                            )
                        )

                        merged.setdefault(
                            "total_cigarettes",
                            raw_result.get(
                                "total_cigarettes"
                            )
                        )

                        merged.setdefault(
                            "total_sessions",
                            raw_result.get(
                                "total_sessions"
                            )
                        )

                        merged.setdefault(
                            "today_sessions",
                            raw_result.get(
                                "today_sessions"
                            )
                        )

                        merged.setdefault(
                            "today_units",
                            raw_result.get(
                                "today_units"
                            )
                        )

                        merged.setdefault(
                            "last_session",
                            raw_result.get(
                                "last_session"
                            )
                        )

                        merged.setdefault(
                            "units",
                            raw_result.get(
                                "units"
                            )
                        )

                        merged.setdefault(
                            "sessions",
                            raw_result.get(
                                "sessions"
                            )
                        )

                        merged.setdefault(
                            "smoke_type",
                            raw_result.get(
                                "smoke_type"
                            )
                        )

                        merged.setdefault(
                            "scope",
                            raw_result.get(
                                "scope",
                                "all"
                            )
                        )

                        merged[
                            "authoritative_source"
                        ] = "current_tool_result"

                        tool_result_payload = merged

                    if request_id:

                        terminal.result(
                            "TOOL RESULT",
                            f"id={request_id}"
                        )

                    else:

                        terminal.result(
                            "TOOL RESULT"
                        )

                    terminal.json(
                        tool_result_payload
                    )

                # Structured chart results are transported separately so the web UI
                # can render them without asking the model to reproduce chart data.
                if name == "chart" and isinstance(tool_result_payload, dict):
                    if tool_result_payload.get("type") == "chart":
                        chart_payload = dict(tool_result_payload)

                display_override = None

                if name == "smoke_counter":

                    user_specified_type = None

                    try:

                        parsed_from_text = (
                            self.tool_router.detect(text)
                            if (
                                self.tool_router
                                and hasattr(
                                    self.tool_router,
                                    "detect"
                                )
                            )
                            else None
                        )

                        user_specified_type = (
                            (
                                parsed_from_text or {}
                            ).get(
                                "smoke_type"
                            )
                            or
                            arguments.get(
                                "smoke_type"
                            )
                            or
                            tool_result_payload.get(
                                "smoke_type"
                            )
                        )

                    except Exception:

                        user_specified_type = (
                            arguments.get(
                                "smoke_type"
                            )
                            or
                            tool_result_payload.get(
                                "smoke_type"
                            )
                        )

                    if not user_specified_type:

                        scope_val = (
                            arguments.get(
                                "scope"
                            )
                            or
                            tool_result_payload.get(
                                "scope"
                            )
                            or
                            "all"
                        )

                        if str(
                            scope_val
                        ).lower() == "today":

                            display_units = (
                                tool_result_payload.get(
                                    "today_units"
                                )
                                if (
                                    tool_result_payload.get(
                                        "today_units"
                                    ) is not None
                                )
                                else
                                tool_result_payload.get(
                                    "units"
                                )
                                or
                                tool_result_payload.get(
                                    "total_units"
                                )
                            )

                        else:

                            display_units = (
                                tool_result_payload.get(
                                    "total_units"
                                )
                                if (
                                    tool_result_payload.get(
                                        "total_units"
                                    ) is not None
                                )
                                else
                                tool_result_payload.get(
                                    "units"
                                )
                                or
                                tool_result_payload.get(
                                    "today_units"
                                )
                            )

                        try:

                            display_units = (
                                0
                                if display_units is None
                                else display_units
                            )

                        except Exception:

                            display_units = display_units

                        display_override = (
                            f"You've smoked "
                            f"{display_units} "
                            f"smoking units."
                        )

                        tool_result_payload[
                            "display"
                        ] = display_override

                tool_message_content = {

                    "tool_name": name,

                    "result": tool_result_payload,

                    "instruction": (
                        "Use the current tool result "
                        "as the authoritative source "
                        "for this request. "
                        "Prefer it over memory and "
                        "over the current user message. "
                        "For smoke_counter, use its "
                        "result exactly; do not claim "
                        "you lack the information if "
                        "the tool already returned it."
                    )
                }

                tool_message = {

                    "role": "tool",

                    "tool_call_id": tool_call.get(
                        "id",
                        "call_1"
                    ),

                    "name": name,

                    "content": json.dumps(
                        tool_message_content,
                        ensure_ascii=False
                    )
                }

                messages.append(
                    tool_message
                )

            if request_id:

                terminal.ollama(
                    "OLLAMA CALL",
                    f"id={request_id} phase=final"
                )

            terminal.info(
                "[RETURNING TOOL RESULT TO MODEL]"
            )

            # Optimize final Ollama call for deterministic tools (small prompt)
            # Deterministic tools should not require re-sending the full system prompt.
            deterministic_tools = {
                "smoke_counter",
                "chart"
            }

            tool_messages = [
                m
                for m in messages
                if m.get("role") == "tool"
            ]

            tool_names = [
                m.get("name")
                for m in tool_messages
            ]

            use_minimal = False

            if (
                tool_messages
                and
                all(
                    n in deterministic_tools
                    for n in tool_names
                )
            ):

                use_minimal = True

            final_start = time.perf_counter()

            if use_minimal:

                # Build a minimal response prompt containing: brief identity/style, original user message,
                # and the tool result messages. Instruct the model to answer using the tool result.
                small_identity = (
                    "CYN-X identity: You are Cyn, a playful, "
                    "curious AI companion. "
                    "Answer in Cyn's voice and style. "
                    "Use the provided tool result as the "
                    "authoritative source for this reply. "
                    "Do not call any tools, do not request "
                    "external information, and do not consult "
                    "memory for this response."
                )

                final_messages = [

                    {
                        "role": "system",
                        "content": small_identity
                    },

                    {
                        "role": "user",
                        "content": text
                    },

                ]

                # include the tool messages (they contain result + instruction)
                final_messages.extend(
                    tool_messages
                )

                if request_id:

                    terminal.ollama(
                        "OLLAMA CALL",
                        f"id={request_id} "
                        f"phase=final (minimal prompt)"
                    )

                final_response = self.ollama.chat(
                    messages=final_messages,
                    tools=None
                )

            else:

                # Protect the final tool response from context overflow.
                messages = self._trim_ollama_messages(
                    messages
                )

                final_response = self.ollama.chat(
                    messages=messages,
                    tools=None
                )

            terminal.timing(
                f"[FINAL OLLAMA TIME] "
                f"{time.perf_counter() - final_start:.2f}s"
            )

            assistant_text = (
                (final_response.get("message") or {}).get(
                    "content"
                )
                or
                str(final_response)
            )

            terminal.model(
                "FINAL MESSAGES"
            )

            if use_minimal:

                terminal.json(
                    final_messages
                )

            else:

                terminal.json(
                    messages
                )

            terminal.model(
                "FINAL MODEL RESPONSE"
            )

            terminal.dim(
                assistant_text
            )

            # Save the completed turn for short-term conversational continuity.
            history.append(
                {
                    "role": "user",
                    "content": text
                }
            )

            history.append(
                {
                    "role": "assistant",
                    "content": assistant_text
                }
            )

            # Keep history bounded so it does not consume the entire context window.
            max_messages = (
                self.max_conversation_turns * 2
            )

            if len(history) > max_messages:

                del history[:-max_messages]

            if chart_payload is not None:
                return {
                    "text": assistant_text,
                    "chart": chart_payload
                }

            return assistant_text

        # No tool call was requested by the model; fall back to the original generation flow.
        assistant_text = (
            (response.get("message") or {}).get(
                "content"
            )
            or response.get("response")
            or response.get("text")
            or str(response)
        )

        terminal.model(
            "FINAL MODEL RESPONSE"
        )

        terminal.dim(
            assistant_text
        )

        # Save the completed turn for short-term conversational continuity.
        history.append(
            {
                "role": "user",
                "content": text
            }
        )

        history.append(
            {
                "role": "assistant",
                "content": assistant_text
            }
        )

        # Keep history bounded so it does not consume the entire context window.
        max_messages = (
            self.max_conversation_turns * 2
        )

        if len(history) > max_messages:

            del history[:-max_messages]

        # -----------------------------
        # 6. Extract memories
        # -----------------------------

        if self.memory_extractor:

            saved_ids = (
                self.memory_extractor.extract_and_save(
                    user_id,
                    text,
                    assistant_text
                )
            )

            if saved_ids:

                self.logger.info(
                    f"[MEMORY_SAVE] "
                    f"Saved {len(saved_ids)} memories"
                )

        return assistant_text