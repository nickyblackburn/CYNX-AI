"""Load shared lab config from lepro-lab.toml."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from lepro.paths import repo_path

DEFAULT_CONFIG_PATH = repo_path("lepro-lab.toml")
ENV_CONFIG = "LEPRO_LAB_CONFIG"


@dataclass(frozen=True)
class DeviceConfig:
    id: str = ""
    friendly_name: str = "patio-lights"


@dataclass(frozen=True)
class LabConfig:
    cdn_host: str = "dvc-eu-iot.example.home"
    mqtt_host: str = "mqtt.example.home"
    mqtt_port: str = "8883"


@dataclass(frozen=True)
class WifiConfig:
    ssid: str = "your-iot-wifi"
    password: str = "secret"


@dataclass(frozen=True)
class BridgeConfig:
    home_broker: str = "mqtt://127.0.0.1:1883"
    lepro_broker: str = ""
    ca_file: str = "deploy/docker/certs/ca.pem"
    topic_prefix: str = ""


@dataclass(frozen=True)
class LeproLabConfig:
    device: DeviceConfig
    lab: LabConfig
    wifi: WifiConfig
    bridge: BridgeConfig


def config_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    env = os.environ.get(ENV_CONFIG)
    if env:
        return Path(env)
    return DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None) -> LeproLabConfig:
    cfg_path = config_path(path)
    if not cfg_path.is_file():
        return LeproLabConfig(
            device=DeviceConfig(),
            lab=LabConfig(),
            wifi=WifiConfig(),
            bridge=BridgeConfig(),
        )
    data = tomllib.loads(cfg_path.read_text())
    device = data.get("device", {})
    lab = data.get("lab", {})
    wifi = data.get("wifi", {})
    bridge = data.get("bridge", {})
    device_cfg = DeviceConfig(
        id=str(device.get("id", "")),
        friendly_name=str(device.get("friendly_name", "patio-lights")),
    )
    lab_cfg = LabConfig(
        cdn_host=str(lab.get("cdn_host", LabConfig.cdn_host)),
        mqtt_host=str(lab.get("mqtt_host", LabConfig.mqtt_host)),
        mqtt_port=str(lab.get("mqtt_port", LabConfig.mqtt_port)),
    )
    wifi_cfg = WifiConfig(
        ssid=str(wifi.get("ssid", WifiConfig.ssid)),
        password=str(wifi.get("password", wifi.get("pass", WifiConfig.password))),
    )
    bridge_cfg = BridgeConfig(
        home_broker=str(bridge.get("home_broker", BridgeConfig.home_broker)),
        lepro_broker=str(bridge.get("lepro_broker", "")),
        ca_file=str(bridge.get("ca_file", BridgeConfig.ca_file)),
        topic_prefix=str(bridge.get("topic_prefix", device_cfg.friendly_name)),
    )
    return LeproLabConfig(
        device=device_cfg,
        lab=lab_cfg,
        wifi=wifi_cfg,
        bridge=bridge_cfg,
    )
