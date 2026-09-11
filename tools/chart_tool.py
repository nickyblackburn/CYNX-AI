"""
CYN-X Chart Tool
================

Creates structured chart specifications for the CYN-X frontend.

This tool does NOT:
    - query databases
    - own application data
    - render HTML
    - render React
    - render images

Other tools remain responsible for retrieving authoritative data.

Example flow:

    SmokeCounterTool
            ↓
       structured data
            ↓
         ChartTool
            ↓
      chart specification
            ↓
        ChatEngine
            ↓
        Frontend/UI
            ↓
          chart
"""

from __future__ import annotations

from typing import Any, Dict, List

from tools.base import BaseTool, ToolResult


class ChartTool(BaseTool):
    """
    General-purpose CYN-X visualization tool.

    The output is a structured object intended for the frontend.
    """

    name = "chart"

    description = (
        "Create charts from structured data. Supports bar, line, pie, "
        "and scatter charts for trends, comparisons, proportions, "
        "rankings, and numeric relationships."
    )

    SUPPORTED_CHART_TYPES = {
        "bar",
        "line",
        "pie",
        "scatter",
    }

    SUPPORTED_VALUE_FORMATS = {
        "compact",
        "integer",
        "raw",
    }

    def call(self, args: Dict[str, Any]) -> ToolResult:
        """
        Main BaseTool entry point.

        ToolRouter calls:

            tool.call(args)

        and expects a ToolResult.
        """

        try:
            if not isinstance(args, dict):
                return ToolResult(
                    False,
                    "Chart tool arguments must be an object."
                )

            chart_type = args.get("chart_type")
            title = args.get("title")
            data = args.get("data")

            if not chart_type:
                return ToolResult(
                    False,
                    "Chart type is required."
                )

            if not title:
                return ToolResult(
                    False,
                    "Chart title is required."
                )

            if data is None:
                return ToolResult(
                    False,
                    "Chart data is required."
                )

            chart = self.create_chart(
                chart_type=chart_type,
                title=title,
                data=data,
                x_key=args.get("x_key"),
                series=args.get("series"),
                description=args.get("description"),
                footer=args.get("footer"),
                x_axis_label=args.get("x_axis_label"),
                x_axis_scale=args.get("x_axis_scale"),
                y_axis_min=args.get("y_axis_min"),
                y_axis_max=args.get("y_axis_max"),
                layout=args.get("layout"),
                name_key=args.get("name_key"),
                value_key=args.get("value_key"),
            )

            return ToolResult(
                True,
                self._format_output(chart),
            )

        except Exception as exc:
            return ToolResult(
                False,
                f"Chart tool error: {exc}",
            )

    # ================================================================
    # MAIN CHART CREATOR
    # ================================================================

    def create_chart(
        self,
        chart_type: str,
        title: str,
        data: List[Dict[str, Any]],
        x_key: str | None = None,
        series: List[Dict[str, Any]] | None = None,
        description: str | None = None,
        footer: str | None = None,
        x_axis_label: str | None = None,
        x_axis_scale: str | None = None,
        y_axis_min: float | None = None,
        y_axis_max: float | None = None,
        layout: str | None = None,
        name_key: str | None = None,
        value_key: str | None = None,
    ) -> Dict[str, Any]:
        """
        Create one complete chart specification.
        """

        chart_type = self._normalize_chart_type(chart_type)

        self._validate_chart_type(chart_type)
        self._validate_title(title)
        self._validate_data(data)

        normalized_series = self._normalize_series(
            series or []
        )

        # ------------------------------------------------------------
        # Validate chart-specific requirements
        # ------------------------------------------------------------

        if chart_type in {
            "bar",
            "line",
            "scatter",
        }:
            self._validate_cartesian_chart(
                chart_type=chart_type,
                data=data,
                x_key=x_key,
                series=normalized_series,
            )

        elif chart_type == "pie":
            self._validate_pie_chart(
                data=data,
                name_key=name_key,
                value_key=value_key,
            )

        if x_axis_scale is not None:
            self._validate_x_axis_scale(
                chart_type=chart_type,
                x_axis_scale=x_axis_scale,
                data=data,
                x_key=x_key,
            )

        if layout is not None:
            self._validate_layout(layout)

        if (
            y_axis_min is not None
            or y_axis_max is not None
        ):
            self._validate_y_axis(
                y_axis_min=y_axis_min,
                y_axis_max=y_axis_max,
            )

        # ------------------------------------------------------------
        # Build the chart object
        # ------------------------------------------------------------

        chart: Dict[str, Any] = {
            "type": "chart",
            "chartType": chart_type,
            "meta": {
                "title": str(title).strip(),
            },
        }

        if description:
            chart["meta"]["description"] = str(
                description
            ).strip()

        if footer:
            chart["meta"]["footer"] = str(
                footer
            ).strip()

        # ------------------------------------------------------------
        # Cartesian chart configuration
        # ------------------------------------------------------------

        if chart_type in {
            "bar",
            "line",
            "scatter",
        }:
            chart["xKey"] = x_key
            chart["series"] = normalized_series

            if x_axis_scale is not None:
                chart["xAxisScale"] = x_axis_scale

            if x_axis_label:
                chart["xAxisLabel"] = str(
                    x_axis_label
                ).strip()

            if y_axis_min is not None:
                chart["yAxisMin"] = y_axis_min

            if y_axis_max is not None:
                chart["yAxisMax"] = y_axis_max

            if layout is not None:
                chart["layout"] = layout

        # ------------------------------------------------------------
        # Pie chart configuration
        # ------------------------------------------------------------

        elif chart_type == "pie":
            chart["nameKey"] = name_key
            chart["valueKey"] = value_key

            # Series is useful for value formatting.
            if normalized_series:
                chart["series"] = normalized_series

        # ------------------------------------------------------------
        # Data intentionally comes last.
        #
        # This keeps the structure easy for the frontend to consume.
        # ------------------------------------------------------------

        chart["data"] = data

        return chart

    # ================================================================
    # CONVENIENCE METHODS
    # ================================================================

    def bar(
        self,
        title: str,
        data: List[Dict[str, Any]],
        x_key: str,
        series: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:

        return self.create_chart(
            chart_type="bar",
            title=title,
            data=data,
            x_key=x_key,
            series=series,
            **kwargs,
        )

    def line(
        self,
        title: str,
        data: List[Dict[str, Any]],
        x_key: str,
        series: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:

        return self.create_chart(
            chart_type="line",
            title=title,
            data=data,
            x_key=x_key,
            series=series,
            **kwargs,
        )

    def pie(
        self,
        title: str,
        data: List[Dict[str, Any]],
        name_key: str,
        value_key: str,
        series: List[Dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        return self.create_chart(
            chart_type="pie",
            title=title,
            data=data,
            name_key=name_key,
            value_key=value_key,
            series=series or [],
            **kwargs,
        )

    def scatter(
        self,
        title: str,
        data: List[Dict[str, Any]],
        x_key: str,
        series: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Dict[str, Any]:

        return self.create_chart(
            chart_type="scatter",
            title=title,
            data=data,
            x_key=x_key,
            series=series,
            **kwargs,
        )

    # ================================================================
    # SERIES BUILDER
    # ================================================================

    @staticmethod
    def make_series(
        data_key: str,
        label: str | None = None,
        axis_label: str | None = None,
        value_format: str | None = None,
        value_prefix: str | None = None,
        value_suffix: str | None = None,
        stack: str | None = None,
    ) -> Dict[str, Any]:
        """
        Build a series definition.

        Example:

            ChartTool.make_series(
                data_key="cigarettes",
                label="Cigarettes",
                axis_label="Cigarettes",
                value_format="integer",
            )
        """

        if not isinstance(data_key, str):
            raise ValueError(
                "data_key must be a string."
            )

        if not data_key.strip():
            raise ValueError(
                "data_key cannot be empty."
            )

        result: Dict[str, Any] = {
            "dataKey": data_key,
        }

        if label is not None:
            result["label"] = label

        if axis_label is not None:
            result["axisLabel"] = axis_label

        if value_format is not None:
            if value_format not in ChartTool.SUPPORTED_VALUE_FORMATS:
                raise ValueError(
                    "Unsupported value format: "
                    f"{value_format}"
                )

            result["valueFormat"] = value_format

        if value_prefix is not None:
            result["valuePrefix"] = value_prefix

        if value_suffix is not None:
            result["valueSuffix"] = value_suffix

        if stack is not None:
            if not isinstance(stack, str):
                raise ValueError(
                    "stack must be a string."
                )

            if not stack.strip():
                raise ValueError(
                    "stack cannot be empty."
                )

            result["stack"] = stack

        return result

    # ================================================================
    # NORMALIZATION
    # ================================================================

    @staticmethod
    def _normalize_chart_type(
        chart_type: str,
    ) -> str:

        if not isinstance(chart_type, str):
            raise ValueError(
                "chart_type must be a string."
            )

        return chart_type.strip().lower()

    @classmethod
    def _normalize_series(
        cls,
        series: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        if not isinstance(series, list):
            raise ValueError(
                "series must be a list."
            )

        normalized: List[Dict[str, Any]] = []

        for index, item in enumerate(series):

            if not isinstance(item, dict):
                raise ValueError(
                    f"Series entry {index} must be an object."
                )

            data_key = item.get("dataKey")

            # Also accept snake_case from Ollama.
            if data_key is None:
                data_key = item.get("data_key")

            if not isinstance(data_key, str):
                raise ValueError(
                    f"Series entry {index} requires dataKey."
                )

            if not data_key.strip():
                raise ValueError(
                    f"Series entry {index} has an empty dataKey."
                )

            clean: Dict[str, Any] = {
                "dataKey": data_key,
            }

            # --------------------------------------------------------
            # Accept both camelCase and snake_case.
            # --------------------------------------------------------

            aliases = {
                "label": "label",
                "axisLabel": "axis_label",
                "axis_label": "axis_label",
                "valueFormat": "value_format",
                "value_format": "value_format",
                "valuePrefix": "value_prefix",
                "value_prefix": "value_prefix",
                "valueSuffix": "value_suffix",
                "value_suffix": "value_suffix",
                "stack": "stack",
            }

            for source_key, normalized_key in aliases.items():

                if source_key not in item:
                    continue

                value = item[source_key]

                if value is None:
                    continue

                output_key = {
                    "label": "label",
                    "axis_label": "axisLabel",
                    "value_format": "valueFormat",
                    "value_prefix": "valuePrefix",
                    "value_suffix": "valueSuffix",
                    "stack": "stack",
                }[normalized_key]

                clean[output_key] = value

            if "valueFormat" in clean:
                if (
                    clean["valueFormat"]
                    not in cls.SUPPORTED_VALUE_FORMATS
                ):
                    raise ValueError(
                        "Unsupported value format: "
                        f"{clean['valueFormat']}"
                    )

            normalized.append(clean)

        return normalized

    # ================================================================
    # VALIDATION
    # ================================================================

    def _validate_chart_type(
        self,
        chart_type: str,
    ) -> None:

        if chart_type not in self.SUPPORTED_CHART_TYPES:
            supported = ", ".join(
                sorted(self.SUPPORTED_CHART_TYPES)
            )

            raise ValueError(
                f"Unsupported chart type '{chart_type}'. "
                f"Supported types: {supported}"
            )

    @staticmethod
    def _validate_title(
        title: str,
    ) -> None:

        if not isinstance(title, str):
            raise ValueError(
                "Chart title must be a string."
            )

        if not title.strip():
            raise ValueError(
                "Chart title cannot be empty."
            )

    @staticmethod
    def _validate_data(
        data: List[Dict[str, Any]],
    ) -> None:

        if not isinstance(data, list):
            raise ValueError(
                "Chart data must be a list."
            )

        if not data:
            raise ValueError(
                "Chart data cannot be empty."
            )

        for index, row in enumerate(data):

            if not isinstance(row, dict):
                raise ValueError(
                    f"Chart data row {index} must be an object."
                )

    @staticmethod
    def _validate_cartesian_chart(
        chart_type: str,
        data: List[Dict[str, Any]],
        x_key: str | None,
        series: List[Dict[str, Any]],
    ) -> None:

        if not isinstance(x_key, str):
            raise ValueError(
                f"{chart_type} charts require x_key."
            )

        if not x_key.strip():
            raise ValueError(
                f"{chart_type} charts require x_key."
            )

        if not series:
            raise ValueError(
                f"{chart_type} charts require at least "
                "one series."
            )

        for series_item in series:

            data_key = series_item["dataKey"]

            if data_key == x_key:
                raise ValueError(
                    "Series dataKey cannot be the same as xKey."
                )

            for row_index, row in enumerate(data):

                if data_key not in row:
                    raise ValueError(
                        f"Data row {row_index} is missing "
                        f"series key '{data_key}'."
                    )

    @staticmethod
    def _validate_pie_chart(
        data: List[Dict[str, Any]],
        name_key: str | None,
        value_key: str | None,
    ) -> None:

        if not isinstance(name_key, str):
            raise ValueError(
                "Pie charts require name_key."
            )

        if not isinstance(value_key, str):
            raise ValueError(
                "Pie charts require value_key."
            )

        if not name_key.strip():
            raise ValueError(
                "Pie charts require name_key."
            )

        if not value_key.strip():
            raise ValueError(
                "Pie charts require value_key."
            )

        if name_key == value_key:
            raise ValueError(
                "Pie chart name_key and value_key "
                "must be different."
            )

        for index, row in enumerate(data):

            if name_key not in row:
                raise ValueError(
                    f"Pie data row {index} is missing "
                    f"name key '{name_key}'."
                )

            if value_key not in row:
                raise ValueError(
                    f"Pie data row {index} is missing "
                    f"value key '{value_key}'."
                )

            value = row[value_key]

            if not isinstance(
                value,
                (int, float),
            ):
                raise ValueError(
                    f"Pie value at row {index} must be numeric."
                )

    @staticmethod
    def _validate_x_axis_scale(
        chart_type: str,
        x_axis_scale: str,
        data: List[Dict[str, Any]],
        x_key: str | None,
    ) -> None:

        if x_axis_scale != "linear":
            raise ValueError(
                "x_axis_scale must be 'linear'."
            )

        if chart_type != "line":
            raise ValueError(
                "x_axis_scale='linear' is only supported "
                "for line charts."
            )

        if not x_key:
            raise ValueError(
                "x_key is required for a linear x-axis."
            )

        for index, row in enumerate(data):

            value = row.get(x_key)

            if not isinstance(
                value,
                (int, float),
            ):
                raise ValueError(
                    "Linear x-axis values must be numeric. "
                    f"Row {index} contains {value!r}."
                )

    @staticmethod
    def _validate_layout(
        layout: str,
    ) -> None:

        if layout != "vertical":
            raise ValueError(
                "layout must be 'vertical'."
            )

    @staticmethod
    def _validate_y_axis(
        y_axis_min: float | None,
        y_axis_max: float | None,
    ) -> None:

        if y_axis_min is not None:

            if not isinstance(
                y_axis_min,
                (int, float),
            ):
                raise ValueError(
                    "y_axis_min must be numeric."
                )

        if y_axis_max is not None:

            if not isinstance(
                y_axis_max,
                (int, float),
            ):
                raise ValueError(
                    "y_axis_max must be numeric."
                )

        if (
            y_axis_min is not None
            and y_axis_max is not None
        ):
            if y_axis_min >= y_axis_max:
                raise ValueError(
                    "y_axis_min must be less than "
                    "y_axis_max."
                )

    # ================================================================
    # OUTPUT
    # ================================================================

    @staticmethod
    def _format_output(
        chart: Dict[str, Any],
    ) -> str:
        """
        Serialize the chart specification for ToolResult.output.

        ChatEngine can then parse/recognize the structured chart
        object rather than treating it as ordinary prose.
        """

        import json

        return json.dumps(
            chart,
            ensure_ascii=False,
            separators=(",", ":"),
        )


# ====================================================================
# STANDALONE TEST
# ====================================================================

if __name__ == "__main__":

    import json

    tool = ChartTool()

    chart = tool.create_chart(
        chart_type="line",
        title="Smoking This Week",
        description=(
            "Daily cigarette count recorded by CYN-X."
        ),
        x_key="day",
        series=[
            ChartTool.make_series(
                data_key="cigarettes",
                label="Cigarettes",
                axis_label="Cigarettes",
                value_format="integer",
            )
        ],
        data=[
            {
                "day": "Mon",
                "cigarettes": 3,
            },
            {
                "day": "Tue",
                "cigarettes": 5,
            },
            {
                "day": "Wed",
                "cigarettes": 2,
            },
            {
                "day": "Thu",
                "cigarettes": 7,
            },
        ],
    )

    print(
        json.dumps(
            chart,
            indent=2,
            ensure_ascii=False,
        )
    )