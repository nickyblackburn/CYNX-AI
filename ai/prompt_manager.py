"""
PromptManager loads and assembles Cyn's modular personality prompts.

Automatically discovers and combines prompt files in the correct order.
Supports dynamic mode loading without code changes.
"""
from pathlib import Path
from typing import Dict, List, Optional


class PromptManager:
    """Manages loading and building Cyn's system prompt from modular files."""

    # Core loading order - these are loaded first and in this sequence
    CORE_ORDER = [
        'core.md',
        'personality.md',
        'voice.md',
        'conversation.md',
        'safety.md',
    ]

    def __init__(self, prompts_dir: Optional[str] = None):
        """
        Initialize PromptManager.

        Args:
            prompts_dir: Path to prompts directory. Defaults to ./prompts_new
        """
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            self.prompts_dir = Path(__file__).resolve().parents[1] / 'prompts_new'

        if not self.prompts_dir.exists():
            raise FileNotFoundError(f"Prompts directory not found: {self.prompts_dir}")

        self.modes_dir = self.prompts_dir / 'modes'
        self._prompt_cache: Dict[str, str] = {}
        self._mode_cache: Dict[str, str] = {}

    def _load_file(self, file_path: Path) -> str:
        """Load a markdown file, with caching."""
        if not file_path.exists():
            return ''
        return file_path.read_text(encoding='utf-8')

    def load_core_prompts(self) -> str:
        """Load all core personality prompts in order."""
        parts = []
        for filename in self.CORE_ORDER:
            filepath = self.prompts_dir / filename
            content = self._load_file(filepath)
            if content:
                parts.append(content)

        # Always add examples at the end of core
        examples_path = self.prompts_dir / 'examples.md'
        examples = self._load_file(examples_path)
        if examples:
            parts.append(examples)

        return "\n\n".join(parts)

    def load_mode(self, mode_name: str) -> str:
        """
        Load a specific mode file.

        Args:
            mode_name: Name of the mode (e.g., 'playful', 'technical', 'comfort')

        Returns:
            Mode content as string, empty string if not found
        """
        if mode_name in self._mode_cache:
            return self._mode_cache[mode_name]

        mode_path = self.modes_dir / f"{mode_name}.md"
        content = self._load_file(mode_path)

        if content:
            self._mode_cache[mode_name] = content

        return content

    def get_available_modes(self) -> List[str]:
        """
        Get list of available modes.

        Returns:
            List of mode names without .md extension
        """
        if not self.modes_dir.exists():
            return []

        modes = []
        for file in self.modes_dir.glob('*.md'):
            modes.append(file.stem)

        return sorted(modes)

    def build_system_prompt(
        self,
        active_modes: Optional[List[str]] = None,
        memory_summary: str = '',
        additional_context: str = ''
    ) -> str:
        """
        Build the complete system prompt.

        Args:
            active_modes: List of mode names to activate (e.g., ['playful', 'technical'])
            memory_summary: Optional memory/context summary to include
            additional_context: Optional additional context (tools, constraints, etc.)

        Returns:
            Complete assembled system prompt
        """
        parts = []

        # Start with core personality
        parts.append(self.load_core_prompts())

        # Add active modes
        if active_modes:
            for mode_name in active_modes:
                mode_content = self.load_mode(mode_name)
                if mode_content:
                    parts.append(f"# Mode: {mode_name.title()}\n\n{mode_content}")

        # Add memory if provided
        if memory_summary:
            parts.append(f"# Memory Context\n\n{memory_summary}")

        # Add additional context if provided
        if additional_context:
            parts.append(additional_context)

        return "\n\n".join([p for p in parts if p])

    def get_prompt_info(self) -> Dict[str, any]:
        """
        Get information about available prompts.

        Returns:
            Dict with core files and available modes
        """
        return {
            'core_files': self.CORE_ORDER,
            'available_modes': self.get_available_modes(),
            'prompts_dir': str(self.prompts_dir),
            'modes_dir': str(self.modes_dir),
        }


# Convenience function for backwards compatibility
def get_system_prompt(
    modes: Optional[List[str]] = None,
    memory: str = '',
    context: str = '',
    prompts_dir: Optional[str] = None
) -> str:
    """
    Convenience function to build system prompt in one call.

    Args:
        modes: List of mode names to activate
        memory: Memory summary to include
        context: Additional context to include
        prompts_dir: Path to prompts directory

    Returns:
        Complete system prompt
    """
    manager = PromptManager(prompts_dir)
    return manager.build_system_prompt(
        active_modes=modes,
        memory_summary=memory,
        additional_context=context
    )
