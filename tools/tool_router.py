
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
                f"[RESULT] {result.message}"
            )

            return result


        except Exception as e:

            return ToolResult(
                False,
                f"Tool '{name}' exception: {e}"
            )
