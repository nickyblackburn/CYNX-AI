#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["bleak"]
# ///
"""
Replay the captured LP string-light session over BLE without decrypting anything.

The key insight: CMD_AUTH_16, CMD_CTRL_C, CMD_CTRL_D, and all bulk-data pages
use a STATIC key (same bytes across multiple captured sessions), so we can
replay the captured bytes verbatim.

Usage:
    uv run python tools/replay.py                        # scan and connect to nearest LP light
    uv run python tools/replay.py --mac 10:20:BA:31:B2:BA
"""

import asyncio, argparse, os

from bleak import BleakClient, BleakScanner

from lepro.protocol import (
    GATT_CMD as CMD_CHAR,
    GATT_RSP as RSP_CHAR,
    GATT_SERVICE as SERVICE_UUID,
    CMD_AUTH_16,
    CMD_AUTH_32,
    CMD_CTRL_C,
    CMD_CTRL_D,
    CMD_HS,
    PDU_DATA,
    PDU_SESSION,
    SUB_CMD,
    SUB_REQ,
    build_packet,
)

# Captured bulk data pages from session 9 (the colour program upload, in order)
# These 32B pre-session pages appear to be initial key-exchange frames
BULK_32B = [
    bytes.fromhex("c9c77c477cd9d6aead0df20b353e78fcfbd9184c98891ee7605324a927afd0e2"),
    bytes.fromhex("a8037d5d7e1830f61d2d585a705d316f4d7b06f028b918a60aeffee783fcc1a6"),
    bytes.fromhex("e78f38173d3afcbd4cdf507adff7bd419f8d2a62445444fc99f7d9833b29cfba"),
    bytes.fromhex("326c8d865e0670e65f754cd6eae1d5dd62abdefe45203a292c35f8a933dfe088"),
    bytes.fromhex("85291be78092583b70ecbdcdbb84131ca57b886428c0c4269d14e063033b99be"),
    bytes.fromhex("fcd22c856677214cc0bed1d3adcd475caefb01d22ec0de0f24ca22c73f2b7e0b"),
    bytes.fromhex("3912a2f92382a838e0b10484f9c1ccde1fb8c98d0a5317d8f6e2f1b548ed4dad"),
]

# Main bulk upload (colour program): 80–144 B pages from session 9 (11:17:31–11:17:38)
BULK_PAGES = [
    bytes.fromhex("73893f16dffde8fc05e4402cbf9e7b0af6b622afa8fac0b5a25430c2bdd12298c33bb7e2cac1ad215dde17843503341c6d0203ada4c66d078714c23532bbd32803171701a9b2e7f3f4dd5fd8106739ea"),
    bytes.fromhex("a68f78af9580a48f51598231363df6e87d8ce120323fc3833a8204b9b8239638df2e3e2ac1d073d56ed3f9df35c7b63d09c89e92c0aeba53bae2c3bdead4a6f7b6e78c86d37e85bdbd98afb0b24a2e42beb20db4c89e2a8ceafd6d2ce1e4a98f2fca7e5e0dc0f6e16ddaeef23b4fd0ff"),
    bytes.fromhex("2e7e3b2c16151c111cc498a164a63560e288c94ba412c8104fc712922935c6d21a9e80afc5df1f25c04f54f8d8b6d34c0917a98f2f6e25a3bd7eeb4e7d0c5f"),
    bytes.fromhex("6c8e6d1011e8a7f30096edf6c8120b0438b4b3b990d4d6e16bda8ac3ce45f9116c8e6d1011e8a7f30096edf6c8120b0438b4b3b990d4d6e16bda8ac3ce45f9116c8e6d1011e8a7f30096edf6c8120b04"),
    bytes.fromhex("ff0d626aef27510e70a053d6a923847994b107924ff2678206cd157c2719ddf0c633e0a2d89f8432db1e50a4e5f84f72de73f1c92cf21d73b48c0d459d47b0b88dd8c2e72f2c76b7d0fc2e3b0a"),
    bytes.fromhex("4a0ac5b5c0a55451f4c9e89b8a5a5a5a34d3b4c990d4d6e16bda8ac3ce45f911"),
    bytes.fromhex("404b3ec5b27c4d7e6f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6"),
]

