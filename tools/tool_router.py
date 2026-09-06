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
                                    "enum": ["log", "stats", "recent", "last", "reset"]
                                },
                                "smoke_type": {
                                    "type": "string",
                                    "enum": ["cigarette", "weed", "vape", "joint", "bong", "unknown"]
                                },
                                "amount": {"type": "number"},
                                "limit": {"type": "integer"}
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
                                "query": {"type": "string"}
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
        for t in ['cigarette', 'cig', 'bong', 'vape', 'pen', 'weed', 'joint']:
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
        if "smoke" not in tl and "smoked" not in tl and "cigarette" not in tl and "cig" not in tl and "hit" not in tl and "vape" not in tl and "pen" not in tl and "bong" not in tl and "joint" not in tl and "weed" not in tl and "rip" not in tl:
            return False

        read_only_patterns = [
            r"\b(how many|how much|how often|show my|show me|what's my|what is my|what was my|what were my)\b",
            r"\b(stats|statistics|count|counts|total|totals)\b",
            r"\b(recent|last)\b",
            r"\b(today|this week|this month)\b",
            r"\b(how many .* (hit|hits|smoke|smoked|cigarette|cigarettes|vape|pen|bong|joint|weed) .* today)\b",
            r"\b(how many .* did i have today|how much did i smoke today|how many hits did i have today|how many vape hits did i have today|how many cigarettes did i have today)\b"
        ]
        return any(__import__('re').search(p, tl) for p in read_only_patterns)

    def detect(self, text: str):
        """
        Detect whether a message requires a tool.
        """

        text_lower = text.lower()

        # First: detect smoke-counter intents
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
                'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                'a': 1, 'an': 1
            }
            for w, n in words.items():
                if f" {w} " in f" {text} ":
                    return n
            return None

        def parse_smoke_request(text: str):
            # return dict with tool and parsed args if smoking intent detected
            import re
            tl = text.lower()
            if not any(w in tl for w in smoke_words):
                return None

            # reset explicit
            if re.search(r"\breset (my )?(smoke|smoking|smoke counter|tracker)\b", tl):
                return {"tool": "smoke_counter", "action": "reset"}

            # read-only requests must never log
            if self.is_read_only_smoke_query(tl):
                payload = {"tool": "smoke_counter", "action": "stats"}
                smoke_type_for_stats = None
                for candidate in ["vape", "pen", "bong", "cigarette", "cig", "joint", "weed"]:
                    if candidate in tl:
                        smoke_type_for_stats = self.normalize_smoke_type(candidate)
                        break
                if smoke_type_for_stats:
                    payload["smoke_type"] = smoke_type_for_stats
                if "today" in tl:
                    payload["scope"] = "today"
                if "last" in tl and "what was my last" in tl:
                    return {"tool": "smoke_counter", "action": "last"}
                if "recent" in tl or "recent hits" in tl:
                    return {"tool": "smoke_counter", "action": "recent", "limit": parse_number(tl) or 10}
                return payload

            # last
            if re.search(r"\blast (hit|smoke|session)\b", tl) or "what was my last" in tl:
                return {"tool": "smoke_counter", "action": "last"}

            # recent
            if re.search(r"\b(recent|show my recent|recent hits|recent smoking)\b", tl):
                limit = parse_number(tl) or 10
                return {"tool": "smoke_counter", "action": "recent", "limit": limit}

            # stats (including type-filtered counts like 'how many vape hits do I have today?')
            smoke_type_for_stats = None
            for candidate in ["vape", "pen", "bong", "cigarette", "cig", "joint", "weed"]:
                if candidate in tl:
                    smoke_type_for_stats = self.normalize_smoke_type(candidate)
                    break

            if re.search(r"\b(how many|how often|how many times|show my smoking stats|show my stats|how many hits|how many times did|how much have i smoked|how much have i smoked today|how much did i smoke today|how much did i smoke)\b", tl):
                payload = {"tool": "smoke_counter", "action": "stats"}
                if smoke_type_for_stats:
                    payload["smoke_type"] = smoke_type_for_stats
                if "today" in tl:
                    payload["scope"] = "today"
                return payload

            # explicit logging requests only
            if re.search(r"\b(i just smoked|i just had|i just took|i smoked|i took|log|add|record|logged)\b", tl):
                amount = parse_number(tl) or 1
                smoke_type = None
                for candidate in ["vape", "vaped", "pen", "pens", "bong", "bongs", "cigarette", "cigarettes", "cig", "weed", "joint", "hit", "hits", "rip"]:
                    if candidate in tl:
                        if candidate in ('vape', 'vaped'):
                            smoke_type = 'vape'
                        elif candidate in ('pen', 'pens'):
                            smoke_type = 'pen'
                        elif candidate in ('bong', 'bongs'):
                            smoke_type = 'bong'
                        elif candidate in ('cig', 'cigarette', 'cigarettes'):
                            smoke_type = 'cigarette'
                        elif candidate in ('weed', 'joint'):
                            smoke_type = 'weed' if 'weed' in tl else 'joint'
                        else:
                            smoke_type = 'unknown'
                        break
                if smoke_type is None:
                    smoke_type = 'unknown'
                return {"tool": "smoke_counter", "action": "log", "smoke_type": smoke_type, "amount": amount}

            # log patterns
            amount = parse_number(tl) or None
            types = ['cigarette', 'cigarettes', 'cig', 'weed', 'vape', 'vaped', 'pen', 'pens', 'joint', 'bong', 'bongs']
            smoke_type = None
            for t in types:
                if t in tl:
                    if t.endswith('s'):
                        smoke_type = t[:-1]
                    else:
                        smoke_type = t
                    if smoke_type in ('cig', 'cigarette'):
                        smoke_type = 'cigarette'
                    elif smoke_type == 'vaped':
                        smoke_type = 'vape'
                    elif smoke_type in ('pens', 'pen'):
                        smoke_type = 'pen'
                    break

            if amount is None and (
                'hit' in tl or 'rip' in tl or re.search(r"\b(i just smoked|i just had|i just took|i smoked|log|add|i just)\b", tl)
            ):
                amount = 1

            if smoke_type is None and ('bong' in tl or 'hit' in tl or 'rip' in tl):
                smoke_type = 'bong' if 'bong' in tl else 'unknown'

            if smoke_type is not None and amount is not None:
                return {
                    "tool": "smoke_counter",
                    "action": "log",
                    "smoke_type": smoke_type,
                    "amount": amount
                }

            # fallback: if user explicitly asks about smoking counts
            if re.search(r"\b(how many|show my|how often|stats|count|total)\b", tl):
                return {"tool": "smoke_counter", "action": "stats"}

            return None

        smoke_req = parse_smoke_request(text_lower)
        if smoke_req:
            return smoke_req

        # Fallback: search detection
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

        if any(word in text_lower for word in search_words):

            return {
                "tool": "web_search",
                "query": text
            }

        return None