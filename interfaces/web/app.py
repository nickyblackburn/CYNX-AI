
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sys
import os
import sqlite3
import time


sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../"
        )
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



app = FastAPI(
    title="CYN-X"
)



app.mount(
    "/static",
    StaticFiles(
        directory="interfaces/web/static"
    ),
    name="static"
)



templates = Jinja2Templates(
    directory="interfaces/web/templates"
)



# ======================
# AI CORE
# ======================


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



# ======================
# WEB
# ======================


@app.get("/", response_class=HTMLResponse)
async def home(request:Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )




@app.post("/chat")
async def chat(data:dict):


    start=time.perf_counter()



    message=data.get(
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