#!/usr/bin/env python3
"""Download, patch, and verify Lepro ZB1 firmware images."""

from __future__ import annotations

import argparse
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

from lepro.firmware_profile import load_profiles, resolve_profile
from lepro.patch_cdn import DEFAULT_CERT, patch_firmware
from lepro.paths import repo_path


def _resolve(
    profiles_path: Path | None,
    profile_id: str | None,
    firmware_path: Path | None,
):
    profiles = load_profiles(profiles_path)
    if firmware_path is not None:
        return resolve_profile(
            profiles, firmware_path=firmware_path, profile_id=profile_id
        ), profiles
    return resolve_profile(profiles, profile_id=profile_id), profiles


def cmd_fetch(args: argparse.Namespace) -> None:
    profile, _ = _resolve(args.profiles_file, args.profile, None)
    if not profile.ota_url:
        raise SystemExit(f"Profile {profile.id!r} has no ota_url")
    out = args.output or profile.stock_image
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {profile.ota_url}")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(profile.ota_url, context=ctx) as resp:
        data = resp.read()
    out.write_bytes(data)
    print(f"Wrote {out} ({len(data)} bytes)")


def cmd_patch(args: argparse.Namespace) -> None:
    profile, profiles = _resolve(args.profiles_file, args.profile, args.firmware)
    firmware = args.firmware or profile.stock_image
    if args.firmware is not None and args.profile is None:
        profile = resolve_profile(profiles, firmware_path=firmware, profile_id=None)
    output = args.output or profile.patched_image
    if args.chip is not None:
        from dataclasses import replace

        profile = replace(profile, chip=args.chip)

    patch_firmware(
        profile,
        firmware_path=firmware,
        output_path=output,
        cert_path=args.cert,
        cert_host=getattr(args, "cert_host", None),
        cert_connect=getattr(args, "cert_connect", None),
        bundle_off=getattr(args, "bundle_off", None),
        pin_off=getattr(args, "pin_off", None),
        verify_only=False,
        force=getattr(args, "force", False),
    )


def cmd_verify(args: argparse.Namespace) -> None:
    profile, profiles = _resolve(args.profiles_file, args.profile, args.firmware)
    firmware = args.firmware or profile.patched_image
    if args.firmware is not None and args.profile is None:
        profile = resolve_profile(profiles, firmware_path=firmware, profile_id=None)
    if args.chip is not None:
        from dataclasses import replace

        profile = replace(profile, chip=args.chip)

    patch_firmware(
        profile,
        firmware_path=firmware,
        output_path=profile.patched_image,
        cert_path=args.cert,
        cert_host=getattr(args, "cert_host", None),
        cert_connect=getattr(args, "cert_connect", None),
        verify_only=True,
    )


def main() -> None:
    default_profiles = repo_path("firmware/patch-profiles.toml")
    p = argparse.ArgumentParser(description="Lepro ZB1 firmware fetch / patch / verify")
    sub = p.add_subparsers(dest="cmd", required=True)

    profile_kw = dict(
        default=None,
        help="Firmware profile id (default: auto-match from firmware filename or default_profile)",
    )
    profiles_file_kw = dict(
        type=Path,
        default=None,
        help=f"Path to patch-profiles.toml (default: {default_profiles})",
    )

    f = sub.add_parser("fetch", help="Download stock firmware from Lepro OTA CDN")
    f.add_argument("--profile", **profile_kw)
    f.add_argument("--profiles-file", **profiles_file_kw)
    f.add_argument("-o", "--output", type=Path, default=None)

    patch = sub.add_parser("patch", help="Patch CDN cert-bundle pin for lab hijack")
    patch.add_argument("--profile", **profile_kw)
    patch.add_argument("--profiles-file", **profiles_file_kw)
    patch.add_argument("-f", "--firmware", type=Path, default=None)
    patch.add_argument("-c", "--cert", type=Path, default=None)
    patch.add_argument(
        "--cert-host",
        default=None,
        metavar="HOST[:PORT]",
        help="Pin the cert this CDN host actually serves (live TLS scrape) instead "
        "of --cert. Accepts host or host:port (default port 443).",
    )
    patch.add_argument(
        "--cert-connect",
        default=None,
        metavar="IP",
        help="Connect to this IP for --cert-host while keeping the host as SNI.",
    )
    patch.add_argument("-o", "--output", type=Path, default=None)
    patch.add_argument("--chip", default=None)
    patch.add_argument("--bundle-off", type=lambda x: int(x, 0), default=None)
    patch.add_argument("--pin-off", type=lambda x: int(x, 0), default=None)
    patch.add_argument("--force", action="store_true")

    ver = sub.add_parser("verify", help="Verify patched firmware footer")
    ver.add_argument("--profile", **profile_kw)
    ver.add_argument("--profiles-file", **profiles_file_kw)
    ver.add_argument("-f", "--firmware", type=Path, default=None)
    ver.add_argument("-c", "--cert", type=Path, default=DEFAULT_CERT)
    ver.add_argument(
        "--cert-host",
        default=None,
        metavar="HOST[:PORT]",
        help="Verify against the cert this CDN host serves instead of --cert.",
    )
    ver.add_argument(
        "--cert-connect",
        default=None,
        metavar="IP",
        help="Connect to this IP for --cert-host while keeping the host as SNI.",
    )
    ver.add_argument("--chip", default=None)

    args = p.parse_args()
    try:
        if args.cmd == "fetch":
            cmd_fetch(args)
        elif args.cmd == "patch":
            cmd_patch(args)
        elif args.cmd == "verify":
            cmd_verify(args)
    except subprocess.CalledProcessError as exc:
        print(f"Command failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
