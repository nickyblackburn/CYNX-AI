from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from ddgs import DDGS
from tools.base import BaseTool, ToolResult


# ============================================================
# Output Types
# ============================================================

class OutputMode(str, Enum):
    NORMAL = "normal"
    ANSWER = "answer"
    LIST = "list"
    COMPARISON = "comparison"
    PRODUCT = "product"
    GUIDE = "guide"
    POSITIONS = "positions"


# ============================================================
# Ranking Configuration
# ============================================================

@dataclass
class RankingProfile:

    topic_title: int = 10
    topic_body: int = 4

    priority_title: int = 6
    priority_body: int = 2

    context_title: int = 3
    context_body: int = 1

    query_title: int = 4
    query_body: int = 1

    negative_title: int = -8
    negative_body: int = -4



# ============================================================
# Search Intent
# ============================================================

@dataclass
class SearchIntent:
    """
    Represents what the user is actually trying to find.
    """

    subject: str

    modifiers: list[str] = field(
        default_factory=list
    )

    output_type: OutputMode = OutputMode.NORMAL


    # Things we want to find
    positive_keywords: tuple[str, ...] = ()


    # Strong ranking signals
    priority_keywords: tuple[str, ...] = ()


    # Supporting context
    context_keywords: tuple[str, ...] = ()


    # Things that hurt ranking
    negative_keywords: tuple[str, ...] = ()


    # Original query tokens
    query_terms: tuple[str, ...] = ()


    requested_store: str | None = None


    is_adult_search: bool = False


    ranking_profile: RankingProfile = field(
        default_factory=RankingProfile
    )



# ============================================================
# Constants
# ============================================================

QUERY_STOPWORDS = {

    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "me",
    "show",
    "please",
    "with",
    "on",
    "at",
    "by",
    "from",

    "best",
    "top",
    "review",
    "reviews",
    "buy",
    "find",
    "list",

    "guide",
    "product",
    "products",
    "listing",

}



INTENT_PATTERNS = {

    OutputMode.POSITIONS: {

        "position",
        "positions",
        "sex position",
        "sex positions",

    },


    OutputMode.LIST: {

        "best",
        "top",
        "recommend",
        "recommended",
        "list",
        "five",
        "1-5",

    },


    OutputMode.PRODUCT: {

        "buy",
        "purchase",
        "price",
        "review",

    }

}



TOPIC_RULES = {


    "positions": {

        "positive": (

            "position",
            "positions",
            "comfort",
            "intimacy",

        ),

        "priority": (

            "guide",
            "health",
            "relationship",

        ),

        "negative": (

            "community",
            "wiki",
            "fandom",
            "maker",
            "review",

        ),

    },



    "fursuit": {

        "positive": (

            "fursuit",
            "fursuited",
            "furry",

        ),

        "context": (

            "fursuit",
            "furry",

        ),

    },


    "vibrator": {

        "positive": (

            "vibrator",
            "product",

        ),

        "context": (

            "review",
            "product",

        ),

    },


}



PRODUCT_KEYWORDS = {

    "vibrator",
    "headset",
    "keyboard",
    "phone",
    "laptop",
    "mouse",
    "controller",

}



STORE_DOMAINS = {

    "target": "target.com",

    "amazon": "amazon.com",

    "walmart": "walmart.com",

}



TRUSTED_DOMAINS = {

    "github.com": 3,

    "python.org": 5,

    "docs.python.org": 6,

    "wikipedia.org": 2,

    "nih.gov": 6,

}



ADULT_INDICATORS = {

    "sex",
    "porn",
    "nsfw",
    "nude",
    "position",
    "positions",
    "knot",

}



BLOCKED_PHRASES = {

    "massage gun",
    "deep tissue",
    "school supplies",
    "cake recipe",
    "dating app",
    "video chat",
    "vinyl",
    "makeup",

}

# ============================================================
# Utility Functions
# ============================================================