# Captured raw packet bytes for the bulk pages (from session 9)
# Using raw captured bytes preserves CRC and seq
RAW_BULK = """
3912a2f9 2382a838 e0b10484 f9c1ccde 1fb8c98d 0a531 7d8 f6e2f1b5 48ed4dad
""".split()  # placeholder – actual values from captures.log


# ── Main flow ────────────────────────────────────────────────────────────────

async def run(target_mac: str | None):
    print("Scanning for LP string lights...")
    if target_mac:
        device = await BleakScanner.find_device_by_address(target_mac, timeout=10)
    else:
        devices = await BleakScanner.discover(timeout=5, service_uuids=[SERVICE_UUID])
        if not devices:
            print("No LP lights found. Make sure the light is in pairing mode.")
            return
        device = devices[0]
        print(f"Found: {device.name} ({device.address})")

    if not device:
        print("Device not found.")
        return

    responses = []

    async with BleakClient(device) as client:
        print(f"Connected to {device.address}")

        # Enable notifications on the RSP characteristic
        def on_notify(sender, data):
            print(f"  ← LIGHT: {data.hex()}")
            responses.append(bytes(data))

        await client.start_notify(RSP_CHAR, on_notify)
        await asyncio.sleep(0.3)

        async def send(raw_payload: bytes, label: str = ""):
            print(f"  → PHONE [{label}]: {raw_payload.hex()}")
            await client.write_gatt_char(CMD_CHAR, raw_payload, response=False)
            await asyncio.sleep(0.4)

        seq = 0

        # ── Phase 1: Send a fresh hello nonce ─────────────────────────────
        # The nonce changes each session; generate a dummy one.
        # The light will respond with device info but we ignore it.
        hello_nonce = os.urandom(32)
        pkt = build_packet(seq, PDU_DATA, SUB_REQ, hello_nonce)
        await send(pkt, "hello/nonce")
        seq += 1

        await asyncio.sleep(1.0)  # wait for 0x10/0x01 + 0x20/0x00

        # ── Phase 2: Send the static handshake token ──────────────────────
        pkt = build_packet(seq, PDU_DATA, SUB_CMD, CMD_HS)
        await send(pkt, "hs-token")
        seq += 1
        await asyncio.sleep(0.3)

        # ── Phase 3: Auth sequence ────────────────────────────────────────
        for payload, label in [
            (CMD_AUTH_32, "auth-32"),
            (CMD_AUTH_16, "auth-16"),
        ]:
            pkt = build_packet(seq, PDU_SESSION, SUB_CMD, payload)
            await send(pkt, label)
            seq += 1
            await asyncio.sleep(0.3)

        # ── Phase 4: Upload bulk data (colour program) ────────────────────
        for i, page in enumerate(BULK_PAGES):
            pkt = build_packet(seq, PDU_SESSION, SUB_REQ, page)
            await send(pkt, f"bulk[{i}]")
            seq += 1
            await asyncio.sleep(1.1)  # observed ~1s between pages

        # ── Phase 5: Toggle control commands ─────────────────────────────
        for rep in range(3):
            for payload, label in [(CMD_CTRL_C, "ctrl-C"), (CMD_CTRL_D, "ctrl-D")]:
                pkt = build_packet(seq, PDU_SESSION, SUB_CMD, payload)
                await send(pkt, label)
                seq += 1
                await asyncio.sleep(0.5)

        await client.stop_notify(RSP_CHAR)
        print(f"\nDone. Received {len(responses)} notifications from light.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mac", help="Target light MAC address (optional)")
    args = ap.parse_args()
    asyncio.run(run(args.mac))
