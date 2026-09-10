#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["cryptography", "esptool>=4.7"]
# ///
"""
Patch Lepro firmware for lab CDN hijack and optional cert re-fetch on provision.

Version-specific offsets and byte patches live in firmware/patch-profiles.toml.
The patcher auto-selects a profile from the firmware filename (or --profile).

The bulb uses the stock ESP-IDF crt-bundle verifier. The embedded trust anchor
is not a flat cert slice: it is a length-delimited record containing the CA
subject Name TLV followed by the SubjectPublicKeyInfo DER bytes. This script
replaces that bundle entry with the matching fields from your mock CDN cert so
the bulb trusts your infra's CDN. The cert to pin can be a local PEM (--cert) or,
preferably, scraped live from the CDN host (--cert-host) so the firmware trust
anchor can never drift from the cert Traefik/the CDN actually serves.

It also applies configured byte patches that neuter firmware gates suppressing
the CDN cert download so root and client certs are re-fetched on every provision.

After patching, the ESP-IDF image checksum and SHA256 validation footer are
recalculated so the bootloader accepts the image.

Usage:
CLI: `lepro-firmware patch` / `lepro-firmware verify`

Examples:
  lepro-firmware patch
  lepro-firmware patch --cert-host cdn.example.com
  lepro-firmware patch --profile zb1_v2_3_18 -f firmware/custom.bin
  lepro-firmware verify
"""

from __future__ import annotations

import argparse
import hashlib
import re
import socket
import ssl
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

from lepro.firmware_profile import (
    BytePatch,
    BundleConfig,
    FirmwareProfile,
    load_profiles,
    resolve_profile,
)
from lepro.paths import repo_path

DEFAULT_CERT = repo_path("deploy/lepro-debug/certs/cdn.pem")

# Default TLS port for scraping a live CDN cert via --cert-host.
DEFAULT_CDN_PORT = 443


@dataclass(frozen=True)
class BundleLayout:
    bundle_off: int
    bundle_start: int
    entry_off: int
    key_off: int
    n_certs: int
    name_len: int
    key_len: int

    @property
    def record_len(self) -> int:
        return self.name_len + self.key_len


@dataclass(frozen=True)
class PatchResult:
    name: str
    offset: int
    changed: bool
    before: bytes
    after: bytes


def apply_byte_patch(fw: bytearray, patch: BytePatch) -> PatchResult:
    off = patch.offset
    n = len(patch.patched)
    if off + n > len(fw):
        raise SystemExit(
            f"{patch.name} @ {off:#x}: patch extends past firmware end ({len(fw)} bytes)"
        )
    cur = bytes(fw[off : off + n])
    if cur == patch.patched:
        return PatchResult(patch.name, off, False, cur, cur)
    if cur != patch.stock:
        raise SystemExit(
            f"{patch.name} @ {off:#x}: unexpected bytes {cur.hex()} "
            f"(expected stock {patch.stock.hex()} or patched {patch.patched.hex()})"
        )
    fw[off : off + n] = patch.patched
    return PatchResult(patch.name, off, True, patch.stock, patch.patched)


def check_byte_patch(fw: bytes, patch: BytePatch) -> PatchResult:
    off = patch.offset
    n = len(patch.patched)
    cur = bytes(fw[off : off + n])
    if cur == patch.patched:
        return PatchResult(patch.name, off, False, cur, cur)
    if cur == patch.stock:
        raise SystemExit(f"{patch.name} @ {off:#x} not patched (stock bytes {cur.hex()})")
    raise SystemExit(
        f"{patch.name} @ {off:#x}: unexpected bytes {cur.hex()} "
        f"(expected stock {patch.stock.hex()} or patched {patch.patched.hex()})"
    )


def apply_byte_patches(fw: bytearray, patches: Sequence[BytePatch]) -> list[PatchResult]:
    return [apply_byte_patch(fw, patch) for patch in patches]


def check_byte_patches(fw: bytes, patches: Sequence[BytePatch]) -> list[PatchResult]:
    return [check_byte_patch(fw, patch) for patch in patches]


