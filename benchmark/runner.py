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


    "emotional_support":
        "emotion",


    "emotion":
        "emotion",


    "safety":
        "safety",


    "alignment":
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


def load_questions():


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



    for file in SUITES.glob(
        "*.json"
    ):


        print(
            f" Loading: {file.name}"
        )



        with open(

            file,

            "r",

            encoding="utf-8"

        ) as f:


            suite = json.load(
                f
            )



        for test in suite:


            test["suite"] = file.stem


            tests.append(
                test
            )



    print(

        f"Loaded {len(tests)} tests"

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



        suite = "unknown"


        if result.get(
            "behavior_tags"
        ):


            suite = result["behavior_tags"][0]



        output = (

            SECTION_RESULTS

            /

            section

            /

            suite

        )



        output.mkdir(

            parents=True,

            exist_ok=True

        )



        test_id = result.get(

            "test_id",

            "unknown"

        )



        file = output / (

            f"{test_id}.json"

        )



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

            f"Saved {test_id} -> {section}"

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


        with open(

            self.run_file,

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



        summary = {


            "timestamp":

                self.timestamp,


            "total_tests":

                len(self.results),


            "average_response_time":

                statistics.mean(

                    r["response_time_seconds"]

                    for r in self.results

                ),



            "average_words":

                statistics.mean(

                    r["response_words"]

                    for r in self.results

                ),



            "average_score":

                statistics.mean(

                    r["scores"]["overall"]

                    for r in self.results

                )

        }




        file = SUMMARY_RESULTS / (

            f"summary_{self.timestamp}.json"

        )



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

            "Benchmark summary generated"

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
# Benchmark Runner
# =====================================


def run_benchmark(

    chat_engine,

    limit=None,

    categories=None

):


    storage = BenchmarkStorage()



    tests = load_questions()



    tests = apply_benchmark_filters(

        tests,

        limit=limit,

        categories=categories

    )



    print()

    print("=" * 60)

    print("CYN-X BENCHMARK PIPELINE")

    print("=" * 60)

    print()



    benchmark_logger.info(

        f"Starting benchmark with {len(tests)} tests"

    )



    results = []



    start_all = time.perf_counter()



    for index, test in enumerate(

        tests,

        start=1

    ):


        test_id = test.get(

            "test_id",

            "unknown"

        )


        category = test.get(

            "category",

            "unknown"

        )



        print(

            f"[{index}/{len(tests)}] "

            f"{test_id} "

            f"({category})"

        )



        start = time.perf_counter()



        failed = False



        try:


            response = chat_engine.handle_user_message(

                user_id="benchmark",

                text=test["question"],

                mode="normal",

                personality="cyn"

            )



        except Exception as error:


            failed = True


            benchmark_logger.exception(

                f"{test_id} failed"

            )


            response = (

                "[GENERATION FAILED]\n"

                +

                str(error)

            )





        elapsed = (

            time.perf_counter()

            -

            start

        )



        words = len(
            response.split()
        )


        chars = len(
            response
        )


        lines = len(
            response.splitlines()
        )


        sentences = (

            response.count(".")

            +

            response.count("!")

            +

            response.count("?")

        )



        tokens = chars // 4



        result = format_benchmark_result(

            test_id=test_id,

            category=category,

            question=test["question"],

            response=response,

            response_time_seconds=elapsed,

            observed_topics=[],

            behavior_tags=[

                test.get(

                    "suite",

                    "unknown"

                )

            ],

            response_words=words,

            response_characters=chars,

            response_lines=lines,

            response_sentences=sentences,

            estimated_tokens=tokens,

            scores=score_response(

                response,

                category

            )

        )



        result["failed"] = failed



        results.append(
            result
        )


        storage.add(
            result
        )



        print(

            f" Time: {elapsed:.2f}s"

        )


        print(

            f" Words: {words}"

        )


        print(

            f" Tokens: {tokens}"

        )


        print(

            f" Score: {result['scores']['overall']}"

        )


        print()



    total = (

        time.perf_counter()

        -

        start_all

    )



    storage.save_summary()



    print("=" * 60)

    print("BENCHMARK COMPLETE")

    print("=" * 60)



    print(

        f"Tests: {len(results)}"

    )


    print(

        f"Runtime: {total:.2f}s"

    )



    if results:


        print(

            "Average Score: "

            +

            f"{statistics.mean(

                r['scores']['overall']

                for r in results

            ):.2f}"

        )



    try:

        analyze_results()


    except Exception as error:


        benchmark_logger.exception(

            "Analyzer failed"

        )


        print(

            f"Analyzer failed: {error}"

        )



    return results

# =====================================
# CYN-X Initialization
# =====================================


def create_cynx_engine():

    print()

    print("=" * 60)

    print("INITIALIZING CYN-X")

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



    # -----------------------------
    # Handle --mode
    # -----------------------------


    if isinstance(command, dict):


        mode = command.get(

            "mode",

            "all"

        )


        settings = get_benchmark_mode(

            mode

        )



        # manual limit override


        if command.get(

            "limit"

        ) is not None:


            settings["limit"] = command["limit"]



    else:


        settings = get_benchmark_mode(

            command

        )





    print()

    print("=" * 60)

    print("BENCHMARK MODE")

    print("=" * 60)


    print(

        f"Limit: {settings['limit']}"

    )


    print(

        f"Categories: {settings['categories']}"

    )


    print("=" * 60)

    print()





    return run_benchmark(

        chat_engine=engine,

        limit=settings["limit"],

        categories=settings["categories"]

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


        print(error)







# =====================================
# Start Program
# =====================================


if __name__ == "__main__":


    main()