from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LeproConfig:
    """Stores Lepro devices configured for CYN-X."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"devices": {}}

        try:
            data = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return {"devices": {}}

        if not isinstance(data, dict):
            return {"devices": {}}

        data.setdefault("devices", {})
        return data

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.path.write_text(
            json.dumps(data, indent=2) + "\n",
            encoding="utf-8",
        )

    def add_device(
        self,
        name: str,
        mac: str,
        device_type: str = "lepro",
        discovered_name: str | None = None,
    ) -> dict[str, Any]:

        data = self.load()

        device = {
            "name": name,
            "mac": mac,
            "type": device_type,
            "configured": True,
        }

        if discovered_name:
            device["discovered_name"] = discovered_name

        data["devices"][name] = device

        self.save(data)

        return device

    def get_device(
        self,
        name: str,
    ) -> dict[str, Any] | None:

        return self.load()["devices"].get(name)

    def list_devices(self) -> list[dict[str, Any]]:
        return list(
            self.load()["devices"].values()
        )