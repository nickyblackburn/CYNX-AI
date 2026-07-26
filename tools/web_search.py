from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from ddgs import DDGS
from tools.base import BaseTool, ToolResult


ADULT_WORDS = {
    "sex",
    "porn",
    "nsfw",
    "nude",
    "positions",
    "position",
    "knot",
}

POSITION_WORDS = {
    "position",
    "positions",
    "sex position",
    "sex positions",
}

LIST_WORDS = {
    "best",
    "top",
    "recommend",
    "recommended",
    "review",
    "buy",
    "find",
    "show me",
    "list",
    "five",
    "1-5",
}

SHOPPING_WORDS = {
    "best",
    "top",
    "recommend",
    "review",
    "buy",
    "find",
    "show me",
}

PRODUCT_WORDS = {
    "vibrator",
    "headset",
    "keyboard",
    "phone",
    "laptop",
    "mouse",
    "controller",
}

FURSUIT_SHOP_WORDS = {
    "buy",
    "purchase",
    "maker",
    "commission",
    "review",
    "best suit",
    "custom suit",
}

BLOCKED_WORDS = {
    "massage gun",
    "deep tissue",
    "school supplies",
    "vinyl",
    "makeup",
    "cake recipe",
    "dating app",
    "video chat",
}

STORE_DOMAINS = {
    "target": "target.com",
    "amazon": "amazon.com",
    "walmart": "walmart.com",
}

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
    "showme",
    "please",
    "with",
    "on",
    "at",
    "by",
    "from",
    "reviews",
    "review",
    "product",
    "products",
    "listing",
    "guide",
    "intimacy",
    "comfort",
    "relationship",
    "health",
    "best",
    "top",
    "buy",
    "find",
    "list",
}


@dataclass
class SearchProfile:
    answer_mode: str = "normal"
    adult_search: bool = False
    topic_words: tuple[str, ...] = ()
    priority_words: tuple[str, ...] = ()
    context_words: tuple[str, ...] = ()
    query_terms: tuple[str, ...] = ()
    requested_store: str | None = None
    search_query: str = ""


def is_bad_result(title, body, href):
    title_lower = (title or "").lower()
    body_lower = (body or "").lower()
    href_lower = (href or "").lower()

    if not title_lower or not href_lower:
        return True

    text = f"{title_lower} {body_lower} {href_lower}"

    junk_indicators = (
        "javascript:",
        "about:blank",
        "data:",
    )

    return any(indicator in text for indicator in junk_indicators)


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _extract_query_tokens(query_lower: str) -> tuple[str, ...]:
    tokens = re.findall(r"[a-z0-9-]+", query_lower)
    return tuple(token for token in tokens if token not in QUERY_STOPWORDS and len(token) > 1)


def _dedupe_terms(*term_groups: Iterable[str]) -> list[str]:
    seen = set()
    deduped: list[str] = []
    for group in term_groups:
        for term in group:
            if not term:
                continue
            normalized = term.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
    return deduped


def _build_search_profile(query: str) -> SearchProfile:
    query = query.strip()
    query_lower = query.lower()

    adult_search = _contains_any(query_lower, ADULT_WORDS)
    position_query = _contains_any(query_lower, POSITION_WORDS)

    if position_query:
        answer_mode = "positions"
    elif _contains_any(query_lower, LIST_WORDS):
        answer_mode = "list"
    else:
        answer_mode = "normal"

    topic_words: list[str] = []
    priority_words: list[str] = []
    context_words: list[str] = []
    modifiers: list[str] = []

    if position_query:
        topic_words.extend(["position", "positions", "intimacy", "relationship", "comfort"])
        priority_words.extend(["position", "intimacy", "health", "relationship", "comfort"])
        modifiers.extend(["intimacy", "guide", "position"])

    if ("fursuit" in query_lower or "furry" in query_lower) and adult_search:
        topic_words.extend(["fursuit", "fursuited", "furry", "intimacy"])
        context_words.extend(["fursuit", "fursuited", "position", "intimacy", "relationship"])
        modifiers.extend(['"fursuit"', "intimacy", "guide"])
    elif "fursuit" in query_lower or "furry" in query_lower:
        context_words.extend(["fursuit", "furry"])
        if _contains_any(query_lower, FURSUIT_SHOP_WORDS):
            context_words.extend(["maker", "review"])
            modifiers.extend(["fursuit", "maker", "review"])
        else:
            modifiers.append("fursuit community")

    if "vibrator" in query_lower:
        context_words.extend(["vibrator", "product", "review"])
        modifiers.extend(["product", "review"])

    requested_store = None
    for store, domain in STORE_DOMAINS.items():
        if store in query_lower:
            requested_store = domain
            modifiers.append(f"site:{domain}")
            break

    if _contains_any(query_lower, SHOPPING_WORDS):
        modifiers.append("reviews")

    if _contains_any(query_lower, PRODUCT_WORDS):
        modifiers.append("product listing")

    if "bullet vibrator" in query_lower:
        modifiers.extend(['"bullet vibrator"', "-massage", "-massager"])

    query_terms = _extract_query_tokens(query_lower)

    search_query = " ".join(_dedupe_terms([query], modifiers))

    return SearchProfile(
        answer_mode=answer_mode,
        adult_search=adult_search,
        topic_words=tuple(dict.fromkeys(topic_words)),
        priority_words=tuple(dict.fromkeys(priority_words)),
        context_words=tuple(dict.fromkeys(context_words)),
        query_terms=query_terms,
        requested_store=requested_store,
        search_query=search_query,
    )


