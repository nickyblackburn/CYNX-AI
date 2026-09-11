
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sys
import os
import sqlite3
import time

from ai.knowledge.store import KnowledgeStore
from memory.sqlite import connect



sys.path.append(
    os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../"
        )
    )
)


from ai.context_manager import ContextManager
from ai.memory_system.extractor import MemoryExtractor
from ai.memory_system.manager import MemoryManager
from ai.ollama_client import OllamaClient
from ai.prompt_builder import PromptBuilder
from ai.mode_manager import ModeManager
from ai.chat_engine import ChatEngine

from tools.tool_router import ToolRouter
from tools.web_search import WebSearchTool
from tools.calculator import CalculatorTool
from tools.SmokeCounterTool import smoke_counter
from tools.chart_tool import ChartTool
from tools.LeproLightsTool import LeproLightsTool



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


conn = connect()



# ======================
# MEMORY
# ======================

# MemoryManager is now the single
# memory system used by CYN-X.

memory_manager = MemoryManager(
    conn
)


memory_extractor = MemoryExtractor(
    memory_manager
)



# ======================
# TOOLS
# ======================


tool_router = ToolRouter()


tool_router.register_tool(
    WebSearchTool()
)


tool_router.register_tool(
    CalculatorTool()
)


# Register the smoke_counter tool so Cyn
# can call it from the web interface
tool_router.register_tool(
    smoke_counter
)

tool_router.register_tool(
    LeproLightsTool
)

tool_router.register_tool(
    ChartTool
    )


# ======================
# MODE / KNOWLEDGE
# ======================


mode_manager = ModeManager()


knowledge_store = KnowledgeStore(
    conn
)



# ======================
# CONTEXT
# ======================

# ContextManager and MemoryExtractor now
# use the exact same MemoryManager.

context_manager = ContextManager(
    memory_manager,
    knowledge_store,
)



# ======================
# CHAT ENGINE
# ======================


chat_engine = ChatEngine(
    ollama_client,
    prompt_builder,
    memory_manager,
    tool_router,
    mode_manager,
    memory_manager,
    memory_extractor=memory_extractor,
    context_manager=context_manager
    
)



# ======================
# WEB
# ======================


@app.get("/", response_class=HTMLResponse)
async def home(request:Request):

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={}
    )


@app.get("/dashboard")
def dashboard(request:Request):
    
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={}
    )




chat_request_count = 0


@app.post("/chat")
async def chat(data:dict):

    global chat_request_count

    chat_request_count += 1

    request_id = str(chat_request_count)

    start=time.perf_counter()

    message=data.get(
        "message",
        ""
    )

    print(
        f"[CHAT REQUEST] id={request_id} "
        f"count={chat_request_count} "
        f"message_preview={message[:120]}"
    )

    response = chat_engine.handle_user_message(
        user_id="web_user",
        text=message,
        request_id=request_id
    )

    elapsed = round(
        time.perf_counter()-start,
        3
    )

    print(
        f"[CHAT COMPLETE] id={request_id} "
        f"elapsed={elapsed}s"
    )

    return {

        "response":response,

        "response_time":elapsed

    }
