"""Load firmware patch profiles from firmware/patch-profiles.toml."""

from __future__ import annotations

import fnmatch
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from lepro.paths import repo_path

DEFAULT_PROFILES_PATH = repo_path("firmware/patch-profiles.toml")
_HEX_RE = re.compile(r"^[0-9a-fA-F]*$")


@dataclass(frozen=True)
class BytePatch:
    name: str
    offset: int
    stock: bytes
    patched: bytes


@dataclass(frozen=True)
class BundleConfig:
    signature: bytes
    attach_error: bytes
    lookback: int
    expected_cert_count: int
    bundle_off: int | None = None
    entry_off: int | None = None


@dataclass(frozen=True)
class FirmwareProfile:
    id: str
    description: str
    chip: str
    image_glob: str
    stock_image: Path
    patched_image: Path
    ota_url: str
    bundle: BundleConfig
    patches: tuple[BytePatch, ...]


@dataclass(frozen=True)
class PatchProfiles:
    default_profile: str
    profiles: tuple[FirmwareProfile, ...]

    def by_id(self, profile_id: str) -> FirmwareProfile:
        for profile in self.profiles:
            if profile.id == profile_id:
                return profile
        known = ", ".join(p.id for p in self.profiles)
        raise SystemExit(f"Unknown profile {profile_id!r}; known: {known}")


def parse_hex(value: str, *, field: str) -> bytes:
    cleaned = value.strip().replace(" ", "")
    if cleaned.startswith("0x") or cleaned.startswith("0X"):
        cleaned = cleaned[2:]
    if not cleaned:
        raise SystemExit(f"{field}: empty hex string")
    if len(cleaned) % 2:
        raise SystemExit(f"{field}: hex string must have even length, got {len(cleaned)}")
    if not _HEX_RE.fullmatch(cleaned):
        raise SystemExit(f"{field}: invalid hex characters in {value!r}")
    return bytes.fromhex(cleaned)


def _parse_int(value: object, *, field: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise SystemExit(f"{field}: expected integer, got {type(value).__name__}")


def _parse_bundle(raw: dict, *, profile_id: str) -> BundleConfig:
    prefix = f"profile {profile_id!r} bundle"
    signature = parse_hex(str(raw.get("signature_hex", "")), field=f"{prefix}.signature_hex")
    attach_error = str(raw.get("attach_error", "")).encode()
    if not attach_error:
        raise SystemExit(f"{prefix}.attach_error is required")
    lookback = _parse_int(raw.get("lookback", 512), field=f"{prefix}.lookback")
    expected_cert_count = _parse_int(
        raw.get("expected_cert_count", 1),
        field=f"{prefix}.expected_cert_count",
    )
    bundle_off = raw.get("bundle_off")
    entry_off = raw.get("entry_off")
    return BundleConfig(
        signature=signature,
        attach_error=attach_error,
        lookback=lookback,
        expected_cert_count=expected_cert_count,
        bundle_off=_parse_int(bundle_off, field=f"{prefix}.bundle_off") if bundle_off is not None else None,
        entry_off=_parse_int(entry_off, field=f"{prefix}.entry_off") if entry_off is not None else None,
    )


def _parse_patch(raw: dict, *, profile_id: str, index: int) -> BytePatch:
    prefix = f"profile {profile_id!r} patches[{index}]"
    name = str(raw.get("name", ""))
    if not name:
        raise SystemExit(f"{prefix}.name is required")
    offset = _parse_int(raw.get("offset"), field=f"{prefix}.offset")
    stock = parse_hex(str(raw.get("stock_hex", "")), field=f"{prefix}.stock_hex")
    patched = parse_hex(str(raw.get("patched_hex", "")), field=f"{prefix}.patched_hex")
    if len(stock) != len(patched):
        raise SystemExit(
            f"{prefix}: stock_hex ({len(stock)} bytes) and patched_hex "
            f"({len(patched)} bytes) must be the same length"
        )
    return BytePatch(name=name, offset=offset, stock=stock, patched=patched)


def _parse_profile(raw: dict) -> FirmwareProfile:
    profile_id = str(raw.get("id", ""))
    if not profile_id:
        raise SystemExit("profile missing required field 'id'")
    bundle_raw = raw.get("bundle")
    if not isinstance(bundle_raw, dict):
        raise SystemExit(f"profile {profile_id!r} missing required [bundle] section")
    patches_raw = raw.get("patches", [])
    if not isinstance(patches_raw, list):
        raise SystemExit(f"profile {profile_id!r} patches must be a list")
    patches = tuple(
        _parse_patch(entry, profile_id=profile_id, index=i)
        for i, entry in enumerate(patches_raw)
    )
    stock_image = repo_path(str(raw.get("stock_image", "")))
    patched_image = repo_path(str(raw.get("patched_image", "")))
    if not str(raw.get("stock_image", "")):
        raise SystemExit(f"profile {profile_id!r} missing stock_image")
    if not str(raw.get("patched_image", "")):
        raise SystemExit(f"profile {profile_id!r} missing patched_image")
    return FirmwareProfile(
        id=profile_id,
        description=str(raw.get("description", "")),
        chip=str(raw.get("chip", "esp32s3")),
        image_glob=str(raw.get("image_glob", "")),
        stock_image=stock_image,
        patched_image=patched_image,
        ota_url=str(raw.get("ota_url", "")),
        bundle=_parse_bundle(bundle_raw, profile_id=profile_id),
        patches=patches,
    )


def load_profiles(path: Path | None = None) -> PatchProfiles:
    cfg_path = path or DEFAULT_PROFILES_PATH
    if not cfg_path.is_file():
        raise SystemExit(f"Firmware profiles not found: {cfg_path}")
    data = tomllib.loads(cfg_path.read_text())
    default_profile = str(data.get("default_profile", ""))
    if not default_profile:
        raise SystemExit(f"{cfg_path}: default_profile is required")
    raw_profiles = data.get("profiles", [])
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise SystemExit(f"{cfg_path}: at least one [[profiles]] entry is required")
    profiles = tuple(_parse_profile(entry) for entry in raw_profiles)
    ids = {p.id for p in profiles}
    if default_profile not in ids:
        raise SystemExit(
            f"{cfg_path}: default_profile {default_profile!r} not found "
            f"(known: {', '.join(sorted(ids))})"
        )
    return PatchProfiles(default_profile=default_profile, profiles=profiles)


def resolve_profile(
    profiles: PatchProfiles,
    *,
    firmware_path: Path | None = None,
    profile_id: str | None = None,
) -> FirmwareProfile:
    if profile_id is not None:
        return profiles.by_id(profile_id)
    if firmware_path is not None:
        name = firmware_path.name
        matches = [p for p in profiles.profiles if fnmatch.fnmatch(name, p.image_glob)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            ids = ", ".join(p.id for p in matches)
            raise SystemExit(
                f"Firmware {name!r} matches multiple profiles: {ids}; use --profile"
            )
    return profiles.by_id(profiles.default_profile)