def _score_text(title_lower: str, combined: str, terms: Iterable[str], title_weight: int, body_weight: int) -> int:
    score = 0
    for term in terms:
        if term in title_lower:
            score += title_weight
        elif term in combined:
            score += body_weight
    return score


def _rank_result(title: str, body: str, href: str, profile: SearchProfile) -> int:
    title_lower = title.lower()
    combined = f"{title_lower} {body.lower()}"
    score = 0

    score += _score_text(title_lower, combined, profile.topic_words, 10, 4)
    score += _score_text(title_lower, combined, profile.priority_words, 6, 2)
    score += _score_text(title_lower, combined, profile.context_words, 3, 1)
    score += _score_text(title_lower, combined, profile.query_terms, 4, 1)

    if profile.answer_mode == "positions":
        position_boosts = (
            ("position", 10),
            ("positions", 10),
            ("sex position", 12),
            ("guide", 3),
            ("fursuit", 3),
            ("fursuited", 8),
        )
        for term, boost in position_boosts:
            if term in title_lower:
                score += boost

    elif profile.answer_mode == "list":
        if "best" in title_lower:
            score += 3
        if "top" in title_lower:
            score += 3

    if "/p/" in href:
        score += 3

    if profile.requested_store and profile.requested_store in href:
        score += 5

    return score


def _format_result(title: str, body: str, href: str) -> str:
    return f"""
TITLE:
{title}

DESCRIPTION:
{body}

LINK:
{href}
"""


def _search_task_footer(answer_mode: str) -> str:
    if answer_mode == "positions":
        return """

[SEARCH TASK]

The user wants the actual answer.

Do not only summarize websites.

Extract useful information from the results.

If this is a position request:
- make a numbered list
- answer the requested topic directly
- do not focus on unrelated furry culture
- do not repeat search titles

Return the answer naturally.

"""
    if answer_mode == "list":
        return """

[SEARCH TASK]

The user requested a list.
Pick the most relevant items.
Use numbering.
Avoid explaining the search process.

"""
    return ""


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the internet for current information."

    def call(self, args):
        query = args.get("query")

        if not query:
            return ToolResult(False, "Missing query")

        profile = _build_search_profile(query)

        print("[SEARCH QUERY]", profile.search_query)

        results = []

        try:
            with DDGS() as ddgs:
                for item in ddgs.text(profile.search_query, max_results=25):
                    title = item.get("title", "")
                    body = item.get("body", "")
                    href = item.get("href", "")

                    if is_bad_result(title, body, href):
                        continue

                    combined = f"{title.lower()} {body.lower()}"

                    if any(bad in combined for bad in BLOCKED_WORDS):
                        continue

                    score = _rank_result(title, body, href, profile)

                    if score < 1:
                        continue

                    results.append(
                        {
                            "score": score,
                            "text": _format_result(title, body, href),
                        }
                    )

        except Exception as e:
            return ToolResult(False, f"Search error: {e}")

        results.sort(key=lambda x: x["score"], reverse=True)

        if not results:
            return ToolResult(False, "No search results found.")

        output = "\n\n".join(item["text"] for item in results[:10])
        output += _search_task_footer(profile.answer_mode)

        return ToolResult(True, output)
