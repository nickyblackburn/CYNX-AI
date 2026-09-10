#!/usr/bin/env python3
"""Query Lepro ZB1 datapoint state over BLE."""

from __future__ import annotations

import argparse
import asyncio

from lepro.bond import normalize_mac
from lepro.cli._common import run_status


def main() -> None:
    p = argparse.ArgumentParser(description="Query Lepro ZB1 state over BLE")
    p.add_argument("--mac", required=True, help="Target light MAC address")
    p.add_argument("--dry-run", action="store_true", help="Print TX hex without BLE")
    p.add_argument("--debug-rx", action="store_true")
    args = p.parse_args()
    asyncio.run(
        run_status(
            normalize_mac(args.mac),
            dry_run=args.dry_run,
            debug_rx=args.debug_rx,
        )
    )


if __name__ == "__main__":
    main()
