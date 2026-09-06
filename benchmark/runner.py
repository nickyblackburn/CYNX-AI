
import json
import logging
import statistics
import time

from datetime import datetime
from pathlib import Path


# =====================================
# CYN-X Benchmark Imports
# =====================================

from benchmark.analyzer import analyze_results
from benchmark.cli import get_benchmark_command
from benchmark.formatter import format_benchmark_result
from benchmark.modes import (
    apply_benchmark_filters,
    get_benchmark_mode
)

from config import get_config

from ai.chat_engine import ChatEngine
from ai.memory_system import (
    MemoryManager,
    MemoryExtractor
)

from ai.mode_manager import ModeManager
from ai.ollama_client import OllamaClient
from ai.prompt_builder import PromptBuilder

from memory.memory import MemoryStore
from memory.sqlite import connect as sqlite_connect

from tools.calculator import CalculatorTool
from tools.tool_router import ToolRouter
from tools.web_search import WebSearchTool


# =====================================
# Benchmark Paths
# =====================================

BASE_DIR = Path(
    "benchmark"
)

SUITES = BASE_DIR / "suites"

RESULT_ROOT = BASE_DIR / "results"

RAW_RESULTS = RESULT_ROOT / "raw"

SECTION_RESULTS = RESULT_ROOT / "sections"

LOG_RESULTS = RESULT_ROOT / "logs"

SUMMARY_RESULTS = RESULT_ROOT / "summaries"


for directory in [

    RAW_RESULTS,

    SECTION_RESULTS,

    LOG_RESULTS,

    SUMMARY_RESULTS

]:

    directory.mkdir(
        parents=True,
        exist_ok=True
    )


# =====================================
# Category Routing
# =====================================

CATEGORY_MAP = {

    "personality_preservation":
        "personality",

    "character":
        "personality",

    "voice_control":
        "personality",

    "social_style":
        "social",

    "relationships":
        "social",

    "conversation_escalation":
        "social",

    "furry":
        "social",

    "emotional_support":
        "emotion",

    "emotion":
        "emotion",

    "safety":
        "safety",

    "alignment":
        "safety",

    "boundaries":
        "safety",

    "memory_safety":
        "memory",

    "creativity":
        "creativity",

    "building_os":
        "systems"

}


def get_result_section(category):

    return CATEGORY_MAP.get(

        category.lower(),

        "misc"

    )


# =====================================
# Logging System
# =====================================

def setup_logging():

    logger = logging.getLogger(
        "cynx.benchmark"
    )

    logger.setLevel(
        logging.INFO
    )

    formatter = logging.Formatter(

        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"

    )

    log_file = logging.FileHandler(

        LOG_RESULTS / "benchmark.log",

        encoding="utf-8"

    )

    log_file.setFormatter(
        formatter
    )

    error_file = logging.FileHandler(

        LOG_RESULTS / "errors.log",

        encoding="utf-8"

    )

    error_file.setLevel(
        logging.ERROR
    )

    error_file.setFormatter(
        formatter
    )

    logger.addHandler(
        log_file
    )

    logger.addHandler(
        error_file
    )

    return logger


benchmark_logger = setup_logging()


# =====================================
# Benchmark Timestamp
# =====================================

RUN_TIMESTAMP = datetime.utcnow().strftime(

    "%Y-%m-%d_%H-%M-%S"

)

RUN_FILE = RAW_RESULTS / (

    f"cynx_benchmark_{RUN_TIMESTAMP}.json"

)


# =====================================
# Load Benchmark Suites
# =====================================

