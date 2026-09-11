
from __future__ import annotations

from typing import Any

from hardware.lepro.devices import LeproDevice

from .base import BaseTool, ToolResult


class LeproLightsTool(BaseTool):
    """CYN-X tool for controlling Lepro lights."""

    name = "lepro_lights"
    description = (
        "Control a bonded Lepro light device connected to CYN-X "
        "over Bluetooth."
    )

    def __init__(
        self,
        device_name: str,
        mac: str,
    ):
        self.device = LeproDevice(
            name=device_name,
            mac=mac,
        )

    def schema(self) -> dict[str, Any]:
        """Return the tool schema exposed to CYN."""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "on",
                                "off",
                                "color",
                            ],
                            "description": (
                                "The light action to perform."
                            ),
                        },
                        "brightness": {
                            "type": "integer",
                            "minimum": 10,
                            "maximum": 1000,
                            "description": (
                                "Brightness from 10 to 1000."
                            ),
                        },
                        "red": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 255,
                            "description": "Red value from 0 to 255.",
                        },
                        "green": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 255,
                            "description": "Green value from 0 to 255.",
                        },
                        "blue": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 255,
                            "description": "Blue value from 0 to 255.",
                        },
                    },
                    "required": [
                        "action",
                    ],
                },
            },
        }

    async def execute(
        self,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute a light-control request."""

        action = arguments.get("action")

        try:
            if action == "on":
                brightness = int(
                    arguments.get("brightness", 1000)
                )

                await self.device.turn_on(
                    brightness=brightness
                )

                return ToolResult(
                    success=True,
                    data={
                        "action": "on",
                        "brightness": brightness,
                    },
                )

            if action == "off":
                await self.device.turn_off()

                return ToolResult(
                    success=True,
                    data={
                        "action": "off",
                    },
                )

            if action == "color":
                if not all(
                    key in arguments
                    for key in (
                        "red",
                        "green",
                        "blue",
                    )
                ):
                    return ToolResult(
                        success=False,
                        error=(
                            "Color requires red, green, "
                            "and blue values."
                        ),
                    )

                red = int(arguments["red"])
                green = int(arguments["green"])
                blue = int(arguments["blue"])

                brightness = int(
                    arguments.get("brightness", 1000)
                )

                await self.device.set_color_rgb(
                    red=red,
                    green=green,
                    blue=blue,
                    brightness=brightness,
                )

                return ToolResult(
                    success=True,
                    data={
                        "action": "color",
                        "red": red,
                        "green": green,
                        "blue": blue,
                        "brightness": brightness,
                    },
                )

            return ToolResult(
                success=False,
                error=f"Unknown light action: {action}",
            )

        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
            )
