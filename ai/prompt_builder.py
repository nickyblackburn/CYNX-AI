"""
PromptBuilder assembles the system prompt from template files, personality fragments, mode instructions,
examples, recent history, and memory summaries.
"""
from pathlib import Path
from typing import List, Optional


class PromptBuilder:
    def __init__(self, templates_dir: Optional[str] = None):
        self.templates_dir = Path(templates_dir) if templates_dir else Path(__file__).resolve().parents[1] / 'prompts'

    def _load_template(self, name: str) -> str:
        path = self.templates_dir / name
        if path.exists():
            return path.read_text(encoding='utf-8')
        return ''

    def build_prompt(self, user_input: str, mode_fragment: str = '', personality_fragment: str = '',
                     history: Optional[List[dict]] = None, memory_summary: str = '', tools_spec: str = '') -> str:
        parts = []
        parts.append(self._load_template('core.md'))
        if personality_fragment:
            parts.append(personality_fragment)
        if mode_fragment:
            parts.append(mode_fragment)
        if tools_spec:
            parts.append(tools_spec)
        parts.append(self._load_template('examples.md'))
        if memory_summary:
            parts.append("Memory summary:\n" + memory_summary)
        if history:
            parts.append("Recent conversation:")
            for msg in history[-10:]:
                parts.append(f"{msg.get('role')}: {msg.get('content')}")
        parts.append("User: " + user_input)
        return "\n\n".join([p for p in parts if p])