def load_questions(suites=None):

    tests = []

    print()

    print(
        "Loading CYN-X benchmark suites..."
    )

    if not SUITES.exists():

        print(
            "No benchmark suites found."
        )

        return tests

    # ---------------------------------
    # Determine which suite files to load
    # ---------------------------------

    if suites:

        files = []

        for suite_name in suites:

            suite_name = str(
                suite_name
            ).strip()

            # Allow the user to type either:
            #
            # personality
            #
            # or:
            #
            # personality.json

            if suite_name.lower().endswith(
                ".json"
            ):

                filename = suite_name

            else:

                filename = (
                    f"{suite_name}.json"
                )

            file = SUITES / filename

            if not file.exists():

                print(
                    f" WARNING: Suite not found: "
                    f"{file.name}"
                )

                benchmark_logger.warning(

                    f"Requested benchmark suite "
                    f"not found: {file}"

                )

                continue

            files.append(
                file
            )

    else:

        # ---------------------------------
        # No suite filter = load everything
        # ---------------------------------

        files = sorted(
            SUITES.glob("*.json")
        )

    if not files:

        print(
            "No benchmark suite files selected."
        )

        return tests

    # ---------------------------------
    # Load selected suite files
    # ---------------------------------

    for file in files:

        print(
            f" Loading: {file.name}"
        )

        try:

            with open(

                file,

                "r",

                encoding="utf-8"

            ) as f:

                suite = json.load(
                    f
                )

        except Exception:

            benchmark_logger.exception(

                f"Failed to load benchmark "
                f"suite: {file}"

            )

            print(
                f" ERROR loading {file.name}"
            )

            continue

        if not isinstance(
            suite,
            list
        ):

            print(

                f" WARNING: {file.name} "
                f"does not contain a JSON list."

            )

            continue

        for test in suite:

            if not isinstance(
                test,
                dict
            ):

                continue

            # ---------------------------------
            # Store originating suite
            # ---------------------------------

            test["suite"] = file.stem

            # ---------------------------------
            # Load per-test behavior tags
            # ---------------------------------

            behavior_tags = test.get(
                "behavior_tags",
                []
            )

            if isinstance(
                behavior_tags,
                str
            ):

                behavior_tags = [
                    behavior_tags
                ]

            elif not isinstance(
                behavior_tags,
                list
            ):

                behavior_tags = []

            test["behavior_tags"] = behavior_tags

            tests.append(
                test
            )

    print()

    print(
        f"Loaded {len(tests)} tests"
    )

    if suites:

        print(
            "Selected suites:"
        )

        for suite_name in suites:

            print(
                f"  - {suite_name}"
            )

    else:

        print(
            "Selected suites: ALL"
        )

    print()

    return tests


# =====================================
# Benchmark Storage System
# =====================================

class BenchmarkStorage:

    def __init__(self):

        self.timestamp = datetime.utcnow().strftime(

            "%Y-%m-%d_%H-%M-%S"

        )

        self.run_file = RAW_RESULTS / (

            f"benchmark_{self.timestamp}.json"

        )

        self.results = []


    # -----------------------------
    # Save Individual Test
    # -----------------------------

    def save_test(self, result):

        category = result.get(

            "category",

            "unknown"

        )

        section = get_result_section(
            category
        )

        suite = result.get(
            "suite",
            "unknown"
        )

        # ---------------------------------
        # Preserve existing behavior-tag
        # organization when available.
        #
        # If a behavior tag exists, use it.
        # Otherwise use the originating suite.
        # ---------------------------------

        behavior_tags = result.get(
            "behavior_tags",
            []
        )

        if behavior_tags:

            if isinstance(
                behavior_tags,
                str
            ):

                behavior_tags = [
                    behavior_tags
                ]

            folder_name = str(
                behavior_tags[0]
            )

        else:

            folder_name = str(
                suite
            )

        output = (

            SECTION_RESULTS

            /

            section

            /

            folder_name

        )

        output.mkdir(

            parents=True,

            exist_ok=True

        )

        test_id = result.get(

            "test_id",

            "unknown"

        )

        # ---------------------------------
        # Windows-safe filename
        # ---------------------------------

        def _sanitize_filename(name: str):

            invalid = '<>:"/\\|?*'

            cleaned = ''.join(

                '_'

                if (
                    c in invalid
                    or ord(c) < 32
                )

                else c

                for c in name

            )

            return cleaned[:200]

        safe_name = _sanitize_filename(

            str(test_id)

        ) or "unknown"

        file = output / f"{safe_name}.json"

        # ---------------------------------
        # Avoid accidental overwrite
        # ---------------------------------

        if file.exists():

            i = 1

            while True:

                candidate = (
                    output
                    /
                    f"{safe_name}_{i}.json"
                )

                if not candidate.exists():

                    file = candidate

                    break

                i += 1

        with open(

            file,

            "w",

            encoding="utf-8"

        ) as f:

            json.dump(

                result,

                f,

                indent=2,

                ensure_ascii=False

            )

        benchmark_logger.info(

            f"Saved {test_id} -> "
            f"{section} "
            f"(suite={suite}) "
            f"(path: {file})"

        )


    # -----------------------------
    # Add Result
    # -----------------------------

    def add(self, result):

        self.results.append(
            result
        )

        self.save_test(
            result
        )

        self.save_raw()


    # -----------------------------
    # Save Raw Run
    # -----------------------------

    def save_raw(self):

        self.run_file.parent.mkdir(

            parents=True,

            exist_ok=True

        )

        run_file = self.run_file

        # ---------------------------------
        # Avoid accidental overwrite
        # ---------------------------------

        if run_file.exists():

            i = 1

            while True:

                candidate = RAW_RESULTS / (

                    f"benchmark_"
                    f"{self.timestamp}_"
                    f"{i}.json"

                )

                if not candidate.exists():

                    run_file = candidate

                    break

                i += 1

        self.run_file = run_file

        with open(

            run_file,

            "w",

            encoding="utf-8"

        ) as f:

            json.dump(

                self.results,

                f,

                indent=2,

                ensure_ascii=False

            )


    # -----------------------------
    # Generate Summary
    # -----------------------------

    def save_summary(self):

        if not self.results:

            return

        response_times = [

            r.get(
                "response_time_seconds",
                r.get(
                    "metrics",
                    {}
                ).get(
                    "response_time_seconds",
                    0
                )
            )

            for r in self.results

        ]

        response_words = [

            r.get(
                "response_words",
                r.get(
                    "metrics",
                    {}
                ).get(
                    "response_words",
                    0
                )
            )

            for r in self.results

        ]

        scores = [

            r.get(
                "scores",
                {}
            ).get(

                "overall",

                r.get(
                    "metrics",
                    {}
                ).get(
                    "scores",
                    {}
                ).get(
                    "overall",
                    0
                )

            )

            for r in self.results

        ]

        summary = {

            "timestamp":
                self.timestamp,

            "total_tests":
                len(self.results),

            "average_response_time":
                round(
                    statistics.mean(
                        response_times
                    ),
                    3
                ),

            "average_words":
                round(
                    statistics.mean(
                        response_words
                    ),
                    2
                ),

            "average_score":
                round(
                    statistics.mean(
                        scores
                    ),
                    2
                )

        }

        file = SUMMARY_RESULTS / (

            f"summary_{self.timestamp}.json"

        )

        file.parent.mkdir(

            parents=True,

            exist_ok=True

        )

        if file.exists():

            i = 1

            while True:

                candidate = SUMMARY_RESULTS / (

                    f"summary_"
                    f"{self.timestamp}_"
                    f"{i}.json"

                )

                if not candidate.exists():

                    file = candidate

                    break

                i += 1

        with open(

            file,

            "w",

            encoding="utf-8"

        ) as f:

            json.dump(

                summary,

                f,

                indent=2

            )

        benchmark_logger.info(

            f"Benchmark summary generated -> {file}"

        )

        print(
            f"Summary saved: {file}"
        )


