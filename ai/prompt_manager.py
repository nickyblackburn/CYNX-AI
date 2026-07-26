"""
PromptManager loads Cyn's modular personality prompts.

Keeps the base personality small and loads optional material dynamically.
"""

from pathlib import Path
from typing import Dict, List, Optional


class PromptManager:

    CORE_ORDER = [
        "core.md",
        "personality.md",
        "voice.md",
    ]

    OPTIONAL_FILES = {
        "safety": "safety.md",
        "conversation": "conversation.md",
    }


    def __init__(self, prompts_dir: Optional[str] = None):

        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            self.prompts_dir = (
                Path(__file__).resolve().parents[1]
                / "prompts_new"
            )

        if not self.prompts_dir.exists():
            raise FileNotFoundError(
                f"Missing prompts directory: {self.prompts_dir}"
            )

        self.modes_dir = self.prompts_dir / "modes"

        self._cache = {}
        self._mode_cache = {}


    def _load_file(self, path: Path):

        key = str(path)

        if key in self._cache:
            return self._cache[key]

        if not path.exists():
            return ""

        text = path.read_text(
            encoding="utf-8"
        )

        self._cache[key] = text

        return text



    def load_core_prompts(self):

        parts = []

        for file in self.CORE_ORDER:

            text = self._load_file(
                self.prompts_dir / file
            )

            if text:
                parts.append(text)


        return "\n\n".join(parts)



    def load_optional(self, name):

        filename = self.OPTIONAL_FILES.get(name)

        if not filename:
            return ""

        return self._load_file(
            self.prompts_dir / filename
        )



    def load_mode(self, mode_name):

        if mode_name in self._mode_cache:
            return self._mode_cache[mode_name]


        path = (
            self.modes_dir /
            f"{mode_name}.md"
        )

        text = self._load_file(path)


        if text:
            self._mode_cache[mode_name] = text


        return text



    def build_system_prompt(
        self,
        active_modes=None,
        memory_summary="",
        additional_context="",
        include_safety=True,
    ):

        parts = []


        # Small personality core
        core = self.load_core_prompts()

        if core:
            parts.append(core)



        # Load only safety if wanted
        if include_safety:

            safety = self.load_optional(
                "safety"
            )

            if safety:
                parts.append(safety)



        # Modes only when activated
        if active_modes:

            for mode in active_modes:

                mode_text = self.load_mode(
                    mode
                )

                if mode_text:

                    parts.append(
                        f"[{mode.upper()} MODE]\n{mode_text}"
                    )



        # Memory
        if memory_summary:

            parts.append(
                f"[MEMORY]\n{memory_summary}"
            )



        if additional_context:

            parts.append(
                additional_context
            )



        prompt = "\n\n".join([p for p in parts if p])

        print("\n===== CYN PROMPT DEBUG =====")
        print("Characters:", len(prompt))
        print("Estimated tokens:", len(prompt.split()) * 1.3)
        print("===== END DEBUG =====\n")

        return "\n\n".join(parts)