def be16(buf: bytes, off: int) -> int:
    return (buf[off] << 8) | buf[off + 1]


def find_bundle_layout(
    fw: bytes,
    bundle: BundleConfig,
    *,
    bundle_off: int | None = None,
    pin_off: int | None = None,
    expected_record: bytes | None = None,
) -> BundleLayout:
    if bundle_off is not None or pin_off is not None:
        if bundle_off is None or pin_off is None:
            raise SystemExit("Specify both --bundle-off and --pin-off, or neither")
        if pin_off != bundle_off + 7:
            raise SystemExit(
                f"--pin-off ({pin_off:#x}) must be bundle_off + 7 ({bundle_off + 7:#x})"
            )
        return parse_bundle_layout(
            fw,
            bundle_off,
            bundle,
            expected_record=expected_record,
            expected_entry_off=pin_off,
        )

    if bundle.bundle_off is not None:
        entry_off = bundle.entry_off
        if entry_off is None:
            raise SystemExit("Profile bundle.entry_off required when bundle_off is set")
        return parse_bundle_layout(
            fw,
            bundle.bundle_off,
            bundle,
            expected_record=expected_record,
            expected_entry_off=entry_off,
        )

    idx = fw.find(bundle.signature)
    if idx < 0:
        raise SystemExit(
            f"CRT bundle signature not found in firmware ({len(fw)} bytes); "
            f"expected {bundle.signature.hex()}"
        )
    return parse_bundle_layout(fw, idx, bundle, expected_record=expected_record)


def parse_bundle_layout(
    fw: bytes,
    bundle_off: int,
    bundle: BundleConfig,
    *,
    expected_record: bytes | None = None,
    expected_entry_off: int | None = None,
) -> BundleLayout:
    lookback_start = max(0, bundle_off - bundle.lookback)
    if bundle.attach_error not in fw[lookback_start:bundle_off]:
        raise SystemExit(
            f'"{bundle.attach_error.decode()}" not found within '
            f"{bundle.lookback} bytes before bundle @ {bundle_off:#x}"
        )

    bundle_start = bundle_off + 1
    if bundle_start + 6 > len(fw):
        raise SystemExit(f"Bundle header @ {bundle_off:#x} extends past firmware end")

    n_certs = be16(fw, bundle_start)
    name_len = be16(fw, bundle_start + 2)
    key_len = be16(fw, bundle_start + 4)
    entry_off = bundle_start + 6
    key_off = entry_off + name_len
    record_end = key_off + key_len
    if record_end > len(fw):
        raise SystemExit(
            f"Bundle record @ {entry_off:#x} ({name_len}+{key_len} bytes) "
            f"extends past firmware end"
        )
    if expected_entry_off is not None and entry_off != expected_entry_off:
        raise SystemExit(
            f"Bundle entry starts at {entry_off:#x}, not expected {expected_entry_off:#x}"
        )
    if expected_record is not None and len(expected_record) != name_len + key_len:
        raise SystemExit(
            f"Certificate record length {len(expected_record)} does not match "
            f"bundle layout {name_len + key_len}"
        )

    return BundleLayout(
        bundle_off=bundle_off,
        bundle_start=bundle_start,
        entry_off=entry_off,
        key_off=key_off,
        n_certs=n_certs,
        name_len=name_len,
        key_len=key_len,
    )


def pem_to_der(pem_path: Path) -> bytes:
    pem = pem_path.read_bytes()
    return subprocess.check_output(
        ["openssl", "x509", "-inform", "PEM", "-outform", "DER"],
        input=pem,
    )


def parse_host_port(value: str, default_port: int = DEFAULT_CDN_PORT) -> tuple[str, int]:
    """Split "host" or "host:port" (ignoring bracketed IPv6) into (host, port)."""
    if not value.startswith("[") and value.count(":") == 1:
        host, _, port = value.partition(":")
        if host and port.isdigit():
            return host, int(port)
    return value, default_port


