"""
Application configuration helper.
Reads environment variables (with optional .env) and provides a simple Config dataclass.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    ollama_url: str
    model_name: str
    db_path: str
    templates_dir: str
    log_dir: str
    log_level: int


def get_config() -> Config:
    root = Path(__file__).resolve().parent
    return Config(
        ollama_url=os.getenv('OLLAMA_URL', 'http://localhost:11434'),
        model_name=os.getenv('MODEL_NAME', 'cyn-x:latest'),
        db_path=os.getenv('CYNX_DB_PATH', str(root / 'database' / 'cyn.db')),
        templates_dir=os.getenv('CYNX_TEMPLATES_DIR', str(root / 'prompts')),
        log_dir=os.getenv('CYNX_LOG_DIR', str(root / 'logs')),
        log_level=int(os.getenv('CYNX_LOG_LEVEL', logging_level_from_env())) if os.getenv('CYNX_LOG_LEVEL') else 20,
    )


def logging_level_from_env() -> int:
    # Helper: accept names like DEBUG/INFO or numeric
    v = os.getenv('CYNX_LOG_LEVEL', '20')
    try:
        return int(v)
    except Exception:
        import logging
        return getattr(logging, v.upper(), 20)
