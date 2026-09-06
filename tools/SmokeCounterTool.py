
"""
CYN Studio - Smoke Counter Tool

Conversational smoking tracker for CYN.

Supported actions:
    log     -> Log a smoking session
    stats   -> Get overall statistics
    recent  -> Get recent sessions
    reset   -> Reset the entire tracker

Data is stored locally in:
    smoking_log.json

Example tool calls:

    smoke_counter(action="log", smoke_type="weed", amount=1)
    smoke_counter(action="log", smoke_type="cigarette", amount=1)
    smoke_counter(action="stats")
    smoke_counter(action="recent")
    smoke_counter(action="reset")
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

# ============================================================
# Configuration
# ============================================================

import os
from typing import Any, Dict
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(BASE_DIR, "smoking_log.json")



# ============================================================
# Data Handling
# ============================================================

def empty_data() -> Dict[str, Any]:
    """Return a fresh tracker structure."""
    return {
        "total_units": 0,
        "total_cigarettes": 0,
        "sessions": []
    }


def reconcile_totals(data: Dict[str, Any]) -> Dict[str, Any]:
    """Keep cumulative totals derived from the session list so they can't drift."""
    sessions = data.get("sessions", [])
    data["total_units"] = sum(float(s.get("units", 0) or 0) for s in sessions)
    data["total_cigarettes"] = sum(float(s.get("cigarettes", 0) or 0) for s in sessions)
    return data


