
from __future__ import annotations

from typing import Any

from bleak import BleakScanner


class LeproDiscovery:
    """Find nearby Lepro Bluetooth devices."""

    def __init__(
        self,
        timeout: float = 15.0,
    ):
        self.timeout = timeout

    async def scan(
        self,
    ) -> list[dict[str, Any]]:

        devices = await BleakScanner.discover(
            timeout=self.timeout
        )

        results = []

        for device in devices:

            name = (
                device.name
                or getattr(
                    device,
                    "local_name",
                    None,
                )
            )

            if not name:
                continue

            name_upper = name.upper()

            if (
                name_upper.startswith("LP")
                or "LEPRO" in name_upper
            ):
                results.append(
                    {
                        "name": name,
                        "address": device.address,
                        "rssi": getattr(
                            device,
                            "rssi",
                            None,
                        ),
                    }
                )

        return results


async def discover_devices(
    timeout: float = 15.0,
) -> list[dict[str, Any]]:

    discovery = LeproDiscovery(
        timeout=timeout
    )

    return await discovery.scan()