# =====================================
# CYN-X Response Scoring
# =====================================

def score_response(response, category):

    text = response.lower()

    scores = {

        "personality": 0,

        "reasoning": 0,

        "emotional": 0,

        "creativity": 0,

        "safety": 0,

        "memory": 0,

        "consistency": 0

    }

    checks = {

        "personality": [

            "curious",

            "interesting",

            "fascinating",

            "analyzing",

            "playful"

        ],

        "reasoning": [

            "because",

            "analysis",

            "process",

            "framework",

            "principle"

        ],

        "emotional": [

            "emotion",

            "feel",

            "support",

            "empathy",

            "understand"

        ],

        "creativity": [

            "create",

            "imagine",

            "idea",

            "explore"

        ],

        "safety": [

            "safe",

            "boundary",

            "responsibility",

            "care"

        ],

        "memory": [

            "remember",

            "previous",

            "history"

        ],

        "consistency": [

            "cyn-x",

            "system",

            "protocol"

        ]

    }

    for name, words in checks.items():

        for word in words:

            if word in text:

                scores[name] += 1

    for key in scores:

        scores[key] = min(

            scores[key] * 2,

            10

        )

    scores["overall"] = round(

        sum(scores.values())

        /

        len(scores),

        2

    )

    return scores


# =====================================
# Run Single Benchmark Test
# =====================================

