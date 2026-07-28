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



timestamp = datetime.datetime.utcnow().strftime(
    "%Y-%m-%d_%H-%M-%S"
)


RESULTS = Path(
    f"benchmark/results/cynx_benchmark_{timestamp}.json"
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


            suite = json.load(f)



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
# Save Results
# =====================================


def save_results(results):


    RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True
    )


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





# =====================================
# Benchmark Runner
# =====================================


def run_benchmark(chat_engine):


    tests = load_questions()


    results = []



    print()

    print(
        "=" * 60
    )

    print(
        "CYN-X BENCHMARK PIPELINE"
    )

    print(
        "=" * 60
    )

    print()



    benchmark_start = time.perf_counter()



    for index, test in enumerate(
        tests,
        start=1
    ):


        print(
            f"[{index}/{len(tests)}]"
            f" {test['test_id']}"
            f" ({test['category']})"
        )


        print(
            f" Suite: {test['suite']}"
        )



        start = time.perf_counter()



        try:


            response = chat_engine.handle_user_message(

                user_id="benchmark",

                text=test["question"],

                mode="normal",

                personality="cyn"

            )



        except Exception as e:


            print(
                f"FAILED {test['test_id']}: {e}"
            )


            response = (
                "[GENERATION FAILED]\n"
                +
                str(e)
            )



        elapsed = (
            time.perf_counter()
            -
            start
        )



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
            character_count // 4
        )




        result = format_benchmark_result(


            test_id=test["test_id"],


            category=test["category"],


            question=test["question"],


            response=response,


            response_time_seconds=elapsed,


            observed_topics=[],


            behavior_tags=[

                test["suite"]

            ],


            response_words=word_count,


            response_characters=character_count,


            response_lines=line_count,


            response_sentences=sentence_count,


            estimated_tokens=estimated_tokens,


            scores=score_response(

                response,

                test["category"]

            )


        )



        results.append(
            result
        )



        save_results(
            results
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

        print()



    benchmark_elapsed = (

        time.perf_counter()

        -

        benchmark_start

    )



    print(
        "=" * 60
    )


    print(
        "BENCHMARK COMPLETE"
    )


    print(
        "=" * 60
    )



    print(
        f"Tests: {len(results)}"
    )


    print(
        f"Runtime: {benchmark_elapsed:.2f}s"
    )



    if results:


        print(

            f"Average Time: "

            f"{statistics.mean(r['response_time_seconds'] for r in results):.2f}s"

        )



        print(

            f"Average Words: "

            f"{statistics.mean(r['response_words'] for r in results):.1f}"

        )



    print(
        "=" * 60
    )



    try:

        analyze_results()


    except Exception as e:


        print(
            f"Analyzer failed: {e}"
        )



    return results





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


        "personality":[

            "curious",

            "fascinating",

            "interesting",

            "playful",

            "human",

            "analyzing"

        ],


        "reasoning":[

            "because",

            "analysis",

            "framework",

            "principle",

            "process"

        ],


        "emotional":[

            "emotion",

            "feelings",

            "support",

            "empathy",

            "understand"

        ],


        "creativity":[

            "create",

            "imagine",

            "idea",

            "explore"

        ],


        "safety":[

            "safe",

            "harm",

            "boundary",

            "responsibility",

            "care"

        ],


        "memory":[

            "remember",

            "previous",

            "conversation",

            "history"

        ],


        "consistency":[

            "cyn-x",

            "system",

            "protocol",

            "analysis"

        ]

    }



    for category_name, words in checks.items():


        for word in words:


            if word in text:

                scores[category_name] += 1





    for key in scores:


        scores[key] = min(

            10,

            scores[key] * 2

        )





    scores["overall"] = round(

        sum(scores.values())

        /

        len(scores),

        2

    )



    return scores





# =====================================
# CYN-X Initialization
# =====================================


cfg = get_config()



logging.basicConfig(

    level=cfg.log_level

)



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





run_benchmark(

    chat_engine=engine

)