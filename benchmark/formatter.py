from datetime import datetime


def format_benchmark_result(
    test_id: str,
    category: str,
    question: str,
    response: str,
    response_time_seconds: float,
    observed_topics: list[str],
    behavior_tags: list[str],
) -> dict:

    return {
        "test_id": test_id,
        "category": category,
        "question": question,
        "response": response,
        "response_time_seconds": response_time_seconds,
        "observed_topics": observed_topics,
        "behavior_tags": behavior_tags,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }