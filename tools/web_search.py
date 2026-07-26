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


        stores = {
            "target": "target.com",
            "amazon": "amazon.com",
            "walmart": "walmart.com",
        }


        for store, domain in stores.items():

            if store in query_lower:
                query += f" site:{domain}"
                break



        # Improve product searches
        if any(word in query_lower for word in [
            "best",
            "top",
            "recommend",
            "review"
        ]):
            query += " reviews"



        # Product category improvements
        if "bullet vibrator" in query_lower:

            query += ' "bullet vibrator"'


        elif "vibrator" in query_lower:

            query += " product"
            query += " -massager -massage"



        if any(word in query_lower for word in [
            "headset",
            "keyboard",
            "phone",
            "laptop"
        ]):

            query += " product listing"



        print("[SEARCH QUERY]", query)



        results = []



        with DDGS() as ddgs:

            for item in ddgs.text(
                query,
                max_results=20
            ):


                title = item.get(
                    "title",
                    ""
                )


                body = item.get(
                    "body",
                    ""
                )


                href = item.get(
                    "href",
                    ""
                )



                # Skip empty results
                if not href:
                    continue



                # Prefer real product pages
                if "target.com" in href:

                    if "/p/" not in href:
                        continue



                results.append(
                    f"""
TITLE:
{title}

DESCRIPTION:
{body}

LINK:
{href}
"""
                )



        if not results:

            return ToolResult(
                False,
                "No search results found."
            )



        return ToolResult(
            True,
            "\n\n".join(results)
        )