def load_data() -> Dict[str, Any]:
    """
    Load smoking data from disk.

    Also converts the older tracker format automatically.
    """

    if not os.path.exists(FILE):
        return empty_data()

    try:
        with open(FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    except (json.JSONDecodeError, OSError):
        # Do not crash CYN if the log is damaged.
        return empty_data()

    # --------------------------------------------------------
    # Convert old tracker format
    # --------------------------------------------------------

    if "total" in data and "total_units" not in data:

        new_data = {
            "total_units": 0,
            "total_cigarettes": 0,
            "sessions": []
        }

        for s in data.get("sessions", []):

            amount = float(s.get("amount", 0))
            smoke_type = str(
                s.get("type", "unknown")
            ).lower().strip()

            # Fix old typo
            if smoke_type == "ciggerette":
                smoke_type = "cigarette"

            if smoke_type == "cigarette":

                units = amount * 0.5

                new_data["total_cigarettes"] += amount

            else:

                units = amount

            new_data["total_units"] += units

            new_data["sessions"].append({
                "time": s.get(
                    "time",
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                ),
                "type": smoke_type,
                "units": units,
                "cigarettes": (
                    amount
                    if smoke_type == "cigarette"
                    else 0
                )
            })

        save_data(new_data)
        return new_data

    # --------------------------------------------------------
    # Make sure expected fields exist
    # --------------------------------------------------------

    data.setdefault("total_units", 0)
    data.setdefault("total_cigarettes", 0)
    data.setdefault("sessions", [])

    return reconcile_totals(data)


def save_data(data: Dict[str, Any]) -> None:
    """Save tracker data safely."""

    data = reconcile_totals(data)

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# Core Tracker Functions
# ============================================================

def log_smoke(
    smoke_type: str,
    amount: float = 1
) -> Dict[str, Any]:
    """
    Log a smoking session.

    Cigarettes:
        1 cigarette = 0.5 units

    Other types:
        amount = units directly
    """

    data = load_data()

    smoke_type = str(smoke_type).lower().strip()

    if not smoke_type:
        smoke_type = "unknown"

    # Prevent invalid negative entries
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return {
            "success": False,
            "error": "Amount must be a number."
        }

    if amount <= 0:
        return {
            "success": False,
            "error": "Amount must be greater than zero."
        }

    # --------------------------------------------------------
    # Cigarettes
    # --------------------------------------------------------

    if smoke_type == "cigarette":

        cigarettes = amount

        # 1 cigarette = 0.5 units
        units = cigarettes * 0.5

        session = {
            "time": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "type": "cigarette",
            "cigarettes": cigarettes,
            "units": units
        }

    # --------------------------------------------------------
    # Other smoke types
    # --------------------------------------------------------

    else:

        units = amount

        session = {
            "time": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "type": smoke_type,
            "units": units
        }

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    data["sessions"].append(session)
    data = reconcile_totals(data)
    save_data(data)

    # Merge stats so callers always receive the full up-to-date statistics
    stats = get_stats()

    result = {
        "success": True,
        "message": "Smoking session logged.",
        "type": smoke_type,
        "amount": amount,
        "added_units": units,
        "time": session["time"]
    }
    # copy numeric/stat fields from stats
    for k in ("total_units", "total_cigarettes", "total_sessions", "today_sessions", "today_units", "last_session"):
        result[k] = stats.get(k)

    return result


# ============================================================
# Statistics
# ============================================================

def normalize_smoke_type(value: Optional[str]) -> Optional[str]:
    """Normalize common aliases to canonical smoke types."""
    if value is None:
        return None
    v = str(value).lower().strip()
    if not v:
        return None
    aliases = {
        "cig": "cigarette",
        "cigs": "cigarette",
        "cigarette": "cigarette",
        "cigarettes": "cigarette",
        "bong": "bong",
        "bongs": "bong",
        "vape": "vape",
        "vapes": "vape",
        "vaped": "vape",
        "pen": "pen",
        "pens": "pen",
        "weed": "weed",
        "joint": "joint",
        "joints": "joint"
    }
    return aliases.get(v, v)


def get_stats(smoke_type: Optional[str] = None, scope: str = "all") -> Dict[str, Any]:
    """Return smoking statistics.

    If smoke_type is provided, only matches that smoke type.
    If scope == 'today', only count today's sessions.
    """

    data = load_data()
    sessions = data.get("sessions", [])

    normalized = normalize_smoke_type(smoke_type)
    if normalized:
        sessions = [
            s for s in sessions
            if normalize_smoke_type(str(s.get("type", ""))) == normalized
        ]

    today = datetime.now().strftime("%Y-%m-%d")
    if str(scope).lower() == "today":
        sessions = [
            s for s in sessions
            if str(s.get("time", "")).startswith(today)
        ]

    units = sum(float(s.get("units", 0) or 0) for s in sessions)
    session_count = len(sessions)
    last_session = sessions[-1] if sessions else None

    if normalized is not None:
        return {
            "success": True,
            "scope": str(scope).lower() if scope else "all",
            "smoke_type": normalized,
            "units": units,
            "sessions": session_count,
            "today_sessions": len([s for s in sessions if str(s.get("time", "")).startswith(today)]),
            "today_units": sum(float(s.get("units", 0) or 0) for s in sessions if str(s.get("time", "")).startswith(today)),
            "last_session": last_session,
        }

    today_sessions = [
        s for s in data.get("sessions", [])
        if str(s.get("time", "")).startswith(today)
    ]
    today_units = sum(float(s.get("units", 0) or 0) for s in today_sessions)

    return {
        "success": True,
        "total_units": data.get("total_units", 0),
        "total_cigarettes": data.get("total_cigarettes", 0),
        "total_sessions": len(data.get("sessions", [])),
        "today_sessions": len(today_sessions),
        "today_units": today_units,
        "last_session": (
            data.get("sessions", [])[-1]
            if data.get("sessions")
            else None
        ),
        "scope": "all",
        "smoke_type": None,
        "units": data.get("total_units", 0),
        "sessions": len(data.get("sessions", [])),
    }


# ============================================================
# Recent Sessions
# ============================================================

def get_recent(limit: int = 10) -> Dict[str, Any]:
    """Return the most recent smoking sessions."""

    data = load_data()

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10

    limit = max(1, min(limit, 100))

    sessions = data.get("sessions", [])

    recent = sessions[-limit:]

    return {
        "success": True,
        "count": len(recent),
        "sessions": recent
    }


# ============================================================
# Last Session
# ============================================================

def get_last() -> Dict[str, Any]:
    """Return the most recently logged session."""

    data = load_data()

    sessions = data.get("sessions", [])

    if not sessions:
        return {
            "success": True,
            "last_session": None,
            "message": "No smoking sessions have been logged."
        }

    return {
        "success": True,
        "last_session": sessions[-1]
    }


# ============================================================
# Reset
# ============================================================

def reset_stats() -> Dict[str, Any]:
    """
    Completely reset the smoking tracker.

    This intentionally requires an explicit tool action.
    """

    data = empty_data()
    save_data(data)

    return {
        "success": True,
        "message": "Smoking tracker has been reset.",
        "total_units": 0,
        "total_cigarettes": 0,
        "total_sessions": 0
    }


# ============================================================
# Conversational Tool
# ============================================================

from tools.base import BaseTool, ToolResult

class SmokeCounterTool(BaseTool):
    """
    Conversational smoke counter for CYN Studio.

    This class intentionally does NOT use input() or print().
    CYN can call it directly and receive structured data.
    """

    name = "smoke_counter"

    description = """
    Track smoking sessions and retrieve smoking statistics.

    Actions:

    log:
        Log a smoking session.

        Parameters:
            smoke_type:
                cigarette, weed, vape, etc.

            amount:
                Number of cigarettes or units.

    stats:
        Get overall and today's statistics.

    recent:
        Get recent smoking sessions.

    last:
        Get the most recent smoking session.

    reset:
        Reset the entire smoking tracker.
    """

    def call(self, args=None, action: str = "stats", smoke_type: Optional[str] = None, amount: float = 1, limit: int = 10, scope: str = "all") -> ToolResult:
        """
        Flexible call interface:
        - If args is a dict (tool_router), use it.
        - Otherwise accept keyword args for backward compatibility.
        Returns a ToolResult with a human-readable output and metadata containing the raw result dict.
        """

        # Normalize args
        if isinstance(args, dict):
            req = args.copy()
            req.pop('tool', None)
            action = str(req.get('action', action)).lower().strip()
            smoke_type = req.get('smoke_type', smoke_type)
            amount = req.get('amount', amount)
            limit = req.get('limit', limit)
            scope = str(req.get('scope', scope)).lower()
        else:
            action = str(action).lower().strip()
            scope = str(scope).lower()

        # Call underlying functions and get a structured result
        try:
            if action == "log":
                # If no smoke_type provided, log as unknown per conversational rules
                if not smoke_type:
                    smoke_type = "unknown"
                result = log_smoke(smoke_type=smoke_type, amount=amount)

                if result.get('success'):
                    out = (
                        f"Logged it. That's {result.get('added_units')} units, bringing your total to {result.get('total_units')}."
                    )
                else:
                    out = f"Error logging smoke: {result.get('error', 'Unknown error')}"

                return ToolResult(result.get('success', False), out, metadata=result)

            elif action == "stats":
                smoke_type_value = normalize_smoke_type(smoke_type)
                scope_value = str(scope).lower() if scope else 'all'
                result = get_stats(smoke_type=smoke_type_value, scope=scope_value)
                if result.get('success'):
                    if smoke_type_value:
                        out = (
                            f"{smoke_type_value.title()} total for {scope_value}: {result.get('units')} units across {result.get('sessions')} sessions."
                        )
                    else:
                        out = (
                            f"Total units: {result.get('total_units')}. "
                            f"Total cigarettes: {result.get('total_cigarettes')}. "
                            f"Sessions: {result.get('total_sessions')}. "
                            f"Today: {result.get('today_sessions')} sessions ({result.get('today_units')} units)."
                        )
                else:
                    out = "Statistics not available."
                return ToolResult(result.get('success', False), out, metadata=result)

            elif action == "recent":
                result = get_recent(limit)
                if result.get('success'):
                    sessions = result.get('sessions', [])
                    lines = []
                    for s in sessions:
                        lines.append(f"{s.get('time')} - {s.get('type')} - {s.get('units')} units")
                    out = "Recent sessions:\n" + "\n".join(lines) if lines else "No recent sessions."
                else:
                    out = "Could not retrieve recent sessions."
                return ToolResult(result.get('success', False), out, metadata=result)

            elif action == "last":
                result = get_last()
                if result.get('success'):
                    last = result.get('last_session')
                    if last:
                        out = f"Last session: {last.get('time')} - {last.get('type')} - {last.get('units')} units"
                    else:
                        out = result.get('message', 'No sessions logged yet.')
                else:
                    out = "Could not retrieve last session."
                return ToolResult(result.get('success', False), out, metadata=result)

            elif action == "reset":
                result = reset_stats()
                out = result.get('message', 'Tracker reset.') if result.get('success') else f"Reset failed: {result.get('error', '')}"
                return ToolResult(result.get('success', False), out, metadata=result)

            else:
                return ToolResult(False, f"Unknown action: {action}. Valid actions: log, stats, recent, last, reset.")

        except Exception as e:
            return ToolResult(False, f"SmokeCounter error: {e}")


# ============================================================
# Tool Instance
# ============================================================

smoke_counter = SmokeCounterTool()


# ============================================================
# Optional Direct Python API
# ============================================================

def smoke_counter_call(
    action: str = "stats",
    smoke_type: Optional[str] = None,
    amount: float = 1,
    limit: int = 10,
    scope: str = "all"
) -> Dict[str, Any]:

    """
    Convenience function for CYN's tool registry.
    """

    return smoke_counter.call(
        action=action,
        smoke_type=smoke_type,
        amount=amount,
        limit=limit,
        scope=scope
    )


# ============================================================
# Utilities
# ============================================================

def repair_aggregates() -> Dict[str, Any]:
    """Force-recompute and persist aggregate fields from sessions without changing sessions.

    Returns the reconciled data dict.
    """
    data = load_data()
    save_data(data)
    return data


# ============================================================
# Test / CLI
# ============================================================

if __name__ == "__main__":

    print("CYN Smoke Counter Tool")
    print("======================")

    result = smoke_counter.call(
        action="stats"
    )

    print(json.dumps(
        result,
        indent=4
    ))
