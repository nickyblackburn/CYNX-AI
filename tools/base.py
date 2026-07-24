"""
Base tool primitives: BaseTool and ToolResult dataclasses used by tool implementations and the router.
"""
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ToolResult:
    success: bool
    output: str
    metadata: Dict[str, Any] = None


class BaseTool:
    name: str = 'base'
    description: str = 'Base tool'

    def call(self, args: Dict) -> ToolResult:
        raise NotImplementedError
