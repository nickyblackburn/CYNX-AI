import requests
from tools.base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the internet for current information."

    def __init__(self, api_key):
        self.api_key = api_key

    def call(self, args):

        query = args.get("query")

        if not query:
            return ToolResult(False, "Missing query")

        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key
            },
            params={
                "q": query,
                "count": 5
            }
        )

        data = response.json()

        results = []

        for item in data.get("web", {}).get("results", []):
            results.append(
                f"{item['title']}\n{item['description']}\n{item['url']}"
            )

        return ToolResult(
            True,
            "\n\n".join(results)
        )