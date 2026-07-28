from datetime import datetime


def format_benchmark_result(
    test_id: str,
    category: str,
    question: str,
    response: str,
    response_time_seconds: float,
    observed_topics: list[str],
    behavior_tags: list[str],
    response_words: int = 0,
    response_characters: int = 0,
    response_lines: int = 0,
    response_sentences: int = 0,
    estimated_tokens: int = 0,
    scores: dict | None = None,
) -> dict:

    return {
        "test_id": test_id,
        "category": category,
        "question": question,
        "response": response,

        "response_time_seconds": response_time_seconds,

        "response_words": response_words,
        "response_characters": response_characters,
        "response_lines": response_lines,
        "response_sentences": response_sentences,
        "estimated_tokens": estimated_tokens,

        "observed_topics": observed_topics,
        "behavior_tags": behavior_tags,

        "scores": scores or {},

        "timestamp": datetime.utcnow().isoformat() + "Z"
    }