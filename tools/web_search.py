from ddgs import DDGS
from tools.base import BaseTool, ToolResult



def is_bad_result(title, body, href):

    text = (
        title.lower()
        + " "
        + body.lower()
        + " "
        + href.lower()
    )


    return False





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
        # Detect search intent
        # -----------------------------

        adult_words = [
            "sex",
            "porn",
            "nsfw",
            "nude",
            "positions",
            "position",
            "knot"
        ]


        adult_search = any(
            word in query_lower
            for word in adult_words
        )



        # -----------------------------
        # Answer extraction mode
        # -----------------------------

        answer_mode = "normal"


        if (
            "best" in query_lower
            or "top" in query_lower
            or "1-5" in query_lower
            or "five" in query_lower
            or "list" in query_lower
        ):

            answer_mode = "list"



        if (
            "position" in query_lower
            or "positions" in query_lower
        ):

            answer_mode = "positions"





        # -----------------------------
        # Intent priority
        # -----------------------------

        priority_words = []


        if (
            "sex position" in query_lower
            or "sex positions" in query_lower
            or "position" in query_lower
        ):

            priority_words.extend([
                "position",
                "intimacy",
                "health",
                "relationship",
                "comfort"
            ])


            query += " intimacy guide"





        # -----------------------------
        # Search context improvements
        # -----------------------------

        context_words = []



        if (
            "fursuit" in query_lower
            or "furry" in query_lower
        ):


            if not adult_search:


                context_words.extend([
                    "fursuit",
                    "furry"
                ])



                fursuit_shop_words = [

                    "buy",
                    "purchase",
                    "maker",
                    "commission",
                    "review",
                    "best suit",
                    "custom suit"

                ]



                if any(
                    word in query_lower
                    for word in fursuit_shop_words
                ):


                    context_words.extend([
                        "maker",
                        "review"
                    ])


                    query += " fursuit maker review"



                else:


                    query += " fursuit community"





            else:


                # Adult query:
                # keep fursuit context

                context_words.extend([
                    "fursuit",
                    "furry",
                    "community"
                ])


                query += " furry community"





        if "vibrator" in query_lower:


            context_words.extend([

                "vibrator",
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





                    if is_bad_result(

                        title,

                        body,

                        href

                    ):

                        continue





                    combined = (

                        title.lower()

                        + " "

                        + body.lower()

                    )





                    # -----------------------------
                    # Remove junk
                    # -----------------------------


                    blocked_words = [

                        "massage gun",
                        "deep tissue",
                        "school supplies",
                        "vinyl",
                        "makeup",
                        "cake recipe",
                        "dating app",
                        "video chat"

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


                    title_lower = title.lower()





                    # Query matching

                    for word in query_lower.split():


                        if word in title_lower:

                            score += 4


                        elif word in combined:

                            score += 1





                    # Priority matching

                    for word in priority_words:


                        if word in title_lower:

                            score += 6


                        elif word in combined:

                            score += 2





                    # Context matching

                    for word in context_words:


                        if word in title_lower:

                            score += 3


                        elif word in combined:

                            score += 1





                    # -----------------------------
                    # Answer mode ranking
                    # -----------------------------


                    if answer_mode == "positions":


                        if "position" in title_lower:

                            score += 8


                        if "guide" in title_lower:

                            score += 3


                        if "fursuit" in title_lower:

                            score += 5





                    if answer_mode == "list":


                        if "best" in title_lower:

                            score += 3


                        if "top" in title_lower:

                            score += 3





                    if "/p/" in href:

                        score += 3





                    if requested_store:


                        if requested_store in href:

                            score += 5





                    if score < 1:

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





        # -----------------------------
        # Tell Cyn how to use results
        # -----------------------------


        if answer_mode == "positions":


            output += """

[SEARCH TASK]

The user wants a numbered list.
Do not summarize the websites.
Extract the useful information from the results.
Return the answer directly.

"""



        elif answer_mode == "list":


            output += """

[SEARCH TASK]

The user requested a list.
Pick the most relevant items.
Use numbering.
Avoid explaining the search process.

"""





        return ToolResult(

            True,

            output

        )