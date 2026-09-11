"""CYN-X chart/graph tool.

The browser renders the returned structured chart specification.
For smoke_counter charts, SQLite remains the authoritative data source.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from tools.base import BaseTool, ToolResult


DB_FILE = Path(__file__).resolve().parent / "smoking_log.db"


class ChartTool(BaseTool):
    name = "chart"
    description = "Create a chart or graph from CYN-X data."

    def _ensure_db(self):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS smoke_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    smoke_type TEXT NOT NULL,
                    units REAL NOT NULL,
                    cigarettes REAL NOT NULL DEFAULT 0
                )"""
            )
            conn.commit()

    def _smoke_data(self, scope: str = "7d", smoke_type: str | None = None):
        self._ensure_db()
        now = datetime.now()
        if scope == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif scope == "30d":
            start = now - timedelta(days=29)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif scope == "all":
            start = None
        else:
            start = now - timedelta(days=6)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)

        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            if start is None:
                sql = """
                    SELECT substr(timestamp, 1, 10) AS day,
                           smoke_type,
                           SUM(units) AS units,
                           SUM(cigarettes) AS cigarettes
                    FROM smoke_sessions
                    WHERE (? IS NULL OR smoke_type = ?)
                    GROUP BY day, smoke_type
                    ORDER BY day
                """
                rows = conn.execute(sql, (smoke_type, smoke_type)).fetchall()
            else:
                sql = """
                    SELECT substr(timestamp, 1, 10) AS day,
                           smoke_type,
                           SUM(units) AS units,
                           SUM(cigarettes) AS cigarettes
                    FROM smoke_sessions
                    WHERE timestamp >= ?
                      AND (? IS NULL OR smoke_type = ?)
                    GROUP BY day, smoke_type
                    ORDER BY day
                """
                rows = conn.execute(sql, (start.isoformat(timespec="seconds"), smoke_type, smoke_type)).fetchall()

        # Fill missing days so a 7d/30d graph is honest and easy to read.
        if scope == "all":
            days = sorted({r["day"] for r in rows})
        else:
            count = 1 if scope == "today" else (30 if scope == "30d" else 7)
            first = (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=count - 1))
            days = [(first + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(count)]

        totals = {day: 0.0 for day in days}
        for row in rows:
            totals[row["day"]] = totals.get(row["day"], 0.0) + float(row["units"] or 0)

        labels = days
        values = [round(totals.get(day, 0.0), 4) for day in days]
        return labels, values

    def call(self, args: Dict[str, Any]) -> ToolResult:
        args = args or {}
        chart_type = str(args.get("chart_type") or "line").lower()
        if chart_type not in {"line", "bar", "pie", "doughnut"}:
            chart_type = "line"

        source = str(args.get("source") or "data").lower()
        title = str(args.get("title") or "CYN-X Chart")

        if source == "smoke_counter":
            scope = str(args.get("scope") or "7d").lower()
            if scope not in {"today", "7d", "30d", "all"}:
                scope = "7d"
            smoke_type = args.get("smoke_type") or None
            labels, values = self._smoke_data(scope, smoke_type)
            if not title or title == "CYN-X Chart":
                title = "Smoking Activity"

        else:
            labels = args.get("labels") or []
            raw_series = args.get("series") or []
            values = args.get("values") or []
            if not isinstance(labels, list):
                return ToolResult(False, "Chart labels must be an array.")
            if not labels:
                return ToolResult(False, "No chart labels were provided.")

            if raw_series:
                if not isinstance(raw_series, list):
                    return ToolResult(False, "Chart series must be an array.")
                series = []
                for index, item in enumerate(raw_series):
                    if not isinstance(item, dict):
                        continue
                    vals = item.get("values") or []
                    if not isinstance(vals, list):
                        continue
                    try:
                        vals = [float(x) for x in vals[:len(labels)]]
                    except (TypeError, ValueError):
                        return ToolResult(False, "Chart series values must be numeric.")
                    series.append({
                        "name": str(item.get("name") or f"Series {index + 1}"),
                        "values": vals
                    })
                if not series:
                    return ToolResult(False, "No valid chart series were provided.")
            else:
                if not isinstance(values, list) or not values:
                    return ToolResult(False, "Chart data must contain a values array.")
                n = min(len(labels), len(values))
                labels = labels[:n]
                try:
                    values = [float(x) for x in values[:n]]
                except (TypeError, ValueError):
                    return ToolResult(False, "Chart values must be numeric.")
                series = [{"name": "Value", "values": values}]

            labels = [str(x) for x in labels]

        if source == "smoke_counter":
            series = [{
                "name": "Smoking units",
                "values": values
            }]

        chart_spec = {
            "type": "chart",
            "chartType": chart_type,
            "meta": {
                "title": title,
                "description": "Generated from structured CYN-X data.",
                "footer": "Source: SQLite smoke counter" if source == "smoke_counter" else "Source: supplied data"
            },
            "labels": labels,
            "series": series
        }

        return ToolResult(
            True,
            f"Created {chart_type} chart: {title}",
            metadata=chart_spec
        )


chart_tool = ChartTool()
