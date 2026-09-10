#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["cryptography"]
# ///
"""
Reconstruct and validate the Lepro ZB1 bulb's MQTT trust anchor (`mqtt_cert_srv`).

WHY THIS IS NOT A LITERAL NVS DUMP
----------------------------------
This firmware exposes NO BLE opcode that reads back NVS / certificates, and the
server CA (`mqtt_cert_srv`) is only used locally to verify the broker — it never
goes on the wire. So we cannot read it over BLE or sniff it.

However (confirmed in Ghidra, v2.3.18 ELF):
  * the HTTPS cert fetch `FUN_4200b1ac` stores the response body VERBATIM into the
    NVS key `mqtt_cert_srv` via `FUN_4200cf38` (nvs_set_blob + commit), and
  * the MQTT client (`FUN_4200be28`) loads that exact blob as the *only* TLS trust
    anchor (cacert_buf) — no crt-bundle, no global CA store.

Therefore the effective contents of `mqtt_cert_srv` == the bytes the CDN serves at
the provisioned `root` path. This tool fetches those bytes (the authoritative
source of what the device installs) and emulates the bulb's mbedTLS verification
of the live broker chain. That answers the only question that matters:

    Does the CA the device installs actually verify the broker it connects to?

Usage:
  uv run python tools/mqtt_ca_dump.py
  uv run python tools/mqtt_ca_dump.py --cdn-host dvc-eu-iot.example.home --cdn-ip 10.0.0.5 \
      --root pub/cert/AmazonRootCA13.pem \
      --mqtt-host mqtt.example.home --mqtt-ip 10.0.0.5 --mqtt-port 8883 \
      --ca deploy/lepro-debug/certs/ca.pem
"""

from __future__ import annotations

import argparse
import hashlib
import socket
import ssl
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

# Defaults mirror provision.py + the lab layout.
DEFAULT_CDN_HOST = "dvc-eu-iot.example.home"
DEFAULT_CDN_IP = "10.0.0.5"
DEFAULT_ROOT = "pub/cert/AmazonRootCA13.pem"
DEFAULT_MQTT_HOST = "mqtt.example.home"
DEFAULT_MQTT_IP = "10.0.0.5"
DEFAULT_MQTT_PORT = 8883
from lepro.paths import repo_path

DEFAULT_CA = repo_path("deploy/lepro-debug/certs/ca.pem")


def _spki_fp(cert: x509.Certificate) -> str:
    spki = cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return hashlib.sha256(spki).hexdigest()


def _cert_fp(cert: x509.Certificate) -> str:
    return cert.fingerprint(hashes.SHA256()).hex()


def _name(n: x509.Name) -> str:
    return n.rfc4514_string()


def fetch_cdn_body(host: str, ip: str, root: str) -> bytes:
    """HTTPS GET of the provisioned root path — the bytes the bulb stores verbatim."""
    ctx = ssl._create_unverified_context()
    path = "/" + root.lstrip("/")
    with socket.create_connection((ip, 443), timeout=8) as raw:
        with ctx.wrap_socket(raw, server_hostname=host) as s:
            s.send(
                f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                f"User-Agent: esp32\r\nConnection: close\r\n\r\n".encode()
            )
            buf = b""
            while True:
                chunk = s.recv(8192)
                if not chunk:
                    break
                buf += chunk
    head, _, body = buf.partition(b"\r\n\r\n")
    status = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
    if "Transfer-Encoding: chunked".lower() in head.decode("latin-1", "replace").lower():
        body = _dechunk(body)
    return status, body


def _dechunk(body: bytes) -> bytes:
    out = b""
    while body:
        size_line, _, rest = body.partition(b"\r\n")
        try:
            size = int(size_line.strip(), 16)
        except ValueError:
            return body
        if size == 0:
            break
        out += rest[:size]
        body = rest[size + 2 :]
    return out