def contains_any(text: str, words: Iterable[str]) -> bool:
    return any(word in text for word in words)



def dedupe_terms(*groups: Iterable[str]) -> list[str]:

    seen = set()
    output = []

    for group in groups:

        for item in group:

            item = item.strip()

            if item and item not in seen:

                seen.add(item)
                output.append(item)

    return output



def extract_query_tokens(query: str) -> tuple[str, ...]:

    tokens = re.findall(
        r"[a-z0-9-]+",
        query.lower()
    )

    return tuple(
        token
        for token in tokens
        if token not in QUERY_STOPWORDS
        and len(token) > 1
    )



# ============================================================
# Output Detection
# ============================================================

def detect_output_type(query: str) -> OutputMode:

    query = query.lower()

    for mode, keywords in INTENT_PATTERNS.items():

        if contains_any(query, keywords):

            return mode


    return OutputMode.NORMAL



# ============================================================
# Intent Builder
# ============================================================

def build_intent(query: str) -> SearchIntent:

    query_lower = query.lower().strip()


    output_type = detect_output_type(
        query_lower
    )


    positive = []
    priority = []
    context = []
    negative = []
    modifiers = []



    adult_search = contains_any(
        query_lower,
        ADULT_INDICATORS
    )



    # -------------------------
    # Position intent
    # -------------------------

    if output_type == OutputMode.POSITIONS:

        rules = TOPIC_RULES["positions"]


        positive.extend(
            rules["positive"]
        )


        priority.extend(
            rules["priority"]
        )


        negative.extend(
            rules["negative"]
        )


        modifiers.extend(
            [
                "guide",
                "comfort",
            ]
        )



    # -------------------------
    # Fursuit modifier
    # -------------------------

    has_fursuit = contains_any(
        query_lower,
        {
            "fursuit",
            "furry"
        }
    )


    if has_fursuit:

        rules = TOPIC_RULES["fursuit"]


        positive.extend(
            rules["positive"]
        )


        context.extend(
            rules["context"]
        )


        # IMPORTANT:
        # Fursuit is a modifier.
        # It does NOT replace the topic.

        if adult_search:

            modifiers.extend(
                [
                    '"fursuit"',
                    "guide",
                ]
            )


        else:

            modifiers.append(
                "fursuit"
            )



    # -------------------------
    # Product intent
    # -------------------------

    if contains_any(
        query_lower,
        PRODUCT_KEYWORDS
    ):

        rules = TOPIC_RULES["vibrator"]


        positive.extend(
            rules["positive"]
        )


        context.extend(
            rules["context"]
        )


        modifiers.append(
            "product review"
        )



    # -------------------------
    # Store targeting
    # -------------------------

    requested_store = None


    for store, domain in STORE_DOMAINS.items():

        if store in query_lower:

            requested_store = domain

            modifiers.append(
                f"site:{domain}"
            )

            break



    # -------------------------
    # Shopping keywords
    # -------------------------

    if contains_any(
        query_lower,
        {
            "best",
            "top",
            "recommend",
            "review",
            "buy",
            "find",
            "show me",
        }
    ):

        modifiers.append(
            "reviews"
        )



    # -------------------------
    # Product boosting
    # -------------------------

    if contains_any(
        query_lower,
        PRODUCT_KEYWORDS
    ):

        modifiers.append(
            "product listing"
        )



    # -------------------------
    # Special bullet vibrator
    # -------------------------

    if "bullet vibrator" in query_lower:

        modifiers.extend(
            [
                '"bullet vibrator"',
                "-massage",
                "-massager",
            ]
        )



    return SearchIntent(

        subject=query,

        modifiers=dedupe_terms(
            modifiers
        ),

        output_type=output_type,


        positive_keywords=tuple(
            dedupe_terms(
                positive
            )
        ),


        priority_keywords=tuple(
            dedupe_terms(
                priority
            )
        ),


        context_keywords=tuple(
            dedupe_terms(
                context
            )
        ),


        negative_keywords=tuple(
            dedupe_terms(
                negative
            )
        ),


        query_terms=extract_query_tokens(
            query_lower
        ),


        requested_store=requested_store,


        is_adult_search=adult_search,

    )



