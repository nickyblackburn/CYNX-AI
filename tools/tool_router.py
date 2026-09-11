from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class ToolRouter:
    """
    Central tool registry and deterministic natural-language router.

    Responsibilities:
      - Register tools
      - Expose registered tools to Ollama
      - Detect deterministic intents before LLM tool calling
      - Normalize smoke-counter requests
      - Route tool calls to registered BaseTool instances

    The router does NOT own application data.
    Tools remain responsible for their own data/storage/logic.
    """

    def __init__(self):
        self.tools: Dict[str, Any] = {}

    # ============================================================
    # TOOL REGISTRATION
    # ============================================================

    def register_tool(self, tool: Any) -> None:
        """
        Register a BaseTool-compatible instance.

        Expected:
            tool.name
            tool.call(args)

        Some older tools may expose their name differently, so
        class-name fallback is retained.
        """
        name = getattr(tool, "name", None)

        if not name:
            name = getattr(tool, "tool_name", None)

        if not name:
            class_name = tool.__class__.__name__
            name = class_name

            if class_name.endswith("Tool"):
                name = class_name[:-4]

        name = str(name).strip().lower()

        self.tools[name] = tool

    def unregister_tool(self, name: str) -> None:
        self.tools.pop(str(name).strip().lower(), None)

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())


    def describe_tools(self) -> List[str]:
        """
        Return human-readable descriptions of all registered tools.

        ChatEngine uses this for context/debugging. This does not
        replace as_ollama_tools(); it is simply the human-readable
        counterpart.
        """

        descriptions = []

        for name, tool in self.tools.items():
            description = getattr(tool, "description", None)

            if not description:
                description = getattr(tool, "tool_description", None)

            if not description:
                description = f"Registered tool: {name}"

            descriptions.append(
                f"{name}: {description}"
            )

        return descriptions

    # ============================================================
    # TOOL LOOKUP
    # ============================================================

    def get_tool(self, name: str) -> Optional[Any]:
        if not name:
            return None

        return self.tools.get(str(name).strip().lower())

    # ============================================================
    # OLLAMA TOOL SCHEMAS
    # ============================================================

    def as_ollama_tools(self) -> List[Dict[str, Any]]:
        """
        Convert registered tools into Ollama-compatible function
        definitions.

        Tool-specific schemas are kept here because this router is
        the bridge between the application's tools and Ollama.
        """

        schemas: List[Dict[str, Any]] = []

        # --------------------------------------------------------
        # WEB SEARCH
        # --------------------------------------------------------

        if "web_search" in self.tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": (
                            "Search the web for current or external "
                            "information."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The web search query.",
                                },
                            },
                            "required": ["query"],
                        },
                    },
                }
            )

        # --------------------------------------------------------
        # CALCULATOR
        # --------------------------------------------------------

        if "calculator" in self.tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "description": (
                            "Perform mathematical calculations accurately."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": (
                                        "Mathematical expression to calculate."
                                    ),
                                },
                            },
                            "required": ["expression"],
                        },
                    },
                }
            )

        # --------------------------------------------------------
        # SMOKE COUNTER
        # --------------------------------------------------------

        if "smoke_counter" in self.tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": "smoke_counter",
                        "description": (
                            "Track smoking sessions and retrieve smoking "
                            "statistics from the authoritative smoke counter."
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
                                        "reset",
                                    ],
                                },
                                "smoke_type": {
                                    "type": "string",
                                    "description": (
                                        "Type of smoking session. "
                                        "Examples: cigarette, vape, pen, "
                                        "bong, weed, joint."
                                    ),
                                },
                                "amount": {
                                    "type": "number",
                                    "description": (
                                        "Number of cigarettes/hits/sessions "
                                        "being logged."
                                    ),
                                },
                                "limit": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 100,
                                },
                                "scope": {
                                    "type": "string",
                                    "enum": [
                                        "all",
                                        "today",
                                        "week",
                                        "month",
                                    ],
                                },
                                "events": {
                                    "type": "array",
                                    "description": (
                                        "Multiple smoking events to log "
                                        "from one user message."
                                    ),
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "smoke_type": {
                                                "type": "string"
                                            },
                                            "amount": {
                                                "type": "number"
                                            },
                                        },
                                        "required": [
                                            "smoke_type",
                                            "amount",
                                        ],
                                    },
                                },
                            },
                            "required": ["action"],
                        },
                    },
                }
            )

        # --------------------------------------------------------
        # CHART TOOL
        # --------------------------------------------------------

        if "chart" in self.tools:
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": "chart",
                        "description": (
                            "Create structured chart data for the CYN-X "
                            "interface. Use this when the user asks to "
                            "graph, chart, visualize, plot, compare, or "
                            "display numerical data visually."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "chart_type": {
                                    "type": "string",
                                    "enum": [
                                        "bar",
                                        "line",
                                        "pie",
                                        "scatter",
                                    ],
                                    "description": "Type of chart.",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Chart title.",
                                },
                                "description": {
                                    "type": "string",
                                    "description": (
                                        "Optional short description."
                                    ),
                                },
                                "footer": {
                                    "type": "string",
                                    "description": (
                                        "Optional footer or data note."
                                    ),
                                },
                                "x_key": {
                                    "type": "string",
                                    "description": (
                                        "Object key used for the X axis."
                                    ),
                                },
                                "x_axis_label": {
                                    "type": "string",
                                },
                                "x_axis_scale": {
                                    "type": "string",
                                    "enum": [
                                        "linear",
                                        "category",
                                        "time",
                                    ],
                                },
                                "y_axis_min": {
                                    "type": "number",
                                },
                                "y_axis_max": {
                                    "type": "number",
                                },
                                "layout": {
                                    "type": "string",
                                },
                                "name_key": {
                                    "type": "string",
                                    "description": (
                                        "Object key used for pie labels."
                                    ),
                                },
                                "value_key": {
                                    "type": "string",
                                    "description": (
                                        "Object key used for pie values."
                                    ),
                                },
                                "series": {
                                    "type": "array",
                                    "description": (
                                        "Chart series definitions."
                                    ),
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "dataKey": {
                                                "type": "string"
                                            },
                                            "label": {
                                                "type": "string"
                                            },
                                            "axisLabel": {
                                                "type": "string"
                                            },
                                            "valueFormat": {
                                                "type": "string"
                                            },
                                            "valuePrefix": {
                                                "type": "string"
                                            },
                                            "valueSuffix": {
                                                "type": "string"
                                            },
                                            "stack": {
                                                "type": "string"
                                            },
                                        },
                                        "required": ["dataKey"],
                                    },
                                },
                                "data": {
                                    "type": "array",
                                    "description": (
                                        "Structured data to visualize. "
                                        "Each item should be an object."
                                    ),
                                    "items": {
                                        "type": "object",
                                    },
                                },
                            },
                            "required": [
                                "chart_type",
                                "title",
                                "data",
                            ],
                        },
                    },
                }
            )

        return schemas

    # ============================================================
    # SMOKE TYPE NORMALIZATION
    # ============================================================

    def normalize_smoke_type(self, text: Any) -> str:
        """
        Normalize free-form smoking terminology into canonical values.

        Canonical values:
            pen
            vape
            cigarette
            bong
            weed
            joint

        Unknown values are cleaned and returned rather than silently
        being converted to something else.
        """

        if text is None:
            return "unknown"

        value = str(text).strip().lower()

        if not value:
            return "unknown"

        # Important:
        # Check PEN before VAPE so "pen" never becomes "vape".
        if re.search(r"\bpen\b|\bvape\s*pen\b", value):
            return "pen"

        if re.search(
            r"\bvape\b|\bvaping\b|\be[- ]?cig\b|\be[- ]?cigarette\b",
            value,
        ):
            return "vape"

        if re.search(
            r"\bcig\b|\bcigs\b|\bcigarette\b|\bcigarettes\b",
            value,
        ):
            return "cigarette"

        if re.search(
            r"\bbong\b|\bbong\s*hit\b|\bbong\s*hitting\b",
            value,
        ):
            return "bong"

        if re.search(r"\bweed\b|\bmarijuana\b|\bpot\b|\bflower\b", value):
            return "weed"

        if re.search(r"\bjoint\b|\bjoints\b", value):
            return "joint"

        # Remove generic quantity terminology while preserving
        # unknown custom types.
        cleaned = re.sub(
            r"\b(hits?|puffs?|sessions?|times?)\b",
            "",
            value,
        )

        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned or "unknown"

    # ============================================================
    # SMOKE QUERY DETECTION
    # ============================================================

    def is_read_only_smoke_query(self, text: str) -> bool:
        """
        Return True only when the user is clearly asking for existing
        smoke-counter information.

        IMPORTANT:
        'today' alone is NOT enough to classify something as read-only.
        This prevents:
            'I smoked 3 cigarettes today'
        from being changed into a stats query.
        """

        text = (text or "").strip().lower()

        if not text:
            return False

        read_patterns = [
            r"\bhow many\b",
            r"\bhow much\b",
            r"\bwhat'?s my\b",
            r"\bwhat is my\b",
            r"\bshow me\b",
            r"\bshow my\b",
            r"\bdisplay my\b",
            r"\bcheck my\b",
            r"\bget my\b",
            r"\btell me my\b",
            r"\bwhat did i smoke\b",
            r"\bhow many times did i smoke\b",
            r"\bsmoking stats?\b",
            r"\bsmoke stats?\b",
            r"\brecent (?:smoking|smoke|hits?|sessions?)\b",
            r"\blast (?:smoking|smoke|hit|session)\b",
        ]

        return any(re.search(pattern, text) for pattern in read_patterns)

    # ============================================================
    # NUMBER PARSING
    # ============================================================

    def _parse_number(self, value: str) -> Optional[float]:
        if not value:
            return None

        value = value.strip().lower()

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
        }

        if value in number_words:
            return float(number_words[value])

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # ============================================================
    # SMOKE REQUEST PARSER
    # ============================================================

    def parse_smoke_request(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Convert common natural-language smoking requests into a
        deterministic smoke_counter request.

        This intentionally stays conservative so casual mentions such
        as "I want to hit my pen" do not accidentally create a log.
        """

        original = text or ""
        text = original.strip().lower()

        if not text:
            return None

        smoke_words = (
            r"(?:smoke|smoked|smoking|cig(?:arette)?s?|"
            r"vape|vaping|pen|bong|weed|joint|"
            r"hit|hits|puff|puffs)"
        )

        # --------------------------------------------------------
        # RESET
        # --------------------------------------------------------

        if re.search(
            r"\b(reset|clear|wipe)\b.*\b(smoke|smoking|counter)\b",
            text,
        ):
            return {
                "tool": "smoke_counter",
                "action": "reset",
            }

        # --------------------------------------------------------
        # RECENT
        # --------------------------------------------------------

        if re.search(
            r"\b(recent|latest|last few)\b.*\b"
            r"(smoke|smoking|hit|hits|session|sessions)\b",
            text,
        ):
            return {
                "tool": "smoke_counter",
                "action": "recent",
                "limit": 10,
            }

        # --------------------------------------------------------
        # LAST
        # --------------------------------------------------------

        if re.search(
            r"\b(last|most recent)\b.*\b"
            r"(smoke|smoking|hit|session)\b",
            text,
        ):
            return {
                "tool": "smoke_counter",
                "action": "last",
            }

        # --------------------------------------------------------
        # STATS
        # --------------------------------------------------------

        if self.is_read_only_smoke_query(text):
            smoke_type = None

            type_matches = [
                "pen",
                "vape",
                "bong",
                "cigarette",
                "cig",
                "weed",
                "joint",
            ]

            for smoke_type_text in type_matches:
                if re.search(
                    rf"\b{re.escape(smoke_type_text)}\b",
                    text,
                ):
                    smoke_type = self.normalize_smoke_type(
                        smoke_type_text
                    )
                    break

            scope = "all"

            if re.search(r"\btoday\b", text):
                scope = "today"
            elif re.search(r"\bthis week\b|\bthis week'?s\b", text):
                scope = "week"
            elif re.search(r"\bthis month\b|\bthis month'?s\b", text):
                scope = "month"

            request: Dict[str, Any] = {
                "tool": "smoke_counter",
                "action": "stats",
                "scope": scope,
            }

            if smoke_type:
                request["smoke_type"] = smoke_type

            return request

        # --------------------------------------------------------
        # MULTIPLE EXPLICIT EVENTS
        #
        # Example:
        #   "I smoked 4 cigarettes and 3 pen hits today"
        #
        # -> two events
        # --------------------------------------------------------

        event_pattern = re.compile(
            r"(?P<number>\d+(?:\.\d+)?|"
            r"zero|one|two|three|four|five|six|seven|eight|nine|ten)"
            r"\s+"
            r"(?P<type>"
            r"cigarettes?|cigs?|"
            r"vapes?|"
            r"pens?|"
            r"bongs?|"
            r"joints?|"
            r"weed"
            r")"
            r"(?:\s+(?:hits?|puffs?|times?))?",
            re.IGNORECASE,
        )

        events: List[Dict[str, Any]] = []

        for match in event_pattern.finditer(text):
            amount = self._parse_number(match.group("number"))
            smoke_type = self.normalize_smoke_type(
                match.group("type")
            )

            if amount is not None and amount > 0:
                events.append(
                    {
                        "smoke_type": smoke_type,
                        "amount": amount,
                    }
                )

        if len(events) > 1:
            return {
                "tool": "smoke_counter",
                "action": "log",
                "events": events,
            }

        # --------------------------------------------------------
        # SINGLE EVENT
        # --------------------------------------------------------

        single_pattern = re.search(
            r"\b(?:"
            r"log|record|track|add|smoked?|"
            r"i\s+(?:just\s+)?smoked|"
            r"i\s+(?:just\s+)?took|"
            r"i\s+(?:just\s+)?had"
            r")\b"
            r".{0,30}?"
            r"(?P<number>\d+(?:\.\d+)?|"
            r"zero|one|two|three|four|five|six|seven|eight|nine|ten)"
            r"(?:\s+"
            r"(?P<type>"
            r"cigarettes?|cigs?|"
            r"vapes?|"
            r"pens?|"
            r"bongs?|"
            r"joints?|"
            r"weed"
            r"))?",
            text,
            re.IGNORECASE,
        )

        if single_pattern:
            amount = self._parse_number(
                single_pattern.group("number")
            )

            smoke_type_raw = single_pattern.group("type")

            smoke_type = (
                self.normalize_smoke_type(smoke_type_raw)
                if smoke_type_raw
                else "unknown"
            )

            if amount is not None and amount > 0:
                return {
                    "tool": "smoke_counter",
                    "action": "log",
                    "smoke_type": smoke_type,
                    "amount": amount,
                }

        # --------------------------------------------------------
        # "I took 3 hits" / "I had 3 hits"
        # --------------------------------------------------------

        hit_pattern = re.search(
            r"\b(?:took|had|did)\s+"
            r"(?P<number>\d+(?:\.\d+)?|"
            r"zero|one|two|three|four|five|six|seven|eight|nine|ten)"
            r"\s+(?P<type>"
            r"cigarette|cigarettes|cig|cigs|"
            r"vape|vapes|"
            r"pen|pens|"
            r"bong|bongs|"
            r"joint|joints|"
            r"weed"
            r")?"
            r"(?:\s+(?:hits?|puffs?))?",
            text,
            re.IGNORECASE,
        )

        if hit_pattern:
            amount = self._parse_number(
                hit_pattern.group("number")
            )

            smoke_type_raw = hit_pattern.group("type")

            smoke_type = (
                self.normalize_smoke_type(smoke_type_raw)
                if smoke_type_raw
                else "unknown"
            )

            if amount is not None and amount > 0:
                return {
                    "tool": "smoke_counter",
                    "action": "log",
                    "smoke_type": smoke_type,
                    "amount": amount,
                }

        # --------------------------------------------------------
        # Explicit "I just smoked" with no quantity
        # --------------------------------------------------------

        if re.search(
            r"\b(i\s+just\s+smoked|"
            r"i\s+smoked|"
            r"i\s+just\s+had\s+a\s+smoke)\b",
            text,
        ):
            # Only use the default one-event behavior when the user
            # clearly states that they smoked.
            detected_type = "unknown"

            for candidate in (
                "pen",
                "vape",
                "bong",
                "cigarette",
                "joint",
                "weed",
            ):
                if re.search(
                    rf"\b{re.escape(candidate)}\b",
                    text,
                ):
                    detected_type = self.normalize_smoke_type(candidate)
                    break

            return {
                "tool": "smoke_counter",
                "action": "log",
                "smoke_type": detected_type,
                "amount": 1,
            }

        return None

    # ============================================================
    # CHART INTENT DETECTION
    # ============================================================

    def parse_chart_request(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Deterministically detect explicit chart/graph requests.

        This does NOT manufacture data.

        It only tells ChatEngine/Ollama that the chart tool is relevant.
        The actual data should come from a tool result or from the
        user's supplied data.
        """

        text = (text or "").strip().lower()

        if not text:
            return None

        if not re.search(
            r"\b(chart|graph|plot|visuali[sz]e|"
            r"visualization|visualise|graphing)\b",
            text,
        ):
            return None

        return {
            "tool": "chart",
            "action": "create",
        }

    # ============================================================
    # WEB SEARCH DETECTION
    # ============================================================

    def detect_search_request(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Conservative search detection.

        The LLM remains responsible for normal tool calling when
        deterministic detection does not identify a search.
        """

        text = (text or "").strip()

        if not text:
            return None

        lowered = text.lower()

        search_patterns = [
            r"\bsearch (?:the )?web\b",
            r"\bsearch online\b",
            r"\blook (?:it|that) up\b",
            r"\blook this up\b",
            r"\bgoogle\b",
            r"\bfind me\b",
            r"\bfind information about\b",
            r"\bwhat'?s the latest\b",
            r"\bwhat is the latest\b",
            r"\blatest news\b",
            r"\bcurrent price\b",
            r"\bcurrent weather\b",
            r"\bwho is\b",
            r"\bwhat happened\b",
        ]

        if not any(
            re.search(pattern, lowered)
            for pattern in search_patterns
        ):
            return None

        # Avoid stealing obvious smoke-counter requests.
        if self.parse_smoke_request(text):
            return None

        # Remove common search-intent prefixes.
        query = re.sub(
            r"^\s*(?:search|google|look up|find me|find information about)"
            r"\s*(?:the\s+)?",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        if not query:
            query = text

        return {
            "tool": "web_search",
            "query": query,
        }

    # ============================================================
    # MAIN DETECTOR
    # ============================================================

    def detect(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Detect deterministic tool intent.

        Priority:
            1. Smoke counter
            2. Chart
            3. Web search
            4. None

        Returning None is intentional: ChatEngine can then allow
        normal Ollama conversation/tool calling to proceed.
        """

        text = text or ""

        # Smoke first because phrases like
        # "how many vape hits did I have today?"
        # must never become a generic search.
        smoke_request = self.parse_smoke_request(text)

        if smoke_request:
            return smoke_request

        chart_request = self.parse_chart_request(text)

        if chart_request and "chart" in self.tools:
            return chart_request

        search_request = self.detect_search_request(text)

        if search_request:
            return search_request

        return None

    # ============================================================
    # TOOL CALL DISPATCH
    # ============================================================

    def call_tool(
        self,
        name: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Dispatch a tool call to the registered tool instance.

        The complete argument dictionary is passed through so individual
        tools can ignore fields they don't need.
        """

        tool_name = str(name).strip().lower()

        tool = self.get_tool(tool_name)

        if tool is None:
            raise ValueError(
                f"Tool '{tool_name}' is not registered. "
                f"Available tools: {self.list_tools()}"
            )

        arguments = dict(args or {})

        # --------------------------------------------------------
        # Normalize smoke arguments at the router boundary.
        # --------------------------------------------------------

        if tool_name == "smoke_counter":
            self._sanitize_smoke_arguments(arguments)

        # --------------------------------------------------------
        # Chart arguments.
        #
        # Keep the structured object intact. ChartTool owns validation.
        # --------------------------------------------------------

        if tool_name == "chart":
            self._sanitize_chart_arguments(arguments)

        return tool.call(arguments)

    # ============================================================
    # ARGUMENT SANITIZATION
    # ============================================================

    def _sanitize_smoke_arguments(
        self,
        arguments: Dict[str, Any],
    ) -> None:
        """
        Normalize model-produced smoke arguments before they reach
        SmokeCounterTool.
        """

        if "smoke_type" in arguments:
            arguments["smoke_type"] = self.normalize_smoke_type(
                arguments["smoke_type"]
            )

        if "amount" in arguments:
            arguments["amount"] = self._coerce_number(
                arguments["amount"]
            )

        if "events" in arguments and isinstance(
            arguments["events"],
            list,
        ):
            cleaned_events = []

            for event in arguments["events"]:
                if not isinstance(event, dict):
                    continue

                smoke_type = self.normalize_smoke_type(
                    event.get("smoke_type")
                )

                amount = self._coerce_number(
                    event.get("amount")
                )

                if amount is None:
                    continue

                cleaned_events.append(
                    {
                        "smoke_type": smoke_type,
                        "amount": amount,
                    }
                )

            arguments["events"] = cleaned_events

    def _sanitize_chart_arguments(
        self,
        arguments: Dict[str, Any],
    ) -> None:
        """
        Perform only safe structural cleanup for ChartTool.

        ChartTool remains responsible for actual validation.
        """

        if "chart_type" in arguments:
            arguments["chart_type"] = str(
                arguments["chart_type"]
            ).strip().lower()

        if "title" in arguments:
            arguments["title"] = str(
                arguments["title"]
            ).strip()

        if "data" in arguments:
            if arguments["data"] is None:
                arguments["data"] = []

        if "series" in arguments:
            if arguments["series"] is None:
                arguments["series"] = []

    @staticmethod
    def _coerce_number(value: Any) -> Optional[float]:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return value

        try:
            value = str(value).strip()

            if not value:
                return None

            number = float(value)

            if number.is_integer():
                return int(number)

            return number

        except (TypeError, ValueError):
            return None