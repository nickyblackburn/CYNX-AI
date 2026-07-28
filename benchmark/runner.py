import asyncio
import datetime
import json
import logging
import statistics
import time

from pathlib import Path


from benchmark.analyzer import analyze_results
from benchmark.formatter import format_benchmark_result


from config import get_config


from ai.chat_engine import ChatEngine
from ai.memory_system import MemoryManager, MemoryExtractor
from ai.mode_manager import ModeManager
from ai.ollama_client import OllamaClient
from ai.prompt_builder import PromptBuilder


from memory.memory import MemoryStore
from memory.sqlite import connect as sqlite_connect


from tools.calculator import CalculatorTool
from tools.tool_router import ToolRouter
from tools.web_search import WebSearchTool


from interfaces.terminal import TerminalAdapter



# =====================================
# Benchmark Paths
# =====================================


SUITES = Path(
    "benchmark/suites"
)


RESULT_ROOT = Path(
    "benchmark/results"
)


RAW_RESULTS = RESULT_ROOT / "raw"

SECTION_RESULTS = RESULT_ROOT / "sections"

REPORT_RESULTS = RESULT_ROOT / "reports"


RUN_TIMESTAMP = datetime.datetime.utcnow().strftime(
    "%Y-%m-%d_%H-%M-%S"
)


RESULTS = RAW_RESULTS / (
    f"cynx_benchmark_{RUN_TIMESTAMP}.json"
)


LATEST_RESULT = RESULT_ROOT / "latest.json"



# =====================================
# Result Directory Setup
# =====================================


def setup_result_directories():

    paths = [

        RAW_RESULTS,

        SECTION_RESULTS,

        REPORT_RESULTS

    ]


    for path in paths:

        path.mkdir(
            parents=True,
            exist_ok=True
        )



# =====================================
# Benchmark Section Mapping
# =====================================


CATEGORY_MAP = {


    "personality_preservation":
        "personality",


    "character":
        "personality",


    "social_style":
        "personality",


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
        "systems",


    "voice_control":
        "personality"

}



# =====================================
# Save Individual Test Result
# =====================================


def save_test_result(result):


    category = result.get(
        "category",
        "unknown"
    ).lower()



    section = CATEGORY_MAP.get(
        category,
        "misc"
    )



    suite = "unknown"



    if result.get(
        "behavior_tags"
    ):


        suite = result[
            "behavior_tags"
        ][0]



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



# =====================================
# Save Complete Benchmark
# =====================================


def save_results(results):


    with open(
        RESULTS,
        "w",
        encoding="utf-8"
    ) as f:


        json.dump(

            results,

            f,

            indent=2,

            ensure_ascii=False

        )



    update_latest()



# =====================================
# Update Latest Benchmark Pointer
# =====================================


def update_latest():


    with open(
        RESULTS,
        "r",
        encoding="utf-8"
    ) as source:


        data = json.load(
            source
        )



    with open(
        LATEST_RESULT,
        "w",
        encoding="utf-8"
    ) as target:


        json.dump(

            data,

            target,

            indent=2,

            ensure_ascii=False

        )



# =====================================
# Load Multiple Benchmark Suites
# =====================================


def load_questions():


    tests = []



    print()

    print(
        "Loading CYN-X benchmark suites..."
    )



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


                test["suite"] = (
                    file.stem
                )



                tests.append(
                    test
                )



    print(
        f"Loaded {len(tests)} tests"
    )


    print()



    return tests

# =====================================
# CYN-X Benchmark Storage System
# =====================================

from datetime import datetime


RESULT_ROOT = Path("results")


RAW_DIR = RESULT_ROOT / "raw"
SECTION_DIR = RESULT_ROOT / "sections"
LOG_DIR = RESULT_ROOT / "logs"
SUMMARY_DIR = RESULT_ROOT / "summaries"



for directory in [
    RAW_DIR,
    SECTION_DIR,
    LOG_DIR,
    SUMMARY_DIR
]:
    directory.mkdir(
        parents=True,
        exist_ok=True
    )



# =====================================
# Logging Setup
# =====================================


def setup_logging():


    benchmark_logger = logging.getLogger(
        "cynx.benchmark"
    )


    benchmark_logger.setLevel(
        logging.INFO
    )


    formatter = logging.Formatter(

        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"

    )



    file_handler = logging.FileHandler(

        LOG_DIR /
        "benchmark.log",

        encoding="utf-8"

    )


    file_handler.setFormatter(
        formatter
    )



    error_handler = logging.FileHandler(

        LOG_DIR /
        "errors.log",

        encoding="utf-8"

    )


    error_handler.setLevel(
        logging.ERROR
    )


    error_handler.setFormatter(
        formatter
    )



    benchmark_logger.addHandler(
        file_handler
    )


    benchmark_logger.addHandler(
        error_handler
    )



    return benchmark_logger





