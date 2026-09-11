"""
CYN Studio - Smoke Counter Tool

Conversational smoking tracker for CYN.

Supported actions:
    log     -> Log a smoking session
    stats   -> Get overall statistics
    recent  -> Get recent sessions
    reset   -> Reset the entire tracker

Data is stored locally in SQLite:
    smoking_log.db

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

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "smoking_log.db")


# ============================================================
# Database
# ============================================================

def get_connection() -> sqlite3.Connection:
    """Open the smoke-counter SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the smoke-session table if it does not already exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS smoke_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                smoke_type TEXT NOT NULL,
                units REAL NOT NULL,
                cigarettes REAL NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()


def _row_to_session(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a SQLite row into the session structure used by CYN."""
    session = {
        "time": row["timestamp"],
        "type": row["smoke_type"],
        "units": row["units"],
    }

    if row["cigarettes"]:
        session["cigarettes"] = row["cigarettes"]

    return session


def migrate_json_once() -> None:
    """
    Migrate the legacy smoking_log.json into SQLite once.

    The JSON file is never used as the active source of truth after migration.
    """
    legacy_file = os.path.join(BASE_DIR, "smoking_log.json")

    if not os.path.exists(legacy_file):
        return

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT COUNT(*) FROM smoke_sessions"
        ).fetchone()[0]

    # Do not import repeatedly.
    if existing > 0:
        return

    try:
        import json

        with open(legacy_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        sessions = data.get("sessions", [])

        with get_connection() as conn:
            for s in sessions:
                amount = float(s.get("amount", s.get("units", 0)) or 0)
                smoke_type = str(
                    s.get("type", "unknown")
                ).lower().strip()

                if smoke_type == "ciggerette":
                    smoke_type = "cigarette"

                timestamp = s.get(
                    "time",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

                if smoke_type == "cigarette":
                    cigarettes = float(
                        s.get("cigarettes", amount) or 0
                    )

                    # Old tracker stored cigarettes as 0.5 units each.
                    units = float(
                        s.get("units", cigarettes * 0.5) or 0
                    )
                else:
                    cigarettes = 0.0
                    units = float(
                        s.get("units", amount) or 0
                    )

                conn.execute(
                    """
                    INSERT INTO smoke_sessions
                    (timestamp, smoke_type, units, cigarettes)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        timestamp,
                        smoke_type or "unknown",
                        units,
                        cigarettes,
                    ),
                )

            conn.commit()

    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        # Never let a damaged legacy JSON file crash CYN.
        return


# Initialize and migrate at module load.
init_db()
migrate_json_once()


# ============================================================
# Core Tracker Functions
# ============================================================

