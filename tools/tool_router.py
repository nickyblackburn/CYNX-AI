
"""
ToolRouter:
- Register tools
- Expose tool descriptions to the LLM
- Dispatch tool calls
- Log usage
"""

from typing import Dict, Any
from tools.base import BaseTool, ToolResult


class ToolRouter:

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}


    def register_tool(self, tool: BaseTool):
        self.tools[tool.name] = tool


    def list_tools(self):
        return list(self.tools.keys())


    def describe_tools(self):
        """
        Gives the AI a list of available tools.
        """
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in self.tools.values()
        ]


    def as_ollama_tools(self):
        """Convert the registered tools into Ollama function-calling schemas."""
        tools = []

        for tool in self.tools.values():

            if getattr(tool, "name", None) == "smoke_counter":

                schema = {
                    "type": "function",
                    "function": {
                        "name": "smoke_counter",
                        "description": "Track smoking sessions and retrieve smoking statistics.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "log",
                                        "stats",
                                        "recent",
                                        "last",
                                        "reset"
                                    ]
                                },
                                "smoke_type": {
                                    "type": "string",
                                    "enum": [
                                        "cigarette",
                                        "weed",
                                        "vape",
                                        "joint",
                                        "bong",
                                        "unknown"
                                    ]
                                },
                                "amount": {
                                    "type": "number"
                                },
                                "limit": {
                                    "type": "integer"
                                }
                            },
                            "required": []
                        }
                    }
                }

            elif getattr(tool, "name", None) == "web_search":

                schema = {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the internet for current information.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }

            else:

                schema = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                }

            tools.append(schema)

        return tools


    def call_tool(
        self,
        name: str,
        args: Dict[str, Any]
    ) -> ToolResult:

        print(f"[TOOL CALL] {name}")
        print(f"[ARGS] {args}")

        if name not in self.tools:
            return ToolResult(
                False,
                f"Tool '{name}' not found"
            )

        tool = self.tools[name]

        try:

            result = tool.call(args)

            print(
                f"[RESULT] {result.output}"
            )

            return result

        except Exception as e:

            return ToolResult(
                False,
                f"Tool '{name}' exception: {e}"
            )


    def normalize_smoke_type(self, text: str):
        """Normalize a freeform smoke_type string into a canonical type (pen, vape, cigarette, bong, weed, joint, unknown)."""

        if not text:
            return None

        tl = str(text).lower()

        # canonical types in priority order
        for t in [
            'cigarette',
            'cig',
            'bong',
            'vape',
            'pen',
            'weed',
            'joint'
        ]:

            if t in tl:

                if t == 'cig':
                    return 'cigarette'

                return t

        return tl.strip()


    def is_read_only_smoke_query(self, text: str) -> bool:
        """Return True when the request is asking for counts/stats/history instead of logging."""

        if not text:
            return False

        tl = str(text).lower()

        if (
            "smoke" not in tl
            and "smoked" not in tl
            and "cigarette" not in tl
            and "cig" not in tl
            and "hit" not in tl
            and "vape" not in tl
            and "pen" not in tl
            and "bong" not in tl
            and "joint" not in tl
            and "weed" not in tl
            and "rip" not in tl
        ):
            return False

        read_only_patterns = [
            r"\b(how many|how much|how often|show my|show me|what's my|what is my|what was my|what were my)\b",
            r"\b(stats|statistics|count|counts|total|totals)\b",
            r"\b(recent|last)\b",
            r"\b(today|this week|this month)\b",
            r"\b(how many .* (hit|hits|smoke|smoked|cigarette|cigarettes|vape|pen|bong|joint|weed) .* today)\b",
            r"\b(how many .* did i have today|how much did i smoke today|how many hits did i have today|how many vape hits did i have today|how many cigarettes did i have today)\b"
        ]

        return any(
            __import__('re').search(p, tl)
            for p in read_only_patterns
        )


    def detect(self, text: str):
        """
        Detect whether a message requires a tool.
        """

        if not text:
            return None

        text_lower = text.lower()


        # ========================================================
        # First: detect smoke-counter intents
        # ========================================================

        smoke_words = [
            "smoke",
            "smoked",
            "smoking",
            "cigarette",
            "cigarettes",
            "cig",
            "hit",
            "hits",
            "rip",
            "bong",
            "bongs",
            "vape",
            "vaped",
            "pen",
            "pens",
            "weed",
            "joint",
            "puff",
            "nicotine",
            "quit",
            "reset"
        ]


        def parse_number(text: str):

            # crude number parsing: digits first, then simple words
            import re

            m = re.search(r"\b(\d+)\b", text)

            if m:

                try:
                    return int(m.group(1))

                except Exception:
                    pass

            words = {
                'one': 1,
                'two': 2,
                'three': 3,
                'four': 4,
                'five': 5,
                'six': 6,
                'seven': 7,
                'eight': 8,
                'nine': 9,
                'ten': 10,
                'a': 1,
                'an': 1
            }

            for w, n in words.items():

                if f" {w} " in f" {text} ":
                    return n

            return None


        def parse_smoke_request(text: str):

            # return dict with tool and parsed args if smoking
            # intent is explicitly detected.
            import re

            tl = text.lower()

            if not any(
                re.search(
                    rf"\b{re.escape(w)}\b",
                    tl
                )
                for w in smoke_words
            ):
                return None


            # --------------------------------------------------------
            # IMPORTANT:
            #
            # Mentioning smoking is NOT enough to activate the tool.
            #
            # Example:
            #
            # "I want to take hits off my pen"
            #
            # is conversation, not a logging request.
            #
            # The tool requires an actual tracking/statistics action.
            # --------------------------------------------------------


            # reset explicit

            if re.search(
                r"\breset (my )?(smoke|smoking|smoke counter|tracker)\b",
                tl
            ):

                return {
                    "tool": "smoke_counter",
                    "action": "reset"
                }


            # read-only requests must never log

            if self.is_read_only_smoke_query(tl):

                payload = {
                    "tool": "smoke_counter",
                    "action": "stats"
                }

                smoke_type_for_stats = None

                for candidate in [
                    "vape",
                    "pen",
                    "bong",
                    "cigarette",
                    "cig",
                    "joint",
                    "weed"
                ]:

                    if re.search(
                        rf"\b{re.escape(candidate)}\b",
                        tl
                    ):

                        smoke_type_for_stats = (
                            self.normalize_smoke_type(
                                candidate
                            )
                        )

                        break

                if smoke_type_for_stats:

                    payload[
                        "smoke_type"
                    ] = smoke_type_for_stats

                if "today" in tl:

                    payload[
                        "scope"
                    ] = "today"

                if (
                    "last" in tl
                    and "what was my last" in tl
                ):

                    return {
                        "tool": "smoke_counter",
                        "action": "last"
                    }

                if (
                    "recent" in tl
                    or "recent hits" in tl
                ):

                    return {
                        "tool": "smoke_counter",
                        "action": "recent",
                        "limit": parse_number(tl) or 10
                    }

                return payload


            # last

            if (
                re.search(
                    r"\blast (hit|smoke|session)\b",
                    tl
                )
                or "what was my last" in tl
            ):

                return {
                    "tool": "smoke_counter",
                    "action": "last"
                }


            # recent

            if re.search(
                r"\b(recent|show my recent|recent hits|recent smoking)\b",
                tl
            ):

                limit = parse_number(tl) or 10

                return {
                    "tool": "smoke_counter",
                    "action": "recent",
                    "limit": limit
                }


            # stats
            # including type-filtered counts like
            # 'how many vape hits do I have today?'

            smoke_type_for_stats = None

            for candidate in [
                "vape",
                "pen",
                "bong",
                "cigarette",
                "cig",
                "joint",
                "weed"
            ]:

                if re.search(
                    rf"\b{re.escape(candidate)}\b",
                    tl
                ):

                    smoke_type_for_stats = (
                        self.normalize_smoke_type(
                            candidate
                        )
                    )

                    break

            if re.search(
                r"\b(how many|how often|how many times|show my smoking stats|show my stats|how many hits|how many times did|how much have i smoked|how much have i smoked today|how much did i smoke today|how much did i smoke)\b",
                tl
            ):

                payload = {
                    "tool": "smoke_counter",
                    "action": "stats"
                }

                if smoke_type_for_stats:

                    payload[
                        "smoke_type"
                    ] = smoke_type_for_stats

                if "today" in tl:

                    payload[
                        "scope"
                    ] = "today"

                return payload


            # --------------------------------------------------------
            # Explicit logging requests only
            # --------------------------------------------------------
            #
            # These are phrases that actually communicate that the
            # user wants the smoking tracker updated.
            #
            # A casual mention like:
            #
            # "I want to take hits off my pen"
            #
            # will NOT match this section.
            # --------------------------------------------------------

            explicit_log_patterns = [
                r"\blog\b",
                r"\badd\b",
                r"\brecord\b",
                r"\btrack\b",
                r"\btracker\b",
                r"\blogged\b",
                r"\badd(ed)?\b",
                r"\bcount this\b",
                r"\bcount that\b",
                r"\bput (this|that) in\b",
                r"\badd this\b",
                r"\badd that\b"
            ]

            explicit_logging_request = any(
                re.search(
                    pattern,
                    tl
                )
                for pattern in explicit_log_patterns
            )

            # Natural logging statements are also accepted,
            # but only when they describe an event that actually
            # happened rather than a future intention.
            natural_log_patterns = [
                r"\bi just smoked\b",
                r"\bi just had\b",
                r"\bi just took\b",
                r"\bi smoked\b",
                r"\bi took\b",
                r"\bi had\b"
            ]

            natural_logging_request = any(
                re.search(
                    pattern,
                    tl
                )
                for pattern in natural_log_patterns
            )

            if (
                explicit_logging_request
                or natural_logging_request
            ):

                amount = parse_number(tl) or 1

                smoke_type = None

                for candidate in [
                    "vape",
                    "vaped",
                    "pen",
                    "pens",
                    "bong",
                    "bongs",
                    "cigarette",
                    "cigarettes",
                    "cig",
                    "weed",
                    "joint",
                    "hit",
                    "hits",
                    "rip"
                ]:

                    if re.search(
                        rf"\b{re.escape(candidate)}\b",
                        tl
                    ):

                        if candidate in (
                            'vape',
                            'vaped'
                        ):

                            smoke_type = 'vape'

                        elif candidate in (
                            'pen',
                            'pens'
                        ):

                            smoke_type = 'pen'

                        elif candidate in (
                            'bong',
                            'bongs'
                        ):

                            smoke_type = 'bong'

                        elif candidate in (
                            'cig',
                            'cigarette',
                            'cigarettes'
                        ):

                            smoke_type = 'cigarette'

                        elif candidate in (
                            'weed',
                            'joint'
                        ):

                            smoke_type = (
                                'weed'
                                if 'weed' in tl
                                else 'joint'
                            )

                        else:

                            smoke_type = 'unknown'

                        break

                if smoke_type is None:

                    smoke_type = 'unknown'

                return {
                    "tool": "smoke_counter",
                    "action": "log",
                    "smoke_type": smoke_type,
                    "amount": amount
                }


            # --------------------------------------------------------
            # IMPORTANT:
            #
            # Do NOT use the old generic fallback:
            #
            # "if smoke_type and amount -> log"
            #
            # because that caused casual conversation containing
            # "pen", "hit", etc. to become a logging request.
            # --------------------------------------------------------

            # No explicit smoke-counter intent detected.
            return None


        smoke_req = parse_smoke_request(
            text_lower
        )

        if smoke_req:

            return smoke_req


        # ========================================================
        # Research / factual-question detection
        # ========================================================

        research_words = [
            "research",
            "studies",
            "study",
            "science",
            "scientific",
            "scientists",
            "researchers",
            "evidence",
            "academic",
            "psychology",
            "psychological",
            "medical",
            "clinical",
            "prevalence",
            "statistics",
            "according to research",
            "what does research say",
            "what do studies say",
            "look this up",
            "look it up",
            "search the internet",
            "search online",
            "find out",
            "latest information",
            "recent information"
        ]


        research_question_patterns = [
            "why do people",
            "why do humans",
            "why does",
            "why did",
            "why are people",
            "why are humans",
            "why would people",
            "why would humans",
            "what causes",
            "what makes people",
            "what makes humans",
            "what is the psychology",
            "psychology of",
            "what researchers",
            "what does science",
            "what does research",
            "what do studies",
            "what are the effects",
            "what are the risks",
            "how common",
            "how often",
            "how prevalent"
        ]


        # --------------------------------------------------------
        # Normalize common casual typos
        # --------------------------------------------------------

        normalized_text = text_lower

        typo_replacements = {
            "wy ": "why ",
            "wit ": "with ",
            "wth ": "with ",
            "ave ": "have ",
            "hav ": "have ",
        }

        for old, new in typo_replacements.items():

            normalized_text = normalized_text.replace(
                old,
                new
            )


        # --------------------------------------------------------
        # Explicit research requests
        # --------------------------------------------------------

        if any(
            word in normalized_text
            for word in research_words
        ):

            return {
                "tool": "web_search",
                "query": text
            }


        # --------------------------------------------------------
        # Known research question patterns
        # --------------------------------------------------------

        if any(
            pattern in normalized_text
            for pattern in research_question_patterns
        ):

            return {
                "tool": "web_search",
                "query": text
            }


        # --------------------------------------------------------
        # General causal questions
        # --------------------------------------------------------

        import re

        why_pattern = re.search(
            r"\bwhy\s+"
            r"(?:do|does|did|are|is|was|were|would|can|could)\b",
            normalized_text
        )

        if why_pattern:

            return {
                "tool": "web_search",
                "query": text
            }


        # --------------------------------------------------------
        # General factual questions
        # --------------------------------------------------------

        factual_pattern = re.search(
            r"\b(?:what|how)\s+"
            r"(?:is|are|does|do|did|can|could|common|often|"
            r"causes|caused|affects|affect)\b",
            normalized_text
        )

        if factual_pattern:

            return {
                "tool": "web_search",
                "query": text
            }


        # ========================================================
        # Fallback: search detection
        # ========================================================

        search_words = [
            "search",
            "find",
            "look up",
            "best",
            "compare",
            "reviews",
            "price",
            "target",
            "amazon",
            "where can i buy"
        ]


        if any(
            word in text_lower
            for word in search_words
        ):

            return {
                "tool": "web_search",
                "query": text
            }


        return None
