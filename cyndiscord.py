import os
import discord
from dotenv import load_dotenv

load_dotenv()

from ai.ollama_client import OllamaClient
from ai.prompt_builder import PromptBuilder
from ai.mode_manager import ModeManager
from ai.chat_engine import ChatEngine
from memory.sqlite import connect
from memory.memory import MemoryStore
from ai.memory_system.manager import MemoryManager
from ai.memory_system.extractor import MemoryExtractor
from ai.context_manager import ContextManager
from tools.tool_router import ToolRouter
from tools.web_search import WebSearchTool
from tools.calculator import CalculatorTool
from tools.SmokeCounterTool import smoke_counter

TOKEN = os.getenv("DISCORD_TOKEN")
MODEL = os.getenv("OLLAMA_MODEL", "cyn-x")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# Conversation history per channel (simple local history)
history = {}

# -------------------------
# Build ChatEngine (like web app)
# -------------------------
ollama_client = OllamaClient(model=MODEL)
prompt_builder = PromptBuilder()
conn = connect()
memory_store = MemoryStore(conn)

tool_router = ToolRouter()
# register existing tools
tool_router.register_tool(WebSearchTool())
tool_router.register_tool(CalculatorTool())
# register the smoke counter instance
tool_router.register_tool(smoke_counter)

# print available tools for debugging
print("[AVAILABLE_TOOLS]", tool_router.list_tools())
print("[SMOKE TOOL MODULE]", smoke_counter.__class__.__module__)

mode_manager = ModeManager()
memory_manager = MemoryManager(conn)
memory_extractor = MemoryExtractor(memory_store)
knowledge_store = None
context_manager = ContextManager(memory_store, knowledge_store) if True else None

chat_engine = ChatEngine(
    ollama_client=ollama_client,
    prompt_builder=prompt_builder,
    memory_store=memory_store,
    tool_router=tool_router,
    mode_manager=mode_manager,
    memory_manager=memory_manager,
    memory_extractor=memory_extractor,
    context_manager=context_manager
)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Only respond when mentioned or when using !ai
    if not (
        client.user in message.mentions
        or message.content.startswith("!ai")
    ):
        return

    prompt = (
        message.content.replace("!ai", "")
        .replace(f"<@{client.user.id}>", "")
        .strip()
    )

    if not prompt:
        return

    channel = str(message.channel.id)

    if channel not in history:
        history[channel] = []

    history[channel].append({
        "role": "user",
        "content": prompt
    })

    async with message.channel.typing():
        try:
            # Use ChatEngine so tools are detected and executed
            reply = chat_engine.handle_user_message(user_id=channel, text=prompt)

            history[channel].append({
                "role": "assistant",
                "content": reply
            })

            # Prevent history from growing forever
            history[channel] = history[channel][-20:]

            # Discord message limit
            for i in range(0, len(reply), 1900):
                await message.channel.send(reply[i:i+1900])

        except Exception as e:
            await message.channel.send(f"Error: {e}")

client.run(TOKEN)