# ============================================================
# Search Query Builder
# ============================================================

def build_search_query(
    intent: SearchIntent
) -> str:

    return " ".join(
        dedupe_terms(
            [
                intent.subject
            ],
            intent.modifiers
        )
    )


# ============================================================
# Result Filtering
# ============================================================

class ResultFilter:
    """
    Removes duplicate, broken, and unrelated results.
    """

    def __init__(self):

        self.seen_urls = set()



    def is_bad_result(
        self,
        title: str,
        body: str,
        href: str
    ) -> bool:


        if not title or not href:

            return True



        href_lower = href.lower()


        if href_lower in self.seen_urls:

            return True



        self.seen_urls.add(
            href_lower
        )


        combined = (
            title.lower()
            + " "
            + body.lower()
            + " "
            + href_lower
        )



        # Broken pages

        if contains_any(
            combined,
            {
                "javascript:",
                "about:blank",
                "data:"
            }
        ):

            return True



        # Junk topics

        if contains_any(
            combined,
            BLOCKED_PHRASES
        ):

            return True



        return False



# ============================================================
# Ranking Engine
# ============================================================

class ResultRanker:
    """
    Scores search results based on intent.
    """

    def __init__(
        self,
        intent: SearchIntent
    ):

        self.intent = intent
        self.profile = intent.ranking_profile



    def rank(
        self,
        title: str,
        body: str,
        href: str
    ) -> int:


        title_lower = title.lower()

        combined = (
            title_lower
            + " "
            + body.lower()
        )


        score = 0



        # Positive topic matching

        score += self.score_keywords(
            title_lower,
            combined,
            self.intent.positive_keywords,
            self.profile.topic_title,
            self.profile.topic_body
        )



        # Important keywords

        score += self.score_keywords(
            title_lower,
            combined,
            self.intent.priority_keywords,
            self.profile.priority_title,
            self.profile.priority_body
        )



        # Context

        score += self.score_keywords(
            title_lower,
            combined,
            self.intent.context_keywords,
            self.profile.context_title,
            self.profile.context_body
        )



        # Original query

        score += self.score_keywords(
            title_lower,
            combined,
            self.intent.query_terms,
            self.profile.query_title,
            self.profile.query_body
        )



        # Negative ranking

        score += self.score_negative(
            title_lower,
            combined
        )



        # Output type

        score += self.output_bonus(
            title_lower
        )



        # Store bonus

        score += self.store_bonus(
            href
        )



        # Domain quality

        score += self.domain_bonus(
            href
        )



        return score



    # --------------------------------------------------------

    @staticmethod
    def score_keywords(
        title: str,
        combined: str,
        keywords: tuple[str, ...],
        title_weight: int,
        body_weight: int
    ) -> int:


        score = 0


        for keyword in keywords:


            if keyword in title:

                score += title_weight


            elif keyword in combined:

                score += body_weight



        return score



    # --------------------------------------------------------

    def score_negative(
        self,
        title: str,
        combined: str
    ) -> int:


        score = 0


        for keyword in self.intent.negative_keywords:


            if keyword in title:

                score += self.profile.negative_title


            elif keyword in combined:

                score += self.profile.negative_body



        return score



    # --------------------------------------------------------

    def output_bonus(
        self,
        title: str
    ) -> int:


        score = 0



        if self.intent.output_type == OutputMode.POSITIONS:


            if "position" in title:

                score += 10


            if "positions" in title:

                score += 10


            if "guide" in title:

                score += 3



        elif self.intent.output_type == OutputMode.LIST:


            if "top" in title:

                score += 3


            if "best" in title:

                score += 3



        elif self.intent.output_type == OutputMode.PRODUCT:


            if "review" in title:

                score += 3


            if "product" in title:

                score += 3



        return score



    # --------------------------------------------------------

    def store_bonus(
        self,
        href: str
    ) -> int:


        if (
            self.intent.requested_store
            and self.intent.requested_store in href
        ):

            return 5



        return 0



    # --------------------------------------------------------

    @staticmethod
    def domain_bonus(
        href: str
    ) -> int:


        score = 0


        href_lower = href.lower()


        for domain, bonus in TRUSTED_DOMAINS.items():


            if domain in href_lower:

                score += bonus



        if "/p/" in href_lower:

            score += 3



        return score


