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

            # last
            if re.search(r"\blast (hit|smoke|session)\b", tl) or "what was my last" in tl:
                return {"tool": "smoke_counter", "action": "last"}

            # recent
            if re.search(r"\b(recent|show my recent|recent hits|recent smoking)\b", tl):
                # optional limit
                limit = parse_number(tl) or 10
                return {"tool": "smoke_counter", "action": "recent", "limit": limit}

            # stats
            if re.search(r"\b(how many|how often|how many times|show my smoking stats|how many hits|how many times did)\b", tl):
                return {"tool": "smoke_counter", "action": "stats"}

            # log patterns
            # e.g. "log 2 cigarettes", "add one cigarette", "i just smoked", "i took 3 hits"
            amount = parse_number(tl) or None
            # smoke type detection — include pen and prefer exact matches to avoid misclassifying 'pen' as 'vape'
            types = ['cigarette', 'cigarettes', 'cig', 'weed', 'vape', 'vaped', 'pen', 'pens', 'joint', 'bong', 'bongs']
            smoke_type = None
            for t in types:
                if t in tl:
                    # normalize
                    if t.endswith('s'):
                        smoke_type = t[:-1]
                    else:
                        smoke_type = t
                    # Normalize common aliases
                    if smoke_type in ('cig', 'cigarette'):
                        smoke_type = 'cigarette'
                    elif smoke_type == 'vaped':
                        smoke_type = 'vape'
                    elif smoke_type in ('pens', 'pen'):
                        smoke_type = 'pen'
                    break

            # treat bong hit / bong rip / hit / rip as one default session when no explicit amount exists
            if amount is None and (
                'hit' in tl or 'rip' in tl or re.search(r"\b(i just smoked|i just had|i just took|i smoked|log|add|i just)\b", tl)
            ):
                amount = 1

            if smoke_type is None and ('bong' in tl or 'hit' in tl or 'rip' in tl):
                smoke_type = 'bong' if 'bong' in tl else 'unknown'

            if smoke_type is None:
                # default to unknown when logging
                # but do not assume logging intent for ambiguous statements that mention smoking
                # If verbs indicate logging, proceed
                if re.search(r"\b(i just smoked|i just had|log|add|i smoked|i took)\b", tl):
                    smoke_type = 'unknown'

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

            # If still ambiguous but smoking words present and a verb indicating recent action, log unknown
            if re.search(r"\b(i just|i just smoked|i smoked|i took)\b", tl):
                return {"tool": "smoke_counter", "action": "log", "smoke_type": "unknown", "amount": 1}

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