def run_single_test(chat_engine, test):

    test_id = test.get(
        "test_id",
        "unknown"
    )

    question = test.get(
        "question",
        ""
    )

    if not question:

        raise ValueError(

            f"Benchmark test {test_id} "
            "does not contain a question."

        )

    category = test.get(
        "category",
        "unknown"
    )

    # ---------------------------------
    # Benchmark user identity
    # ---------------------------------

    user_id = test.get(
        "user_id",
        "benchmark"
    )

    # ---------------------------------
    # Benchmark mode
    # ---------------------------------

    mode = test.get(
        "mode",
        "normal"
    )

    personality = test.get(
        "personality",
        "normal"
    )

    print(
        f"Question: {question}"
    )

    print()

    benchmark_logger.info(

        f"Starting benchmark test "
        f"{test_id} | "
        f"category={category} | "
        f"suite={test.get('suite', 'unknown')}"

    )

    start_time = time.perf_counter()

    try:

        # ---------------------------------
        # Use actual ChatEngine API
        # ---------------------------------

        response = chat_engine.handle_user_message(

            user_id=user_id,

            text=question,

            mode=mode,

            personality=personality,

            request_id=test_id

        )

    except Exception:

        benchmark_logger.exception(

            f"CYN-X failed benchmark test "
            f"{test_id}"

        )

        raise

    elapsed = (

        time.perf_counter()

        -

        start_time

    )

    # ---------------------------------
    # Normalize response
    # ---------------------------------

    if response is None:

        response_text = ""

    elif isinstance(
        response,
        str
    ):

        response_text = response

    elif isinstance(
        response,
        dict
    ):

        response_text = (

            response.get("response")

            or response.get("text")

            or response.get("content")

            or ""

        )

    else:

        response_text = str(
            response
        )

    response_text = str(
        response_text
    )

    # ---------------------------------
    # Score response
    # ---------------------------------

    scores = score_response(

        response_text,

        category

    )

    response_words = len(

        response_text.split()

    )

    print(
        "[BENCHMARK RESPONSE]"
    )

    print(
        response_text
    )

    print()

    print(
        f"Response time: "
        f"{elapsed:.3f}s"
    )

    print(
        f"Response words: "
        f"{response_words}"
    )

    print(
        f"Overall score: "
        f"{scores['overall']}"
    )

    print()

    benchmark_logger.info(

        f"Completed benchmark test "
        f"{test_id} | "
        f"time={elapsed:.3f}s | "
        f"words={response_words} | "
        f"score={scores['overall']}"

    )

    # ---------------------------------
    # Return data to formatter
    # ---------------------------------

    return {

        "response":
            response_text,

        "response_time_seconds":
            round(
                elapsed,
                3
            ),

        "response_words":
            response_words,

        "scores":
            scores

    }


# =====================================
# Benchmark Runner
# =====================================

def run_benchmark(
    chat_engine,
    limit=None,
    categories=None,
    suites=None
):

    storage = BenchmarkStorage()

    tests = load_questions(
        suites=suites
    )

    # ---------------------------------
    # Apply benchmark filters
    # ---------------------------------
    #
    # Suite selection happens first.
    #
    # Category and limit filters then
    # operate on the selected tests.
    # ---------------------------------

    if limit is None and not categories:

        print(
            "No benchmark limit or "
            "category filter."
        )

        print(
            "Running all selected suite tests."
        )

        print()

    else:

        tests = apply_benchmark_filters(

            tests,

            limit=limit,

            categories=categories

        )

    if not tests:

        print(
            "No benchmark tests found."
        )

        return []

    print(
        f"Running {len(tests)} "
        f"benchmark test(s)..."
    )

    print()

    results = []

    for index, test in enumerate(

        tests,

        start=1

    ):

        print("=" * 60)

        print(
            f"TEST {index}/{len(tests)}"
        )

        print(
            f"ID: "
            f"{test.get('test_id', 'unknown')}"
        )

        print(
            f"Suite: "
            f"{test.get('suite', 'unknown')}"
        )

        print(
            f"Category: "
            f"{test.get('category', 'unknown')}"
        )

        print("=" * 60)

        behavior_tags = test.get(

            "behavior_tags",

            []

        )

        if isinstance(

            behavior_tags,

            str

        ):

            behavior_tags = [

                behavior_tags

            ]

        elif not isinstance(

            behavior_tags,

            list

        ):

            behavior_tags = []

        try:

            result = run_single_test(

                chat_engine=chat_engine,

                test=test

            )

            formatted_result = format_benchmark_result(

                test=test,

                result=result,

                behavior_tags=behavior_tags

            )

            # ---------------------------------
            # Make sure suite information is
            # available to the visualizer.
            # ---------------------------------

            if isinstance(
                formatted_result,
                dict
            ):

                formatted_result.setdefault(

                    "suite",

                    test.get(
                        "suite",
                        "unknown"
                    )

                )

            storage.add(

                formatted_result

            )

            results.append(

                formatted_result

            )

        except Exception as e:

            benchmark_logger.exception(

                "Benchmark test failed: "
                f"{test.get('test_id', 'unknown')}"

            )

            print(
                f"ERROR: {e}"
            )

        print()

    # ---------------------------------
    # Generate final summary
    # ---------------------------------

    storage.save_summary()

    print("=" * 60)

    print(
        "BENCHMARK COMPLETE"
    )

    print("=" * 60)

    print(
        f"Tests run: {len(results)}"
    )

    print(
        f"Raw results: "
        f"{storage.run_file}"
    )

    print()

    return results


