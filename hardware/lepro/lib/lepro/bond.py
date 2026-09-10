#!/usr/bin/env python3
"""
Bond credentials: persist long-lived tokens to ~/.lepro/<mac>.json.

Tokens are device-specific opaque blobs (16–32 B) sent raw on 0x1102.
Native requestBond only returns a uint32 result; harvest heuristics scan
RX during bond (cert blob, device info, any notify payloads).

Usage:
  lepro-bond --mac 10:20:BA:31:B2:BA
  lepro-bond --mac 10:20:BA:31:B2:BA --force-bond --debug-rx
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lepro.apk_analysis import TOKEN_FIELDS
from lepro.crypto import derive_aes_key
from lepro.frame import DecryptedFrame, parse_bond_result
from lepro.protocol import (
    CMD_AUTH_16,
    CMD_AUTH_32,
    CMD_CTRL_C,
    CMD_CTRL_D,
    LIGHT_ACK,
    OP_BOND_RESP,
)

BOND_SUCCESS = 0
BOND_SUCCESS_PAIRED = 7  # factory-reset bond complete (observed on live device)
BOND_ERR_INVALID = 3
BOND_ERR_ALREADY = 10
LEPRO_DIR = Path.home() / ".lepro"


@dataclass
class BondTokens:
    hs: bytes
    auth_16: bytes
    auth_32: bytes
    ctrl_c: bytes
    ctrl_d: bytes

    def validate(self) -> None:
        expected = {"hs": 16, "auth_16": 16, "auth_32": 32, "ctrl_c": 16, "ctrl_d": 16}
        for name, size in expected.items():
            blob = getattr(self, name)
            if len(blob) != size:
                raise ValueError(f"token {name}: expected {size}B, got {len(blob)}B")

    def to_dict(self) -> dict[str, str]:
        return {k: getattr(self, k).hex() for k in TOKEN_FIELDS}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> BondTokens:
        return cls(
            hs=bytes.fromhex(d["hs"]),
            auth_16=bytes.fromhex(d["auth_16"]),
            auth_32=bytes.fromhex(d["auth_32"]),
            ctrl_c=bytes.fromhex(d["ctrl_c"]),
            ctrl_d=bytes.fromhex(d["ctrl_d"]),
        )


@dataclass
class BondCredentials:
    mac: str
    tokens: BondTokens
    bonded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    aes_key: str | None = None

    def __post_init__(self) -> None:
        self.tokens.validate()
        if self.aes_key is None:
            self.aes_key = derive_aes_key(self.mac).hex()

    def to_json_dict(self) -> dict:
        return {
            "mac": self.mac,
            "aes_key": self.aes_key,
            "bonded_at": self.bonded_at,
            "tokens": self.tokens.to_dict(),
        }

    @classmethod
    def from_json_dict(cls, d: dict) -> BondCredentials:
        return cls(
            mac=d["mac"],
            tokens=BondTokens.from_dict(d["tokens"]),
            bonded_at=d.get("bonded_at", ""),
            aes_key=d.get("aes_key"),
        )


class BondHarvestError(Exception):
    """Bond or token step failed."""


OP_BOND_KEY_PUSH = 0x2100


def tokens_from_bond_frames(
    frames: list[DecryptedFrame],
    *,
    after_index: int = 0,
) -> BondTokens:
    """Bond keys from post-bond 0x2100 notify (64 B: hs + auth_16 + auth_32).

    Ghidra: libiot requestBond only sends encrypted magic; no tokens in .so.
    Firmware pushes per-bond keys on 0x2100 (FUN_4200e078 / FUN_4201d274 result 7).
    ctrl_c/ctrl_d stay device-static (protocol.py captures).
    """
    bond_key: bytes | None = None
    for frame in frames[after_index:]:
        if frame.opcode == OP_BOND_KEY_PUSH and len(frame.payload) >= 64:
            bond_key = frame.payload[:64]

    if bond_key is None:
        for frame in frames:
            if frame.opcode == OP_BOND_KEY_PUSH and len(frame.payload) >= 64:
                bond_key = frame.payload[:64]

    if bond_key is None:
        raise BondHarvestError(
            "no 0x2100 bond-key notify (64B) after requestBond — check bond_wait"
        )

    tokens = BondTokens(
        hs=bond_key[:16],
        auth_16=bond_key[16:32],
        auth_32=bond_key[32:64],
        ctrl_c=CMD_CTRL_C,
        ctrl_d=CMD_CTRL_D,
    )
    tokens.validate()
    return tokens


def is_bond_success(frame: DecryptedFrame) -> bool:
    """True for bond result 0/7 or 16-byte LIGHT_ACK on 0x1003."""
    if frame.opcode not in (OP_BOND_RESP, 0xAAAA):
        return False
    data = frame.payload
    if len(data) >= 16 and data[:16] == LIGHT_ACK:
        return True
    result = parse_bond_result(frame)
    return result in (BOND_SUCCESS, BOND_SUCCESS_PAIRED)


def normalize_mac(mac: str) -> str:
    parts = mac.replace("-", ":").upper().split(":")
    if len(parts) != 6:
        raise ValueError(f"invalid MAC: {mac!r}")
    return ":".join(f"{int(p, 16):02X}" for p in parts)


def creds_path(mac: str) -> Path:
    slug = normalize_mac(mac).replace(":", "-").lower()
    return LEPRO_DIR / f"{slug}.json"


def load_creds(mac: str) -> BondCredentials | None:
    path = creds_path(mac)
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    return BondCredentials.from_json_dict(data)


def save_creds(creds: BondCredentials) -> Path:
    path = creds_path(creds.mac)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(creds.to_json_dict(), indent=2) + "\n")
    return path


def harvest_tokens(frames: list[DecryptedFrame], raw_rx: list[bytes]) -> BondTokens:
    """
    Heuristic token harvest from bond-session RX.

    Scans decrypted cert/device-info payloads and raw notify bytes for
    unique 16B and 32B candidates. Prefer blobs appearing in cert (0x2000).
    """
    candidates_16: list[bytes] = []
    candidates_32: list[bytes] = []
    cert_blobs: list[bytes] = []

    for frame in frames:
        if frame.opcode == 0x2000:
            cert_blobs.append(frame.payload)
        _scan_blob(frame.payload, candidates_16, candidates_32)

    for raw in raw_rx:
        if len(raw) >= 26:
            _scan_blob(raw[10 : 10 + raw[9]], candidates_16, candidates_32)

    pool_16 = _unique(candidates_16)
    pool_32 = _unique(candidates_32)

    if cert_blobs:
        cert_16, cert_32 = [], []
        for blob in cert_blobs:
            _scan_blob(blob, cert_16, cert_32)
        if cert_16:
            pool_16 = _unique(cert_16) + [b for b in pool_16 if b not in cert_16]
        if cert_32:
            pool_32 = _unique(cert_32) + [b for b in pool_32 if b not in cert_32]

    if len(pool_32) < 1 or len(pool_16) < 3:
        raise BondHarvestError(
            f"insufficient token candidates: {len(pool_16)}×16B, {len(pool_32)}×32B "
            f"(need ≥3×16B and ≥1×32B). Save --debug-rx log for manual extraction."
        )

    auth_32 = pool_32[0]
    hs = pool_16[0]
    auth_16 = pool_16[1] if len(pool_16) > 1 else pool_16[0]
    ctrl_c = pool_16[2] if len(pool_16) > 2 else pool_16[-1]
    ctrl_d = pool_16[3] if len(pool_16) > 3 else pool_16[-1]

    tokens = BondTokens(hs=hs, auth_16=auth_16, auth_32=auth_32, ctrl_c=ctrl_c, ctrl_d=ctrl_d)
    tokens.validate()
    return tokens


def check_bond_result(frames: list[DecryptedFrame]) -> int:
    for frame in frames:
        result = parse_bond_result(frame)
        if result is not None:
            return result
    raise BondHarvestError("no 0x1003 bond response received")


def _scan_blob(data: bytes, out_16: list[bytes], out_32: list[bytes]) -> None:
    for size, out in ((16, out_16), (32, out_32)):
        for i in range(max(0, len(data) - size + 1)):
            chunk = data[i : i + size]
            if chunk.count(0) == size:
                continue
            out.append(chunk)


def _unique(items: list[bytes]) -> list[bytes]:
    seen: set[bytes] = set()
    result: list[bytes] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def export_provision_header(creds: BondCredentials) -> str:
    """C header for ESP32 NVS / compile-time flash."""
    t = creds.tokens
    mac = normalize_mac(creds.mac)
    return f"""/* Auto-generated by lepro-bond --export-provision — do not edit */
