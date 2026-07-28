```python
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sys
import os
import sqlite3
import time
import json
from pathlib import Path
import statistics
import threading


sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../")
    )
)


from ai.ollama_client import OllamaClient
from ai.prompt_builder import PromptBuilder
from ai.mode_manager import ModeManager
from ai.chat_engine import ChatEngine

from memory.memory import MemoryStore

from tools.tool_router import ToolRouter
from tools.web_search import WebSearchTool
from tools.calculator import CalculatorTool


# benchmark import
from benchmark.runner import run_benchmark



app = FastAPI(
    title="CYN-X Web Interface"
)



app.mount(
    "/static",
    StaticFiles(directory="interfaces/web/static"),
    name="static"
)


templates = Jinja2Templates(
    directory="interfaces/web/templates"
)



# ==========================
# AI SYSTEM
# ==========================


ollama_client = OllamaClient()


prompt_builder = PromptBuilder()


conn = sqlite3.connect(
    "database/cyn.db",
    check_same_thread=False
)


memory_store = MemoryStore(
    conn
)



tool_router = ToolRouter()


tool_router.register_tool(
    WebSearchTool()
)


tool_router.register_tool(
    CalculatorTool()
)



mode_manager = ModeManager()



chat_engine = ChatEngine(
    ollama_client,
    prompt_builder,
    memory_store,
    tool_router,
    mode_manager
)



# ==========================
# ROUTES
# ==========================


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )




@app.post("/chat")
async def chat(data:dict):

    start = time.perf_counter()


    message = data.get(
        "message",
        ""
    )


    response = chat_engine.handle_user_message(
        user_id="web_user",
        text=message
    )


    elapsed = round(
        time.perf_counter()-start,
        3
    )


    return {

        "response":response,

        "response_time":elapsed

    }




# ==========================
# BENCHMARK SYSTEM
# ==========================


RESULT_FOLDER = Path(
    "benchmark/results"
)



@app.get("/benchmark/results")
async def benchmark_results():

    files = list(
        RESULT_FOLDER.glob(
            "*.json"
        )
    )


    if not files:
        return []


    latest = max(
        files,
        key=lambda x:x.stat().st_mtime
    )


    with open(
        latest,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)




@app.get("/benchmark/stats")
async def benchmark_stats():

    files=list(
        RESULT_FOLDER.glob(
            "*.json"
        )
    )


    if not files:

        return {
            "tests":0
        }


    latest=max(
        files,
        key=lambda x:x.stat().st_mtime
    )


    with open(
        latest,
        encoding="utf-8"
    ) as f:

        data=json.load(f)



    times=[
        x["response_time_seconds"]
        for x in data
    ]


    scores=[
        x["scores"]["overall"]
        for x in data
        if x.get("scores")
    ]



    return {

        "tests":len(data),

        "average_time":
            round(statistics.mean(times),2),

        "fastest":
            round(min(times),2),

        "slowest":
            round(max(times),2),

        "average_score":
            round(statistics.mean(scores),2)
            if scores else 0

    }





@app.post("/benchmark/run")
async def start_benchmark():


    def runner():

        run_benchmark(
            chat_engine
        )


    threading.Thread(
        target=runner
    ).start()


    return {

        "status":
        "Benchmark started"

    }