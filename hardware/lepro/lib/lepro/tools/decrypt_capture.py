#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pycryptodome"]
# ///
"""
Decrypt encrypted packets in captures.log.

Lepro uses two AES keys per BLE session:
  - 0x1000 search hello: MAC-derived key + SEARCH_IV
  - everything else (0x1008, 0x1100, …): session key + MAIN_IV

Session key = MAC key with bytes [3:7] replaced by rand() from bleInit.
That rand is leaked in the search-hello plaintext as ctx1 (2nd uint32).

Usage:
  uv run python tools/decrypt_capture.py
  uv run python tools/decrypt_capture.py --mac 10:20:BA:31:B2:BA --session 19:17
  uv run python tools/decrypt_capture.py --opcode 0x1008
"""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

from lepro.crypto import decrypt_cbc, decrypt_search_hello, derive_session_key
from lepro.protocol import OP_SEARCH, parse_packet, verify_packet

LOG_RE = re.compile(r"\[(\d+:\d+:\d+\.\d+)\] (\S+)\s+hex=([0-9a-f]+)")

DECRYPT_OPCODES = frozenset({
    0x1001, 0x1003, 0x1005, 0x1007, 0x1008, 0x1009, 0x100B,
    0x1011, 0x1013, 0x1051, 0x1100, 0x1103, 0x2000, 0x2100,
})


def _format_plaintext(opcode: int, plain: bytes) -> str:
    text = plain.rstrip(b"\x00")
    if opcode == 0x1008:
        try:
            return json.dumps(json.loads(text.decode()), indent=2)
        except json.JSONDecodeError:
            pass
    if opcode in (0x1100, 0x1103, 0x2000, 0x2100, 0x1001):
        try:
            return text.decode("utf-8")
        except UnicodeDecodeError:
            pass
    if opcode in (0x1009, 0x100B, 0x1003) and len(text) >= 4:
        return f"result={struct.unpack('<I', text[:4])[0]} raw={text.hex()}"
    return text.hex()


def decrypt_log(
    path: Path,
    mac: str,
    *,
    session_filter: str | None = None,
    opcode_filter: int | None = None,
) -> None:
    lines = path.read_text().splitlines()
    session_rand: int | None = None
    session_label = ""

    for line in lines:
        m = LOG_RE.match(line.strip())
        if not m:
            continue
        ts, direction, hexdata = m.groups()
        raw = bytes.fromhex(hexdata)
        if len(raw) < 10 or not verify_packet(raw):
            continue

        hdr = parse_packet(raw)
        if hdr is None:
            continue

        if hdr.opcode == OP_SEARCH and direction == "PHONE→LIGHT" and len(hdr.payload) == 32:
            _, _, session_rand, _ = decrypt_search_hello(hdr.payload, mac)
            session_label = ts[:8]
            print(f"\n{'='*72}\nSESSION {session_label}  session_rand={session_rand:#010x}\n{'='*72}")
            continue

        if session_rand is None:
            continue
        if session_filter and session_filter not in session_label:
            continue
        if hdr.opcode not in DECRYPT_OPCODES:
            continue
        if opcode_filter is not None and hdr.opcode != opcode_filter:
            continue
        if not hdr.payload or len(hdr.payload) % 16:
            continue

        try:
            plain = decrypt_cbc(hdr.payload, derive_session_key(mac, session_rand))
        except ValueError:
            continue

        print(f"[{ts}] {direction} {hdr.opcode:#06x} ({len(hdr.payload)}B)")
        print(_format_plaintext(hdr.opcode, plain))
        print()


def main() -> None:
    p = argparse.ArgumentParser(description="Decrypt captures.log encrypted BLE payloads")
    p.add_argument("--file", type=Path, default=Path("captures.log"))
    p.add_argument("--mac", default="10:20:BA:31:B2:BA")
    p.add_argument("--session", help="Filter to session time prefix, e.g. 19:17")
    p.add_argument("--opcode", type=lambda x: int(x, 0), help="Filter to one opcode, e.g. 0x1008")
    args = p.parse_args()
    decrypt_log(args.file, args.mac, session_filter=args.session, opcode_filter=args.opcode)


if __name__ == "__main__":
    main()
