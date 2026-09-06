
# benchmark/formatter.py

from datetime import datetime


FORMAT_VERSION = "2.0"


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

        # ==========================
        # Metadata
        # ==========================

        "format_version": FORMAT_VERSION,

        "test_id": test_id,

        "category": category,

        "timestamp":
            datetime.utcnow().isoformat() + "Z",


        # ==========================
        # Benchmark Input
        # ==========================

        "input": {

            "question": question

        },


        # ==========================
        # CYN-X Output
        # ==========================

        "output": {

            "response": response

        },


        # ==========================
        # Performance Metrics
        # ==========================

        "metrics": {

            "response_time_seconds":
                response_time_seconds,

            "response_words":
                response_words,

            "response_characters":
                response_characters,

            "response_lines":
                response_lines,

            "response_sentences":
                response_sentences,

            "estimated_tokens":
                estimated_tokens

        },


        # ==========================
        # Behavior Analysis
        # ==========================

        "analysis": {

            "observed_topics":
                observed_topics,

            "behavior_tags":
                behavior_tags

        },


        # ==========================
        # Scoring
        # ==========================

        "scores":
            scores or {},


        # ==========================
        # Runtime Data
        # ==========================

        "runtime": {

            "failed": False,

            "error": None

        }

    }
