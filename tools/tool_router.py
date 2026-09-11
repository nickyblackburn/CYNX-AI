
"""
ToolRouter:
- Register tools
- Expose tool descriptions to the LLM
- Dispatch tool calls
- Log usage
"""

from typing import Dict, Any
import re

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
                        "description": (
                            "Track smoking sessions and retrieve smoking statistics."
                        ),
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
                                        "pen",
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
                                },
                                "scope": {
                                    "type": "string"
                                },
                                "events": {
                                    "type": "array",
                                    "description": (
                                        "Multiple smoking events when a user "
                                        "mentions different smoke types or amounts "
                                        "in the same message."
                                    ),
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "smoke_type": {
                                                "type": "string",
                                                "enum": [
                                                    "cigarette",
                                                    "weed",
                                                    "vape",
                                                    "pen",
                                                    "joint",
                                                    "bong",
                                                    "unknown"
                                                ]
                                            },
                                            "amount": {
                                                "type": "number"
                                            }
                                        },
                                        "required": [
                                            "smoke_type",
                                            "amount"
                                        ]
                                    }
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
                        "description": (
                            "Search the internet for current information."
                        ),
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
        """
        Normalize a freeform smoke_type string into a canonical type.

        Canonical types:
        - cigarette
        - pen
        - vape
        - bong
        - weed
        - joint
        - unknown
        """

        if not text:
            return None

        tl = str(text).lower().strip()

        # Order matters here.
        # Check more specific aliases before shorter ones.
        aliases = [
            ("cigarettes", "cigarette"),
            ("cigarette", "cigarette"),
            ("cigs", "cigarette"),
            ("cig", "cigarette"),

            ("vapes", "vape"),
            ("vaped", "vape"),
            ("vape", "vape"),

            ("pens", "pen"),
            ("pen", "pen"),

            ("bongs", "bong"),
            ("bong", "bong"),

            ("joints", "joint"),
            ("joint", "joint"),

            ("weed", "weed"),

            ("hits", "unknown"),
            ("hit", "unknown"),
            ("rips", "unknown"),
            ("rip", "unknown"),
        ]

        for alias, canonical in aliases:

            if re.search(
                rf"\b{re.escape(alias)}\b",
                tl
            ):
                return canonical

        return tl

    def is_read_only_smoke_query(self, text: str) -> bool:
        """
        Return True when the request is asking for counts/stats/history
        instead of logging.

        IMPORTANT:
        Date words such as "today" do NOT make a query read-only by
        themselves.

        Example:

            "I smoked 4 cigarettes today"

        must remain a logging request.
        """

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
            r"\b(how many .* (hit|hits|smoke|smoked|cigarette|cigarettes|vape|pen|bong|joint|weed) .* today)\b",
            r"\b(how many .* did i have today|how much did i smoke today|how many hits did i have today|how many vape hits did i have today|how many cigarettes did i have today)\b"
        ]

        return any(
            re.search(pattern, tl)
            for pattern in read_only_patterns
        )

    def detect(self, text: str):
        """
        Detect whether a message requires a tool.
        """

        if not text:
            return None

        text_lower = text.lower()

        # ========================================================
        # Smoke parsing helpers
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
            "rips",
            "bong",
            "bongs",
            "vape",
            "vaped",
            "vapes",
            "pen",
            "pens",
            "weed",
            "joint",
            "joints",
            "puff",
            "nicotine",
            "quit",
            "reset"
        ]

        number_words = {
            "zero": 0,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "a": 1,
            "an": 1
        }

        def parse_number(value: str):

            if not value:
                return None

            value = value.lower()

            # Digits first.
            match = re.search(
                r"\b(\d+(?:\.\d+)?)\b",
                value
            )

            if match:

                try:
                    number = float(match.group(1))

                    if number.is_integer():
                        return int(number)

                    return number

                except Exception:
                    pass

            # Then number words.
            for word, number in number_words.items():

                if re.search(
                    rf"\b{re.escape(word)}\b",
                    value
                ):
                    return number

            return None

        def smoke_type_from_word(word: str):

            word = word.lower()

            if word in (
                "cigarette",
                "cigarettes",
                "cig",
                "cigs"
            ):
                return "cigarette"

            if word in (
                "vape",
                "vaped",
                "vapes"
            ):
                return "vape"

            if word in (
                "pen",
                "pens"
            ):
                return "pen"

            if word in (
                "bong",
                "bongs"
            ):
                return "bong"

            if word in (
                "joint",
                "joints"
            ):
                return "joint"

            if word == "weed":
                return "weed"

            if word in (
                "hit",
                "hits",
                "rip",
                "rips"
            ):
                return "unknown"

            return None

        def parse_smoke_events(value: str):
            """
            Extract multiple smoking events from one natural-language
            statement.

            Examples:

                "I smoked 4 cigarettes and 3 pen hits"

                ->
                [
                    {
                        "smoke_type": "cigarette",
                        "amount": 4
                    },
                    {
                        "smoke_type": "pen",
                        "amount": 3
                    }
                ]

                "I smoked four cigarettes and three pen hits"

                ->
                [
                    {
                        "smoke_type": "cigarette",
                        "amount": 4
                    },
                    {
                        "smoke_type": "pen",
                        "amount": 3
                    }
                ]
            """

            tl = value.lower()

            # Number can be a digit, simple number word, "a", or "an".
            number_pattern = (
                r"(?:"
                r"\d+(?:\.\d+)?"
                r"|zero|one|two|three|four|five|six|seven|eight|nine|ten"
                r"|a|an"
                r")"
            )

            # Smoke type aliases.
            type_pattern = (
                r"(?:"
                r"cigarettes?|cigs?|"
                r"vapes?|vaped|"
                r"pens?|"
                r"bongs?|"
                r"joints?|"
                r"weed"
                r")"
            )

            # Match:
            #
            #   4 cigarettes
            #   3 pen
            #   3 pen hits
            #   four cigarettes
            #   three vape hits
            #
            event_pattern = re.compile(
                rf"\b("
                rf"{number_pattern}"
                rf")\s+"
                rf"({type_pattern})"
                rf"(?:\s+(?:hits?|rips?|puffs?))?\b"
            )

            events = []

            for match in event_pattern.finditer(tl):

                number_text = match.group(1)
                type_text = match.group(2)

                amount = number_words.get(
                    number_text,
                    None
                )

                if amount is None:

                    try:
                        number = float(number_text)

                        if number.is_integer():
                            amount = int(number)
                        else:
                            amount = number

                    except Exception:
                        amount = 1

                smoke_type = smoke_type_from_word(
                    type_text
                )

                if smoke_type is None:
                    continue

                events.append(
                    {
                        "smoke_type": smoke_type,
                        "amount": amount
                    }
                )

            return events

        def parse_single_smoke_type(value: str):

            candidates = [
                "vape",
                "vaped",
                "vapes",
                "pen",
                "pens",
                "bong",
                "bongs",
                "cigarette",
                "cigarettes",
                "cig",
                "cigs",
                "weed",
                "joint",
                "joints",
                "hit",
                "hits",
                "rip",
                "rips"
            ]

            for candidate in candidates:

                if re.search(
                    rf"\b{re.escape(candidate)}\b",
                    value
                ):

                    result = smoke_type_from_word(
                        candidate
                    )

                    if result:
                        return result

            return "unknown"

        def parse_smoke_request(value: str):

            # --------------------------------------------------------
            # Determine whether this is even a smoking-related request.
            # --------------------------------------------------------

            has_smoke_word = any(
                re.search(
                    rf"\b{re.escape(word)}\b",
                    value
                )
                for word in smoke_words
            )

            # Some smoke-counter history requests don't explicitly say
            # "smoke", e.g. "show my recent sessions".
            history_request_without_smoke_word = (
                re.search(
                    r"\b(show|give|get)\s+my\s+recent\s+sessions\b",
                    value
                )
                or re.search(
                    r"\b(show|give|get)\s+my\s+last\s+sessions?\b",
                    value
                )
            )

            if (
                not has_smoke_word
                and not history_request_without_smoke_word
            ):
                return None

            # --------------------------------------------------------
            # Explicit reset
            # --------------------------------------------------------

            if re.search(
                r"\breset (my )?(smoke|smoking|smoke counter|tracker)\b",
                value
            ):

                return {
                    "tool": "smoke_counter",
                    "action": "reset"
                }

            # --------------------------------------------------------
            # Read-only requests
            # --------------------------------------------------------

            if self.is_read_only_smoke_query(value):

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
                        value
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

                if "today" in value:

                    payload[
                        "scope"
                    ] = "today"

                if (
                    "last" in value
                    and "what was my last" in value
                ):

                    return {
                        "tool": "smoke_counter",
                        "action": "last"
                    }

                if (
                    "recent" in value
                    or "recent hits" in value
                    or "recent sessions" in value
                ):

                    return {
                        "tool": "smoke_counter",
                        "action": "recent",
                        "limit": parse_number(value) or 10
                    }

                return payload

            # --------------------------------------------------------
            # Last
            # --------------------------------------------------------

            if (
                re.search(
                    r"\blast (hit|smoke|session)\b",
                    value
                )
                or "what was my last" in value
            ):

                return {
                    "tool": "smoke_counter",
                    "action": "last"
                }

            # --------------------------------------------------------
            # Recent
            # --------------------------------------------------------

            if re.search(
                r"\b(recent|show my recent|recent hits|recent smoking|recent sessions)\b",
                value
            ):

                limit = parse_number(value) or 10

                return {
                    "tool": "smoke_counter",
                    "action": "recent",
                    "limit": limit
                }

            # --------------------------------------------------------
            # Stats
            # --------------------------------------------------------

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
                    value
                ):

                    smoke_type_for_stats = (
                        self.normalize_smoke_type(
                            candidate
                        )
                    )

                    break

            if re.search(
                r"\b("
                r"how many|"
                r"how often|"
                r"how many times|"
                r"show my smoking stats|"
                r"show my stats|"
                r"how many hits|"
                r"how many times did|"
                r"how much have i smoked|"
                r"how much have i smoked today|"
                r"how much did i smoke today|"
                r"how much did i smoke"
                r")\b",
                value
            ):

                payload = {
                    "tool": "smoke_counter",
                    "action": "stats"
                }

                if smoke_type_for_stats:

                    payload[
                        "smoke_type"
                    ] = smoke_type_for_stats

                if "today" in value:

                    payload[
                        "scope"
                    ] = "today"

                return payload

            # --------------------------------------------------------
            # Explicit logging requests
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
                    value
                )
                for pattern in explicit_log_patterns
            )

            # --------------------------------------------------------
            # Natural logging statements
            # --------------------------------------------------------

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
                    value
                )
                for pattern in natural_log_patterns
            )

            if (
                explicit_logging_request
                or natural_logging_request
            ):

                # ----------------------------------------------------
                # IMPORTANT:
                #
                # Parse every independently stated event first.
                #
                # This prevents:
                #
                #   "I smoked 4 cigarettes and 3 pen hits"
                #
                # from becoming:
                #
                #   cigarette=4
                #
                # while silently losing the pen event.
                # ----------------------------------------------------

                events = parse_smoke_events(value)

                if events:

                    # One event: preserve the existing scalar format
                    # for compatibility with the existing tool pipeline.
                    if len(events) == 1:

                        return {
                            "tool": "smoke_counter",
                            "action": "log",
                            "smoke_type": events[0]["smoke_type"],
                            "amount": events[0]["amount"]
                        }

                    # Multiple events: return all events explicitly.
                    return {
                        "tool": "smoke_counter",
                        "action": "log",
                        "events": events
                    }

                # ----------------------------------------------------
                # Fallback for an explicit logging request where a
                # number/type pair wasn't found.
                # ----------------------------------------------------

                amount = parse_number(value) or 1

                smoke_type = parse_single_smoke_type(
                    value
                )

                return {
                    "tool": "smoke_counter",
                    "action": "log",
                    "smoke_type": smoke_type,
                    "amount": amount
                }

            # --------------------------------------------------------
            # Do NOT use the old generic fallback:
            #
            # "if smoke_type and amount -> log"
            #
            # because that caused casual conversation containing
            # "pen", "hit", etc. to become a logging request.
            # --------------------------------------------------------

            return None

        # ========================================================
        # First: detect smoke-counter intents
        # ========================================================

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