def log_smoke(
    smoke_type: str,
    amount: float = 1
) -> Dict[str, Any]:
    """
    Log a smoking session into SQLite.

    Cigarettes:
        1 cigarette = 0.5 units

    Other types:
        amount = units directly
    """

    smoke_type = str(smoke_type).lower().strip()

    if not smoke_type:
        smoke_type = "unknown"

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

    if smoke_type == "cigarette":
        cigarettes = amount
        units = cigarettes * 0.5
    else:
        cigarettes = 0.0
        units = amount

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO smoke_sessions
                (timestamp, smoke_type, units, cigarettes)
                VALUES (?, ?, ?, ?)
                """,
                (
                    timestamp,
                    smoke_type,
                    units,
                    cigarettes,
                ),
            )

            session_id = cursor.lastrowid
            conn.commit()

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"Database error: {e}"
        }

    session = {
        "time": timestamp,
        "type": smoke_type,
        "units": units,
    }

    if cigarettes:
        session["cigarettes"] = cigarettes

    stats = get_stats()

    result = {
        "success": True,
        "message": "Smoking session logged.",
        "id": session_id,
        "type": smoke_type,
        "amount": amount,
        "added_units": units,
        "time": timestamp,
    }

    for k in (
        "total_units",
        "total_cigarettes",
        "total_sessions",
        "today_sessions",
        "today_units",
        "last_session",
    ):
        result[k] = stats.get(k)

    return result


# ============================================================
# Statistics
# ============================================================

def normalize_smoke_type(
    value: Optional[str]
) -> Optional[str]:
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
        "joints": "joint",
    }

    return aliases.get(v, v)


def get_stats(
    smoke_type: Optional[str] = None,
    scope: str = "all"
) -> Dict[str, Any]:
    """Return smoking statistics directly from SQLite."""

    normalized = normalize_smoke_type(smoke_type)
    scope_value = str(scope).lower() if scope else "all"

    where = []
    params = []

    if normalized:
        where.append("smoke_type = ?")
        params.append(normalized)

    if scope_value == "today":
        where.append("DATE(timestamp) = DATE('now', 'localtime')")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    try:
        with get_connection() as conn:

            row = conn.execute(
                f"""
                SELECT
                    COUNT(*) AS sessions,
                    COALESCE(SUM(units), 0) AS units,
                    COALESCE(SUM(cigarettes), 0) AS cigarettes
                FROM smoke_sessions
                {where_sql}
                """,
                params,
            ).fetchone()

            last_row = conn.execute(
                f"""
                SELECT *
                FROM smoke_sessions
                {where_sql}
                ORDER BY id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()

            if normalized is not None:
                today_params = [normalized]

                today_row = conn.execute(
                    """
                    SELECT
                        COUNT(*) AS sessions,
                        COALESCE(SUM(units), 0) AS units
                    FROM smoke_sessions
                    WHERE smoke_type = ?
                    AND DATE(timestamp) = DATE('now', 'localtime')
                    """,
                    today_params,
                ).fetchone()

                return {
                    "success": True,
                    "scope": scope_value,
                    "smoke_type": normalized,
                    "units": row["units"],
                    "sessions": row["sessions"],
                    "today_sessions": today_row["sessions"],
                    "today_units": today_row["units"],
                    "last_session": (
                        _row_to_session(last_row)
                        if last_row else None
                    ),
                }

            today_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS sessions,
                    COALESCE(SUM(units), 0) AS units
                FROM smoke_sessions
                WHERE DATE(timestamp) = DATE('now', 'localtime')
                """
            ).fetchone()

            total_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS sessions,
                    COALESCE(SUM(units), 0) AS units,
                    COALESCE(SUM(cigarettes), 0) AS cigarettes
                FROM smoke_sessions
                """
            ).fetchone()

            last_total = conn.execute(
                """
                SELECT *
                FROM smoke_sessions
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

            return {
                "success": True,
                "total_units": total_row["units"],
                "total_cigarettes": total_row["cigarettes"],
                "total_sessions": total_row["sessions"],
                "today_sessions": today_row["sessions"],
                "today_units": today_row["units"],
                "last_session": (
                    _row_to_session(last_total)
                    if last_total else None
                ),
                "scope": "all",
                "smoke_type": None,
                "units": total_row["units"],
                "sessions": total_row["sessions"],
            }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"Database error: {e}"
        }


# ============================================================
# Recent Sessions
# ============================================================

def get_recent(limit: int = 10) -> Dict[str, Any]:
    """Return the most recent smoking sessions from SQLite."""

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10

    limit = max(1, min(limit, 100))

    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM smoke_sessions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        # Preserve the old API's oldest -> newest presentation order.
        sessions = [
            _row_to_session(row)
            for row in reversed(rows)
        ]

        return {
            "success": True,
            "count": len(sessions),
            "sessions": sessions,
        }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"Database error: {e}"
        }


# ============================================================
# Last Session
# ============================================================

def get_last() -> Dict[str, Any]:
    """Return the most recently logged session."""

    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM smoke_sessions
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        if not row:
            return {
                "success": True,
                "last_session": None,
                "message": "No smoking sessions have been logged.",
            }

        return {
            "success": True,
            "last_session": _row_to_session(row),
        }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"Database error: {e}"
        }


# ============================================================
# Reset
# ============================================================

def reset_stats() -> Dict[str, Any]:
    """
    Completely reset the smoking tracker.

    This deletes all rows from the SQLite smoke-session table.
    """

    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM smoke_sessions")
            conn.commit()

        return {
            "success": True,
            "message": "Smoking tracker has been reset.",
            "total_units": 0,
            "total_cigarettes": 0,
            "total_sessions": 0,
        }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"Database error: {e}"
        }


# ============================================================
# Utilities
# ============================================================

def repair_aggregates() -> Dict[str, Any]:
    """
    Return current database-derived statistics.

    Kept for compatibility with the old API. SQLite is already
    the source of truth, so no aggregate repair is necessary.
    """
    return get_stats()



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