def fetch_broker_chain(host: str, ip: str, port: int) -> list[x509.Certificate]:
    """Pull the FULL cert chain the broker presents (leaf first).

    Python's ssl only exposes the leaf when verification fails (which is exactly
    our case), so shell out to `openssl s_client -showcerts` to capture every
    certificate the server sends, regardless of trust.
    """
    import subprocess

    proc = subprocess.run(
        [
            "openssl", "s_client", "-connect", f"{ip}:{port}",
            "-servername", host, "-showcerts",
        ],
        input=b"",
        capture_output=True,
        timeout=12,
    )
    out = proc.stdout.decode("latin-1", "replace")
    chain: list[x509.Certificate] = []
    marker = "-----BEGIN CERTIFICATE-----"
    end = "-----END CERTIFICATE-----"
    idx = 0
    while True:
        start = out.find(marker, idx)
        if start < 0:
            break
        stop = out.find(end, start)
        if stop < 0:
            break
        pem = out[start : stop + len(end)]
        idx = stop + len(end)
        try:
            chain.append(x509.load_pem_x509_certificate(pem.encode()))
        except ValueError:
            continue
    return chain


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cdn-host", default=DEFAULT_CDN_HOST)
    ap.add_argument("--cdn-ip", default=DEFAULT_CDN_IP)
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--mqtt-host", default=DEFAULT_MQTT_HOST)
    ap.add_argument("--mqtt-ip", default=DEFAULT_MQTT_IP)
    ap.add_argument("--mqtt-port", type=int, default=DEFAULT_MQTT_PORT)
    ap.add_argument("--ca", type=Path, default=DEFAULT_CA, help="Local reference CA for comparison")
    ap.add_argument("--save", type=Path, help="Write the reconstructed mqtt_cert_srv anchor to this file")
    args = ap.parse_args()

    print("Lepro MQTT trust-anchor reconstruction")
    print("=" * 60)

    # 1) The anchor the device installs == bytes the CDN serves at `root`.
    installed_ca: x509.Certificate | None = None
    try:
        status, body = fetch_cdn_body(args.cdn_host, args.cdn_ip, args.root)
        print(f"\n[CDN] GET https://{args.cdn_host}/{args.root.lstrip('/')} via {args.cdn_ip}")
        print(f"      status      : {status}")
        print(f"      body length : {len(body)} bytes")
        if args.save:
            args.save.write_bytes(body)
            print(f"      saved anchor: {args.save}")
        installed_ca = x509.load_pem_x509_certificate(body)
        print(f"      => mqtt_cert_srv subject: {_name(installed_ca.subject)}")
        print(f"      => mqtt_cert_srv SPKI   : {_spki_fp(installed_ca)}")
    except Exception as exc:  # noqa: BLE001 - diagnostic tool
        print(f"\n[CDN] fetch failed: {exc!r}")

    # 2) Local reference CA (what the repo currently thinks is the CA).
    local_ca: x509.Certificate | None = None
    if args.ca.is_file():
        local_ca = x509.load_pem_x509_certificate(args.ca.read_bytes())
        print(f"\n[local] {args.ca}")
        print(f"      subject: {_name(local_ca.subject)}")
        print(f"      SPKI   : {_spki_fp(local_ca)}")
        if installed_ca is not None:
            same = _spki_fp(local_ca) == _spki_fp(installed_ca)
            print(f"      CDN serves the SAME CA key as local ca.pem: {same}")

    # 3) The chain the broker actually presents.
    print(f"\n[broker] {args.mqtt_host}:{args.mqtt_port} via {args.mqtt_ip}")
    try:
        chain = fetch_broker_chain(args.mqtt_host, args.mqtt_ip, args.mqtt_port)
    except Exception as exc:  # noqa: BLE001
        print(f"      handshake/chain fetch failed: {exc!r}")
        return 2
    for i, c in enumerate(chain):
        role = "leaf" if i == 0 else ("CA" if c.subject == c.issuer else "intermediate")
        print(f"      [{i}] {role:12} subject={_name(c.subject)}")
        print(f"          issuer={_name(c.issuer)}")
        print(f"          cert_fp={_cert_fp(c)}")
        if role != "leaf":
            print(f"          SPKI   ={_spki_fp(c)}")

    # 4) The verdict: does the installed anchor verify the broker chain?
    print("\n" + "=" * 60)
    print("VERDICT")
    broker_ca = next((c for c in chain if c.subject == c.issuer), None)
    if installed_ca is None:
        print("  Could not reconstruct mqtt_cert_srv (CDN fetch failed) — rerun on the IoT network.")
        return 2
    if broker_ca is None:
        print("  Broker did not present a self-signed CA in its chain.")
    else:
        names_match = broker_ca.subject == installed_ca.subject
        keys_match = _spki_fp(broker_ca) == _spki_fp(installed_ca)
        print(f"  broker in-chain CA subject == installed CA subject : {names_match}")
        print(f"  broker in-chain CA key     == installed CA key     : {keys_match}")
        if names_match and not keys_match:
            print()
            print("  >> ROOT CAUSE: same CA *name*, different CA *key*.")
            print("     The broker chain was signed by a DIFFERENT 'Lepro Mock CA' keypair")
            print("     than the ca.pem the CDN serves and the bulb installs. The bulb's")
            print("     mbedTLS rejects it with certificate-signature-failure => alert 48")
            print("     unknown_ca. This is lab PKI deployment drift, NOT a firmware bug.")
            print("     Fix (not applied): redeploy the broker with a server cert signed by")
            print("     the current ca.pem (server-fullchain.pem/server.key in deploy/).")
        elif keys_match:
            print()
            print("  >> Installed CA key matches the broker's signing CA.")
            print("     Content is correct -> if the bulb still emits unknown_ca, it is the")
            print("     stale one-shot client binding (needs a cold boot with the cert already")
            print("     present before the first 'network connected' event).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
