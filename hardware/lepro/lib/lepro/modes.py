#!/usr/bin/env python3
"""
Fancy light modes — work-mode catalog, d50/d6 builders, preset loader.

Target device: Lepro ZB1 string lights (RGBIC_LIGHT_ZB1), not TB1 tree strips.
TB1 presets in tmp/LeproTB1/presets/ are reference-only (196-LED topology).
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from lepro.commands import DpPayload, dp_json_text

# ── Device profile ────────────────────────────────────────────────────────────

DEVICE_SERIES = os.environ.get("LEPRO_SERIES", "ZB1")

# ZB1: bulb string; neon_length (d53) from device status, app default 15
# (PaletteWarmWhiteFragment.java — reads DpStatusData.neon_length)
ZB1_DEFAULT_BULB_COUNT = 15

# TB1 tree strip (LeproTB1 captures only — do not replay on ZB1)
TB1_LED_COUNT = 196
TB1_RING_LENGTHS = (88, 62, 46)

# APK built-in bulb scenes (BasicEffectBulbLampAdapter.java:61-68), dpType "d6"
APK_SCENE_GRADIENT = (
    "000032006401000003E803E80000000001001D03E803E80000000001003C03E803E800000000"
    "01007803E803E8000000000100B403E803E8000000000100F003E803E80000000001012C03E803E800000000"
)
APK_SCENE_RAINBOW = (
    "000032006402000003E803E80000000002001D03E803E80000000002003C03E803E800000000"
    "02007803E803E8000000000200B403E803E8000000000200F003E803E80000000002012C03E803E800000000"
)

DIY_EFFECTS = (
    "Steady",
    "Breathe",
    "Gradient",
    "Leftward",
    "Rightward",
    "Circle",
    "Flash",
    "CenterOut",
    "CenterIn",
)

# APK type id per effect name (LightDiyModeAdapter / libiot-core.so diyValue)
EFFECT_APK_TYPE: dict[str, int] = {
    "Steady": 1,
    "Breathe": 2,
    "Rightward": 3,
    "Leftward": 4,
    "Gradient": 5,
    "Circle": 7,
    "Flash": 9,
    "CenterOut": 12,
    "CenterIn": 13,
}

from lepro.paths import repo_path

PRESETS_DIR = repo_path("tmp/LeproTB1/presets")

# ── Work modes (Dp2WorkMode.java) ─────────────────────────────────────────────

WORK_MODE_WHITE = 0
WORK_MODE_COLOR = 1
WORK_MODE_SCENE = 2  # RGB-IC scene mode: d50 animations on ZB1/TB1-class devices
WORK_MODE_MUSIC = 3

WORK_MODES: dict[int, str] = {
    WORK_MODE_WHITE: "white (CCT)",
    WORK_MODE_COLOR: "solid RGB (d5 HSV)",
    WORK_MODE_SCENE: "scene / segmented (d50 or d6)",
    WORK_MODE_MUSIC: "music sync (d60+)",
}


def default_bulb_count() -> int:
    return ZB1_DEFAULT_BULB_COUNT if DEVICE_SERIES == "ZB1" else TB1_LED_COUNT


_HEX6 = re.compile(r"^[0-9A-Fa-f]{6}$")


def hsv_hex(hue: float, sat: int = 1000, val: int = 1000) -> str:
    """12-char HSV protocol string (Hsv.toProtocolString)."""
    h = int(hue) % 360
    s = max(0, min(1000, sat))
    v = max(0, min(1000, val))
    return f"{h:04X}{s:04X}{v:04X}"


def rgbic_scene(d50: str, *, brightness: int = 1000, power: bool = True) -> dict[str, Any]:
    """Segmented / RGB-IC scene mode (d2=2 + d50 + d52)."""
    payload: dict[str, Any] = {
        "d2": WORK_MODE_SCENE,
        "d50": d50,
        "d52": max(100, min(1000, brightness)),
    }
    if power:
        payload["d1"] = 1
    return payload


def white_mode(brightness: int = 500, temp: int = 400, *, power: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "d2": WORK_MODE_WHITE,
        "d3": max(10, min(1000, brightness)),
        "d4": max(0, min(1000, temp)),
    }
    if power:
        payload["d1"] = 1
    return payload


def legacy_scene_d6(d6: str, *, power: bool = True) -> dict[str, Any]:
    """Legacy bulb gradient/rainbow scenes on d6 (EffectEntity dpType=d6)."""
    payload: dict[str, Any] = {"d2": WORK_MODE_SCENE, "d6": d6}
    if power:
        payload["d1"] = 1
    return payload


def scene_gradient(*, power: bool = True) -> dict[str, Any]:
    return legacy_scene_d6(APK_SCENE_GRADIENT, power=power)


def scene_rainbow(*, power: bool = True) -> dict[str, Any]:
    return legacy_scene_d6(APK_SCENE_RAINBOW, power=power)


def _speed_to_hex(speed: int) -> str:
    s = max(0, min(100, int(speed)))
    if s <= 0:
        return "1000"
    raw = int(round(-117.41 * math.log(s + 1) + 597.75))
    return f"0{raw:03X}"


def _speed_to_hex_center(speed: int) -> str:
    """Center-side native clamps speed_time below 0x41 to 0x40 (diyValueCenterSide)."""
    sp = _speed_to_hex(speed)
    val = int(sp, 16)
    if val < 0x40:
        val = 0x40
    return f"{val:04X}"


def effect_tail(name: str, speed: int = 50) -> str:
    """Six DIY effect tails confirmed in D50_FORMAT.md."""
    sp = _speed_to_hex(speed)
    match name:
        case "Steady":
            return "000640000E1"
        case "Breathe":
            return f"000640000E4{sp}0000{sp}1664"
        case "Gradient":
            return f"100640000E3{sp}C2O6{sp}"
        case "Leftward":
            return f"00164{sp}E1"
        case "Rightward":
            return f"00264{sp}E1"
        case "Circle":
            return f"100640000E1C2O6{sp}"
        case "Flash" | "CenterOut" | "CenterIn":
            raise ValueError(
                f"effect {name!r} uses a non-flat d50 envelope; use build_d50_flash() or build_d50_center_solid()"
            )
        case _:
            raise ValueError(f"unknown effect {name!r}; expected one of {DIY_EFFECTS}")


def build_d50_flash(color: str, *, speed: int = 50) -> str:
    """Type 9 Flash — no F21 length segment; U3F3 opcode (diyValue case 9, lightMode=1)."""
    c = color.lstrip("#").upper()
    if not _HEX6.match(c):
        raise ValueError(f"{color!r} is not a 6-hex RGB color")
    sp = _speed_to_hex(speed)
    return f"N01:P10001{c}U3F300101E2{sp};"


def build_d50_center_solid(
    color: str,
    effect: str,
    *,
    speed: int = 50,
    bulb_count: int | None = None,
) -> str:
    """Types 12/13 center-side animation on uniform color (#V:02 + #I00/#I01)."""
    if effect not in ("CenterOut", "CenterIn"):
        raise ValueError(f"center effect must be CenterOut or CenterIn, got {effect!r}")
    c = color.lstrip("#").upper()
    if not _HEX6.match(c):
        raise ValueError(f"{color!r} is not a 6-hex RGB color")
    n = bulb_count if bulb_count is not None else default_bulb_count()
    ic1 = (n + 1) // 2
    ic2 = n - ic1
    sp = _speed_to_hex_center(speed)
    if effect == "CenterOut":
        tail1, tail2 = f"00264{sp}E1", f"00164{sp}E1"
    else:
        tail1, tail2 = f"00164{sp}E1", f"00264{sp}E1"
    header = f"#V:02{ic1:02X}{n:02X}00000000{ic2:02X}00000000;"
    seg0 = f"#I00:N01:P10001{c}F210001{ic1:04X}U3V3{tail1};"
    seg1 = f"#I01:N01:P10001{c}F210001{ic2:04X}U3V3{tail2};"
    return header + seg0 + seg1


def build_d50_solid(
    color: str,
    effect: str = "Steady",
    *,
    speed: int = 50,
    bulb_count: int | None = None,
) -> str:
    """Single-color whole-string d50 (one group, all bulbs same color)."""
    if effect == "Flash":
        return build_d50_flash(color, speed=speed)
    if effect in ("CenterOut", "CenterIn"):
        return build_d50_center_solid(color, effect, speed=speed, bulb_count=bulb_count)
    c = color.lstrip("#").upper()
    if not _HEX6.match(c):
        raise ValueError(f"{color!r} is not a 6-hex RGB color")
    n = bulb_count if bulb_count is not None else default_bulb_count()
    tail = effect_tail(effect, speed)
    return f"N01:P10001{c}F210001{n:04X}U3V3{tail};"


def build_d50_from_leds(
    leds: list[str | None],
    effect: str = "Steady",
    *,
    speed: int = 50,
    bulb_count: int | None = None,
) -> str:
    """Full-string d50 from per-bulb colors."""
    n = bulb_count if bulb_count is not None else default_bulb_count()
    if len(leds) != n:
        raise ValueError(f"leds must have {n} entries, got {len(leds)}")

    norm = ["000000" if c is None else c.lstrip("#").upper() for c in leds]
    runs: list[tuple[str, int]] = []
    for color in norm:
        if runs and runs[-1][0] == color:
            runs[-1] = (color, runs[-1][1] + 1)
        else:
            runs.append((color, 1))

    colors = "".join(c for c, _ in runs)
    lengths = "".join(f"{n:04X}" for _, n in runs)
    n_groups = len(runs)
    tail = effect_tail(effect, speed)
    return f"N01:P1000{n_groups}{colors}F21000{n_groups}{lengths}U3V3{tail};"


def diy_solid(
    color: str,
    effect: str = "Steady",
    *,
    speed: int = 50,
    brightness: int = 1000,
    bulb_count: int | None = None,
) -> dict[str, Any]:
    return rgbic_scene(
        build_d50_solid(color, effect, speed=speed, bulb_count=bulb_count),
        brightness=brightness,
    )


@dataclass(frozen=True)
class ModeSpec:
    id: str
    title: str
    dp_keys: tuple[str, ...]
    description: str
    builder: str  # human hint for CLI


BUILTIN_MODES: tuple[ModeSpec, ...] = (
    ModeSpec("white", "White / temperature", ("d1", "d2", "d3", "d4"), "CCT white mode", "white_mode()"),
    ModeSpec("color", "Solid RGB", ("d1", "d2", "d5", "d3"), "HSV on d5", "color_hsv()"),
    ModeSpec("segment-solid", "Segment solid", ("d1", "d2", "d50", "d52"), "Simple N01 d50", "segment_solid()"),
    ModeSpec("diy", "DIY solid + effect", ("d1", "d2", "d50", "d52"), f"Effects: {', '.join(DIY_EFFECTS)}", "diy_solid()"),
    ModeSpec("gradient", "Bulb gradient (d6)", ("d1", "d2", "d6"), "APK built-in", "scene_gradient()"),
    ModeSpec("rainbow", "Bulb rainbow (d6)", ("d1", "d2", "d6"), "APK built-in", "scene_rainbow()"),
    ModeSpec("preset", "Captured preset (TB1)", ("d1", "d2", "d50", "d52"), "TB1-only refs — not for ZB1 replay", "load_preset()"),
)


def list_presets(presets_dir: Path | None = None) -> list[Path]:
    root = presets_dir or PRESETS_DIR
    if not root.is_dir():
        return []
    return sorted(root.glob("*.json"))


def load_preset(name: str, *, presets_dir: Path | None = None) -> dict[str, Any]:
    """Load preset JSON by stem name (e.g. 'hulk')."""
    root = presets_dir or PRESETS_DIR
    path = root / f"{name}.json"
    if not path.is_file():
        matches = list(root.glob(f"*{name}*.json"))
        if len(matches) == 1:
            path = matches[0]
        elif matches:
            names = ", ".join(p.stem for p in matches)
            raise FileNotFoundError(f"ambiguous preset {name!r}: {names}")
        else:
            raise FileNotFoundError(f"preset not found: {name!r} (looked in {root})")
    return json.loads(path.read_text())


def preset_frames(preset: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize preset to list of frame payloads (each gets d1=1 if missing)."""
    if "frames" in preset:
        frames = preset["frames"]
    elif "payload" in preset:
        frames = [preset["payload"]]
    else:
        raise ValueError("preset must have 'frames' or 'payload'")

    out: list[dict[str, Any]] = []
    for frame in frames:
        merged = dict(frame)
        merged.setdefault("d1", 1)
        merged.setdefault("d2", WORK_MODE_SCENE)
        out.append(merged)
    return out


def preset_duration_ms(preset: dict[str, Any], default: int = 4000) -> int:
    return int(preset.get("frame_duration_ms", default))


def resolve_mode(name: str, **kwargs: Any) -> DpPayload:
    """Build a single DP payload from a built-in mode id."""
    n = name.lower().replace("-", "_")
    if n == "white":
        return white_mode(kwargs.get("brightness", 500), kwargs.get("temp", 400))
    if n == "gradient":
        return scene_gradient()
    if n == "rainbow":
        return scene_rainbow()
    if n == "diy":
        color = kwargs.get("color", "FFAA00")
        effect = kwargs.get("effect", "Steady")
        return diy_solid(
            color,
            effect,
            speed=kwargs.get("speed", 50),
            brightness=kwargs.get("brightness", 1000),
            bulb_count=kwargs.get("bulb_count"),
        )
    if n == "segment_solid":
        from lepro.commands import segment_solid as _seg

        rgb = kwargs.get("rgb", (255, 255, 255))
        return _seg(
            rgb=tuple(rgb),
            brightness=kwargs.get("brightness", 1000),
            bulb_count=kwargs.get("bulb_count"),
        )
    raise KeyError(f"unknown mode {name!r}; use list_modes() or a preset name")


def debug_payload(mac: str, payload: DpPayload) -> dict[str, Any]:
    """Return JSON text + encrypted size + estimated BLE page count."""
    from lepro.commands import build_dp_value_packets, build_get_dp_state_packet

    text = dp_json_text(payload)
    if isinstance(payload, list):
        from lepro.protocol import parse_packet

        pkt = build_get_dp_state_packet(mac, 0, payload, session_rand=0)
        hdr = parse_packet(pkt)
        ct_len = len(hdr.payload) if hdr else 0
        return {"json": text, "opcode": "0x1102", "packets": 1, "ciphertext_bytes": ct_len}
    from lepro.protocol import parse_packet

    packets, _ = build_dp_value_packets(mac, 0, payload, session_rand=0)
    ct_lens = [len(parse_packet(p).payload) for p in packets if parse_packet(p)]
    return {
        "json": text,
        "json_len": len(text),
        "opcode": "0x1100",
        "packets": len(packets),
        "ciphertext_bytes": ct_lens,
        "needs_bulk_pre_pages": len(packets) > 1 or (ct_lens and ct_lens[0] > 32),
    }


def format_mode_catalog() -> str:
    lines = [
        f"Device profile: {DEVICE_SERIES} (override: LEPRO_SERIES=…)",
        f"Default bulb count: {default_bulb_count()} (ZB1 uses d53/neon_length; set --length)",
        "",
        "Work modes (d2):",
        "",
    ]
    for val, label in WORK_MODES.items():
        lines.append(f"  {val}  {label}")
    lines.extend(["", "Built-in commands:", ""])
    for spec in BUILTIN_MODES:
        keys = ", ".join(spec.dp_keys)
        lines.append(f"  {spec.id:<14} {spec.title}")
        lines.append(f"                 keys: {keys}")
        lines.append(f"                 {spec.description}")
    presets = list_presets()
    if presets:
        lines.extend([
            "",
            f"TB1 reference presets ({PRESETS_DIR}) — wrong topology for ZB1:",
            "",
        ])
        for p in presets:
            try:
                data = json.loads(p.read_text())
                n_frames = len(data.get("frames", [data.get("payload")]))
                desc = data.get("description", "")[:70]
                lines.append(f"  {p.stem:<20} {n_frames} frame(s)  {desc}")
            except Exception:
                lines.append(f"  {p.stem}")
    lines.extend(["", "DIY effects (d50 tail):", f"  {', '.join(DIY_EFFECTS)}"])
    return "\n".join(lines)


def iter_preset_play(name: str, **kwargs: Any) -> Iterator[tuple[dict[str, Any], int]]:
    preset = load_preset(name, presets_dir=kwargs.get("presets_dir"))
    duration = preset_duration_ms(preset)
    for frame in preset_frames(preset):
        yield frame, duration
