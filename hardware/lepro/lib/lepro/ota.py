#!/usr/bin/env python3
"""
BLE firmware OTA for Lepro ZB1 (native opcodes 0x1010 / 0x1012).

OTA start JSON schema (FUN_42008eb0 @ Ghidra — flat BLE 0x1010 path):
  version  — e.g. "2.3.19" (must differ from running fw when do_check=1)
  hash     — MD5 hex digest of the firmware image
  path     — CDN-relative path, e.g. pub/ota/3_le_light_zb1_pid_55_v2.3.18.bin
  size     — image byte count as JSON string (max 10 chars), e.g. "1008368"
  secret   — cloud OTA secret (empty string for local BLE flash)
  do_check — optional JSON number, default 1 (skip version gate when 0)
  fwType   — optional product type string (max 16 chars)

Stock image source:
  curl -k -o firmware/3_le_light_zb1_pid_55_v2.3.18.bin \\
    "https://ota-dvc-eu-iot.lepro.com/pub/ota/3_le_light_zb1_pid_55_v2.3.18.bin"

Preconditions:
  - Light BLE-reachable (onboarding mode if needed)
  - Bond first: uv run lepro-bond --mac <MAC>  (saves ~/.lepro/<mac>.json)
  - Patched firmware for lab CDN: `lepro-firmware patch` on v2.3.18.bin
  - Device on v2.3.18: do not flash v2.2.13 without --force

Usage:
  lepro-bond --mac 10:20:BA:31:B2:BA
  lepro-ota --mac 10:20:BA:31:B2:BA --firmware firmware/3_le_light_zb1_pid_55_v2.3.18.patched.bin
  lepro-ota --mac ... --dry-run
  lepro-ota --mac ... --ota-json custom.json
  lepro-ota --mac ... --debug-tx --debug-rx   # full wire hex

Same-version reflash: the firmware version gate (FUN_42008eb0 strcmp when
do_check=1) is skipped because BLE OTA sends do_check:0. The image keeps its
on-disk version string (e.g. 2.3.18). Pass --reflash to opt into bumping the
patch version for cloud/do_check:1 style flashing.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from bleak import BleakClient, BleakScanner

from lepro.bond import creds_path, load_creds, normalize_mac
from lepro.crypto import derive_session_key, encrypt_cbc, MAIN_IV
from lepro.frame import DecryptedFrame, OP_BOND_RESP_ALT, parse_bond_result, parse_ota_data_resp, parse_ota_start_resp
from lepro.protocol import (
    GATT_CMD,
    GATT_RSP,
    MAGIC_SINGLE,
    MAGIC_SINGLE_ENC,
    OP_OTA_DATA,
    OP_OTA_DATA_RESP,
    OP_OTA_START,
    OP_OTA_START_RESP,
    build_packets_fragmented,
    crc16_lepro,
    parse_packet,
)
from lepro.session import BleakTransport, DryRunTransport, LeproSession, SessionConfig
from lepro.paths import repo_path

DEFAULT_FIRMWARE = repo_path("firmware/3_le_light_zb1_pid_55_v2.3.18.patched.bin")
OTA_INNER_SIZE = 0x1400  # 5120 — legacy padded inner (pre-v2.3.18 path)
OTA_MAX_CHUNK = 0x13F8  # 5112 — max chunk payload bytes
OTA_SUCCESS = 0
OTA_ERR_LENGTH = 0x1      # FUN_4200886c: declared len != strlen(json)+1
OTA_ERR_PARSE = 0x112     # FUN_42008eb0 returned 3 (missing/invalid JSON fields)
OTA_START_ALREADY_ACTIVE = 0x101  # FUN_42009054: OTA ctx exists — proceed to data phase
OTA_ERR_CHUNK_SIZE = 0x116  # FUN_420095d4: decrypted len != chunk_len+8 or over total
OTA_ERR_CHUNK_OFFSET = 0x118  # FUN_420095d4: inner offset != bytes written so far
OTA_ERR_CRC = 9             # FUN_420095d4: CRC16 mismatch on chunk data
OTA_ERR_SET_BOOT = 0x106    # FUN_42009890: esp_ota_set_boot_partition failed
OTA_ERR_MD5 = 0x107         # FUN_42009328: running MD5 != JSON hash
OTA_ERR_NO_CTX = 0x115      # FUN_420095d4: no active OTA context
OTA_ERR_OTA_END = 0x117     # FUN_42009890: esp_ota_end image verify failed

POST_REBOOT_WAIT_S = 2.0
POST_REBOOT_RETRY_S = 90.0
POST_REBOOT_SCAN_BURST_S = 4.0
POST_REBOOT_RETRY_INTERVAL_S = 1.5
DISCOVERY_CONFIRM_ATTEMPTS = 3

_VERSION_RE = re.compile(r"v?(\d+\.\d+\.\d+)", re.I)
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_PATH_RE = re.compile(r"(\d+_le_light_[^_]+_pid_\d+_v[\d.]+\.bin)", re.I)
_DISCOVERY_VERSION_ANCHOR = bytes.fromhex("624441824444624445")
_DISCOVERY_VERSION_IMM_OFFSETS = {
    "major": -12,
    "minor": -7,
    "patch": -2,
}


@dataclass
class OtaTransferResult:
    """Outcome of the BLE OTA data phase."""

    chunks_sent: int
    total_bytes: int
    last_chunk_result: int | None
    probable_finalize_reboot: bool = False

    @property
    def finalize_code(self) -> int | None:
        return self.last_chunk_result

    @property
    def transfer_complete(self) -> bool:
        return self.chunks_sent > 0 and self.total_bytes > 0


@dataclass
class OtaConfirmVerdict:
    """Post-reboot discovery verdict."""

    status: str  # stuck | rolled_back | reconnect_failed | unknown_version
    flashed_ver: str
    running_ver: str | None
    reconnect_elapsed_s: float
    message: str


@dataclass
class OtaLog:
    """Timestamped, flushed stdout logging for long OTA runs."""

    verbose: bool = True

    def info(self, msg: str) -> None:
        if not self.verbose:
            return
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)

    def phase(self, name: str) -> None:
        self.info(f"── {name} ──")

    def wait(self, msg: str, timeout: float) -> None:
        self.info(f"{msg} (timeout {timeout:.0f}s)…")



@dataclass
class OtaTransport(BleakTransport):
    """BLE transport with compact or full TX/RX logging."""

    log: OtaLog = field(default_factory=OtaLog)
    debug_tx: bool = False

    def on_notify(self, _sender: object, data: bytearray) -> None:
        raw = bytes(data)
        if self.debug_rx:
            self.log.info(f"RX {len(raw)} B: {raw.hex()}")
        self._queue.put_nowait(raw)

    async def send(self, data: bytes, label: str = "") -> None:
        if label and self.debug_tx:
            self.log.info(f"TX [{label}] {len(data)} B: {data.hex()}")
        await self.client.write_gatt_char(self.cmd_char, data, response=False)  # type: ignore[attr-defined]


_FRAG_ACK_MAGICS = frozenset({MAGIC_SINGLE_ENC, MAGIC_SINGLE})


async def wait_ota_frag_ack(session: LeproSession, seq: int, *, timeout: float = 5.0) -> DecryptedFrame:
    """Wait for per-fragment ACK with matching seq.

    Mid-fragment ACKs use magic 0x54; the final fragment ACK uses magic 0x50 (0xAAAA).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = await session.transport.recv(deadline - time.monotonic())
        if raw is None:
            continue
        if (
            len(raw) >= 6
            and raw[2] == 0x5A
            and raw[3] in _FRAG_ACK_MAGICS
            and raw[4:6] == struct.pack(">H", seq)
        ):
            for frame in session._ingest_rx(raw):
                if frame.seq == seq:
                    return frame
    raise TimeoutError(f"timeout waiting for OTA frag ACK seq={seq}")


