import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai.ollama_client import OllamaClient
from ai.prompt_builder import PromptBuilder
from ai.mode_manager import ModeManager
from ai.chat_engine import ChatEngine
from memory.sqlite import connect as sqlite_connect
from memory.memory import MemoryStore
from ai.memory_system import MemoryManager, MemoryExtractor
from tools.tool_router import ToolRouter
from tools.web_search import WebSearchTool
from tools.calculator import CalculatorTool
from tools.SmokeCounterTool import smoke_counter, FILE, load_data
import sqlite3, os, time

conn = sqlite3.connect(':memory:')
memory_store = MemoryStore(conn)
memory_manager = MemoryManager(conn)
memory_extractor = MemoryExtractor(memory_manager)

tool_router = ToolRouter()
tool_router.register_tool(WebSearchTool())
tool_router.register_tool(CalculatorTool())
tool_router.register_tool(smoke_counter)

engine = ChatEngine(
    ollama_client=OllamaClient(model='cyn-x:latest'),
    prompt_builder=PromptBuilder('C:/Users/nickk/Documents/CYNX-AI/prompts_new'),
    memory_store=memory_store,
    tool_router=tool_router,
    mode_manager=ModeManager(),
    memory_manager=memory_manager,
    memory_extractor=memory_extractor,
    context_manager=None,
)

tests = [
    'log 3 pen hits',
    'how many hits do I have today?',
    'log 1 cigarette hit',
    'what was my last hit?',
    'show my recent sessions'
]

for t in tests:
    print('\n=== TEST ===')
    print('USER:', t)
    resp = engine.handle_user_message(user_id='test', text=t)
    print('ASSISTANT:\n', resp)
    print('[CURRENT JSON]', FILE)
    print(load_data())
    time.sleep(0.5)
