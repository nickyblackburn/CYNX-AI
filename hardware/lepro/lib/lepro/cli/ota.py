#!/usr/bin/env python3
"""BLE firmware OTA for Lepro ZB1 (opcodes 0x1010 / 0x1012)."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from lepro.ota import DEFAULT_FIRMWARE, POST_REBOOT_RETRY_S, POST_REBOOT_WAIT_S, run_ota


def main() -> None:
    p = argparse.ArgumentParser(description="Lepro ZB1 BLE firmware OTA")
    p.add_argument("--mac", required=True, help="Target light MAC")
    p.add_argument(
        "--firmware",
        type=Path,
        default=DEFAULT_FIRMWARE,
        help=f"ESP-IDF image (default: {DEFAULT_FIRMWARE})",
    )
    p.add_argument("--chunk-size", type=int, default=4096)
    p.add_argument("--ota-json", type=Path, help="Override OTA start JSON file")
    p.add_argument("--ota-version", help="version in start JSON")
    p.add_argument("--ota-path-version", help="Version in path filename")
    p.add_argument(
        "--reflash",
        action="store_true",
        help=(
            "Opt-in: bump patch version (e.g. for cloud/do_check:1 flashing). "
            "Not needed for the default BLE do_check:0 path"
        ),
    )
    p.add_argument("--ota-secret", default="")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--quiet", "-q", action="store_true")
    p.add_argument("--debug-tx", action="store_true")
    p.add_argument("--debug-rx", action="store_true")
    p.add_argument("--scan-timeout", type=float, default=15.0)
    p.add_argument("--confirm-wait", type=float, default=POST_REBOOT_WAIT_S)
    p.add_argument("--confirm-retry", type=float, default=POST_REBOOT_RETRY_S)
    asyncio.run(run_ota(p.parse_args()))


if __name__ == "__main__":
    main()
