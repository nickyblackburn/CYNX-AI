#!/usr/bin/env python3
"""Bond a Lepro ZB1 light and save credentials to ~/.lepro/."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from lepro.bond import (
    BondHarvestError,
    creds_path,
    export_provision_header,
    export_provision_nvs,
    load_creds,
    normalize_mac,
)
from lepro.cli._common import connect_transport
from lepro.crypto import encrypt_search_hello
from lepro.protocol import OP_SEARCH, build_packet_opcode
from lepro.session import DryRunTransport, LeproSession, SessionConfig, bond_device


async def _cmd_bond(args: argparse.Namespace) -> None:
    mac = normalize_mac(args.mac)
    if args.probe:
        transport = DryRunTransport()
        session = LeproSession(mac, transport, config=SessionConfig(dry_run=True, send_delay=0))
        hello = encrypt_search_hello(mac)
        await transport.send(build_packet_opcode(0, OP_SEARCH, hello), "searchDeviceInfo")
        print("Probe dry-run: discovery TX only")
        for label, pkt in transport.sent:
            print(f"  {label}: {pkt.hex()}")
        return

    transport, client = await connect_transport(
        mac, debug_rx=args.debug_rx, scan_timeout=args.scan_timeout
    )
    session: LeproSession | None = None
    try:
        session = LeproSession(mac, transport)
        if args.force_bond:
            await bond_device(session, mac, force=True)
        else:
            existing = load_creds(mac)
            if existing:
                print(f"Credentials already exist: {creds_path(mac)}")
                return
            await bond_device(session, mac, force=True)
        print(f"Bond saved: {creds_path(mac)}")
    except BondHarvestError as e:
        print(f"Bond harvest failed: {e}", file=sys.stderr)
        if args.debug_rx and session is not None:
            print(
                f"Captured {len(session._rx_raw)} RX packets — inspect for token blobs",
                file=sys.stderr,
            )
        raise SystemExit(1) from e
    finally:
        await client.disconnect()


def _cmd_export(args: argparse.Namespace) -> None:
    from lepro.bond import load_creds

    mac = normalize_mac(args.mac)
    creds = load_creds(mac)
    if creds is None:
        raise SystemExit(f"No credentials at {creds_path(mac)}")

    if args.format == "header":
        content = export_provision_header(creds)
        default_name = "lepro_creds.h"
    else:
        content = export_provision_nvs(creds)
        default_name = "lepro_creds.csv"

    out = args.output or Path("esp32/include") / default_name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)
    print(f"Wrote {out}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Bond a Lepro ZB1 string light (saves tokens to ~/.lepro/)"
    )
    p.add_argument("--mac", required=True, help="Target light MAC address")
    p.add_argument("--force-bond", action="store_true", help="Re-bond even if creds exist")
    p.add_argument("--debug-rx", action="store_true", help="Log all light notifications")
    p.add_argument("--probe", action="store_true", help="Discovery only, no bond TX")
    p.add_argument("--scan-timeout", type=float, default=15.0)
    p.add_argument(
        "--export-provision",
        action="store_true",
        help="After bond (or with existing creds), export ESP32 provision file",
    )
    p.add_argument("--format", choices=("header", "nvs"), default="header")
    p.add_argument("--output", "-o", type=Path, help="Export output path")
    args = p.parse_args()

    if args.export_provision:
        creds = load_creds(normalize_mac(args.mac))
        if creds is None:
            asyncio.run(_cmd_bond(args))
        _cmd_export(args)
        return

    asyncio.run(_cmd_bond(args))


if __name__ == "__main__":
    main()
