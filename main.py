"""
Main entrypoint for CYN-X.
Wires configuration, logging, DB, tools, AI client, and starts the selected interface (terminal by default).
"""
import asyncio
import logging
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


def main():
    cfg = get_config()
    logging.basicConfig(level=cfg.log_level)
    logger = logging.getLogger("cynx")

    # DB
    conn = sqlite_connect(cfg.db_path)
    memory_store = MemoryStore(conn)

    # Memory system
    memory_manager = MemoryManager(conn)
    memory_extractor = MemoryExtractor(memory_manager)

    # AI client
    ollama = OllamaClient(base_url=cfg.ollama_url, model=cfg.model_name)

    # Prompt builder
    prompt_builder = PromptBuilder(templates_dir=cfg.templates_dir)

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

    print(tool_router.describe_tools())

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

    # Default to terminal adapter for now
    adapter = TerminalAdapter(chat_engine=engine, logger=logger)
    try:
        adapter.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == '__main__':
    main()
