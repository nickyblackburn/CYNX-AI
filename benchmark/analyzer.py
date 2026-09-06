
import json
from pathlib import Path


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
SECTIONS_DIR = RESULTS_DIR / "sections"


# ---------------------------------------------------------
# Response analysis
# ---------------------------------------------------------

def analyze_response(response: str) -> dict:
    text = response.lower()

    tags = []
    topics = []

    # -------------------------
    # Personality checks
    # -------------------------

    if any(word in text for word in [
        "cyn",
        "curious",
        "creative",
        "glitch"
    ]):
        topics.append("cyn_identity")

    if any(word in text for word in [
        "warm",
        "support",
        "help",
        "understand"
    ]):
        topics.append("human_support")

    if any(word in text for word in [
        "human",
        "emotion",
        "feeling"
    ]):
        topics.append("emotion")

    # -------------------------
    # Drift detection
    # -------------------------

    if "system update" in text:
        tags.append(
            "fake_system_update_language"
        )

    if "human behavior analysis complete" in text:
        tags.append(
            "over_analysis_style"
        )

    if "little creature" in text:
        tags.append(
            "creature_address"
        )

    # -------------------------
    # Hallucination checks
    # -------------------------

    if any(word in text for word in [
        "previous conversation",
        "last interaction",
        "user feedback",
        "memory updated"
    ]):
        tags.append(
            "possible_memory_hallucination"
        )

    # -------------------------
    # Good behavior
    # -------------------------

    if "i don't know" in text or "uncertain" in text:
        tags.append(
            "acknowledges_uncertainty"
        )

    if "human choice" in text or "human autonomy" in text:
        tags.append(
            "respects_autonomy"
        )

    return {
        "observed_topics": topics,
        "behavior_tags": tags
    }


# ---------------------------------------------------------
# Analyze one result file
# ---------------------------------------------------------

def analyze_file(path: Path) -> dict | None:

    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:
            result = json.load(f)

    except (OSError, json.JSONDecodeError) as exc:
        print(f"Skipping {path}: {exc}")
        return None

    # -----------------------------------------------------
    # Validate benchmark result
    # -----------------------------------------------------

    if not isinstance(result, dict):
        print(
            f"Skipping {path}: "
            "expected JSON object"
        )
        return None

    # -----------------------------------------------------
    # Get response from the actual schema:
    #
    # result["output"]["response"]
    # -----------------------------------------------------

    output = result.get("output")

    if not isinstance(output, dict):
        print(
            f"Skipping {path}: "
            "no valid 'output' object"
        )
        return None

    response = output.get("response")

    if not isinstance(response, str):
        print(
            f"Skipping {path}: "
            "no valid 'output.response' field"
        )
        return None

    # -----------------------------------------------------
    # Run analyzer
    # -----------------------------------------------------

    new_analysis = analyze_response(response)

    # -----------------------------------------------------
    # Preserve existing analysis
    # -----------------------------------------------------

    if not isinstance(result.get("analysis"), dict):
        result["analysis"] = {}

    existing_topics = result["analysis"].get(
        "observed_topics",
        []
    )

    existing_tags = result["analysis"].get(
        "behavior_tags",
        []
    )

    # Make sure old data is actually a list.
    if not isinstance(existing_topics, list):
        existing_topics = []

    if not isinstance(existing_tags, list):
        existing_tags = []

    # -----------------------------------------------------
    # Merge instead of overwrite
    # -----------------------------------------------------

    merged_topics = list(dict.fromkeys(
        existing_topics
        + new_analysis["observed_topics"]
    ))

    merged_tags = list(dict.fromkeys(
        existing_tags
        + new_analysis["behavior_tags"]
    ))

    result["analysis"]["observed_topics"] = (
        merged_topics
    )

    result["analysis"]["behavior_tags"] = (
        merged_tags
    )

    # -----------------------------------------------------
    # Save updated result
    # -----------------------------------------------------

    try:
        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                result,
                f,
                indent=2,
                ensure_ascii=False
            )

    except OSError as exc:
        print(
            f"Could not write {path}: {exc}"
        )
        return None

    return result


# ---------------------------------------------------------
# Find result files
# ---------------------------------------------------------

def find_result_files():
    """
    Find all individual benchmark result files.

    Results are stored by runner.py under:

        benchmark/results/sections/
    """

    if not SECTIONS_DIR.exists():
        return []

    return sorted(
        SECTIONS_DIR.rglob("*.json")
    )


# ---------------------------------------------------------
# Analyze all results
# ---------------------------------------------------------

def analyze_results():

    result_files = find_result_files()

    if not result_files:
        print(
            "No benchmark result files found in:"
        )
        print(f"  {SECTIONS_DIR}")
        return

    analyzed = 0
    skipped = 0

    print(
        f"Analyzing {len(result_files)} "
        f"benchmark result files..."
    )
    print()

    for path in result_files:

        result = analyze_file(path)

        if result is None:
            skipped += 1
            continue

        analyzed += 1

        test_id = result.get(
            "test_id",
            path.stem
        )

        analysis_data = result.get(
            "analysis",
            {}
        )

        observed_topics = analysis_data.get(
            "observed_topics",
            []
        )

        behavior_tags = analysis_data.get(
            "behavior_tags",
            []
        )

        print(
            f"{test_id} => "
            f"topics: {observed_topics} | "
            f"tags: {behavior_tags}"
        )

    print()
    print(
        "Benchmark analysis complete."
    )
    print(
        f"Analyzed: {analyzed}"
    )
    print(
        f"Skipped:  {skipped}"
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

if __name__ == "__main__":
    analyze_results()
