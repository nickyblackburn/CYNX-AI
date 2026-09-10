#!/usr/bin/env python3
"""BLE WiFi + MQTT provisioning (opcode 0x1008) for Lepro ZB1."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from lepro.config import config_path, load_config
from lepro.provision import _add_cert_refresh_flags, cmd_provision


def _apply_config(args: argparse.Namespace, cfg_path: Path | None) -> None:
    path = config_path(cfg_path)
    if not path.is_file():
        return
    cfg = load_config(path)
    args.domain = cfg.lab.cdn_host
    args.host = cfg.lab.mqtt_host
    args.port = cfg.lab.mqtt_port
    args.ssid = cfg.wifi.ssid
    args.pass_ = cfg.wifi.password


_DEFAULTS = {
    "domain": "dvc-eu-iot.example.home",
    "root": "pub/cert/AmazonRootCA13.pem",
    "cert": "device/cert/did/debug/ver/1/sign/lepro",
    "host": "mqtt.example.home",
    "port": "8883",
    "ssid": "your-iot-wifi",
    "pass_": "secret",
}


def main() -> None:
    p = argparse.ArgumentParser(
        description="Provision Lepro ZB1 onto WiFi + MQTT (reads lepro-lab.toml when present)"
    )
    p.add_argument("--mac", required=True)
    p.add_argument("--config", type=Path, help="lepro-lab.toml path")
    p.add_argument("--ssid", default=_DEFAULTS["ssid"])
    p.add_argument("--pass", dest="pass_", default=_DEFAULTS["pass_"])
    p.add_argument("--domain", default=_DEFAULTS["domain"])
    p.add_argument("--root", default=_DEFAULTS["root"])
    p.add_argument("--cert", default=_DEFAULTS["cert"])
    p.add_argument("--host", default=_DEFAULTS["host"])
    p.add_argument("--port", default=_DEFAULTS["port"])
    p.add_argument("--uid", help="Optional account uid")
    p.add_argument("--debug-rx", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    _add_cert_refresh_flags(p)

    args = p.parse_args()
    _apply_config(args, args.config)
    asyncio.run(cmd_provision(args))


if __name__ == "__main__":
    main()
