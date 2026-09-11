from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .config import LeproConfig
from .devices import LeproDevice
from .discovery import discover_devices


class LeproSetup:
    """Interactive setup process for Lepro devices."""

    def __init__(
        self,
        base_dir: Path | None = None,
    ):
        self.base_dir = Path(
            base_dir
            or Path(__file__).resolve().parent
        )

        self.config = LeproConfig(
            self.base_dir / "devices.json"
        )

    async def run(
        self,
    ) -> dict[str, Any]:

        print()
        print("==============================")
        print("       CYN-X LEPRO SETUP")
        print("==============================")
        print()

        # -----------------------------------------
        # 1. CHECK LIBRARY
        # -----------------------------------------

        print(
            "[1/4] Checking Lepro library..."
        )

        lib_path = (
            self.base_dir
            / "lib"
            / "lepro"
        )

        if not lib_path.exists():

            return self.fail(
                "library",
                f"Library not found: {lib_path}",
            )

        print("      OK")

        # -----------------------------------------
        # 2. DISCOVER
        # -----------------------------------------

        print()
        print(
            "[2/4] Searching for Lepro devices..."
        )
        print(
            "      Make sure your light is powered on."
        )
        print()

        try:

            devices = await discover_devices()

        except Exception as exc:

            return self.fail(
                "discovery",
                str(exc),
            )

        if not devices:

            return self.fail(
                "discovery",
                "No Lepro Bluetooth devices found.",
            )

        print("Found:")
        print()

        for number, device in enumerate(
            devices,
            start=1,
        ):

            name = device.get(
                "name",
                "Unknown",
            )

            address = device.get(
                "address",
                "Unknown",
            )

            rssi = device.get("rssi")

            if rssi is not None:

                print(
                    f"  [{number}] "
                    f"{name} "
                    f"({address}) "
                    f"RSSI={rssi}"
                )

            else:

                print(
                    f"  [{number}] "
                    f"{name} "
                    f"({address})"
                )

        # -----------------------------------------
        # SELECT DEVICE
        # -----------------------------------------

        while True:

            choice = input(
                "\nSelect your light: "
            ).strip()

            try:

                index = int(choice) - 1

                if index < 0:
                    raise IndexError

                selected = devices[index]

                break

            except (
                ValueError,
                IndexError,
            ):

                print(
                    "Please enter a valid device number."
                )

        mac = str(
            selected["address"]
        )

        discovered_name = str(
            selected.get(
                "name",
                "Lepro Light",
            )
        )

        # -----------------------------------------
        # NAME
        # -----------------------------------------

        print()

        name = input(
            f"Name this device "
            f"[{discovered_name}]: "
        ).strip()

        if not name:
            name = discovered_name

        # -----------------------------------------
        # BOND
        # -----------------------------------------

        print()
        print(
            "[3/4] Bonding with device..."
        )

        device = LeproDevice(
            name=name,
            mac=mac,
        )

        try:

            await device.bond(
                force=False
            )

        except Exception as exc:

            return self.fail(
                "bond",
                str(exc),
            )

        print(
            "      Bond successful."
        )

        # -----------------------------------------
        # SAVE CYN-X DEVICE
        # -----------------------------------------

        print()
        print(
            "[4/4] Saving device..."
        )

        saved = self.config.add_device(
            name=name,
            mac=device.mac,
            discovered_name=discovered_name,
        )

        print(
            "      Device saved."
        )

        print()
        print("==============================")
        print("        SETUP COMPLETE")
        print("==============================")
        print()
        print(
            f"Name: {name}"
        )
        print(
            f"MAC:  {device.mac}"
        )
        print()

        return {
            "success": True,
            "stage": "complete",
            "device": saved,
        }

    @staticmethod
    def fail(
        stage: str,
        message: str,
    ) -> dict[str, Any]:

        print()
        print(
            "=============================="
        )
        print("        SETUP FAILED")
        print(
            "=============================="
        )
        print()

        print(
            f"Stage: {stage}"
        )

        print(
            f"Error: {message}"
        )

        return {
            "success": False,
            "stage": stage,
            "message": message,
        }


def main() -> None:

    result = asyncio.run(
        LeproSetup().run()
    )

    raise SystemExit(
        0 if result["success"] else 1
    )


if __name__ == "__main__":
    main()