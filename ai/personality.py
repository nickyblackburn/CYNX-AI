"""
Personality registry and helper functions.
Each personality exposes a short system fragment and optional constraints.
"""
from pathlib import Path
from typing import Dict


PERSONALITIES: Dict[str, Dict] = {
    "normal": {
        "name": "normal",
        "file": "core.md",
    },

    "solver": {
        "name": "solver",
        "file": "solver.md",
    },

    "gremlin": {
        "name": "gremlin",
        "file": "gremlin.md",
    },

    "helper": {
        "name": "helper",
        "file": "helper.md",
    },

    "flirty": {
        "name": "flirty",
        "file": "flirty.md",
    },

    "habits": {
        "name": "habits",
        "file": "habits.md",
    },
}


def get_personality(name: str) -> str:
    personality = PERSONALITIES.get(name, PERSONALITIES["normal"])

    path = Path("prompts") / personality["file"]

    if path.exists():
        return path.read_text(encoding="utf-8")

    return ""