# ============================================================
# CYN Extraction Instructions
# ============================================================

OUTPUT_INSTRUCTIONS = {

    OutputMode.POSITIONS: """

[SEARCH TASK]

The user wants the actual answer.

Use the search results as information sources.

Rules:
- Extract the useful information.
- Ignore unrelated pages.
- Do not summarize each website.
- Do not talk about the search process.
- Return a numbered list when appropriate.
- Keep the answer focused on the user's requested topic.

Return the answer naturally as CYN.

""",


    OutputMode.LIST: """

[SEARCH TASK]

The user requested a list.

Rules:
- Pick the most relevant items.
- Use numbering.
- Remove duplicates.
- Ignore advertisements.
- Do not explain the search process.

Return the list directly.

""",


    OutputMode.PRODUCT: """

[SEARCH TASK]

The user wants product information.

Rules:
- Extract the useful products.
- Include important differences.
- Ignore unrelated results.
- Do not just repeat product titles.

Answer naturally.

""",


    OutputMode.NORMAL: """

[SEARCH TASK]

Answer the user's question using the search results.

Rules:
- Extract useful information.
- Ignore unrelated results.
- Do not mention searching unless needed.

""",

}



# ============================================================
# Main Search Tool
# ============================================================

class WebSearchTool(BaseTool):

    name = "web_search"

    description = (
        "Search the internet for current information."
    )



    def call(self, args):


        query = args.get(
            "query"
        )


        if not query:


            return ToolResult(

                False,

                "Missing query"

            )



        # -------------------------
        # Understand request
        # -------------------------

        intent = build_intent(
            query
        )


        search_query = build_search_query(
            intent
        )


        print(
            "[SEARCH QUERY]",
            search_query
        )



        # -------------------------
        # Search
        # -------------------------

        results = []


        filter_engine = ResultFilter()

        ranker = ResultRanker(
            intent
        )



        try:


            with DDGS() as ddgs:


                for item in ddgs.text(

                    search_query,

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



                    if filter_engine.is_bad_result(

                        title,

                        body,

                        href

                    ):

                        continue



                    score = ranker.rank(

                        title,

                        body,

                        href

                    )



                    # Ignore weak matches

                    if score < 1:

                        continue



                    results.append(

                        {

                            "score": score,

                            "text": format_result(

                                title,

                                body,

                                href

                            )

                        }

                    )



        except Exception as e:


            return ToolResult(

                False,

                f"Search error: {e}"

            )



        # -------------------------
        # Sort results
        # -------------------------

        results.sort(

            key=lambda item: item["score"],

            reverse=True

        )



        if not results:


            return ToolResult(

                False,

                "No search results found."

            )



        # -------------------------
        # Send to Cyn
        # -------------------------

        output = "\n\n".join(

            item["text"]

            for item in results[:10]

        )



        output += OUTPUT_INSTRUCTIONS.get(

            intent.output_type,

            OUTPUT_INSTRUCTIONS[

                OutputMode.NORMAL

            ]

        )



        return ToolResult(

            True,

            output

        )


    # ============================================================
    # Result Formatter
    # ============================================================

    def format_result(
        title: str,
        body: str,
        href: str
    ) -> str:

        return f"""
    TITLE:
    {title}

    DESCRIPTION:
    {body}

    LINK:
    {href}
    """

    