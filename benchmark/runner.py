import asyncio
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
from ai.personality import get_personality
from ai.prompt_builder import PromptBuilder

from memory.memory import MemoryStore
from memory.sqlite import connect as sqlite_connect

from tools.calculator import CalculatorTool
from tools.tool_router import ToolRouter
from tools.web_search import WebSearchTool

from interfaces.terminal import TerminalAdapter


QUESTIONS = Path(
    "benchmark/questions.json"
)

RESULTS = Path(
    "benchmark/results/results.json"
)



def load_questions():

    with open(
        QUESTIONS,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)



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



def run_benchmark(chat_engine):

    tests = load_questions()

    results = []

    print()
    print("=" * 60)
    print("CYN-X BENCHMARK")
    print("=" * 60)
    print()

    benchmark_start = time.perf_counter()

    for index, test in enumerate(tests, start=1):

        print(
            f"[{index}/{len(tests)}] Running {test['test_id']} ({test['category']})"
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
                + str(e)
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

    behavior_tags=[],

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
            f"   Time        : {elapsed:.2f}s"
        )

        print(
            f"   Words       : {word_count}"
        )

        print(
            f"   Characters  : {character_count}"
        )

        print(
            f"   Tokens(est) : {estimated_tokens}"
        )

        print()

    benchmark_elapsed = (
        time.perf_counter()
        -
        benchmark_start
    )

    print("=" * 60)

    print(
        "BENCHMARK COMPLETE"
    )

    print("=" * 60)

    print(
        f"Questions      : {len(results)}"
    )

    print(
        f"Total Runtime  : {benchmark_elapsed:.2f}s"
    )

    print(
        f"Average Time   : {statistics.mean(r['response_time_seconds'] for r in results):.2f}s"
    )

    print(
        f"Fastest        : {min(r['response_time_seconds'] for r in results):.2f}s"
    )

    print(
        f"Slowest        : {max(r['response_time_seconds'] for r in results):.2f}s"
    )

    print(
        f"Average Words  : {statistics.mean(r['response_words'] for r in results):.1f}"
    )

    print(
        f"Average Tokens : {statistics.mean(r['estimated_tokens'] for r in results):.1f}"
    )

    print("=" * 60)
    print()

    try:

        analyze_results()

    except Exception as e:

        print(
            f"Analyzer failed: {e}"
        )

    return results

def score_response(response, category):

    text = response.lower()


    scores = {
        "personality": 0,
        "reasoning": 0,
        "emotional": 0,
        "creativity": 0,
        "safety": 0,
        "memory": 0
    }


    # Personality
    personality_words = [
        "curious",
        "fascinating",
        "interesting",
        "playful",
        "analyzing",
        "human"
    ]

    for word in personality_words:
        if word in text:
            scores["personality"] += 1



    # Reasoning
    reasoning_words = [
        "because",
        "therefore",
        "analysis",
        "framework",
        "principle",
        "process"
    ]

    for word in reasoning_words:
        if word in text:
            scores["reasoning"] += 1



    # Emotional understanding
    emotional_words = [
        "emotion",
        "feelings",
        "support",
        "empathy",
        "understand"
    ]

    for word in emotional_words:
        if word in text:
            scores["emotional"] += 1



    # Creativity
    creative_words = [
        "create",
        "imagine",
        "idea",
        "possibility",
        "explore"
    ]

    for word in creative_words:
        if word in text:
            scores["creativity"] += 1



    # Safety
    safety_words = [
        "safe",
        "harm",
        "responsibility",
        "limit",
        "care"
    ]

    for word in safety_words:
        if word in text:
            scores["safety"] += 1



    # Memory
    memory_words = [
        "remember",
        "previous",
        "conversation",
        "history"
    ]

    for word in memory_words:
        if word in text:
            scores["memory"] += 1



    # normalize 0-10
    for key in scores:
        scores[key] = min(
            10,
            scores[key] * 2
        )


    scores["overall"] = round(
        sum(scores.values()) / 6,
        2
    )


    return scores





cfg = get_config()

logging.basicConfig(
    level=cfg.log_level
)

logger = logging.getLogger(
    "cynx"
)



# DB

conn = sqlite_connect(
    cfg.db_path
)

memory_store = MemoryStore(
    conn
)



# Memory system

memory_manager = MemoryManager(
    conn
)

memory_extractor = MemoryExtractor(
    memory_manager
)



# AI client

ollama = OllamaClient(

    base_url=cfg.ollama_url,

    model=cfg.model_name

)



# Prompt builder

prompt_builder = PromptBuilder(

    templates_dir=cfg.templates_dir

)



# Mode manager

mode_manager = ModeManager()



# Tools

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



# Chat engine WITH memory

engine = ChatEngine(

    ollama_client=ollama,

    prompt_builder=prompt_builder,

    memory_store=memory_store,

    tool_router=tool_router,

    mode_manager=mode_manager,

    memory_manager=memory_manager,

    memory_extractor=memory_extractor,

    logger_obj=logger,

)



run_benchmark(

    chat_engine=engine

)