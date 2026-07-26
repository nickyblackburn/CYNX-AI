"""
Personality registry and helper functions.

Uses PromptManager to dynamically load personality fragments.
Maintains backwards compatibility with legacy personality definitions.
"""
from pathlib import Path
from typing import Dict, List

from .prompt_manager import PromptManager


# Legacy personality registry (for backwards compatibility)
PERSONALITIES: Dict[str, Dict] = {
    "normal": {
        "name": "normal",
        "file": "core.md",
    },
    "safety": {
        "name": "safety",
        "file": "safety.md",
    },
    "examples": {
        "name": "examples",
        "file": "examples.md",
    },
}

# New approach: mode registry
MODES = {
    "playful": "playful.md",
    "technical": "technical.md",
    "comfort": "comfort.md",
}

# Initialize PromptManager
_manager: PromptManager = None


def get_manager() -> PromptManager:
    """Get or initialize the PromptManager singleton."""
    global _manager
    if _manager is None:
        _manager = PromptManager()
    return _manager


def get_personality(name: str) -> str:
    """
    Load a personality fragment (legacy support).

    Args:
        name: Name of the personality

    Returns:
        Content of the personality file
    """
    manager = get_manager()
    personality = PERSONALITIES.get(name, PERSONALITIES["normal"])

    # Try new location first
    path = manager.prompts_dir / personality["file"]
    if path.exists():
        return path.read_text(encoding="utf-8")

    # Fall back to old location
    old_path = Path("prompts") / personality["file"]
    if old_path.exists():
        return old_path.read_text(encoding="utf-8")

    return ""


def get_mode(name: str) -> str:
    """
    Load a mode fragment.

    Args:
        name: Name of the mode (playful, technical, comfort)

    Returns:
        Content of the mode file
    """
    manager = get_manager()
    return manager.load_mode(name)


def get_available_modes() -> List[str]:
    """
    Get list of available modes.

    Returns:
        List of mode names
    """
    manager = get_manager()
    return manager.get_available_modes()


def build_system_prompt(
    core: bool = True,
    modes: List[str] = None,
    memory: str = "",
    context: str = ""
) -> str:
    """
    Build a complete system prompt with selected components.

    Args:
        core: Include core personality (default True)
        modes: List of modes to activate
        memory: Optional memory context
        context: Optional additional context

    Returns:
        Complete system prompt
    """
    manager = get_manager()

    if not modes:
        modes = []

    return manager.build_system_prompt(
        active_modes=modes if modes else None,
        memory_summary=memory,
        additional_context=context
    )