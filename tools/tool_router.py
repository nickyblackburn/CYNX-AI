"""
ToolRouter: register tools, validate tool calls, dispatch, and log tool usage.
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

    def call_tool(self, name: str, args: Dict[str, Any]) -> ToolResult:
        if name not in self.tools:
            return ToolResult(False, f"Tool '{name}' not found")
        tool = self.tools[name]
        try:
            result = tool.call(args)
            return result
        except Exception as e:
            return ToolResult(False, f"Tool '{name}' raised exception: {e}")
