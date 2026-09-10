#!/usr/bin/env python3
"""
BLE WiFi + MQTT provisioning (opcode 0x1008) for Lepro ZB1 string lights.

Mirrors the real app payload seen in captures.log:
  domain, root, cert, host, port, ssid, pass — optional uid.

Usage:
  uv run lepro-bond --mac 10:20:BA:31:B2:BA --force-bond
  uv run lepro-provision --mac 10:20:BA:31:B2:BA --config lepro-lab.toml
"""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
from pathlib import Path

from bleak import BleakClient, BleakScanner

from lepro.bond import (
    BOND_ERR_ALREADY,
    BondCredentials,
    is_bond_success,
    load_creds,
    normalize_mac,
)
from lepro.crypto import encrypt_bond_request, encrypt_dp_json
from lepro.frame import parse_bond_result
from lepro.protocol import (
    GATT_CMD,
    GATT_RSP,
    OP_WIFI_MQTT,
    OP_WIFI_MQTT_RESP,
    OP_WIFI_PROGRESS,
    build_packet_opcode,
)
from lepro.session import BleakTransport, LeproSession

DEFAULT_DOMAIN = "dvc-eu-iot.example.home"
DEFAULT_ROOT = "pub/cert/AmazonRootCA13.pem"
DEFAULT_CERT = "device/cert/did/debug/ver/1/sign/lepro"
DEFAULT_HOST = "mqtt.example.home"
DEFAULT_PORT = "8883"


def _prov_paths_file(mac: str) -> Path:
    slug = normalize_mac(mac).replace(":", "-").lower()
    return Path.home() / ".lepro" / f"{slug}-prov-paths.json"


def resolve_cert_paths(
    mac: str,
    root: str,
    cert: str,
    *,
    update_cert_paths: bool = False,
) -> tuple[str, str]:
    """
    Return root/cert paths to send in provision JSON.

    Verified against ZB1 v2.3.18 firmware (ota_state_machine_advance, state 0x2b):
    for each of "root"/"cert" the bulb ARMS its per-resource CDN fetch flag
    (sentinel 0x5a5a5a5a) only when the NVS key is missing (first provision) OR the
    path we send is byte-identical to the path already stored in NVS. If the path
    DIFFERS, the firmware does nothing — it neither updates NVS nor arms a fetch.
    Resend the exact stored path to re-arm and re-download (e.g. after rotating the
    cert file at the same CDN URL).

    On **stock** firmware the HTTPS download still requires onboarding mode
    (prov_mode 2/3); see prepare_cert_refetch(). On **patched** firmware
    (`lepro-firmware patch`, default) the prov_mode gate is removed so re-provision
    with the same paths re-fetches certs on an already-provisioned bulb.
    """
    path = _prov_paths_file(mac)
    if update_cert_paths or not path.is_file():
        return root, cert
    try:
        stored = json.loads(path.read_text())
        s_root = str(stored["root"])
        s_cert = str(stored["cert"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return root, cert
    if (s_root, s_cert) == (root, cert):
        return root, cert
    print(
        "Cert refresh: reusing stored CDN paths (firmware skips cert fetch when paths change):"
    )
    print(f"  root: {s_root}")
    print(f"  cert: {s_cert}")
    return s_root, s_cert


def save_cert_paths(mac: str, root: str, cert: str) -> None:
    path = _prov_paths_file(mac)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"root": root, "cert": cert}, indent=2) + "\n")


async def prepare_cert_refetch(session: LeproSession) -> None:
    """
    Re-send requestBond magic before WiFi/MQTT provision.

    On **stock** ZB1 v2.3.18: requestBond runs ota_state_machine_advance(0x14),
    which bumps prov_mode (ota_ctx+8) to 3 ONLY when it is already 2 or 3. The CDN
    cert fetch at WiFi-up (state 0x2d) is gated on prov_mode in {2, 3}. prov_mode is
    decided at boot and is 1 (NORMAL) on an already-provisioned bulb, so requestBond
    cannot enable cert re-download on stock firmware without a pairing/factory reset.

    On **patched** firmware (`lepro-firmware patch`) this call is harmless but not
    required for cert refresh — the prov_mode gate NOP makes state 0x2d always fetch.
    """
    magic = encrypt_bond_request(session.mac, session_rand=session._require_session_rand())
    try:
        resp = await session._request_bond(magic, "requestBond(cert-refresh)")
    except TimeoutError:
        print("Cert refresh: requestBond timed out (continuing with provision)")
        return
    result = parse_bond_result(resp)
    if is_bond_success(resp):
        print("Cert refresh: requestBond ok (prov_mode should allow CDN fetch on WiFi-up)")
    elif result == BOND_ERR_ALREADY:
        print("Cert refresh: already bonded (requestBond side effect may still apply)")
    else:
        print(f"Cert refresh: requestBond result={result} (continuing with provision)")


def build_wifi_mqtt_json(
    *,
    ssid: str,
    password: str,
    domain: str = DEFAULT_DOMAIN,
    root: str = DEFAULT_ROOT,
    cert: str = DEFAULT_CERT,
    host: str = DEFAULT_HOST,
    port: str = DEFAULT_PORT,
    uid: str | None = None,
) -> str:
    payload: dict[str, str] = {
        "domain": domain,
        "root": root,
        "cert": cert,
        "host": host,
        "port": port,
        "ssid": ssid,
        "pass": password,
    }
    if uid:
        payload["uid"] = uid
    return json.dumps(payload, separators=(",", ":"))


