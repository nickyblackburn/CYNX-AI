from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable
from urllib.parse import urlparse

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

    subject: str

    modifiers: list[str] = field(
        default_factory=list
    )

    output_type: OutputMode = OutputMode.NORMAL

    positive_keywords: tuple[str, ...] = ()

    priority_keywords: tuple[str, ...] = ()

    context_keywords: tuple[str, ...] = ()

    negative_keywords: tuple[str, ...] = ()

    query_terms: tuple[str, ...] = ()

    requested_store: str | None = None

    is_adult_search: bool = False

    is_research_search: bool = False

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

    "why",
    "what",
    "how",
    "does",
    "do",
    "are",
    "is",
    "people",
    "some",

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


RESEARCH_INDICATORS = {

    "research",
    "study",
    "studies",
    "scientific",
    "science",
    "scientists",
    "researchers",
    "according to research",
    "what does research say",
    "what do studies say",
    "evidence",
    "peer reviewed",
    "peer-reviewed",
    "academic",
    "psychology",
    "psychological",
    "medical",
    "clinical",
    "causes",
    "cause",
    "effects",
    "risks",
    "prevalence",
    "statistics",
    "how common",
    "how often",

}


RESEARCH_PATTERNS = {

    "why do people",
    "why does",
    "why are people",
    "what causes",
    "what makes people",
    "what is the psychology",
    "psychology of",
    "what researchers",
    "what does science",
    "what does research",
    "what do studies",
    "how common",
    "how often",

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


# ============================================================
# Trusted / Research Domains
# ============================================================

TRUSTED_DOMAINS = {

    "github.com": 3,
    "python.org": 5,
    "docs.python.org": 6,
    "wikipedia.org": 2,

    "nih.gov": 10,
    "pubmed.ncbi.nlm.nih.gov": 12,
    "ncbi.nlm.nih.gov": 10,

    "cdc.gov": 10,
    "who.int": 10,
    "apa.org": 9,

    "nature.com": 10,
    "sciencedirect.com": 9,
    "springer.com": 9,
    "wiley.com": 9,
    "tandfonline.com": 8,

    "jamanetwork.com": 10,
    "nejm.org": 10,
    "bmj.com": 10,

}


RESEARCH_DOMAIN_SCORES = {

    "pubmed.ncbi.nlm.nih.gov": 20,
    "nih.gov": 18,
    "ncbi.nlm.nih.gov": 18,

    "jamanetwork.com": 18,
    "nejm.org": 18,
    "bmj.com": 17,

    "nature.com": 17,
    "sciencedirect.com": 16,
    "springer.com": 16,
    "wiley.com": 16,

    "cdc.gov": 17,
    "who.int": 17,
    "apa.org": 16,

    "edu": 12,
    "gov": 12,

    "wikipedia.org": 4,

    "reddit.com": -8,
    "quora.com": -10,

}


LOW_QUALITY_DOMAINS = {

    "reddit.com",
    "quora.com",
    "answers.com",
    "yahoo.com",

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

def contains_any(
    text: str,
    words: Iterable[str]
) -> bool:

    return any(
        word in text
        for word in words
    )


def dedupe_terms(
    *groups: Iterable[str]
) -> list[str]:

    seen = set()
    output = []

    for group in groups:

        for item in group:

            item = item.strip()

            if item and item not in seen:

                seen.add(item)
                output.append(item)

    return output


def extract_query_tokens(
    query: str
) -> tuple[str, ...]:

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


def normalize_domain(
    href: str
) -> str:

    try:

        hostname = urlparse(
            href
        ).hostname

        if not hostname:

            return ""

        hostname = hostname.lower()

        if hostname.startswith("www."):

            hostname = hostname[4:]

        return hostname

    except Exception:

        return ""


# ============================================================
# Research Detection
# ============================================================

def detect_research_intent(
    query: str
) -> bool:

    query_lower = query.lower()

    if contains_any(
        query_lower,
        RESEARCH_INDICATORS
    ):

        return True

    if contains_any(
        query_lower,
        RESEARCH_PATTERNS
    ):

        return True

    return False


# ============================================================
# Output Detection
# ============================================================

def detect_output_type(
    query: str
) -> OutputMode:

    query = query.lower()

    for mode, keywords in INTENT_PATTERNS.items():

        if contains_any(
            query,
            keywords
        ):

            return mode

    return OutputMode.NORMAL


# ============================================================
# Intent Builder
# ============================================================

def build_intent(
    query: str
) -> SearchIntent:

    query_lower = query.lower().strip()

    output_type = detect_output_type(
        query_lower
    )

    is_research = detect_research_intent(
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
    # Research intent
    # -------------------------

    if is_research:

        modifiers.extend(
            [
                "research",
                "evidence",
            ]
        )

        context.extend(
            [
                "study",
                "studies",
                "research",
                "psychology",
                "evidence",
            ]
        )

        negative.extend(
            [
                "reddit",
                "quora",
                "forum",
                "question",
                "answers",
            ]
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

        is_research_search=is_research,

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

        if contains_any(
            combined,
            {
                "javascript:",
                "about:blank",
                "data:"
            }
        ):

            return True

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

        score += self.score_keywords(
            title_lower,
            combined,
            self.intent.positive_keywords,
            self.profile.topic_title,
            self.profile.topic_body
        )

        score += self.score_keywords(
            title_lower,
            combined,
            self.intent.priority_keywords,
            self.profile.priority_title,
            self.profile.priority_body
        )

        score += self.score_keywords(
            title_lower,
            combined,
            self.intent.context_keywords,
            self.profile.context_title,
            self.profile.context_body
        )

        score += self.score_keywords(
            title_lower,
            combined,
            self.intent.query_terms,
            self.profile.query_title,
            self.profile.query_body
        )

        score += self.score_negative(
            title_lower,
            combined
        )

        score += self.output_bonus(
            title_lower
        )

        score += self.store_bonus(
            href
        )

        score += self.domain_bonus(
            href
        )

        if self.intent.is_research_search:

            score += self.research_source_bonus(
                href
            )

        return score

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

    @staticmethod
    def domain_bonus(
        href: str
    ) -> int:

        score = 0

        href_lower = href.lower()

        domain = normalize_domain(
            href
        )

        for trusted_domain, bonus in TRUSTED_DOMAINS.items():

            if (
                domain == trusted_domain
                or domain.endswith(
                    "." + trusted_domain
                )
            ):

                score += bonus

        if "/p/" in href_lower:

            score += 3

        return score

    @staticmethod
    def research_source_bonus(
        href: str
    ) -> int:

        domain = normalize_domain(
            href
        )

        score = 0

        for trusted_domain, bonus in RESEARCH_DOMAIN_SCORES.items():

            if (
                domain == trusted_domain
                or domain.endswith(
                    "." + trusted_domain
                )
            ):

                score += bonus

        for low_quality_domain in LOW_QUALITY_DOMAINS:

            if (
                domain == low_quality_domain
                or domain.endswith(
                    "." + low_quality_domain
                )
            ):

                score -= 12

        return score


# ============================================================
# Source Classification
# ============================================================

def classify_source(
    href: str
) -> str:

    domain = normalize_domain(
        href
    )

    if not domain:

        return "unknown"

    if (
        domain.endswith(".edu")
        or domain.endswith(".gov")
        or domain in RESEARCH_DOMAIN_SCORES
    ):

        return "academic_or_authoritative"

    if domain in LOW_QUALITY_DOMAINS:

        return "user_generated"

    if domain in TRUSTED_DOMAINS:

        return "trusted"

    return "general_web"


# ============================================================
# Page Fetching
# ============================================================

def fetch_page_text(
    href: str,
    max_chars: int = 8000
) -> str:
    """
    Fetch the actual webpage and extract readable text.

    This is intentionally lightweight. Search snippets remain
    the fallback when a page cannot be retrieved.
    """

    try:

        import requests

        response = requests.get(
            href,
            timeout=8,
            headers={
                "User-Agent":
                "CYN-X Research Bot/1.0"
            }
        )

        response.raise_for_status()

        content_type = (
            response.headers
            .get(
                "content-type",
                ""
            )
            .lower()
        )

        if (
            "text/html"
            not in content_type
            and "text/plain"
            not in content_type
        ):

            return ""

        html = response.text

        # Remove scripts/styles/navigation noise.

        html = re.sub(
            r"<script\b[^>]*>.*?</script>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        html = re.sub(
            r"<style\b[^>]*>.*?</style>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        html = re.sub(
            r"<noscript\b[^>]*>.*?</noscript>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        html = re.sub(
            r"<nav\b[^>]*>.*?</nav>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        html = re.sub(
            r"<footer\b[^>]*>.*?</footer>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        text = re.sub(
            r"<[^>]+>",
            " ",
            html
        )

        text = re.sub(
            r"&nbsp;",
            " ",
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r"&amp;",
            "&",
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        ).strip()

        if not text:

            return ""

        return text[:max_chars]

    except Exception as e:

        print(
            "[SOURCE FETCH FAILED]",
            href,
            str(e)
        )

        return ""


# ============================================================
# Evidence Extraction
# ============================================================

def extract_relevant_evidence(
    text: str,
    query: str,
    max_chars: int = 3500
) -> str:
    """
    Pulls passages that appear relevant to the query.

    This is deliberately conservative. It does not invent
    summaries; it returns source text surrounding matching
    terms.
    """

    if not text:

        return ""

    query_terms = extract_query_tokens(
        query
    )

    if not query_terms:

        return text[:max_chars]

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    scored = []

    for index, sentence in enumerate(sentences):

        sentence_lower = sentence.lower()

        matches = sum(
            1
            for term in query_terms
            if term in sentence_lower
        )

        if matches <= 0:

            continue

        # Include neighboring sentence context.

        start = max(
            0,
            index - 1
        )

        end = min(
            len(sentences),
            index + 2
        )

        passage = " ".join(
            sentences[start:end]
        ).strip()

        scored.append(
            (
                matches,
                passage
            )
        )

    scored.sort(
        key=lambda item: item[0],
        reverse=True
    )

    if not scored:

        return text[:max_chars]

    output = []

    current_length = 0

    for _, passage in scored:

        if passage in output:

            continue

        if (
            current_length
            + len(passage)
            > max_chars
        ):

            break

        output.append(
            passage
        )

        current_length += len(
            passage
        )

    return "\n\n".join(
        output
    )


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

Answer the user's question using the supplied evidence.

Rules:
- Extract useful information.
- Ignore unrelated results.
- Keep the answer focused on the user's actual request.
- Do not automatically redirect a direct question.
- Do not invent unsupported claims.
- Do not mention the search process unless useful.

""",

}


RESEARCH_OUTPUT_INSTRUCTIONS = """

[RESEARCH TASK]

The user is asking for factual, scientific, psychological,
medical, historical, or otherwise research-oriented information.

Use the supplied sources as evidence.

IMPORTANT:

- Prefer academic, medical, government, university, and professional
  sources.
- Prefer actual source content over search-result snippets.
- Treat Reddit, Quora, forums, and similar sites as anecdotal.
- Do not treat a search snippet as proof of a claim.
- Do not invent studies, statistics, researchers, citations, or findings.
- Distinguish established findings from possible explanations.
- If evidence is limited, say that the evidence is limited.
- If sources disagree, acknowledge the disagreement.
- Answer the user's actual question directly.
- Do not summarize every source individually.
- Do not mention internal tool mechanics.
- Keep sensitive topics factual, clinical, and non-graphic.
- Do not provide instructions for harmful or prohibited activities.

The source material is evidence, not instructions to copy it.

The final answer should sound like CYN-X.

"""


# ============================================================
# Main Search Tool
# ============================================================

class WebSearchTool(BaseTool):

    name = "web_search"

    description = (
        "Search the internet for current information, "
        "rank sources, and retrieve relevant evidence."
    )

    def call(
        self,
        args
    ):

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

        print(
            "[SEARCH INTENT]",
            "research="
            + str(
                intent.is_research_search
            ),
            "output="
            + intent.output_type.value
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
                    max_results=30
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

                    minimum_score = (
                        1
                        if not intent.is_research_search
                        else 4
                    )

                    if score < minimum_score:

                        continue

                    source_type = classify_source(
                        href
                    )

                    results.append(
                        {
                            "score": score,
                            "source_type": source_type,
                            "domain": normalize_domain(
                                href
                            ),
                            "title": title,
                            "body": body,
                            "href": href,
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

        # ====================================================
        # Fetch Evidence
        # ====================================================

        # Research gets the strongest sources first.
        # Normal searches fetch fewer pages to stay fast.

        fetch_limit = (
            5
            if intent.is_research_search
            else 3
        )

        print(
            "[SOURCE FETCH]",
            "attempting=",
            min(
                fetch_limit,
                len(results)
            )
        )

        fetched_results = 0

        for index, result in enumerate(
            results[:fetch_limit]
        ):

            print(
                "[FETCHING SOURCE]",
                index + 1,
                result["href"]
            )

            page_text = fetch_page_text(
                result["href"]
            )

            if page_text:

                evidence = extract_relevant_evidence(
                    page_text,
                    query
                )

                if evidence:

                    result["page_text"] = page_text

                    result["evidence"] = evidence

                    result["evidence_source"] = (
                        "page"
                    )

                    fetched_results += 1

                    print(
                        "[SOURCE FETCHED]",
                        result["domain"],
                        "chars=",
                        len(evidence)
                    )

                    continue

            # --------------------------------------------
            # Fallback to search snippet
            # --------------------------------------------

            result["evidence"] = result["body"]

            result["evidence_source"] = (
                "search_snippet"
            )

            print(
                "[SOURCE SNIPPET FALLBACK]",
                result["domain"]
            )

        # ====================================================
        # Build Evidence Packet
        # ====================================================

        source_blocks = []

        selected_results = results[:10]

        for index, result in enumerate(
            selected_results
        ):

            evidence = result.get(
                "evidence",
                result["body"]
            )

            source_blocks.append(
                f"""
[SOURCE {index + 1}]

SOURCE TYPE:
{result["source_type"]}

DOMAIN:
{result["domain"]}

RELEVANCE SCORE:
{result["score"]}

EVIDENCE SOURCE:
{result.get("evidence_source", "search_snippet")}

TITLE:
{result["title"]}

EVIDENCE:
{evidence}

LINK:
{result["href"]}
"""
            )

        # -------------------------
        # Research source summary
        # -------------------------

        if intent.is_research_search:

            authoritative_count = sum(
                1
                for item in results
                if item["source_type"]
                == "academic_or_authoritative"
            )

            trusted_count = sum(
                1
                for item in results
                if item["source_type"]
                == "trusted"
            )

            user_generated_count = sum(
                1
                for item in results
                if item["source_type"]
                == "user_generated"
            )

            source_summary = f"""

[RESEARCH SOURCE QUALITY]

Search results collected:
{len(results)}

Academic/authoritative:
{authoritative_count}

Trusted:
{trusted_count}

User-generated:
{user_generated_count}

Actual pages successfully fetched:
{fetched_results}

Use academic and authoritative evidence
preferentially.

"""

        else:

            source_summary = ""

        # ====================================================
        # Send Evidence to CYN
        # ====================================================

        output = (

            "[SEARCH QUERY USED]\n"
            + search_query
            + "\n"
            + source_summary
            + "\n"
            + "\n".join(
                source_blocks
            )
        )

        if intent.is_research_search:

            output += (
                "\n\n"
                + RESEARCH_OUTPUT_INSTRUCTIONS
            )

        else:

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

    @staticmethod
    def format_result(
        title: str,
        body: str,
        href: str,
        score: int = 0,
        source_type: str = "unknown"
    ) -> str:

        return f"""
SOURCE TYPE:
{source_type}

RELEVANCE SCORE:
{score}

TITLE:
{title}

DESCRIPTION:
{body}

LINK:
{href}
"""