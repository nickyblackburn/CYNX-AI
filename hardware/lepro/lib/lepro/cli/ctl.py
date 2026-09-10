#!/usr/bin/env python3
"""Control Lepro ZB1 string lights over BLE (on/off/color/modes)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from lepro.bond import normalize_mac
from lepro.cli._common import print_dry_run, run_control, run_dry_control
from lepro.commands import color_hsv, power_off, power_on
from lepro.modes import DIY_EFFECTS, debug_payload, format_mode_catalog, load_preset, preset_duration_ms, preset_frames, resolve_mode


async def _cmd_mode_play(args: argparse.Namespace) -> None:
    mac = normalize_mac(args.mac)
    try:
        preset = load_preset(args.target)
        frames = preset_frames(preset)
        if args.frame is not None:
            frames = [frames[args.frame]]
        duration_s = preset_duration_ms(preset) / 1000.0

        async def _play_once() -> None:
            for i, payload in enumerate(frames):
                print(f"Frame {i + 1}/{len(frames)}")
                if args.dry_run:
                    print_dry_run(await run_dry_control(mac, payload))
                else:
                    await run_control(mac, payload, debug_rx=args.debug_rx)

        if args.dry_run or not args.loop:
            await _play_once()
        else:
            while True:
                await _play_once()
                await asyncio.sleep(duration_s * len(frames))
        return
    except FileNotFoundError:
        pass

    payload = resolve_mode(
        args.target,
        color=args.color,
        effect=args.effect,
        speed=args.speed,
        brightness=args.brightness,
        bulb_count=args.length,
    )
    await run_control(
        mac, payload, dry_run=args.dry_run, debug_rx=args.debug_rx
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Control Lepro ZB1 over BLE")
    p.add_argument("--mac", help="Target light MAC (required for control commands)")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("on", "off"):
        s = sub.add_parser(name, help=f"Turn light {name}")
        s.add_argument("--dry-run", action="store_true")
        s.add_argument("--debug-rx", action="store_true")

    c = sub.add_parser("color", help="Set solid color via HSV")
    c.add_argument("--hue", type=float, required=True)
    c.add_argument("--sat", type=int, default=1000)
    c.add_argument("--val", type=int, default=1000)
    c.add_argument("--brightness", type=int, default=1000)
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--debug-rx", action="store_true")

    m = sub.add_parser("mode", help="Scene / DIY modes")
    m_sub = m.add_subparsers(dest="mode_cmd", required=True)
    m_sub.add_parser("list", help="Show available modes and presets")

    md = m_sub.add_parser("debug", help="Print DP JSON (no BLE)")
    md.add_argument("target")
    md.add_argument("--color", default="FFAA00")
    md.add_argument("--effect", default="Steady", choices=DIY_EFFECTS)
    md.add_argument("--speed", type=int, default=50)
    md.add_argument("--brightness", type=int, default=1000)
    md.add_argument("--frame", type=int, default=0)
    md.add_argument("--length", type=int)
    md.add_argument("--mac", default="10:20:BA:31:B2:BA")

    mp = m_sub.add_parser("play", help="Play a built-in mode or preset")
    mp.add_argument("target")
    mp.add_argument("--color", default="FFAA00")
    mp.add_argument("--effect", default="Steady", choices=DIY_EFFECTS)
    mp.add_argument("--speed", type=int, default=50)
    mp.add_argument("--brightness", type=int, default=1000)
    mp.add_argument("--length", type=int)
    mp.add_argument("--frame", type=int)
    mp.add_argument("--loop", action="store_true")
    mp.add_argument("--dry-run", action="store_true")
    mp.add_argument("--debug-rx", action="store_true")

    args = p.parse_args()

    if args.cmd == "mode":
        if args.mode_cmd == "list":
            print(format_mode_catalog())
            return
        if args.mode_cmd == "debug":
            mac = normalize_mac(args.mac)
            try:
                payload = resolve_mode(
                    args.target,
                    color=args.color,
                    effect=args.effect,
                    speed=args.speed,
                    brightness=args.brightness,
                    bulb_count=args.length,
                )
            except KeyError:
                preset = load_preset(args.target)
                frames = preset_frames(preset)
                idx = args.frame
                if idx < 0 or idx >= len(frames):
                    raise SystemExit(f"frame {idx} out of range") from None
                payload = frames[idx]
            info = debug_payload(mac, payload)
            print(json.dumps(info, indent=2))
            return
        if not args.mac:
            raise SystemExit("--mac required for mode play")
        asyncio.run(_cmd_mode_play(args))
        return

    if not args.mac:
        raise SystemExit("--mac required")

    mac = normalize_mac(args.mac)
    if args.cmd == "on":
        asyncio.run(run_control(mac, power_on(), dry_run=args.dry_run, debug_rx=args.debug_rx))
    elif args.cmd == "off":
        asyncio.run(run_control(mac, power_off(), dry_run=args.dry_run, debug_rx=args.debug_rx))
    elif args.cmd == "color":
        payload = color_hsv(args.hue, args.sat, args.val, args.brightness)
        asyncio.run(run_control(mac, payload, dry_run=args.dry_run, debug_rx=args.debug_rx))


if __name__ == "__main__":
    main()