async def _connect(mac: str, *, debug_rx: bool = False) -> tuple[BleakTransport, BleakClient]:
    device = await BleakScanner.find_device_by_address(mac, timeout=15)
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


async def send_wifi_mqtt(
    session: LeproSession,
    *,
    ssid: str,
    password: str,
    domain: str,
    root: str,
    cert: str,
    host: str,
    port: str,
    uid: str | None,
    dry_run: bool = False,
) -> None:
    if session.session_rand is None:
        raise RuntimeError("call run_phase_discovery() before provisioning")

    body = build_wifi_mqtt_json(
        ssid=ssid,
        password=password,
        domain=domain,
        root=root,
        cert=cert,
        host=host,
        port=port,
        uid=uid,
    )
    print(f"Provision JSON:\n{json.dumps(json.loads(body), indent=2)}")

    ciphertext = encrypt_dp_json(session.mac, body, session_rand=session.session_rand)
    pkt = build_packet_opcode(await session._next_seq(), OP_WIFI_MQTT, ciphertext)
    await session._send(pkt, "sendWifiAndMqttInfo")

    if dry_run:
        print("Dry-run: provision packet sent (no RX wait)")
        return

    try:
        progress = await session._wait_opcode(OP_WIFI_PROGRESS, timeout=15.0)
        if len(progress.payload) >= 4:
            code = struct.unpack("<I", progress.payload[:4])[0]
            print(f"WiFi progress opcode 0x100b: {code:#x}")
    except TimeoutError:
        print("No 0x100b progress within 15s (continuing)")

    try:
        resp = await session._wait_opcode(OP_WIFI_MQTT_RESP, timeout=60.0)
        if len(resp.payload) >= 4:
            result = struct.unpack("<I", resp.payload[:4])[0]
            print(f"Provision result 0x1009: {result}")
            if result != 0:
                raise SystemExit(f"provision failed: result={result}")
        else:
            print(f"Provision ack payload: {resp.payload.hex()}")
    except TimeoutError as e:
        raise SystemExit("Timed out waiting for 0x1009 provision ack — check WiFi/MQTT reachability") from e


async def cmd_provision(args: argparse.Namespace) -> None:
    mac = normalize_mac(args.mac)
    if args.dry_run:
        from lepro.session import DryRunTransport, SessionConfig

        transport = DryRunTransport()
        session = LeproSession(mac, transport, config=SessionConfig(dry_run=True, send_delay=0))
        await session.run_phase_discovery()
        creds = load_creds(mac)
        if creds:
            await session.run_phase_auth(creds)
        root, cert = _resolved_cert_paths(args, mac)
        if not getattr(args, "no_cert_refresh", False):
            await prepare_cert_refetch(session)
        await send_wifi_mqtt(
            session,
            ssid=args.ssid,
            password=args.pass_,
            domain=args.domain,
            root=root,
            cert=cert,
            host=args.host,
            port=args.port,
            uid=args.uid,
            dry_run=True,
        )
        for label, pkt in transport.sent:
            print(f"  [{label}] {pkt.hex()}")
        return

    creds = load_creds(mac)
    if creds is None:
        raise SystemExit(f"No bond creds for {mac}. Run lepro-bond first.")

    transport, client = await _connect(mac, debug_rx=args.debug_rx)
    try:
        session = LeproSession(mac, transport)
        await cmd_provision_with_creds(session, creds, args)
        print(
            "Provision command accepted — bulb should join WiFi.\n"
            "With patched firmware (lepro-firmware patch), root/client certs are "
            "re-downloaded from the CDN on each provision when the same paths are "
            "re-sent. Stock firmware only re-fetches in onboarding mode (prov_mode "
            "2/3); use a pairing reset before re-provision if still on stock."
        )
    finally:
        await client.disconnect()


async def cmd_provision_with_creds(
    session: LeproSession,
    creds: BondCredentials,
    args: argparse.Namespace,
) -> None:
    dev_info = await session.run_phase_discovery()
    print(dev_info.provisioning_summary())
    if dev_info.prov_slot == 7:
        print(
            "  WARNING: bulb reports provisioned. On stock firmware, re-provision "
            "without onboarding will not re-fetch CDN certs; flash patched firmware "
            "or pairing-reset first."
        )
    # Reprovision on bonded lights: discovery → 0x1008 without full auth/commit
    # (0xaaaa if auth is attempted on this firmware path).
    root, cert = _resolved_cert_paths(args, session.mac)
    if not getattr(args, "no_cert_refresh", False):
        await prepare_cert_refetch(session)
    await send_wifi_mqtt(
        session,
        ssid=args.ssid,
        password=args.pass_,
        domain=args.domain,
        root=root,
        cert=cert,
        host=args.host,
        port=args.port,
        uid=args.uid,
        dry_run=getattr(args, "dry_run", False),
    )
    if not getattr(args, "no_cert_refresh", False) and not getattr(args, "dry_run", False):
        save_cert_paths(session.mac, root, cert)


def _resolved_cert_paths(args: argparse.Namespace, mac: str) -> tuple[str, str]:
    if getattr(args, "no_cert_refresh", False):
        return args.root, args.cert
    return resolve_cert_paths(
        mac,
        args.root,
        args.cert,
        update_cert_paths=getattr(args, "update_cert_paths", False),
    )


def _add_cert_refresh_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--no-cert-refresh",
        action="store_true",
        help="Skip requestBond and stored CDN path reuse (paths must still match NVS to arm fetch)",
    )
    p.add_argument(
        "--update-cert-paths",
        action="store_true",
        help="Use --root/--cert from CLI/config instead of last stored paths",
    )


