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

    "habits": {
        "name": "habits",
        "file": "habits.md",
    },
    "examples": {
        "name": "examples",
        "file": "examples.md",
    },   
    "flirty": {
        "name": "flirty",
        "file": "flirty.md",
    },
    "modes": {
        "name": "modes",        
        "file": "modes.md",
    },
    "personality": {
        "name": "personality",
        "file": "personality.md",
    },  
    "safety": {
        "name": "safety",
        "file": "safety.md",
    },
    "spontaneous": {
        "name": "spontaneous",
        "file": "spontaneous.md",
    },

}


def get_personality(name: str) -> str:
    personality = PERSONALITIES.get(name, PERSONALITIES["normal"])

    path = Path("prompts") / personality["file"]

    if path.exists():
        return path.read_text(encoding="utf-8")

    return ""