async def send_ota_packets(
    session: LeproSession,
    packets: list[bytes],
    log: OtaLog,
    *,
    label: str,
) -> DecryptedFrame | None:
    """Send fragmented OTA op, waiting for a per-fragment ACK after each TX."""
    if not packets:
        return None
    log_tx = getattr(session.transport, "debug_tx", False)
    last_ack: DecryptedFrame | None = None
    for i, pkt in enumerate(packets):
        hdr = parse_packet(pkt)
        frag_seq = hdr.seq if hdr else i
        await session._send(pkt, f"{label}[{i}]" if log_tx else "")
        if session.config.dry_run:
            continue
        last_ack = await wait_ota_frag_ack(session, frag_seq, timeout=5.0)
        if (i + 1) % 10 == 0 or i + 1 == len(packets):
            log.info(f"  {label}: {i + 1}/{len(packets)} fragments ACK'd (last seq={frag_seq})")
    return last_ack


async def wait_opcode_verbose(
    session: LeproSession,
    opcode: int,
    *,
    timeout: float,
    log: OtaLog,
    label: str,
    heartbeat: float = 5.0,
) -> DecryptedFrame:
    """Wait for an opcode, logging heartbeats so a stall is obvious."""
    if session.config.dry_run:
        return DecryptedFrame(seq=0, opcode=opcode, payload=b"", raw=b"")

    log.wait(label, timeout)
    t0 = time.monotonic()

    async def _heartbeat() -> None:
        while True:
            await asyncio.sleep(heartbeat)
            elapsed = time.monotonic() - t0
            remaining = timeout - elapsed
            if remaining > 0:
                log.info(f"  still waiting for {label} ({remaining:.0f}s left)")

    hb = asyncio.create_task(_heartbeat())
    try:
        return await session._wait_opcode(opcode, timeout=timeout)
    finally:
        hb.cancel()
        try:
            await hb
        except asyncio.CancelledError:
            pass


