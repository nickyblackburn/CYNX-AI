from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ai.ollama_client import OllamaClient
from ai.prompt_builder import PromptBuilder
from ai.mode_manager import ModeManager

from memory.memory import MemoryStore
from tools.tool_router import ToolRouter

import sys
import os

from voice.audio_player import AudioPlayer
from voice.tts_engine import VoiceEngine
from voice.voice_manager import VoiceManager

# allow importing CYN modules
sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../")
    )
)

from ai.chat_engine import ChatEngine


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



ollama_client = OllamaClient()

prompt_builder = PromptBuilder()

import sqlite3

conn = sqlite3.connect(
    "database/cyn.db",
    check_same_thread=False
)

memory_store = MemoryStore(conn)

tool_router = ToolRouter()

mode_manager = ModeManager()


chat_engine = ChatEngine(
    ollama_client,
    prompt_builder,
    memory_store,
    tool_router,
    mode_manager
)
tts_engine = VoiceEngine()

audio_player = AudioPlayer()

voice_engine = VoiceManager(
    tts_engine,
    audio_player
)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )
@app.post("/chat")
async def chat(data: dict):

    message = data.get("message")

    response = chat_engine.handle_user_message(
        user_id="web_user",
        text=message
    )

    voice_engine.speak(response)

    return {
        "response": response
    }