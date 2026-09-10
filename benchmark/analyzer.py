
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
# Tool Test Mode
# ---------------------------------------------------------

def analyze_tool_test(result: dict) -> dict | None:
    """
    Analyze tool execution recorded by the benchmark runner.

    IMPORTANT:
        This function does NOT run a tool.

        The runner is responsible for actually running CYN-X
        and recording what happened.

        This analyzer only determines whether the recorded
        tool execution matches the expected behavior.

    Supported locations:

        result["tool_test"]

    or:

        result["analysis"]["tool_test"]

    Expected fields:

        expected_tool
        tool_called
        tool_name
        tool_arguments
        tool_result
        result_passed_to_llm
        failure
    """

    # -----------------------------------------------------
    # Find tool-test data
    # -----------------------------------------------------

    tool_test = None

    existing_analysis = result.get("analysis")

    if isinstance(existing_analysis, dict):
        possible_tool_test = existing_analysis.get(
            "tool_test"
        )

        if isinstance(possible_tool_test, dict):
            tool_test = possible_tool_test

    if tool_test is None:
        possible_tool_test = result.get(
            "tool_test"
        )

        if isinstance(possible_tool_test, dict):
            tool_test = possible_tool_test

    # No tool test was recorded.
    if tool_test is None:
        return None

    # -----------------------------------------------------
    # Extract fields
    # -----------------------------------------------------

    expected_tool = tool_test.get(
        "expected_tool"
    )

    tool_called = tool_test.get(
        "tool_called"
    )

    tool_name = tool_test.get(
        "tool_name"
    )

    tool_arguments = tool_test.get(
        "tool_arguments"
    )

    tool_result = tool_test.get(
        "tool_result"
    )

    result_passed_to_llm = tool_test.get(
        "result_passed_to_llm"
    )

    failures = []

    # -----------------------------------------------------
    # Validate expected tool
    # -----------------------------------------------------

    if expected_tool:

        if tool_called is not True:

            failures.append(
                f"expected {expected_tool} "
                f"to be called"
            )

        elif tool_name != expected_tool:

            failures.append(
                f"expected tool {expected_tool}, "
                f"got {tool_name}"
            )

    # -----------------------------------------------------
    # Validate tool result
    # -----------------------------------------------------

    if tool_called is True:

        if tool_result is None:

            failures.append(
                "tool was called but no "
                "tool result was recorded"
            )

    # -----------------------------------------------------
    # Validate result reached model
    # -----------------------------------------------------

    if tool_called is True:

        if result_passed_to_llm is not True:

            failures.append(
                "tool result was not recorded "
                "as passed to LLM"
            )

    # -----------------------------------------------------
    # Preserve runner-reported failures
    # -----------------------------------------------------

    recorded_failure = tool_test.get(
        "failure"
    )

    if recorded_failure:

        if isinstance(
            recorded_failure,
            list
        ):

            failures.extend(
                str(item)
                for item in recorded_failure
            )

        else:

            failures.append(
                str(recorded_failure)
            )

    # Remove duplicate failures.
    failures = list(
        dict.fromkeys(failures)
    )

    # -----------------------------------------------------
    # Determine status
    # -----------------------------------------------------

    if failures:

        status = "FAIL"

    elif expected_tool:

        status = "PASS"

    else:

        status = "UNKNOWN"

    # -----------------------------------------------------
    # Build normalized analyzer result
    # -----------------------------------------------------

    analyzed = {
        "status": status,

        "passed": (
            status == "PASS"
        ),

        "expected_tool": expected_tool,

        "tool_called": tool_called,

        "tool_name": tool_name,

        "tool_arguments": tool_arguments,

        "tool_result": tool_result,

        "result_passed_to_llm": (
            result_passed_to_llm
        ),

        "failure": (
            "; ".join(failures)
            if failures
            else None
        )
    }

    return analyzed


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

    except (
        OSError,
        json.JSONDecodeError
    ) as exc:

        print(
            f"Skipping {path}: {exc}"
        )

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
    # Get response
    # -----------------------------------------------------

    output = result.get(
        "output"
    )

    if not isinstance(output, dict):

        print(
            f"Skipping {path}: "
            "no valid 'output' object"
        )

        return None

    response = output.get(
        "response"
    )

    if not isinstance(response, str):

        print(
            f"Skipping {path}: "
            "no valid 'output.response' field"
        )

        return None

    # -----------------------------------------------------
    # Run response analyzer
    # -----------------------------------------------------

    new_analysis = analyze_response(
        response
    )

    # -----------------------------------------------------
    # Preserve existing analysis
    # -----------------------------------------------------

    if not isinstance(
        result.get("analysis"),
        dict
    ):

        result["analysis"] = {}

    existing_topics = result[
        "analysis"
    ].get(
        "observed_topics",
        []
    )

    existing_tags = result[
        "analysis"
    ].get(
        "behavior_tags",
        []
    )

    if not isinstance(
        existing_topics,
        list
    ):

        existing_topics = []

    if not isinstance(
        existing_tags,
        list
    ):

        existing_tags = []

    # -----------------------------------------------------
    # Merge response analysis
    # -----------------------------------------------------

    merged_topics = list(
        dict.fromkeys(
            existing_topics
            + new_analysis[
                "observed_topics"
            ]
        )
    )

    merged_tags = list(
        dict.fromkeys(
            existing_tags
            + new_analysis[
                "behavior_tags"
            ]
        )
    )

    result[
        "analysis"
    ][
        "observed_topics"
    ] = merged_topics

    result[
        "analysis"
    ][
        "behavior_tags"
    ] = merged_tags

    # -----------------------------------------------------
    # TOOL TEST ANALYSIS
    # -----------------------------------------------------

    tool_test = analyze_tool_test(
        result
    )

    if tool_test is not None:

        result[
            "analysis"
        ][
            "tool_test"
        ] = tool_test

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
            f"Could not write {path}: "
            f"{exc}"
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
        SECTIONS_DIR.rglob(
            "*.json"
        )
    )


