"""
Web search tool stub. Replace the internals with your chosen search provider (SerpAPI, Bing, Google).
"""
from typing import Dict
from tools.base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = 'web_search'
    description = 'Perform a web search and return summarized results.'

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def call(self, args: Dict) -> ToolResult:
        q = args.get('q') or args.get('query')
        if not q:
            return ToolResult(False, 'No query provided')
        # TODO: implement with an HTTP client (httpx/requests) and chosen provider
        # For now, return a placeholder
        return ToolResult(True, f"Search results for: {q} (stub)")