#pragma once
#include <stdint.h>
#include <stddef.h>

#define LEPRO_MAC "{mac}"
#define LEPRO_AES_KEY {{ {", ".join(f"0x{b:02x}" for b in bytes.fromhex(creds.aes_key or ""))} }}

static const uint8_t LEPRO_TOKEN_HS[] = {{ {", ".join(f"0x{b:02x}" for b in t.hs)} }};
static const uint8_t LEPRO_TOKEN_AUTH_16[] = {{ {", ".join(f"0x{b:02x}" for b in t.auth_16)} }};
static const uint8_t LEPRO_TOKEN_AUTH_32[] = {{ {", ".join(f"0x{b:02x}" for b in t.auth_32)} }};
static const uint8_t LEPRO_TOKEN_CTRL_C[] = {{ {", ".join(f"0x{b:02x}" for b in t.ctrl_c)} }};
static const uint8_t LEPRO_TOKEN_CTRL_D[] = {{ {", ".join(f"0x{b:02x}" for b in t.ctrl_d)} }};

#define LEPRO_TOKEN_HS_LEN {len(t.hs)}
#define LEPRO_TOKEN_AUTH_16_LEN {len(t.auth_16)}
#define LEPRO_TOKEN_AUTH_32_LEN {len(t.auth_32)}
#define LEPRO_TOKEN_CTRL_C_LEN {len(t.ctrl_c)}
#define LEPRO_TOKEN_CTRL_D_LEN {len(t.ctrl_d)}
"""


def export_provision_nvs(creds: BondCredentials) -> str:
    """ESP-IDF NVS CSV format."""
    slug = normalize_mac(creds.mac).replace(":", "")
    t = creds.tokens
    lines = [
        "key,type,encoding,value",
        f"lepro,namespace,,",
        f"mac,data,string,{normalize_mac(creds.mac)}",
        f"aes_key,data,string,{creds.aes_key}",
        f"hs,data,hex2bin,{t.hs.hex()}",
        f"auth_16,data,hex2bin,{t.auth_16.hex()}",
        f"auth_32,data,hex2bin,{t.auth_32.hex()}",
        f"ctrl_c,data,hex2bin,{t.ctrl_c.hex()}",
        f"ctrl_d,data,hex2bin,{t.ctrl_d.hex()}",
    ]
    return "\n".join(lines) + "\n"


async def _connect_transport(
    mac: str,
    *,
    debug_rx: bool = False,
    scan_timeout: float = 15.0,
):
    from bleak import BleakClient, BleakScanner

    from lepro.protocol import GATT_CMD, GATT_RSP
    from lepro.session import BleakTransport

    device = await BleakScanner.find_device_by_address(mac, timeout=scan_timeout)
    if device is None:
        device = await BleakScanner.find_device_by_name("LP", timeout=10)
    if device is None:
        raise SystemExit(f"Light not found: {mac}")

    client = BleakClient(device)
    await client.connect()
    transport = BleakTransport(client=client, cmd_char=GATT_CMD, rsp_char=GATT_RSP, debug_rx=debug_rx)
    await client.start_notify(GATT_RSP, transport.on_notify)
    await asyncio.sleep(0.3)
    return transport, client


async def _cmd_bond(args: argparse.Namespace) -> None:
    from lepro.session import LeproSession, bond_device

    mac = normalize_mac(args.mac)
    transport, client = await _connect_transport(
        mac, debug_rx=args.debug_rx, scan_timeout=args.scan_timeout
    )
    try:
        creds = await bond_device(LeproSession(mac, transport), mac, force=args.force_bond)
        print(f"Bond saved: {creds_path(creds.mac)}")
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mac", required=True, help="Target light MAC address")
    parser.add_argument(
        "--force-bond", action="store_true", help="Re-bond even if credentials already exist"
    )
    parser.add_argument("--debug-rx", action="store_true", help="Log all light notifications")
    parser.add_argument(
        "--scan-timeout", type=float, default=15.0, help="BLE scan timeout in seconds"
    )
    args = parser.parse_args()
    asyncio.run(_cmd_bond(args))


if __name__ == "__main__":
    main()
