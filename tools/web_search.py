from ddgs import DDGS
from tools.base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the internet for current information."


    def call(self, args):

        query = args.get("query")

        if not query:
            return ToolResult(False, "Missing query")


        # Store-specific search improvements
        query_lower = query.lower()

        if "target" in query_lower:
            query += " site:target.com"

        if "amazon" in query_lower:
            query += " site:amazon.com"

        if "walmart" in query_lower:
            query += " site:walmart.com"


        results = []


        with DDGS() as ddgs:

            for item in ddgs.text(
                query,
                max_results=5
            ):

                results.append(
                    f"{item['title']}\n{item['body']}\n{item['href']}"
                )


        return ToolResult(
            True,
            "\n\n".join(results)
        )