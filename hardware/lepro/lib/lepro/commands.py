#!/usr/bin/env python3
"""DP JSON builders and encrypted page helpers for Lepro LP BLE control."""

from __future__ import annotations

import colorsys
import json
from typing import Any

from lepro.crypto import encrypt_dp_json
from lepro.protocol import OP_DP_CMD, OP_DP_VALUE, build_packet_opcode, build_packets_fragmented

# Gson DpValue types serialize top-level keys (com.lepro.iotCore.mqtt.model.*).
# TestProvisioningActivity: on/off {"d1":0|1}, getDpState '["d1",…]' string to native.
DpPayload = dict[str, Any] | list[str]


def power_on(brightness: int = 1000) -> dict[str, Any]:
    """Turn lamp on. APK test harness uses {"d1":1} only."""
    payload: dict[str, Any] = {"d1": 1}
    if brightness != 1000:
        payload["d2"] = 1
        payload["d3"] = max(10, min(1000, brightness))
    return payload


def power_off() -> dict[str, Any]:
    return {"d1": 0}


def color_hsv(hue: float, sat: int = 1000, val: int = 1000, brightness: int = 1000) -> dict[str, Any]:
    h = int(hue) % 360
    s = max(0, min(1000, sat))
    v = max(0, min(1000, val))
    b = max(0, min(1000, brightness))
    d5 = f"{h:04X}{s:04X}{v:04X}"
    return {"d1": 1, "d2": 1, "d3": b, "d5": d5}


def color_rgb(r: int, g: int, b: int, brightness: int = 1000) -> dict[str, Any]:
    r, g, b = (max(0, min(255, c)) for c in (r, g, b))
    h_f, s_f, v_f = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return color_hsv(h_f * 360, int(s_f * 1000), int(v_f * 1000), brightness)


def status_query(fields: tuple[str, ...] | None = None) -> list[str]:
    """getDpState query — APK passes a JSON array string to bleGetDpState()."""
    if fields is not None:
        return list(fields)
    # ZB1 / string lights (MqttConnectionPool RGBIC_LIGHT_ZB1 path)
    return ["d1", "d2", "d3", "d4", "d5", "d50", "d52"]


def segment_solid(
    rgb: tuple[int, int, int] = (255, 255, 255),
    brightness: int = 1000,
    *,
    bulb_count: int | None = None,
) -> dict[str, Any]:
    from lepro.modes import default_bulb_count, effect_tail

    r, g, b = (max(0, min(255, c)) for c in rgb)
    colors_str = f"{r:02X}{g:02X}{b:02X}"
    n = bulb_count if bulb_count is not None else default_bulb_count()
    d50 = f"N01:P10001{colors_str}F210001{n:04X}U3V3{effect_tail('Steady')};"
    return {"d1": 1, "d2": 2, "d50": d50, "d52": max(0, min(1000, brightness))}


def dp_json_text(payload: DpPayload) -> str:
    return json.dumps(payload, separators=(",", ":"))


def build_dp_value_packets(
    mac: str,
    seq: int,
    payload: DpPayload,
    *,
    session_rand: int,
    max_payload: int = 128,
) -> tuple[list[bytes], int]:
    """Encrypt DP JSON and return (packets, next_seq)."""
    ct = encrypt_dp_json(mac, dp_json_text(payload), session_rand=session_rand)
    packets = build_packets_fragmented(seq, OP_DP_VALUE, ct, max_payload, encrypted=True)
    return packets, seq + len(packets)


def build_get_dp_state_packet(
    mac: str,
    seq: int,
    payload: DpPayload,
    *,
    session_rand: int,
) -> bytes:
    """Encrypted getDpState query on 0x1102."""
    ct = encrypt_dp_json(mac, dp_json_text(payload), session_rand=session_rand)
    return build_packet_opcode(seq, OP_DP_CMD, ct)


def build_dp_ciphertext_packets(
    seq: int,
    ciphertext: bytes,
    *,
    max_payload: int = 128,
) -> tuple[list[bytes], int]:
    packets = build_packets_fragmented(seq, OP_DP_VALUE, ciphertext, max_payload, encrypted=True)
    return packets, seq + len(packets)


def build_raw_cmd_packet(seq: int, token: bytes) -> bytes:
    """Opaque auth token on 0x1102 (no encryption)."""
    return build_packet_opcode(seq, OP_DP_CMD, token)