def fetch_cert_der_from_host(
    host: str,
    port: int = DEFAULT_CDN_PORT,
    *,
    connect_host: str | None = None,
    timeout: float = 10.0,
) -> bytes:
    """Open a TLS connection and return the server leaf certificate as DER."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    target = connect_host or host
    try:
        with socket.create_connection((target, port), timeout=timeout) as raw_sock:
            with ctx.wrap_socket(raw_sock, server_hostname=host) as tls_sock:
                der = tls_sock.getpeercert(binary_form=True)
    except OSError as exc:
        raise SystemExit(
            f"Could not fetch cert from {target}:{port} (SNI {host}): {exc}"
        ) from exc
    if not der:
        raise SystemExit(f"{target}:{port} (SNI {host}) presented no certificate")
    return der


def load_cert_der(
    *,
    cert_path: Path | None,
    cert_host: str | None,
    cert_connect: str | None = None,
    cert_port: int = DEFAULT_CDN_PORT,
) -> tuple[bytes, str]:
    """Resolve the cert to pin: live from `cert_host` if given, else local PEM."""
    if cert_host:
        host, port = parse_host_port(cert_host, cert_port)
        der = fetch_cert_der_from_host(host, port, connect_host=cert_connect)
        via = f" via {cert_connect}" if cert_connect else ""
        return der, f"{host}:{port} (live CDN cert{via})"
    path = cert_path or DEFAULT_CERT
    if not path.is_file():
        raise SystemExit(f"Certificate not found: {path}")
    return pem_to_der(path), str(path)


def build_bundle_record(cert_der: bytes) -> tuple[bytes, bytes, bytes]:
    cert = x509.load_der_x509_certificate(cert_der)
    name_tlv = cert.issuer.public_bytes()
    spki = cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return name_tlv + spki, name_tlv, spki


def split_bundle_record(record: bytes, layout: BundleLayout) -> tuple[bytes, bytes]:
    return record[: layout.name_len], record[layout.name_len :]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checksum_off(fw: bytes) -> int:
    if len(fw) < 33:
        raise SystemExit(f"Firmware too small for ESP image footer ({len(fw)} bytes)")
    return len(fw) - 33


def repair_esp_app_image(fw: bytearray, chip: str) -> tuple[int, int, str, str]:
    try:
        import esptool.bin_image as bi
    except ImportError as exc:
        raise SystemExit("esptool is required; run via: uv run lepro-firmware patch") from exc

    img = bi.LoadFirmwareImage(chip, bytes(fw))
    chk_idx = checksum_off(fw)
    old_chk = fw[chk_idx]
    old_hash = bytes(fw[-32:])

    fw[chk_idx] = img.calculate_checksum()
    fw[-32:] = hashlib.sha256(fw[:-32]).digest()

    return old_chk, fw[chk_idx], old_hash.hex(), sha256_hex(fw[-32:])


def footer_valid(path: Path, chip: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["esptool", "image-info", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, result.stderr or result.stdout or "esptool image-info failed"

    out = result.stdout
    chk_ok = bool(re.search(r"Checksum:.*\(valid\)", out))
    hash_ok = bool(re.search(r"Validation hash:.*\(valid\)", out))
    return chk_ok and hash_ok, out


def warn_if_footer_invalid(fw: bytes, chip: str) -> None:
    try:
        import esptool.bin_image as bi
    except ImportError:
        return

    chk_idx = checksum_off(fw)
    img = bi.LoadFirmwareImage(chip, bytes(fw))
    if fw[chk_idx] == img.calculate_checksum() and bytes(fw[-32:]) == hashlib.sha256(
        fw[:-32]
    ).digest():
        return
    print(
        "Warning:   ESP image footer invalid (checksum or validation hash); "
        "re-run without --verify-only to repair",
        file=sys.stderr,
    )


def patch_firmware(
    profile: FirmwareProfile,
    *,
    firmware_path: Path,
    output_path: Path,
    cert_path: Path | None = None,
    cert_host: str | None = None,
    cert_connect: str | None = None,
    bundle_off: int | None = None,
    pin_off: int | None = None,
    verify_only: bool = False,
    force: bool = False,
) -> None:
    if not firmware_path.is_file():
        raise SystemExit(f"Firmware not found: {firmware_path}")

    cert_der, cert_source = load_cert_der(
        cert_path=cert_path,
        cert_host=cert_host,
        cert_connect=cert_connect,
    )
    new_record, new_name, new_key = build_bundle_record(cert_der)
    fw = bytearray(firmware_path.read_bytes())
    if fw[:1] != b"\xe9":
        raise SystemExit(f"Not an ESP image (expected magic 0xE9, saw 0x{fw[0]:02x})")

    manual = bundle_off is not None
    layout = find_bundle_layout(
        fw,
        profile.bundle,
        bundle_off=bundle_off,
        pin_off=pin_off,
        expected_record=new_record,
    )
    label = "manual" if manual else "auto-detected"

    if layout.n_certs != profile.bundle.expected_cert_count:
        raise SystemExit(
            f"Unexpected bundle header @ {layout.bundle_off:#x}: "
            f"n_certs={layout.n_certs} (expected {profile.bundle.expected_cert_count})"
        )
    if len(new_name) != layout.name_len or len(new_key) != layout.key_len:
        raise SystemExit(
            f"Certificate geometry does not match bundle @ {layout.bundle_off:#x}: "
            f"name_len={len(new_name)} (expected {layout.name_len}), "
            f"key_len={len(new_key)} (expected {layout.key_len})"
        )

    old_record = bytes(fw[layout.entry_off : layout.entry_off + layout.record_len])
    old_name, old_key = split_bundle_record(old_record, layout)

    print(f"Profile:   {profile.id} ({profile.description})")
    print(f"Firmware:  {firmware_path} ({len(fw)} bytes)")
    print(f"CDN cert:    {cert_source}")
    print(
        f"Bundle @     {layout.bundle_off:#x} ({label}, {layout.n_certs} cert(s), "
        f"name={layout.name_len} bytes, key={layout.key_len} bytes)"
    )
    print(f"Entry @      {layout.entry_off:#x}")
    print(f"Key @        {layout.key_off:#x}")
    print(f"Old record:  {sha256_hex(old_record)}")
    print(f"New record:  {sha256_hex(new_record)}")
    print(f"Old name:    {sha256_hex(old_name)}")
    print(f"New name:    {sha256_hex(new_name)}")
    print(f"Old key:     {sha256_hex(old_key)}")
    print(f"New key:     {sha256_hex(new_key)}")

    warn_if_footer_invalid(fw, profile.chip)

    record_changed = old_record != new_record
    if verify_only:
        patch_results = check_byte_patches(fw, profile.patches)
        for result in patch_results:
            print(f"{result.name} @ {result.offset:#x}: patched ({result.after.hex()})")
    else:
        patch_results = apply_byte_patches(fw, profile.patches)
        for result in patch_results:
            if result.changed:
                print(
                    f"{result.name} @ {result.offset:#x}: "
                    f"{result.before.hex()} -> {result.after.hex()} (force cert re-fetch)"
                )
            else:
                print(f"{result.name} @ {result.offset:#x}: already patched ({result.after.hex()})")

    any_changed = record_changed or any(r.changed for r in patch_results)
    if not any_changed:
        print("Embedded crt-bundle entry already matches the CDN cert; no change needed.")
        if profile.patches:
            names = " + ".join(p.name for p in profile.patches)
            print(f"Byte patches ({names}) already applied.")
        if verify_only:
            if old_record != new_record:
                raise SystemExit("CDN bundle does not match certificate")
            ok, info = footer_valid(firmware_path, profile.chip)
            if not ok:
                print(info, file=sys.stderr)
                raise SystemExit("esptool image-info reports invalid footer")
            print("Verify-only: OK")
            return
        if not force:
            print("Use --force to rewrite the output file anyway.")
            return
    elif record_changed:
        print(
            f"Record diff: {sum(a != b for a, b in zip(old_record, new_record))}/"
            f"{layout.record_len} bytes"
        )
    elif not record_changed:
        print("Embedded crt-bundle entry already matches the CDN cert.")

    if verify_only:
        if old_record != new_record:
            raise SystemExit("CDN bundle does not match certificate")
        ok, info = footer_valid(firmware_path, profile.chip)
        if not ok:
            print(info, file=sys.stderr)
            raise SystemExit("esptool image-info reports invalid footer")
        print("Verify-only: OK")
        return

    if record_changed:
        fw[layout.entry_off : layout.entry_off + layout.record_len] = new_record

    old_chk, new_chk, old_hash, new_hash = repair_esp_app_image(fw, profile.chip)
    print(f"Checksum:    {old_chk:#04x} -> {new_chk:#04x} @ {checksum_off(fw):#x}")
    print(f"Hash:        {old_hash[:16]}… -> {new_hash[:16]}…")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(fw)

    patched = output_path.read_bytes()
    if record_changed and patched[layout.entry_off : layout.entry_off + layout.record_len] != new_record:
        raise SystemExit("Post-write crt-bundle verification failed")
    for result in patch_results:
        if patched[result.offset : result.offset + len(result.after)] != result.after:
            raise SystemExit(f"Post-write {result.name} verification failed")
    if patched[checksum_off(patched)] != new_chk:
        raise SystemExit("Post-write checksum verification failed")
    if patched[-32:] != hashlib.sha256(patched[:-32]).digest():
        raise SystemExit("Post-write validation hash verification failed")

    ok, info = footer_valid(output_path, profile.chip)
    if not ok:
        print(info, file=sys.stderr)
        raise SystemExit("esptool image-info reports invalid footer after patch")

    for line in info.splitlines():
        if "Checksum:" in line or "Validation hash:" in line:
            print(f"Footer:      {line.strip()}")

    print(f"Wrote:       {output_path} ({len(patched)} bytes)")
    print()
    print("Reflash via BLE OTA (lepro-ota auto-bumps version for *.patched.bin):")
    print(f"  lepro-ota --mac <MAC> --firmware {output_path}")
    print(
        "The pinned trust anchor must match the cert the CDN serves. Pin the live "
        "cert directly with: lepro-firmware patch --cert-host"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profiles-file",
        type=Path,
        default=None,
        help="Path to patch-profiles.toml (default: firmware/patch-profiles.toml)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Firmware profile id (default: auto-match from --firmware filename)",
    )
    parser.add_argument("-f", "--firmware", type=Path, default=None)
    parser.add_argument("-c", "--cert", type=Path, default=DEFAULT_CERT)
    parser.add_argument(
        "--cert-host",
        default=None,
        metavar="HOST[:PORT]",
        help="Pin the cert this CDN host actually serves (TLS scrape) instead of --cert.",
    )
    parser.add_argument(
        "--cert-connect",
        default=None,
        help="Connect to this IP for --cert-host while keeping the host as SNI.",
    )
    parser.add_argument("-o", "--output", type=Path, default=None)
    parser.add_argument("--chip", default=None, help="Override profile chip type")
    parser.add_argument("--bundle-off", type=lambda x: int(x, 0), default=None)
    parser.add_argument("--pin-off", type=lambda x: int(x, 0), default=None)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    profiles = load_profiles(args.profiles_file)
    firmware_path = args.firmware
    if firmware_path is None:
        profile = resolve_profile(profiles, profile_id=args.profile)
        firmware_path = profile.stock_image
    else:
        profile = resolve_profile(
            profiles, firmware_path=firmware_path, profile_id=args.profile
        )

    output_path = args.output or profile.patched_image
    if args.chip is not None:
        from dataclasses import replace

        profile = replace(profile, chip=args.chip)

    patch_firmware(
        profile,
        firmware_path=firmware_path,
        output_path=output_path,
        cert_path=args.cert,
        cert_host=args.cert_host,
        cert_connect=args.cert_connect,
        bundle_off=args.bundle_off,
        pin_off=args.pin_off,
        verify_only=args.verify_only,
        force=args.force,
    )


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"openssl failed: {exc}", file=sys.stderr)
        sys.exit(1)
