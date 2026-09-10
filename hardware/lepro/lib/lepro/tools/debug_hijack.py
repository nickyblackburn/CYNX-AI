#!/usr/bin/env python3
"""
Diagnose Lepro ZB1 lab hijack: CDN cert pin, HTTPS cert CDN, MQTT mTLS.

Reads a router pcap, checks firmware pin state, probes mock infra, and appends
NDJSON lines to the Cursor debug log for hypothesis tracking.

Usage:
  uv run python tools/debug_hijack.py
  uv run python tools/debug_hijack.py --pcap ../lepro.pcap --firmware ../firmware/3_le_light_zb1_pid_55_v2.3.18.patched.bin
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from lepro.firmware_profile import load_profiles, resolve_profile
from lepro.patch_cdn import build_bundle_record, find_bundle_layout, sha256_hex, split_bundle_record
from lepro.paths import repo_path

LOG_PATH = repo_path(".cursor/debug-7ed36c.log")
SESSION_ID = "7ed36c"

DEFAULT_PCAP = repo_path("lepro.pcap")
DEFAULT_STOCK = repo_path("firmware/3_le_light_zb1_pid_55_v2.3.18.bin")
DEFAULT_PATCHED = repo_path("firmware/3_le_light_zb1_pid_55_v2.3.18.patched.bin")
DEFAULT_CERT = repo_path("deploy/lepro-debug/certs/cdn.pem")
DEFAULT_CA = repo_path("deploy/lepro-debug/certs/ca.pem")

CDN_HOST = "dvc-eu-iot.internal.sunbury.xyz"
MQTT_HOST = "mqtt.internal.sunbury.xyz"
CDN_LB_IP = "10.1.1.22"
TRAEFIK_IP = "10.1.1.20"


def _log(hypothesis_id: str, location: str, message: str, data: dict, *, run_id: str) -> None:
    # #region agent log
    payload = {
        "sessionId": SESSION_ID,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, separators=(",", ":")) + "\n")
    # #endregion


def _pem_der(path: Path) -> bytes:
    return subprocess.check_output(
        ["openssl", "x509", "-inform", "PEM", "-outform", "DER"],
        input=path.read_bytes(),
    )


def _bundle_record_at(fw: bytes, firmware_path: Path | None = None) -> tuple[object, bytes]:
    profiles = load_profiles()
    profile = resolve_profile(
        profiles,
        firmware_path=firmware_path,
        profile_id=None,
    )
    layout = find_bundle_layout(fw, profile.bundle)
    record = fw[layout.entry_off : layout.entry_off + layout.record_len]
    return layout, record


def _fetch_peer_der(host: str, port: int, *, connect_host: str | None = None) -> bytes:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((connect_host or host, port), timeout=8) as raw_sock:
        with ctx.wrap_socket(raw_sock, server_hostname=host) as tls_sock:
            cert = tls_sock.getpeercert(binary_form=True)
    if not cert:
        raise OSError(f"Peer at {connect_host or host}:{port} did not present a certificate")
    return cert


def check_firmware_pin(stock: Path, patched: Path | None, cert: Path) -> dict:
    stock_fw = stock.read_bytes()
    layout, stock_record = _bundle_record_at(stock_fw, stock)
    stock_name, stock_key = split_bundle_record(stock_record, layout)
    cdn_der = _pem_der(cert)
    expected_record, expected_name, expected_key = build_bundle_record(cdn_der)

    out: dict = {
        "bundle_off": hex(layout.bundle_off),
        "entry_off": hex(layout.entry_off),
        "key_off": hex(layout.key_off),
        "name_len": layout.name_len,
        "key_len": layout.key_len,
        "stock_record_sha256": sha256_hex(stock_record),
        "stock_name_sha256": sha256_hex(stock_name),
        "stock_key_sha256": sha256_hex(stock_key),
        "expected_record_sha256": sha256_hex(expected_record),
        "expected_name_sha256": sha256_hex(expected_name),
        "expected_key_sha256": sha256_hex(expected_key),
        "stock_matches_real_lepro_record": None,
        "patched_path": str(patched) if patched else None,
        "patched_matches_cdn_record": None,
        "patched_matches_live_traefik_record": None,
        "live_traefik_matches_cdn_record": None,
        "patched_diff_from_stock": None,
    }

    try:
        real_record, _, _ = build_bundle_record(_fetch_peer_der("ota-dvc-eu-iot.lepro.com", 443))
        out["real_lepro_record_sha256"] = sha256_hex(real_record)
        out["stock_matches_real_lepro_record"] = stock_record == real_record
    except (subprocess.SubprocessError, OSError, TimeoutError):
        out["stock_matches_real_lepro_record"] = None

    try:
        live_traefik_record, _, _ = build_bundle_record(
            _fetch_peer_der(CDN_HOST, 443, connect_host=TRAEFIK_IP)
        )
        out["live_traefik_record_sha256"] = sha256_hex(live_traefik_record)
        out["live_traefik_matches_cdn_record"] = live_traefik_record == expected_record
    except OSError as exc:
        out["live_traefik_error"] = str(exc)

    if patched and patched.is_file():
        patched_fw = patched.read_bytes()
        patched_layout, patched_record = _bundle_record_at(patched_fw, patched)
        patched_name, patched_key = split_bundle_record(patched_record, patched_layout)
        out["patched_record_sha256"] = sha256_hex(patched_record)
        out["patched_name_sha256"] = sha256_hex(patched_name)
        out["patched_key_sha256"] = sha256_hex(patched_key)
        out["patched_matches_cdn_record"] = patched_record == expected_record
        if "live_traefik_record_sha256" in out:
            out["patched_matches_live_traefik_record"] = (
                patched_record == live_traefik_record
            )
        out["patched_diff_from_stock"] = sum(
            a != b for a, b in zip(stock_record, patched_record)
        )

    return out


def analyze_pcap(pcap: Path) -> dict:
    if not pcap.is_file():
        return {"error": f"pcap missing: {pcap}"}

    def tshark(*fields: str) -> list[str]:
        cmd = ["tshark", "-r", str(pcap), "-T", "fields", *fields]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (FileNotFoundError, subprocess.SubprocessError):
            return []
        if proc.returncode != 0:
            return []
        return [ln for ln in proc.stdout.splitlines() if ln.strip()]

    dns_lines = tshark("-e", "dns.qry.name", "-e", "dns.a")
    dns_names: set[str] = set()
    dns_answers: dict[str, set[str]] = {}
    for ln in dns_lines:
        parts = ln.split("\t")
        if not parts or not parts[0]:
            continue
        name = parts[0]
        dns_names.add(name)
        if len(parts) > 1 and parts[1]:
            dns_answers.setdefault(name, set()).add(parts[1])

    tls_sni = [ln for ln in tshark("-e", "tls.handshake.extensions_server_name") if ln]
    tls_alerts = tshark(
        "-Y",
        "tls.alert_message",
        "-e",
        "ip.src",
        "-e",
        "ip.dst",
        "-e",
        "tcp.dstport",
        "-e",
        "tls.alert_message.desc",
    )

    mqtt_alerts: list[dict] = []
    alert_names = {
        "1": "close_notify",
        "40": "handshake_failure",
        "46": "certificate_unknown",
        "48": "unknown_ca",
    }
    for ln in tls_alerts:
        parts = ln.split("\t")
        if len(parts) < 4:
            continue
        src, dst, dport, code = parts[0], parts[1], parts[2], parts[3]
        if dport == "8883" and code:
            mqtt_alerts.append(
                {
                    "src": src,
                    "dst": dst,
                    "alert": alert_names.get(code, f"code_{code}"),
                }
            )

    https_frames = tshark("-e", "tcp.dstport")
    port_counts: dict[str, int] = {}
    for ln in https_frames:
        for port in ln.split("\t"):
            if port.isdigit():
                port_counts[port] = port_counts.get(port, 0) + 1

    return {
        "pcap": str(pcap),
        "dns_queries": sorted(dns_names),
        "dns_answers": {k: sorted(v) for k, v in dns_answers.items()},
        "tls_sni_hosts": sorted({h for h in tls_sni if h}),
        "mqtt_tls_alerts": mqtt_alerts[:5],
        "mqtt_tls_alert_count": len(mqtt_alerts),
        "tcp_dstport_counts": port_counts,
        "cdn_dns_seen": CDN_HOST in dns_names,
        "mqtt_dns_seen": MQTT_HOST in dns_names,
        "https_443_frames": port_counts.get("443", 0),
        "mqtt_8883_frames": port_counts.get("8883", 0),
    }


def check_dns(host: str) -> dict:
    out: dict = {"host": host, "answers": [], "error": None}
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        out["answers"] = sorted({info[4][0] for info in infos})
    except socket.gaierror as exc:
        out["error"] = str(exc)
    return out


def probe_cdn() -> dict:
    url = f"https://{CDN_HOST}/pub/cert/AmazonRootCA13.pem"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    out: dict = {"url": url, "ok": False, "status": None, "body_len": None, "error": None}
    try:
        req = urllib.request.Request(
            url,
            headers={"Host": CDN_HOST},
            method="HEAD",
        )
        # Resolve via /etc/hosts style override
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
        )
        # Manual connect through LB
        conn = ctx.wrap_socket(
            socket.create_connection((CDN_LB_IP, 443), timeout=8),
            server_hostname=CDN_HOST,
        )
        conn.send(
            f"HEAD /pub/cert/AmazonRootCA13.pem HTTP/1.1\r\nHost: {CDN_HOST}\r\n\r\n".encode()
        )
        resp = conn.recv(4096).decode("latin-1", errors="replace")
        conn.close()
        out["ok"] = "200" in resp.splitlines()[0] if resp else False
        out["status"] = resp.splitlines()[0] if resp else None
        if out["ok"]:
            get_conn = ctx.wrap_socket(
                socket.create_connection((CDN_LB_IP, 443), timeout=8),
                server_hostname=CDN_HOST,
            )
            get_conn.send(
                f"GET /pub/cert/AmazonRootCA13.pem HTTP/1.1\r\nHost: {CDN_HOST}\r\n\r\n".encode()
            )
            raw = get_conn.recv(8192)
            get_conn.close()
            body = raw.split(b"\r\n\r\n", 1)[-1] if b"\r\n\r\n" in raw else b""
            out["body_len"] = len(body)
            if DEFAULT_CA.is_file():
                out["body_matches_ca_pem"] = body == DEFAULT_CA.read_bytes()
    except OSError as exc:
        out["error"] = str(exc)
    return out


def probe_mqtt_tls() -> dict:
    out: dict = {"host": MQTT_HOST, "port": 8883, "server_issuer": None, "error": None}
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        sock = ctx.wrap_socket(
            socket.socket(),
            server_hostname=MQTT_HOST,
        )
        sock.connect((CDN_LB_IP, 8883))
        cert = sock.getpeercert()
        out["server_subject"] = dict(x[0] for x in cert.get("subject", ()))
        out["server_issuer"] = dict(x[0] for x in cert.get("issuer", ()))
        sock.close()
    except OSError as exc:
        out["error"] = str(exc)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcap", type=Path, default=DEFAULT_PCAP)
    parser.add_argument("--stock", type=Path, default=DEFAULT_STOCK)
    parser.add_argument("--patched", type=Path, default=DEFAULT_PATCHED)
    parser.add_argument("--cert", type=Path, default=DEFAULT_CERT)
    parser.add_argument("--run-id", default="pre-fix")
    args = parser.parse_args()

    print("Lepro hijack diagnostics")
    print("=" * 50)

    pin = check_firmware_pin(args.stock, args.patched, args.cert)
    print(f"Firmware bundle @ {pin['bundle_off']} (entry {pin['entry_off']})")
    print(f"  stock record sha: {pin['stock_record_sha256'][:16]}…")
    print(f"  expected sha:     {pin['expected_record_sha256'][:16]}…")
    if pin.get("patched_record_sha256"):
        print(f"  patched sha:      {pin['patched_record_sha256'][:16]}…")
        print(f"  patched OK:       {pin['patched_matches_cdn_record']}")
        print(f"  bytes vs stock:   {pin['patched_diff_from_stock']}/{pin['name_len'] + pin['key_len']}")
    if pin.get("live_traefik_matches_cdn_record") is not None:
        print(f"  live cert OK:     {pin['live_traefik_matches_cdn_record']}")
    _log("H2", "debug_hijack:firmware_pin", "Firmware CDN pin state", pin, run_id=args.run_id)

    pcap_info = analyze_pcap(args.pcap)
    print(f"\nPcap: {pcap_info.get('pcap')}")
    if "error" not in pcap_info:
        print(f"  DNS queries:      {pcap_info['dns_queries']}")
        print(f"  CDN DNS seen:     {pcap_info['cdn_dns_seen']}")
        print(f"  MQTT DNS seen:    {pcap_info['mqtt_dns_seen']}")
        print(f"  TLS SNI:          {pcap_info['tls_sni_hosts']}")
        print(f"  TCP :443 frames:  {pcap_info['https_443_frames']}")
        print(f"  TCP :8883 frames: {pcap_info['mqtt_8883_frames']}")
        if pcap_info["mqtt_tls_alerts"]:
            print(f"  MQTT TLS alert:   {pcap_info['mqtt_tls_alerts'][0]['alert']}")
    _log("H1,H3,H4", "debug_hijack:pcap", "Router capture analysis", pcap_info, run_id=args.run_id)

    for host in (CDN_HOST, MQTT_HOST):
        dns = check_dns(host)
        print(f"\nDNS {host}: {dns['answers'] or dns['error']}")
        _log("H1", f"debug_hijack:dns:{host}", "Resolver check from this host", dns, run_id=args.run_id)

    cdn = probe_cdn()
    print(f"\nCDN probe: {cdn.get('status') or cdn.get('error')}")
    if cdn.get("body_matches_ca_pem") is not None:
        print(f"  AmazonRootCA13 body matches ca.pem: {cdn['body_matches_ca_pem']}")
    _log("H4", "debug_hijack:cdn_probe", "HTTPS cert CDN reachability", cdn, run_id=args.run_id)

    mqtt = probe_mqtt_tls()
    print(f"\nMQTT TLS issuer: {mqtt.get('server_issuer') or mqtt.get('error')}")
    _log("H3", "debug_hijack:mqtt_probe", "MQTT broker TLS cert", mqtt, run_id=args.run_id)

    print(f"\nDebug log: {LOG_PATH.resolve()}")

    # Human summary
    issues: list[str] = []
    cdn_dns = check_dns(CDN_HOST)
    if not cdn_dns.get("answers"):
        issues.append(f"{CDN_HOST} does not resolve — add DNS on IoT router")
    if not pcap_info.get("cdn_dns_seen") and "error" not in pcap_info:
        issues.append(f"No DNS lookup for {CDN_HOST} in pcap — add IoT DNS override → {CDN_LB_IP}")
    if pcap_info.get("https_443_frames", 0) == 0 and "error" not in pcap_info:
        issues.append("No HTTPS :443 traffic — bulb never fetched AmazonRootCA13.pem / client cert")
    alert_kinds = {a["alert"] for a in pcap_info.get("mqtt_tls_alerts", [])}
    if "unknown_ca" in alert_kinds or pcap_info.get("mqtt_tls_alert_count", 0) > 0:
        issues.append(
            "MQTT TLS fails (Unknown CA) — bulb has not installed mock AmazonRootCA13.pem from CDN"
        )
    if pin.get("live_traefik_matches_cdn_record") is False:
        issues.append("Live Traefik cert does not match deploy/lepro-debug/certs/cdn.pem — redeploy certs")
    if pin.get("patched_matches_cdn_record") is False:
        issues.append(
            "Patched firmware crt-bundle entry does not match deploy/lepro-debug/certs/cdn.pem — re-run lepro-firmware patch"
        )
    elif pin.get("patched_diff_from_stock") == 0:
        issues.append("Patched firmware identical to stock crt-bundle entry — flash patched.bin via OTA")

    if issues:
        print("\nLikely blockers:")
        for i, item in enumerate(issues, 1):
            print(f"  {i}. {item}")
    else:
        print("\nNo obvious blockers from automated checks.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
