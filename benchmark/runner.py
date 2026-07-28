import asyncio
import logging
from benchmark.formatter import format_benchmark_result
from config import get_config
from ai.ollama_client import OllamaClient
from ai.prompt_builder import PromptBuilder
from ai.personality import get_personality
from ai.mode_manager import ModeManager
from ai.chat_engine import ChatEngine
from ai.memory_system import MemoryManager, MemoryExtractor
from memory.sqlite import connect as sqlite_connect
from memory.memory import MemoryStore
from tools.calculator import CalculatorTool
from tools.tool_router import ToolRouter
from interfaces.terminal import TerminalAdapter
from tools.web_search import WebSearchTool
from pathlib import Path
import json
import time

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


    for test in tests:

        print(
            f"Running {test['test_id']}"
        )


        start = time.perf_counter()


        response = chat_engine.handle_user_message(

            user_id="benchmark",

            text=test["question"],

            mode="normal",

            personality="cyn"

        )


        elapsed = (
            time.perf_counter()
            -
            start
        )


        result = format_benchmark_result(

            test_id=test["test_id"],

            category=test["category"],

            question=test["question"],

            response=response,

            response_time_seconds=elapsed,

            observed_topics=[],

            behavior_tags=[]

        )


        results.append(result)


        save_results(results)

        print(result)



    return results





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
    WebSearchTool())



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