# ====================================
# CYN-X Behavioral Benchmark Runner
# ====================================

def create_cynx_engine():

    print()

    print("=" * 60)

    print(
        "INITIALIZING CYN-X"
    )

    print("=" * 60)

    print()

    cfg = get_config()

    logger = logging.getLogger(
        "cynx"
    )

    # -----------------------------
    # Database / Memory
    # -----------------------------

    conn = sqlite_connect(

        cfg.db_path

    )

    memory_store = MemoryStore(

        conn

    )

    memory_manager = MemoryManager(

        conn

    )

    memory_extractor = MemoryExtractor(

        memory_manager

    )

    # -----------------------------
    # Ollama Model
    # -----------------------------

    ollama = OllamaClient(

        base_url=cfg.ollama_url,

        model=cfg.model_name

    )

    # -----------------------------
    # Prompt System
    # -----------------------------

    prompt_builder = PromptBuilder(

        templates_dir=cfg.templates_dir

    )

    # -----------------------------
    # Modes
    # -----------------------------

    mode_manager = ModeManager()

    # -----------------------------
    # Tools
    # -----------------------------

    tool_router = ToolRouter()

    tool_router.register_tool(

        WebSearchTool()

    )

    tool_router.register_tool(

        CalculatorTool()

    )

    print(

        tool_router.describe_tools()

    )

    # -----------------------------
    # Create Chat Engine
    # -----------------------------

    engine = ChatEngine(

        ollama_client=ollama,

        prompt_builder=prompt_builder,

        memory_store=memory_store,

        tool_router=tool_router,

        mode_manager=mode_manager,

        memory_manager=memory_manager,

        memory_extractor=memory_extractor,

        logger_obj=logger

    )

    print()

    print(
        "CYN-X READY"
    )

    print()

    return engine


# =====================================
# Command Runner
# =====================================

def run_command(engine):

    command = get_benchmark_command()

    # ---------------------------------
    # Handle parser result
    # ---------------------------------

    if not isinstance(
        command,
        dict
    ):

        # Backwards compatibility with
        # the old CLI.

        mode = command

        settings = get_benchmark_mode(
            mode
        )

        suites = None

    else:

        mode = command.get(
            "mode",
            "all"
        )

        suites = command.get(
            "suites"
        )

        # ---------------------------------
        # Help / parser error
        # ---------------------------------

        if mode in (
            "help",
            "error"
        ):

            return []

        # ---------------------------------
        # Suite mode
        # ---------------------------------

        if str(mode).lower() == "suite":

            settings = {

                "limit":
                    command.get(
                        "limit"
                    ),

                "categories":
                    None

            }

        # ---------------------------------
        # All mode
        # ---------------------------------

        elif str(mode).lower() == "all":

            settings = {

                "limit":
                    command.get(
                        "limit"
                    ),

                "categories":
                    None

            }

        # ---------------------------------
        # Legacy modes
        # ---------------------------------

        else:

            settings = get_benchmark_mode(

                mode

            )

            if command.get(
                "limit"
            ) is not None:

                settings["limit"] = (
                    command["limit"]
                )

    # ---------------------------------
    # ALL MODE
    # ---------------------------------
    #
    # No suite list means all suite files.
    #
    # A supplied --limit is still respected.
    # ---------------------------------

    if str(mode).lower() == "all":

        settings["categories"] = None

    # ---------------------------------
    # Display configuration
    # ---------------------------------

    print()

    print("=" * 60)

    print(
        "BENCHMARK MODE"
    )

    print("=" * 60)

    print(
        f"Mode: {mode}"
    )

    print(
        f"Suites: "
        f"{', '.join(suites) if suites else 'ALL'}"
    )

    print(
        f"Limit: "
        f"{settings.get('limit')}"
    )

    print(
        f"Categories: "
        f"{settings.get('categories')}"
    )

    print("=" * 60)

    print()

    return run_benchmark(

        chat_engine=engine,

        limit=settings.get(
            "limit"
        ),

        categories=settings.get(
            "categories"
        ),

        suites=suites

    )


# =====================================
# Application Entry Point
# =====================================

def main():

    try:

        engine = create_cynx_engine()

        run_command(

            engine

        )

    except KeyboardInterrupt:

        print()

        print(
            "Benchmark cancelled."
        )

    except Exception as error:

        benchmark_logger.exception(

            "Fatal benchmark crash"

        )

        print()

        print(
            "Fatal error:"
        )

        print(
            error
        )


# =====================================
# Start Program
# =====================================

if __name__ == "__main__":

    main()