benchmark_logger = setup_logging()





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
# Result Manager
# =====================================


class BenchmarkStorage:



    def __init__(self):


        self.timestamp = datetime.utcnow().strftime(

            "%Y-%m-%d_%H-%M-%S"

        )



        self.run_file = (

            RAW_DIR /

            f"benchmark_{self.timestamp}.json"

        )



        self.results = []





    def save_test(self, result):


        category = result.get(

            "category",

            "unknown"

        )


        section = get_result_section(
            category
        )



        output = (

            SECTION_DIR /

            section

        )


        output.mkdir(

            parents=True,

            exist_ok=True

        )



        test_id = result.get(

            "test_id",

            "unknown"

        )



        filename = (

            output /

            f"{test_id}.json"

        )



        with open(

            filename,

            "w",

            encoding="utf-8"

        ) as file:


            json.dump(

                result,

                file,

                indent=2,

                ensure_ascii=False

            )



        benchmark_logger.info(

            f"Saved {test_id} -> {section}"

        )






    def add(self,result):


        self.results.append(
            result
        )


        self.save_test(
            result
        )


        self.save_raw()






    def save_raw(self):


        with open(

            self.run_file,

            "w",

            encoding="utf-8"

        ) as file:


            json.dump(

                self.results,

                file,

                indent=2,

                ensure_ascii=False

            )







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

                )

        }



        filename = (

            SUMMARY_DIR /

            f"summary_{self.timestamp}.json"

        )



        with open(

            filename,

            "w",

            encoding="utf-8"

        ) as file:


            json.dump(

                summary,

                file,

                indent=2

            )


        benchmark_logger.info(
            "Summary generated"
        )

        # =====================================
# Benchmark Runner
# =====================================


def run_benchmark(chat_engine):


    storage = BenchmarkStorage()


    tests = load_questions()



    print()

    print("=" * 60)

    print("CYN-X BENCHMARK PIPELINE")

    print("=" * 60)

    print()



    benchmark_logger.info(

        f"Starting benchmark run with {len(tests)} tests"

    )



    results = []



    benchmark_start = time.perf_counter()



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



        benchmark_logger.info(

            f"Running {test_id}"

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



            print(

                f"FAILED {test_id}: {error}"

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



        # -----------------------------
        # Response Metrics
        # -----------------------------


        word_count = len(

            response.split()

        )


        character_count = len(

            response

        )


        line_count = len(

            response.splitlines()

        )



        sentence_count = (

            response.count(".")

            +

            response.count("!")

            +

            response.count("?")

        )



        estimated_tokens = (

            character_count //

            4

        )



        scores = score_response(

            response,

            category

        )





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



            response_words=word_count,



            response_characters=character_count,



            response_lines=line_count,



            response_sentences=sentence_count,



            estimated_tokens=estimated_tokens,



            scores=scores



        )



        # add internal metadata


        result["failed"] = failed


        result["timestamp"] = (

            datetime.utcnow()

            .isoformat()

        )



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

            f" Words: {word_count}"

        )


        print(

            f" Tokens: {estimated_tokens}"

        )


        print(

            f" Score: {scores['overall']}"

        )


        print()



    # =================================
    # Finish Benchmark
    # =================================



    total_time = (

        time.perf_counter()

        -

        benchmark_start

    )



    storage.save_summary()



    print("=" * 60)

    print("BENCHMARK COMPLETE")

    print("=" * 60)



    print(

        f"Tests: {len(results)}"

    )



    print(

        f"Runtime: {total_time:.2f}s"

    )



    if results:


        print(

            "Average Response Time: "

            +

            f"{statistics.mean(

                r['response_time_seconds']

                for r in results

            ):.2f}s"

        )



        print(

            "Average Words: "

            +

            f"{statistics.mean(

                r['response_words']

                for r in results

            ):.1f}"

        )



        print(

            "Average Score: "

            +

            f"{statistics.mean(

                r['scores']['overall']

                for r in results

            ):.2f}"

        )



    print("=" * 60)



    benchmark_logger.info(

        "Benchmark completed"

    )



    # analyzer hook


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
# Application Entry Point
# =====================================


def main():


    print()

    print("=" * 60)

    print("INITIALIZING CYN-X BENCHMARK SYSTEM")

    print("=" * 60)

    print()



    cfg = get_config()



    logger = logging.getLogger(
        "cynx"
    )



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



    ollama = OllamaClient(

        base_url=cfg.ollama_url,

        model=cfg.model_name

    )



    prompt_builder = PromptBuilder(

        templates_dir=cfg.templates_dir

    )



    mode_manager = ModeManager()



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



    run_benchmark(

        chat_engine=engine

    )





# =====================================
# Start Program
# =====================================


if __name__ == "__main__":

    main()