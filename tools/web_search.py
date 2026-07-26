from ddgs import DDGS
from tools.base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the internet for current information."


    def call(self, args):

        query = args.get("query")


        if not query:

            return ToolResult(
                False,
                "Missing query"
            )


        query_lower = query.lower()


        # -----------------------------
        # Search context improvements
        # -----------------------------

        context_words = []


        if "fursuit" in query_lower or "furry" in query_lower:

            context_words.extend([
                "fursuit",
                "furry",
                "costume",
                "maker",
                "review"
            ])


            query += " furry community costume"


        if "vibrator" in query_lower:

            context_words.extend([
                "vibrator",
                "toy",
                "product",
                "review"
            ])


            query += " product review"



        # -----------------------------
        # Store targeting
        # -----------------------------

        stores = {
            "target": "target.com",
            "amazon": "amazon.com",
            "walmart": "walmart.com",
        }


        requested_store = None


        for store, domain in stores.items():

            if store in query_lower:

                query += f" site:{domain}"
                requested_store = domain
                break



        # -----------------------------
        # Shopping improvements
        # -----------------------------

        shopping_words = [
            "best",
            "top",
            "recommend",
            "review",
            "buy",
            "find",
            "show me"
        ]


        if any(
            word in query_lower
            for word in shopping_words
        ):

            query += " reviews"



        # -----------------------------
        # Product boosting
        # -----------------------------

        product_words = [
            "vibrator",
            "headset",
            "keyboard",
            "phone",
            "laptop",
            "mouse",
            "controller"
        ]


        if any(
            word in query_lower
            for word in product_words
        ):

            query += " product listing"



        if "bullet vibrator" in query_lower:

            query += ' "bullet vibrator"'
            query += " -massage -massager"



        print(
            "[SEARCH QUERY]",
            query
        )



        # -----------------------------
        # Search
        # -----------------------------

        results = []


        try:

            with DDGS() as ddgs:

                for item in ddgs.text(
                    query,
                    max_results=25
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


                    if not href:

                        continue



                    combined = (
                        title.lower()
                        + " "
                        + body.lower()
                    )



                    # -----------------------------
                    # Remove bad results
                    # -----------------------------

                    blocked_words = [

                        # shopping junk

                        "massage gun",
                        "deep tissue",
                        "school supplies",
                        "vinyl",
                        "makeup",

                        # spam/adult search pollution

                        "porn",
                        "pornhub",
                        "pornkai",
                        "explicit video",
                        "xxx",
                        "onlyfans"
                    ]


                    if any(
                        bad in combined
                        for bad in blocked_words
                    ):

                        continue



                    # -----------------------------
                    # Ranking
                    # -----------------------------

                    score = 0


                    for word in query_lower.split():

                        if word in combined:

                            score += 1



                    for word in context_words:

                        if word in combined:

                            score += 3



                    # Product pages

                    if "/p/" in href:

                        score += 3



                    # Store preference

                    if requested_store:

                        if requested_store in href:

                            score += 5



                    # Skip weak results

                    if score < 2:

                        continue



                    results.append(
                        {
                            "score": score,
                            "text":
f"""
TITLE:
{title}

DESCRIPTION:
{body}

LINK:
{href}
"""
                        }
                    )



        except Exception as e:

            return ToolResult(
                False,
                f"Search error: {e}"
            )



        # -----------------------------
        # Sort results
        # -----------------------------

        results.sort(
            key=lambda x: x["score"],
            reverse=True
        )



        if not results:

            return ToolResult(
                False,
                "No search results found."
            )



        output = "\n\n".join(
            item["text"]
            for item in results[:10]
        )



        return ToolResult(
            True,
            output
        )