def _write_u16_be(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into(">H", buf, offset, value & 0xFFFF)


def _write_u32_be(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into(">I", buf, offset, value & 0xFFFFFFFF)


def build_ota_start_inner(json_bytes: bytes) -> bytes:
    """Legacy 5120-byte plaintext inner buffer (older OTA path: JSON at +8)."""
    if len(json_bytes) > OTA_MAX_CHUNK:
        raise ValueError(f"OTA start JSON too large ({len(json_bytes)} > {OTA_MAX_CHUNK})")
    buf = bytearray(OTA_INNER_SIZE)
    buf[8 : 8 + len(json_bytes)] = json_bytes
    return bytes(buf)


def build_ota_start_plaintext(json_bytes: bytes) -> bytes:
    """v2.3.18 OTA start plaintext: NUL-terminated JSON C string."""
    if b"\x00" in json_bytes:
        raise ValueError("OTA start JSON must not contain NUL bytes")
    return json_bytes + b"\x00"


def build_ota_chunk_inner(offset: int, chunk: bytes) -> bytes:
    """Legacy 5120-byte padded inner buffer (pre-v2.3.18 otaProcess layout)."""
    if not chunk or len(chunk) > OTA_MAX_CHUNK:
        raise ValueError(f"chunk length must be 1..{OTA_MAX_CHUNK}, got {len(chunk)}")
    buf = bytearray(OTA_INNER_SIZE)
    buf[8 : 8 + len(chunk)] = chunk
    _write_u32_be(buf, 0, offset)
    _write_u16_be(buf, 4, crc16_lepro(chunk))
    _write_u16_be(buf, 6, len(chunk))
    return bytes(buf)


def build_ota_chunk_plaintext(offset: int, chunk: bytes) -> bytes:
    """v2.3.18 OTA data plaintext: 8-byte header + chunk (FUN_420095d4 expects len+8)."""
    if not chunk or len(chunk) > OTA_MAX_CHUNK:
        raise ValueError(f"chunk length must be 1..{OTA_MAX_CHUNK}, got {len(chunk)}")
    buf = bytearray(8 + len(chunk))
    _write_u32_be(buf, 0, offset)
    _write_u16_be(buf, 4, crc16_lepro(chunk))
    _write_u16_be(buf, 6, len(chunk))
    buf[8:] = chunk
    return bytes(buf)


def encrypt_ota_inner(mac: str, session_rand: int, inner: bytes) -> bytes:
    key = derive_session_key(mac, session_rand)
    return encrypt_cbc(inner, key, iv=MAIN_IV)


def build_ota_start_packets(
    mac: str,
    seq: int,
    json_bytes: bytes,
    *,
    session_rand: int,
    max_payload: int = 128,
) -> tuple[list[bytes], int]:
    plaintext = build_ota_start_plaintext(json_bytes)
    ct = encrypt_ota_inner(mac, session_rand, plaintext)
    packets = build_packets_fragmented(seq, OP_OTA_START, ct, max_payload, encrypted=True)
    return packets, seq + len(packets)


def build_ota_chunk_packets(
    mac: str,
    seq: int,
    offset: int,
    chunk: bytes,
    *,
    session_rand: int,
    max_payload: int = 128,
) -> tuple[list[bytes], int]:
    plaintext = build_ota_chunk_plaintext(offset, chunk)
    ct = encrypt_ota_inner(mac, session_rand, plaintext)
    packets = build_packets_fragmented(seq, OP_OTA_DATA, ct, max_payload, encrypted=True)
    return packets, seq + len(packets)


def firmware_version_from_path(path: Path) -> str | None:
    m = _VERSION_RE.search(path.name)
    return m.group(1) if m else None


def version_from_discovery(raw: bytes) -> str | None:
    """Best-effort running fw semver from discovery notify payload."""
    m = _VERSION_RE.search(raw.decode("latin-1", errors="replace"))
    if m:
        return m.group(1)
    # ZB1 firmware also hardcodes semver bytes in the 0x1001 device-info tail.
    # ota.py patches those immediates during reflash so discovery can report the
    # bumped image version instead of the stock 2.3.18 build-time constants.
    idx = 0
    while idx + 2 < len(raw):
        pos = raw.find(b"\x02\x03", idx)
        if pos < 0 or pos + 2 >= len(raw):
            break
        patch = raw[pos + 2]
        if 0 < patch < 100:
            return f"2.3.{patch}"
        idx = pos + 1
    return None


def _semver_tuple(version: str) -> tuple[int, int, int]:
    m = _SEMVER_RE.match(version)
    if not m:
        raise ValueError(f"invalid semver: {version!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def adjust_ota_version_for_running(running: str | None, ota_ver: str, *, reflash: bool) -> str:
    """Bump JSON/embedded version when --reflash and device already reports >= proposed OTA version.

    Only used when --reflash is set. Default BLE OTA sends do_check:0, so the firmware
    version gate is skipped and this ratchet is not needed.
    """
    if not reflash or not running:
        return ota_ver
    try:
        if _semver_tuple(running) >= _semver_tuple(ota_ver):
            return bump_ota_version(running)
    except ValueError:
        return ota_ver
    return ota_ver


def bump_ota_version(version: str) -> str:
    """Bump PATCH so JSON version differs from running fw_version.

    FUN_42008eb0 strcmp's running fw against JSON version when do_check=1.
    """
    m = _SEMVER_RE.match(version)
    if not m:
        raise SystemExit(
            f"Cannot bump OTA version {version!r}; expected MAJOR.MINOR.PATCH "
            "(use --ota-version to set explicitly)"
        )
    major, minor, patch = (int(m.group(i)) for i in range(1, 4))
    return f"{major}.{minor}.{patch + 1}"


def resolve_ota_version(
    firmware: Path,
    *,
    version: str | None = None,
    reflash: bool = False,
) -> str:
    if version is not None:
        return version
    ver = firmware_version_from_path(firmware)
    if not ver:
        raise SystemExit(f"Cannot infer mcu_ota_version from {firmware.name}; use --ota-json")
    return bump_ota_version(ver) if reflash else ver


def firmware_cdn_path(path: Path, *, version: str | None = None) -> str:
    m = _PATH_RE.search(path.name)
    name = m.group(1) if m else path.name.replace(".patched", "")
    if version is not None:
        name = re.sub(r"_v\d+\.\d+\.\d+", f"_v{version}", name, count=1)
    return f"pub/ota/{name}"


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def bump_embedded_version(image: bytearray, old_ver: str, new_ver: str) -> int:
    """Rewrite fixed-width version strings inside an ESP-IDF app image."""
    if len(old_ver) != len(new_ver):
        raise SystemExit(
            f"Embedded version bump {old_ver!r} → {new_ver!r} changes length; "
            "use --ota-version with same-width semver"
        )
    old_b = old_ver.encode()
    new_b = new_ver.encode()
    count = 0
    start = 0
    while True:
        idx = image.find(old_b, start)
        if idx < 0:
            break
        image[idx : idx + len(old_b)] = new_b
        count += 1
        start = idx + len(old_b)
    return count


def _encode_xtensa_movi_n_a8(value: int) -> bytes:
    """Encode `movi.n a8, imm` for non-negative immediates representable in RI7."""
    if not 0 <= value <= 95:
        raise SystemExit(
            f"Discovery version byte {value} is out of range for Xtensa movi.n a8 "
            "(expected 0..95)"
        )
    return bytes(((((value >> 4) & 0x7) << 4) | 0x0C, ((value & 0xF) << 4) | 0x08))


def _decode_xtensa_movi_n_a8(data: bytes) -> int | None:
    """Decode `movi.n a8, imm`; return None when the bytes are not that instruction."""
    if len(data) != 2 or (data[0] & 0x0F) != 0x0C or (data[1] & 0x0F) != 0x08 or data[0] & 0x80:
        return None
    value = (((data[0] >> 4) & 0x7) << 4) | ((data[1] >> 4) & 0xF)
    return value if _encode_xtensa_movi_n_a8(value) == data else None


def patch_discovery_version(image: bytearray, version: str) -> int:
    """Rewrite the hardcoded 0x1001 device-info semver immediates in the firmware."""
    major, minor, patch = _semver_tuple(version)

    anchor_off = image.find(_DISCOVERY_VERSION_ANCHOR)
    if anchor_off < 0:
        raise SystemExit(
            "Discovery version anchor not found in firmware; expected "
            f"{_DISCOVERY_VERSION_ANCHOR.hex()}"
        )
    if image.find(_DISCOVERY_VERSION_ANCHOR, anchor_off + 1) >= 0:
        raise SystemExit(
            "Discovery version anchor matched multiple times; refusing to patch ambiguous firmware"
        )

    changed = 0
    for label, new_value in (("major", major), ("minor", minor), ("patch", patch)):
        site = anchor_off + _DISCOVERY_VERSION_IMM_OFFSETS[label]
        if site < 0 or site + 2 > len(image):
            raise SystemExit(f"Discovery {label} patch site @ {site:#x} is outside the firmware")
        old_instr = bytes(image[site : site + 2])
        old_value = _decode_xtensa_movi_n_a8(old_instr)
        if old_value is None:
            raise SystemExit(
                f"Discovery {label} patch site @ {site:#x} is not movi.n a8,<imm>: "
                f"saw {old_instr.hex()}"
            )
        new_instr = _encode_xtensa_movi_n_a8(new_value)
        if old_instr != new_instr:
            image[site : site + 2] = new_instr
            changed += 1
    return changed


def repair_esp_app_image(image: bytearray, *, chip: str = "esp32s3") -> None:
    """Recalculate ESP-IDF image checksum + validation hash after byte patches."""
    try:
        import esptool.bin_image as bi
    except ImportError as exc:
        raise SystemExit("esptool is required for reflash image prep; use: uv run lepro-ota") from exc

    if len(image) < 33:
        raise SystemExit(f"Firmware too small for ESP image footer ({len(image)} bytes)")
    img = bi.LoadFirmwareImage(chip, bytes(image))
    chk_idx = len(image) - 33
    image[chk_idx] = img.calculate_checksum()
    image[-32:] = hashlib.sha256(image[:-32]).digest()


def prepare_ota_image(
    firmware: Path,
    *,
    version: str | None = None,
    reflash: bool = False,
    chip: str = "esp32s3",
) -> tuple[bytes, str]:
    """Load firmware bytes for OTA, optionally bumping embedded strings + discovery semver."""
    image = bytearray(firmware.read_bytes())
    if image[0] != 0xE9:
        raise SystemExit(f"Not an ESP image (magic 0xE9): {firmware}")
    file_ver = firmware_version_from_path(firmware)
    ota_ver = resolve_ota_version(firmware, version=version, reflash=reflash)
    patch_count = 0
    if reflash and file_ver and ota_ver != file_ver:
        patch_count = bump_embedded_version(image, file_ver, ota_ver)
        if patch_count == 0:
            raise SystemExit(
                f"Reflash: version string {file_ver!r} not found in {firmware.name}"
            )
        patch_discovery_version(image, ota_ver)
        repair_esp_app_image(image, chip=chip)
    return bytes(image), ota_ver


def build_ota_start_json(
    firmware: Path,
    image: bytes,
    *,
    version: str,
    path_version: str | None = None,
    ota_secret: str = "",
) -> bytes:
    """Build raw JSON bytes for BLE OTA start (FUN_42008eb0 flat parser)."""
    # do_check:0 skips the firmware version gate (FUN_42008eb0 strcmp and FUN_420097a8
    # app-descriptor checks). Cloud/MQTT uses fwType + do_check:1.
    payload = {
        "do_check": 0,
        "version": version,
        "hash": md5_hex(image),
        "path": firmware_cdn_path(firmware, version=path_version),
        "size": str(len(image)),
        "secret": ota_secret,
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def describe_ota_start_error(code: int) -> str:
    """Human-readable hint for OTA start response codes."""
    if code == OTA_SUCCESS:
        return "success"
    if code == OTA_ERR_LENGTH:
        return "payload length mismatch (expected NUL-terminated JSON; strlen+1)"
    if code == OTA_ERR_PARSE:
        return (
            "OTA info JSON rejected (0x112) — power-cycle the light and retry; "
            "or use --ota-version 2.3.20+ if version matches running fw; "
            "BLE needs do_check:0 when ctx[0]==0 (fresh boot)"
        )
    if code == OTA_START_ALREADY_ACTIVE:
        return "OTA session already active (resume data transfer)"
    return f"unknown OTA start error"


def describe_ota_data_error(code: int) -> str:
    """Human-readable hint for OTA data response codes (0x1013 / FUN_420095d4)."""
    if code == OTA_SUCCESS:
        return "success"
    if code == OTA_ERR_CHUNK_SIZE:
        return "chunk size mismatch (decrypted len must equal header+data, not 5120 padded)"
    if code == OTA_ERR_CHUNK_OFFSET:
        return "chunk offset does not match bytes written so far"
    if code == OTA_ERR_CRC:
        return "chunk CRC16 mismatch"
    if code == OTA_ERR_SET_BOOT:
        return "esp_ota_set_boot_partition failed (FUN_42009890)"
    if code == OTA_ERR_MD5:
        return "MD5 mismatch vs JSON hash (FUN_42009328)"
    if code == OTA_ERR_NO_CTX:
        return "no active OTA context"
    if code == OTA_ERR_OTA_END:
        return "esp_ota_end image verify failed (FUN_42009890)"
    return f"unknown OTA data error (0x{code:x})"


def classify_ota_verdict(
    flashed_ver: str,
    running_ver: str | None,
    *,
    reconnect_ok: bool,
) -> OtaConfirmVerdict:
    """Classify post-reboot discovery into stuck vs rolled back vs reconnect failure."""
    if not reconnect_ok:
        return OtaConfirmVerdict(
            status="reconnect_failed",
            flashed_ver=flashed_ver,
            running_ver=None,
            reconnect_elapsed_s=POST_REBOOT_RETRY_S,
            message=(
                "Could not reconnect over BLE after reboot. The image may have crashed "
                "before BLE came up (#2 image-prep bug). Power-cycle the light and "
                "re-run; if this persists, inspect lepro-firmware patch / prepare_ota_image."
            ),
        )
    if running_ver is None:
        return OtaConfirmVerdict(
            status="unknown_version",
            flashed_ver=flashed_ver,
            running_ver=None,
            reconnect_elapsed_s=0.0,
            message=(
                f"Reconnected and discovery succeeded, but could not parse a version "
                f"(expected {flashed_ver}). Re-run with --debug-rx."
            ),
        )
    try:
        if _semver_tuple(running_ver) >= _semver_tuple(flashed_ver):
            return OtaConfirmVerdict(
                status="stuck",
                flashed_ver=flashed_ver,
                running_ver=running_ver,
                reconnect_elapsed_s=0.0,
                message=(
                    f"Firmware stuck: running {running_ver} >= flashed {flashed_ver}. "
                    "BLE discovery triggered esp_ota_mark_app_valid_cancel_rollback."
                ),
            )
    except ValueError:
        pass
    return OtaConfirmVerdict(
        status="rolled_back",
        flashed_ver=flashed_ver,
        running_ver=running_ver,
        reconnect_elapsed_s=0.0,
        message=(
            f"Rolled back: running {running_ver}, flashed {flashed_ver}. "
            "Discovery ran but the bootloader reverted the image, or the image still reports "
            "an older hardcoded 0x1001 version."
        ),
    )


def report_ota_verdict(
    verdict: OtaConfirmVerdict,
    transfer: OtaTransferResult,
    log: OtaLog,
) -> None:
    """Log transfer + confirm outcome and exit non-zero on failure."""
    log.phase("OTA verdict")
    if transfer.probable_finalize_reboot:
        log.info(
            "Transfer: all bytes sent; last-chunk ACK missing (device likely rebooting)"
        )
    elif transfer.last_chunk_result is not None:
        fc = transfer.last_chunk_result
        log.info(
            f"Transfer: {transfer.chunks_sent} chunks, finalize code={fc:#06x} "
            f"({describe_ota_data_error(fc)})"
        )
        if fc != OTA_SUCCESS:
            raise SystemExit(
                f"OTA commit failed: finalize code={fc:#06x} "
                f"({describe_ota_data_error(fc)})"
            )
    else:
        log.info(f"Transfer: {transfer.chunks_sent} chunks sent ({transfer.total_bytes} B)")

    log.info(verdict.message)
    if verdict.running_ver:
        log.info(f"Running fw:     {verdict.running_ver}")
    log.info(f"Flashed fw:     {verdict.flashed_ver}")

    if verdict.status == "stuck":
        log.info("Result: SUCCESS — patched firmware is running and confirmed.")
        return
    if verdict.status == "reconnect_failed":
        raise SystemExit(
            "OTA transfer finished but post-reboot BLE reconnect failed. "
            "Power-cycle the light and re-run lepro-ota to retry discovery confirm."
        )
    if verdict.status == "rolled_back":
        if verdict.reconnect_elapsed_s > 25:
            log.info(
                "Hint: reconnect took >25s — discovery likely ran after ESP-IDF rollback. "
                "Re-run lepro-ota immediately (faster post-reboot scan is now default)."
            )
        else:
            log.info(
                "Hint: image may have crashed before BLE (#2), or the flashed image still "
                "reports the stock hardcoded 0x1001 semver — inspect prepare_ota_image / "
                "patch_discovery_version; device rolled back safely."
            )
        raise SystemExit(
            f"OTA finished but device rolled back to {verdict.running_ver} "
            f"(expected {verdict.flashed_ver})."
        )
    raise SystemExit(verdict.message)


def check_version_policy(firmware: Path, *, force: bool) -> None:
    fw_ver = firmware_version_from_path(firmware)
    if fw_ver and fw_ver.startswith("2.2.") and not force:
        raise SystemExit(
            f"Firmware {firmware.name} is v{fw_ver} but device is expected on v2.3.18. "
            "Use v2.3.18.patched.bin or pass --force."
        )


def _device_matches(mac: str, device: object) -> bool:
    """True when a bleak device looks like our target light."""
    mac_norm = normalize_mac(mac).upper()
    addr = str(getattr(device, "address", "") or "").upper()
    name = str(getattr(device, "name", "") or "")
    if name == "LP":
        return True
    return addr == mac_norm


async def _find_device_active(
    mac: str,
    log: OtaLog,
    *,
    timeout: float,
) -> object | None:
    """Active BLE scan; on macOS prefer name 'LP' (random peripheral UUIDs)."""
    if sys.platform == "darwin":
        burst = min(timeout, POST_REBOOT_SCAN_BURST_S)
        log.info(f"  scanning for name 'LP' ({burst:.0f}s)…")
        device = await BleakScanner.find_device_by_name("LP", timeout=burst)
        if device is not None:
            return device
        remaining = max(1.0, timeout - burst)
        log.info(f"  scanning for MAC {mac} ({remaining:.0f}s)…")
        return await BleakScanner.find_device_by_address(mac, timeout=remaining)

    log.info(f"  scanning for MAC {mac} ({timeout:.0f}s)…")
    device = await BleakScanner.find_device_by_address(mac, timeout=timeout)
    if device is None:
        burst = min(timeout, POST_REBOOT_SCAN_BURST_S)
        log.info(f"  scanning for name 'LP' ({burst:.0f}s)…")
        device = await BleakScanner.find_device_by_name("LP", timeout=burst)
    return device


async def _watch_for_device(
    mac: str,
    log: OtaLog,
    *,
    deadline: float,
) -> object | None:
    """Passive scan until the light advertises or deadline passes."""
    candidates: list[object] = []
    event = asyncio.Event()

    def _on_detect(device: object, _advertisement_data: object) -> None:
        if _device_matches(mac, device):
            candidates.append(device)
            event.set()

    scanner = BleakScanner(_on_detect)
    await scanner.start()
    try:
        while time.monotonic() < deadline:
            if event.is_set():
                return candidates[-1]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                await asyncio.wait_for(event.wait(), timeout=min(0.5, remaining))
            except asyncio.TimeoutError:
                continue
    finally:
        await scanner.stop()
    return candidates[-1] if candidates else None


async def _connect_to_device(
    device: object,
    mac: str,
    log: OtaLog,
    *,
    debug_rx: bool = False,
    debug_tx: bool = False,
) -> tuple[OtaTransport, BleakClient]:
    name = getattr(device, "name", None) or "(no name)"
    addr = getattr(device, "address", mac)
    rssi = getattr(device, "rssi", None)
    extra = f", RSSI {rssi} dBm" if rssi is not None else ""
    log.info(f"Found {name} @ {addr}{extra}")

    log.phase("BLE connect")
    client = BleakClient(device)
    await client.connect()
    log.info(f"Connected (MTU={client.mtu_size})")

    transport = OtaTransport(
        client=client,
        cmd_char=GATT_CMD,
        rsp_char=GATT_RSP,
        log=log,
        debug_rx=debug_rx,
        debug_tx=debug_tx,
    )
    await client.start_notify(GATT_RSP, transport.on_notify)
    log.info("Subscribed to response notifications")
    await asyncio.sleep(0.15)
    return transport, client


async def _connect(
    mac: str,
    log: OtaLog,
    *,
    debug_rx: bool = False,
    debug_tx: bool = False,
    scan_timeout: float = 15.0,
    device: object | None = None,
) -> tuple[OtaTransport, BleakClient]:
    if device is None:
        log.phase("BLE scan")
        device = await _find_device_active(mac, log, timeout=scan_timeout)
        if device is None:
            raise SystemExit(
                f"Light not found at {mac} (BLE scan timed out). "
                "Confirm MAC, range, and that the bulb is advertising."
            )
    return await _connect_to_device(
        device, mac, log, debug_rx=debug_rx, debug_tx=debug_tx
    )


async def _confirm_with_discovery(
    mac: str,
    transport: OtaTransport,
    flashed_ver: str,
    log: OtaLog,
) -> OtaConfirmVerdict:
    """Send discovery (0x1000) to trigger esp_ota_mark_app_valid_cancel_rollback."""
    session = LeproSession(
        mac, transport, config=SessionConfig(send_delay=0.05, notify_timeout=5.0)
    )
    verdict: OtaConfirmVerdict | None = None
    for attempt in range(1, DISCOVERY_CONFIRM_ATTEMPTS + 1):
        log.info(f"Sending discovery (0x1000) confirm {attempt}/{DISCOVERY_CONFIRM_ATTEMPTS}…")
        dev_info = await session.run_phase_discovery()
        running_ver = version_from_discovery(dev_info.raw_payload)
        if running_ver:
            log.info(f"  running fw: {running_ver}")
        else:
            log.info("  could not parse version from discovery payload")
        verdict = classify_ota_verdict(flashed_ver, running_ver, reconnect_ok=True)
        if verdict.status == "stuck":
            return verdict
        if attempt < DISCOVERY_CONFIRM_ATTEMPTS:
            await asyncio.sleep(1.0)
    assert verdict is not None
    return verdict


async def run_post_reboot_confirm(
    mac: str,
    flashed_ver: str,
    log: OtaLog,
    *,
    transfer_finished_at: float | None = None,
    debug_rx: bool = False,
    scan_timeout: float = 15.0,
    wait_s: float = POST_REBOOT_WAIT_S,
    retry_s: float = POST_REBOOT_RETRY_S,
    retry_interval_s: float = POST_REBOOT_RETRY_INTERVAL_S,
) -> OtaConfirmVerdict:
    """Reconnect after OTA reboot and run discovery while image is still PENDING_VERIFY."""
    log.phase("Post-reboot confirm")
    t_start = transfer_finished_at if transfer_finished_at is not None else time.monotonic()
    log.info(
        f"Device rebooting — must send discovery within ~{retry_s:.0f}s "
        "(FUN_420088d4 → esp_ota_mark_app_valid_cancel_rollback)"
    )
    if wait_s > 0:
        log.info(f"Reboot blackout {wait_s:.0f}s (radio down during reset)…")
        await asyncio.sleep(wait_s)

    deadline = time.monotonic() + retry_s
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        remaining = deadline - time.monotonic()
        log.info(f"Reconnect attempt {attempt} ({remaining:.0f}s left in window)…")

        burst_end = min(time.monotonic() + POST_REBOOT_SCAN_BURST_S, deadline)
        device = await _watch_for_device(mac, log, deadline=burst_end)
        if device is None:
            device = await _find_device_active(
                mac, log, timeout=min(POST_REBOOT_SCAN_BURST_S, remaining)
            )
        if device is None:
            log.info("  device not advertising yet")
            await asyncio.sleep(retry_interval_s)
            continue

        client: BleakClient | None = None
        try:
            transport, client = await _connect_to_device(
                device, mac, log, debug_rx=debug_rx
            )
            verdict = await _confirm_with_discovery(mac, transport, flashed_ver, log)
            verdict.reconnect_elapsed_s = time.monotonic() - t_start
            if verdict.status == "stuck":
                log.info(
                    f"Confirmed in {verdict.reconnect_elapsed_s:.1f}s — "
                    f"running {verdict.running_ver}"
                )
                return verdict
            if verdict.reconnect_elapsed_s > 20:
                log.info(
                    f"Still on {verdict.running_ver} after {verdict.reconnect_elapsed_s:.0f}s "
                    f"(expected {flashed_ver})"
                )
                return verdict
            log.info(
                f"Discovery saw {verdict.running_ver} — retrying connect "
                "(may still be booting PENDING_VERIFY image)…"
            )
        except Exception as exc:
            log.info(f"  connect/discovery failed: {exc!r}")
        finally:
            if client is not None:
                try:
                    await client.disconnect()
                except Exception:
                    pass
        await asyncio.sleep(retry_interval_s)

    return classify_ota_verdict(flashed_ver, None, reconnect_ok=False)


class BleOtaSession:
    """Discovery + auth + chunked OTA transfer."""

    def __init__(
        self,
        session: LeproSession,
        firmware: Path,
        image: bytes,
        log: OtaLog,
    ) -> None:
        self._session = session
        self._firmware = firmware
        self._image = image
        self._log = log

    async def run(
        self,
        json_bytes: bytes,
        *,
        chunk_size: int = 4096,
        max_retries: int = 3,
        dry_run: bool = False,
    ) -> OtaTransferResult:
        chunk_size = min(chunk_size, OTA_MAX_CHUNK)
        s = self._session
        log = self._log
        if s.session_rand is None:
            raise RuntimeError("session_rand not set")

        total = len(self._image)
        n_chunks = (total + chunk_size - 1) // chunk_size
        log.phase("OTA start")
        log.info(f"Image {total} B ({n_chunks} chunks × {chunk_size} B max)")
        log.info(f"OTA start JSON ({len(json_bytes)} B):")
        for line in json.dumps(json.loads(json_bytes), indent=2).splitlines():
            log.info(f"  {line}")

        packets, s.seq = build_ota_start_packets(
            s.mac, s.seq, json_bytes, session_rand=s.session_rand
        )
        log.info(f"Sending OTA start ({len(packets)} fragments, seq→{s.seq})")
        last_ack = await send_ota_packets(s, packets, log, label="otaStart")

        if dry_run:
            log.info(f"Dry-run: would send {total} bytes in {chunk_size}-byte chunks")
            return OtaTransferResult(chunks_sent=0, total_bytes=total, last_chunk_result=None)

        start_resp: DecryptedFrame | None = None
        if last_ack and last_ack.opcode == OP_OTA_START_RESP:
            start_resp = last_ack
        else:
            try:
                start_resp = await wait_opcode_verbose(
                    s, OP_OTA_START_RESP, timeout=10.0, log=log, label="OTA start ACK (0x1011)"
                )
            except TimeoutError:
                if last_ack and last_ack.opcode == OP_BOND_RESP_ALT:
                    result = parse_bond_result(last_ack)
                    hint = describe_ota_start_error(result) if result is not None else "unknown"
                    raise SystemExit(
                        f"OTA start rejected (final frag rsp 0xAAAA): result={result:#x} "
                        f"({hint}) payload={last_ack.payload.hex()}"
                    ) from None
                raise
        parsed = parse_ota_start_resp(start_resp)
        if parsed is None:
            raise RuntimeError(f"failed to parse 0x1011: {start_resp.payload.hex()}")
        log.info(
            f"OTA start ACK: ack_sn={parsed.ack_sn} code={parsed.code:#06x} offset={parsed.offset}"
        )
        if parsed.code not in (OTA_SUCCESS, OTA_START_ALREADY_ACTIVE):
            raise SystemExit(
                f"OTA start rejected: code={parsed.code:#06x} "
                f"({describe_ota_start_error(parsed.code)}) "
                f"payload={start_resp.payload.hex()}"
            )
        if parsed.code == OTA_START_ALREADY_ACTIVE:
            log.info("OTA session already active — resuming data transfer")

        log.phase("OTA data transfer")
        offset = parsed.offset
        chunk_idx = 0
        t0 = time.monotonic()
        last_chunk_result: int | None = None
        probable_finalize_reboot = False
        while offset < total:
            chunk_idx += 1
            chunk = self._image[offset : offset + chunk_size]
            is_last_chunk = offset + len(chunk) >= total
            log.info(
                f"Chunk {chunk_idx}/{n_chunks}: offset={offset} len={len(chunk)} "
                f"({100.0 * offset / total:.1f}% done)"
            )
            chunk_ok = False
            for attempt in range(max_retries):
                packets, s.seq = build_ota_chunk_packets(
                    s.mac, s.seq, offset, chunk, session_rand=s.session_rand
                )
                data_resp = await send_ota_packets(s, packets, log, label=f"otaData@{offset}")
                if data_resp is None or data_resp.opcode != OP_OTA_DATA_RESP:
                    try:
                        data_resp = await wait_opcode_verbose(
                            s,
                            OP_OTA_DATA_RESP,
                            timeout=15.0 if not is_last_chunk else 8.0,
                            log=log,
                            label=f"chunk {chunk_idx}/{n_chunks} ACK (0x1013)",
                            heartbeat=3.0,
                        )
                    except TimeoutError:
                        if is_last_chunk:
                            log.info(
                                f"  chunk {chunk_idx}/{n_chunks}: no ACK after last chunk "
                                "(device likely rebooting) — deferring verdict to post-reboot check"
                            )
                            probable_finalize_reboot = True
                            last_chunk_result = OTA_SUCCESS
                            offset += len(chunk)
                            chunk_ok = True
                            break
                        if attempt + 1 >= max_retries:
                            raise
                        log.info(
                            f"  chunk {chunk_idx} @ {offset}: timeout, "
                            f"retry {attempt + 2}/{max_retries}"
                        )
                        continue
                dp = parse_ota_data_resp(data_resp)
                if dp is None:
                    raise RuntimeError(
                        f"failed to parse 0x1013 @ {offset}: {data_resp.payload.hex()}"
                    )
                log.info(
                    f"  chunk {chunk_idx}/{n_chunks} result={dp.result:#06x} "
                    f"({describe_ota_data_error(dp.result)})"
                )
                if is_last_chunk:
                    log.info(
                        f"  finalize code={dp.result:#06x} "
                        f"({describe_ota_data_error(dp.result)})"
                    )
                    last_chunk_result = dp.result
                if dp.result != OTA_SUCCESS:
                    if attempt + 1 >= max_retries:
                        raise SystemExit(
                            f"chunk @ {offset} failed: result={dp.result:#06x} "
                            f"({describe_ota_data_error(dp.result)}) "
                            f"payload={data_resp.payload.hex()}"
                        )
                    log.info(
                        f"  chunk {chunk_idx} @ {offset}: NAK {dp.result:#06x}, "
                        f"retry {attempt + 2}/{max_retries}"
                    )
                    continue
                if not is_last_chunk:
                    last_chunk_result = dp.result
                chunk_ok = True
                break
            if not chunk_ok:
                raise RuntimeError(f"chunk {chunk_idx} @ {offset} failed after {max_retries} tries")

            if probable_finalize_reboot:
                break

            offset += len(chunk)
            pct = 100.0 * offset / total
            elapsed = time.monotonic() - t0
            rate = offset / elapsed if elapsed > 0 else 0
            eta = (total - offset) / rate if rate > 0 else 0
            log.info(
                f"  ACK chunk {chunk_idx}/{n_chunks}: {offset}/{total} ({pct:.1f}%) "
                f"— {rate / 1024:.1f} KiB/s, ETA {eta:.0f}s"
            )

        log.phase("OTA transfer complete")
        if probable_finalize_reboot:
            log.info("All bytes sent — device should be rebooting into the new image")
        else:
            log.info("Transfer finished — device should reboot shortly")

        return OtaTransferResult(
            chunks_sent=chunk_idx,
            total_bytes=total,
            last_chunk_result=last_chunk_result,
            probable_finalize_reboot=probable_finalize_reboot,
        )


async def run_ota(args: argparse.Namespace) -> None:
    log = OtaLog(verbose=not args.quiet)
    mac = normalize_mac(args.mac)
    firmware = Path(args.firmware)
    if not firmware.is_file():
        raise SystemExit(f"Firmware not found: {firmware}")

    check_version_policy(firmware, force=args.force)

    reflash = getattr(args, "reflash", False)

    image, ota_ver = prepare_ota_image(
        firmware,
        version=getattr(args, "ota_version", None),
        reflash=reflash,
    )
    fw_ver = firmware_version_from_path(firmware) or "?"
    log.phase("OTA prep")
    log.info(f"Target MAC:     {mac}")
    log.info(f"Firmware:       {firmware}")
    log.info(f"File version:   {fw_ver}")
    log.info(f"Image size:     {len(image)} B")
    log.info(f"Image MD5:      {md5_hex(image)}")
    log.info(f"Chunk size:     {args.chunk_size} B")
    if args.force:
        log.info("Version policy: --force (cross-version allowed)")
    if args.dry_run:
        log.info("Mode:           dry-run (no BLE writes)")

    if args.ota_json:
        json_bytes = Path(args.ota_json).read_bytes()
        log.info(f"OTA JSON:       {args.ota_json}")
    else:
        json_bytes = build_ota_start_json(
            firmware,
            image,
            version=ota_ver,
            path_version=getattr(args, "ota_path_version", None),
            ota_secret=args.ota_secret,
        )
        log.info(f"OTA version:    {ota_ver}" + (" (reflash bump)" if reflash and ota_ver != fw_ver else ""))
    try:
        json_obj = json.loads(json_bytes)
    except json.JSONDecodeError:
        json_obj = {}
    json_meta = json_obj if isinstance(json_obj, dict) else {}

    if args.dry_run:
        transport = DryRunTransport()
        session = LeproSession(mac, transport, config=SessionConfig(dry_run=True, send_delay=0))
        log.phase("Discovery (dry-run)")
        dev_info = await session.run_phase_discovery()
        log.info(f"session_rand=0x{session.session_rand:08X}" if session.session_rand else "no session_rand")
        creds = load_creds(mac)
        if creds:
            log.phase("Auth (dry-run)")
            await session.run_phase_auth(creds)
            log.info("Auth OK (saved bond creds)")
        ota = BleOtaSession(session, firmware, image, log)
        await ota.run(json_bytes, chunk_size=args.chunk_size, dry_run=True)
        for label, pkt in transport.sent:
            log.info(f"  [{label}] {len(pkt)} B: {pkt.hex()}")
        return

    creds = load_creds(mac)
    if creds is None:
        raise SystemExit(
            f"No bond creds at {creds_path(mac)}. Bond first:\n"
            f"  uv run lepro-bond --mac {mac}"
        )

    transport, client = await _connect(
        mac, log, debug_rx=args.debug_rx, debug_tx=args.debug_tx, scan_timeout=args.scan_timeout
    )
    try:
        session = LeproSession(
            mac, transport, config=SessionConfig(send_delay=0.05, notify_timeout=5.0)
        )
        log.phase("Discovery")
        dev_info = await session.run_phase_discovery()
        log.info(f"session_rand=0x{session.session_rand:08X}" if session.session_rand else "no session_rand")
        running_ver = version_from_discovery(dev_info.raw_payload)
        if running_ver:
            log.info(f"Running fw:     {running_ver}")
        if not args.ota_json:
            adjusted = adjust_ota_version_for_running(running_ver, ota_ver, reflash=reflash)
            if adjusted != ota_ver:
                log.info(
                    f"OTA version bump: {ota_ver} → {adjusted} "
                    f"(device already on {running_ver})"
                )
                ota_ver = adjusted
                image, ota_ver = prepare_ota_image(
                    firmware,
                    version=ota_ver,
                    reflash=reflash,
                )
                json_bytes = build_ota_start_json(
                    firmware,
                    image,
                    version=ota_ver,
                    path_version=getattr(args, "ota_path_version", None),
                    ota_secret=args.ota_secret,
                )
        log.phase("Auth")
        log.info("Using saved bond creds")
        await session.run_phase_auth(creds)
        log.info("Auth OK")

        ota = BleOtaSession(session, firmware, image, log)
        transfer = await ota.run(json_bytes, chunk_size=args.chunk_size)
        transfer_finished_at = time.monotonic()

        log.info("Disconnecting before post-reboot confirm…")
        await client.disconnect()
        client = None  # type: ignore[assignment]

        verdict = await run_post_reboot_confirm(
            mac,
            ota_ver,
            log,
            transfer_finished_at=transfer_finished_at,
            debug_rx=args.debug_rx,
            scan_timeout=args.scan_timeout,
            wait_s=args.confirm_wait,
            retry_s=args.confirm_retry,
        )
        report_ota_verdict(verdict, transfer, log)
    finally:
        if client is not None:
            log.info("Disconnecting…")
            await client.disconnect()
            log.info("Disconnected")


def main() -> None:
    p = argparse.ArgumentParser(description="Lepro ZB1 BLE firmware OTA (0x1010/0x1012)")
    p.add_argument("--mac", required=True, help="Target light MAC")
    p.add_argument(
        "--firmware",
        type=Path,
        default=DEFAULT_FIRMWARE,
        help=f"ESP-IDF image to flash (default: {DEFAULT_FIRMWARE})",
    )
    p.add_argument("--chunk-size", type=int, default=4096, help="Data chunk size (max 5112)")
    p.add_argument("--ota-json", type=Path, help="Override OTA start JSON file")
    p.add_argument(
        "--ota-version",
        help="version in start JSON (default: from firmware filename)",
    )
    p.add_argument(
        "--ota-path-version",
        help="Version to place in path filename (default: keep firmware filename version)",
    )
    p.add_argument(
        "--reflash",
        action="store_true",
        help=(
            "Opt-in: bump patch version (e.g. for cloud/do_check:1 flashing). "
            "Not needed for the default BLE do_check:0 path"
        ),
    )
    p.add_argument("--ota-secret", default="", help="secret field (default empty)")
    p.add_argument("--force", action="store_true", help="Allow cross-version flash (e.g. v2.2.13)")
    p.add_argument("--dry-run", action="store_true", help="Build packets only; no BLE transfer")
    p.add_argument("--quiet", "-q", action="store_true", help="Minimal output (errors only)")
    p.add_argument("--debug-tx", action="store_true", help="Log full TX wire hex")
    p.add_argument("--debug-rx", action="store_true", help="Log full RX wire hex")
    p.add_argument("--scan-timeout", type=float, default=15.0, help="BLE scan timeout (seconds)")
    p.add_argument(
        "--confirm-wait",
        type=float,
        default=POST_REBOOT_WAIT_S,
        help="Seconds to wait after OTA reboot before scanning (default: 2)",
    )
    p.add_argument(
        "--confirm-retry",
        type=float,
        default=POST_REBOOT_RETRY_S,
        help="Seconds to keep scanning/connecting for post-reboot discovery (default: 90)",
    )
    asyncio.run(run_ota(p.parse_args()))


if __name__ == "__main__":
    main()
