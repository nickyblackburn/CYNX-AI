"""Shared BLE session helpers for focused CLIs."""

from __future__ import annotations

import asyncio

from bleak import BleakClient, BleakScanner

from lepro.bond import creds_path, load_creds
from lepro.commands import DpPayload
from lepro.crypto import decrypt_dp_json
from lepro.protocol import GATT_CMD, GATT_RSP, OP_DP_CMD, OP_SEARCH, parse_packet
from lepro.session import BleakTransport, DryRunTransport, LeproSession, SessionConfig


async def connect_transport(
    mac: str,
    *,
    debug_rx: bool = False,
    scan_timeout: float = 15.0,
) -> tuple[BleakTransport, BleakClient]:
    device = await BleakScanner.find_device_by_address(mac, timeout=scan_timeout)
    if device is None:
        device = await BleakScanner.find_device_by_name("LP", timeout=10)
    if device is None:
        raise SystemExit(f"Light not found: {mac}")

    client = BleakClient(device)
    await client.connect()
    transport = BleakTransport(
        client=client, cmd_char=GATT_CMD, rsp_char=GATT_RSP, debug_rx=debug_rx
    )
    await client.start_notify(GATT_RSP, transport.on_notify)
    await asyncio.sleep(0.3)
    return transport, client


async def run_dry_control(mac: str, payload: DpPayload) -> list[tuple[str, bytes]]:
    creds = load_creds(mac)
    if creds is None:
        raise SystemExit(
            f"No credentials at {creds_path(mac)}. Run lepro-bond first."
        )
    transport = DryRunTransport()
    session = LeproSession(mac, transport, config=SessionConfig(dry_run=True, send_delay=0))
    await session.run_phase_discovery()
    await session.run_phase_auth(creds)
    await session.send_dp_payload(payload)
    await session.commit_control(creds)
    return transport.sent


def print_dry_run(sent: list[tuple[str, bytes]]) -> None:
    print(f"Dry-run: {len(sent)} TX packets")
    for label, pkt in sent:
        hdr = parse_packet(pkt)
        op = f"{hdr.opcode:#06x}" if hdr else "?"
        print(
            f"  [{label}] opcode={op} seq={hdr.seq if hdr else '?'} "
            f"len={len(pkt)} hex={pkt.hex()}"
        )


async def run_control(
    mac: str,
    payload: DpPayload,
    *,
    dry_run: bool = False,
    debug_rx: bool = False,
) -> None:
    if dry_run:
        print_dry_run(await run_dry_control(mac, payload))
        return

    creds = load_creds(mac)
    if creds is None:
        raise SystemExit(f"No credentials at {creds_path(mac)}. Run: lepro-bond --mac {mac}")

    transport, client = await connect_transport(mac, debug_rx=debug_rx)
    try:
        session = LeproSession(mac, transport)
        await session.run_control(creds, payload)
        print("Done.")
    finally:
        await client.disconnect()


async def run_status(
    mac: str,
    *,
    dry_run: bool = False,
    debug_rx: bool = False,
) -> None:
    from lepro.commands import status_query

    query = status_query()
    if dry_run:
        creds = load_creds(mac)
        if creds is None:
            raise SystemExit(f"No credentials at {creds_path(mac)}")
        transport = DryRunTransport()
        session = LeproSession(mac, transport, config=SessionConfig(dry_run=True, send_delay=0))
        await session.run_phase_discovery()
        await session.run_phase_auth(creds)
        await session.send_get_dp_state(query)
        print_dry_run(transport.sent)
        return

    creds = load_creds(mac)
    if creds is None:
        raise SystemExit(f"No credentials at {creds_path(mac)}")

    transport, client = await connect_transport(mac, debug_rx=debug_rx)
    try:
        session = LeproSession(mac, transport)
        dev_info = await session.run_phase_discovery()
        print(dev_info.provisioning_summary())
        await session.run_phase_auth(creds)
        frame = await session.send_get_dp_state(query)
        try:
            if frame.decrypted:
                text = frame.payload.rstrip(b"\x00").decode("utf-8")
            else:
                text = decrypt_dp_json(
                    frame.payload, mac, session_rand=session.session_rand
                )
            print(text)
        except Exception:
            print(f"Raw response ({len(frame.payload)}B): {frame.payload.hex()}")
    finally:
        await client.disconnect()