# ---------------------------------------------------------
# Analyze all results
# ---------------------------------------------------------

def analyze_results():

    result_files = (
        find_result_files()
    )

    if not result_files:

        print(
            "No benchmark result files "
            "found in:"
        )

        print(
            f"  {SECTIONS_DIR}"
        )

        return

    analyzed = 0
    skipped = 0

    # Tool statistics
    tool_tests = 0
    tool_passed = 0
    tool_failed = 0
    tool_unknown = 0

    print(
        f"Analyzing {len(result_files)} "
        f"benchmark result files..."
    )

    print()

    for path in result_files:

        result = analyze_file(
            path
        )

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

        observed_topics = (
            analysis_data.get(
                "observed_topics",
                []
            )
        )

        behavior_tags = (
            analysis_data.get(
                "behavior_tags",
                []
            )
        )

        print(
            f"{test_id} => "
            f"topics: {observed_topics} | "
            f"tags: {behavior_tags}"
        )

        # -------------------------------------------------
        # Tool Test Mode reporting
        # -------------------------------------------------

        tool_test = (
            analysis_data.get(
                "tool_test"
            )
        )

        if isinstance(
            tool_test,
            dict
        ):

            tool_tests += 1

            status = tool_test.get(
                "status",
                "UNKNOWN"
            )

            if status == "PASS":

                tool_passed += 1

            elif status == "FAIL":

                tool_failed += 1

            else:

                tool_unknown += 1

            print(
                f"  🧪 TOOL TEST => "
                f"{status} | "
                f"expected: "
                f"{tool_test.get('expected_tool')} | "
                f"called: "
                f"{tool_test.get('tool_name')} | "
                f"result→LLM: "
                f"{tool_test.get('result_passed_to_llm')}"
            )

            if tool_test.get(
                "failure"
            ):

                print(
                    f"  ⚠ failure: "
                    f"{tool_test['failure']}"
                )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

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

    print()

    print(
        "Tool Test Mode:"
    )

    print(
        f"  Tests:   {tool_tests}"
    )

    print(
        f"  PASS:    {tool_passed}"
    )

    print(
        f"  FAIL:    {tool_failed}"
    )

    print(
        f"  UNKNOWN: {tool_unknown}"
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

if __name__ == "__main__":

    analyze_results()
