"""Monorepo path helpers (paths relative to repository root, not this package)."""

from __future__ import annotations

from pathlib import Path

# lepro/lepro/paths.py → project dir is lepro/, repo root is parent
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = _PROJECT_ROOT.parent


def repo_path(*parts: str) -> Path:
    return REPO_ROOT.joinpath(*parts)
