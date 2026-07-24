"""
Weather tool stub: implement with a real weather API later.
"""
from typing import Dict
from tools.base import BaseTool, ToolResult


class WeatherTool(BaseTool):
    name = 'weather'
    description = 'Return current weather for a location (stub).'

    def call(self, args: Dict) -> ToolResult:
        loc = args.get('location') or args.get('q') or 'unknown'
        # TODO: call a weather API
        return ToolResult(True, f'Weather for {loc}: Sunny, 25°C (stub)')
