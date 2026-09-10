#!/usr/bin/env python3
"""Cross-check OTA info JSON parser field names against the firmware ELF.

Reads Xtensa ESP32 literal pools at 0x420009ac (field names) and 0x420009f4
(envelope keys) directly from the binary — no Ghidra required for string proof.

Usage:
    uv run python tools/validate_ota_parser.py
    uv run python tools/validate_ota_parser.py --dump-asm
    uv run python tools/validate_ota_parser.py --simulate ../tmp/ota-info-v2-experiment.json
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

from lepro.paths import repo_path

REPO_ROOT = repo_path()
DEFAULT_ELF = repo_path("firmware/3_le_light_zb1_pid_55_v2.3.18.elf")

FIELD_POOL = 0x420009AC
FIELD_COUNT = 7
ENVELOPE_POOL = 0x420009F4
ENVELOPE_COUNT = 2

EXPECTED_FIELDS = (
    "fwType",
    "do_check",
    "version",
    "hash",
    "path",
    "size",
    "secret",
)
EXPECTED_ENVELOPE = ("action", "fwUpgrade")
EXPECTED_ACTION_VALUE = "fwUpgrade"
EXPECTED_PARAMS = "params"

HELPER_POOL = {
    0x420009D4: ("cJSON_IsString", 0x420B855C),
    0x420009D8: ("validate_string_len", 0x400014F4),
    0x420009DC: ("cJSON_IsNumber", 0x420B8548),
    0x420009E0: ("cJSON_GetStringValue", 0x40001380),
    0x42000A00: ("cJSON_IsArray", 0x420B8570),
}

FUN_42008EB0_ASM = """\
; FUN_42008eb0 — OTA info object parser (v2.3.18)
; a2 = cJSON object, a3 = mode flag, a4 = ctx
; Returns a2: 0=ok, 3=fail (BLE maps 3 -> 0x112)

42008eb0: entry a1,0x20
42008eb3: bnez.n a2,0x42008eb9
42008eb5: j 0x42008f60                    ; null root -> fail
42008eb9: l32r a11,0x420009ac             ; "fwType"
42008ebc: mov a10,a2
42008ebf: call8 0x42038c8c                ; cJSON_GetObjectItem
42008ec5: bnez a10,0x42008ed5
42008ec8: call8 0x42009728                ; log missing fwType
42008ecd: bnez.n a10,0x42008ef5
42008ecf: j 0x42008f60                    ; fail
42008ed5: l32r a8,0x420009d4              ; cJSON_IsString
42008ed8: callx8 a8
42008edb: beqz a10,0x42008ec8
42008ede: l32i.n a10,a4,0x10              ; string value ptr
42008ee0: movi a12,0x10                   ; max len 16
42008ee3: movi a11,0x0
42008ee6: l32r a8,0x420009d8              ; validate_string_len
42008ee9: callx8 a8
42008eef: beqz a10,0x42008ec8
42008ef5: l32r a11,0x420009b0             ; "do_check"
42008efb: call8 0x42038c8c
42008f01: bnez a10,0x42008f09
42008f04: movi.n a5,0x1                   ; default do_check=1
42008f09: l32r a8,0x420009dc              ; cJSON_IsNumber
42008f12: l8ui a5,a5,0x14                 ; cJSON.number.valueint
42008f15: l32r a11,0x420009b4             ; "version"
42008f18: s8i a5,a4,0x1b                  ; store do_check byte
42008f1d: call8 0x42038c8c
42008f22: beqz.n a10,0x42008f65           ; version required
42008f24: l32r a8,0x420009d4              ; cJSON_IsString
42008f36: l32i.n a10,a5,0x10
42008f38: l32r a8,0x420009e0              ; cJSON_GetStringValue
42008f41: s32i.n a10,a4,0x24              ; ctx->version (no counter++)
42008f43: beqz.n a5,0x42008f6a           ; if do_check==0 force path below
42008f6c: l32r a11,0x420009b8             ; "hash"
42008f71: call8 0x42038c8c
42008f76: beqz.n a10,0x42008f96           ; hash required
42008f8c: addi.n a5,a5,0x1                  ; counter++
42008f94: s32i.n a10,a4,0x20
42008f96: l32r a11,0x420009bc             ; "path"
42008f9b: call8 0x42038c8c
42008fa0: beqz.n a10,0x42008fc5           ; path required
42008fb9: addi a5,a5,0x1                    ; counter++
42008fc2: s32i a10,a4,0x28
42008fc5: l32r a11,0x420009c0             ; "size"
42008fca: call8 0x42038c8c
42008fcf: bnez.n a10,0x42008fd4
42008fdc: l32i.n a10,a4,0x1c              ; reuse cached size ptr if missing
42008fd4: l32r a8,0x420009d4              ; cJSON_IsString (NOT number!)
42008fe4: movi.n a12,0xa                  ; max len 10
42008fe8: l32r a8,0x420009d8              ; validate_string_len
42008ff0: addi.n a5,a5,0x1                  ; counter++ if parsed
42008ff9: l32r a11,0x420009c4             ; "secret"
42008fff: call8 0x42038c8c
42009005: bnez a10,0x42009025
42009008: log "ota info error" / "le_ota"   ; secret missing
42009020: movi.n a2,0x3
42009025: l32r a8,0x420009d4              ; cJSON_IsString
42009045: bnei a5,0x4,0x42009008           ; need counter==4
42009048: movi.n a2,0x0                   ; success
42009052: retw.n
"""


class Elf32:
    def __init__(self, data: bytes) -> None:
        if data[:4] != b"\x7fELF" or data[4] != 1:
            raise ValueError("expected 32-bit ELF")
        self.data = data
        self.phoff = struct.unpack_from("<I", data, 0x1C)[0]
        self.phentsize = struct.unpack_from("<H", data, 0x2A)[0]
        self.phnum = struct.unpack_from("<H", data, 0x2C)[0]

    def u32(self, off: int) -> int:
        return struct.unpack_from("<I", self.data, off)[0]

    def vma_to_offset(self, vma: int) -> int | None:
        for i in range(self.phnum):
            base = self.phoff + i * self.phentsize
            p_type, p_offset, p_vaddr, _p_paddr, p_filesz, _p_memsz, _flags, _align = (
                struct.unpack_from("<IIIIIIII", self.data, base)
            )
            if p_type != 1:
                continue
            if p_vaddr <= vma < p_vaddr + p_filesz:
                return p_offset + (vma - p_vaddr)
        return None

    def read_cstr(self, vma: int) -> str | None:
        off = self.vma_to_offset(vma)
        if off is None:
            return None
        end = self.data.index(b"\x00", off)
        return self.data[off:end].decode("utf-8", "replace")

    def pool_strings(self, pool_vma: int, count: int) -> list[tuple[int, int, str | None]]:
        pool_off = self.vma_to_offset(pool_vma)
        if pool_off is None:
            raise ValueError(f"literal pool {pool_vma:#x} not in ELF")
        out: list[tuple[int, int, str | None]] = []
        for i in range(count):
            slot_vma = pool_vma + i * 4
            ptr = self.u32(pool_off + i * 4)
            out.append((slot_vma, ptr, self.read_cstr(ptr)))
        return out


def simulate_parse(obj: dict[str, Any], *, ctx0: int = 1, running_version: str = "2.3.18") -> str:
    """Walk the FUN_42008eb0 branch logic symbolically; return failing PC label."""

    def fail(label: str) -> str:
        return label

    if not obj:
        return fail("0x42008eb0 null root")

    fw = obj.get("fwType")
    if fw is not None:
        if not isinstance(fw, str):
            return fail("0x42008ed5 fwType not string")
        if not (0 < len(fw) <= 16):
            return fail("0x42008ef2 fwType length validate")

    dc = obj.get("do_check", 1)
    if dc is not None and not isinstance(dc, (int, float)):
        dc = 1
    do_check = int(dc) if isinstance(dc, (int, float)) else 1

    ver = obj.get("version")
    if ver is None or not isinstance(ver, str):
        counter = 0
    else:
        if do_check != 0:
            if ctx0 == 0:
                return fail("0x42008f48 ctx[0]==0 (version gate)")
            if ver == running_version:
                return fail("0x42008f56 strcmp(ctx,version)==0 (same version)")
        counter = 1

    for field in ("hash", "path"):
        val = obj.get(field)
        if val is None or not isinstance(val, str):
            return fail(f"0x42008f96 missing/invalid {field}")
        counter += 1

    size = obj.get("size")
    if size is not None:
        if not isinstance(size, str):
            return fail("0x42008fd4 size not string")
        if not (0 < len(size) <= 10):
            return fail("0x42008fe8 size length validate")
        counter += 1
    elif not isinstance(obj.get("size"), str):
        # missing size: counter may still pass if ctx+0x1c preloaded; treat as fail
        return fail("0x42008fc5 size missing")

    if "secret" not in obj:
        return fail("0x42009005 secret key missing")
    if not isinstance(obj["secret"], str):
        return fail("0x42009025 secret not string")

    if counter != 4:
        return fail(f"0x42009045 counter=={counter} (need 4)")

    return "0x42009050 success (return 0)"


def validate(elf_path: Path) -> int:
    elf = Elf32(elf_path.read_bytes())
    ok = True

    print(f"ELF: {elf_path}")
    print()

    fields = elf.pool_strings(FIELD_POOL, FIELD_COUNT)
    print("Field literal pool @ 0x420009ac:")
    for slot, ptr, name in fields:
        expected = EXPECTED_FIELDS[(slot - FIELD_POOL) // 4]
        mark = "OK" if name == expected else "MISMATCH"
        if name != expected:
            ok = False
        print(f"  {slot:#10x} -> {ptr:#10x}  {name!r:12}  [{mark}]")

    print()
    env = elf.pool_strings(ENVELOPE_POOL, ENVELOPE_COUNT)
    print("Envelope literal pool @ 0x420009f4:")
    action_slot, action_ptr, action_key = env[0]
    value_slot, value_ptr, action_val = env[1]
    params_ptr = elf.u32(elf.vma_to_offset(0x420009FC) or 0)
    params = elf.read_cstr(params_ptr)
    print(f"  {action_slot:#10x} -> {action_ptr:#10x}  {action_key!r}")
    print(f"  {value_slot:#10x} -> {value_ptr:#10x}  {action_val!r}  (strcmp target)")
    print(f"  {'0x420009fc':>10} -> {params_ptr:#10x}  {params!r}")
    if action_key != "action" or action_val != EXPECTED_ACTION_VALUE or params != EXPECTED_PARAMS:
        ok = False

    print()
    print("Helper pointers:")
    for slot, (label, expect) in HELPER_POOL.items():
        off = elf.vma_to_offset(slot)
        got = elf.u32(off) if off is not None else 0
        mark = "OK" if got == expect else f"expected {expect:#x}"
        if got != expect:
            ok = False
        print(f"  {slot:#10x}  {label:22}  {got:#10x}  [{mark}]")

    err_ptr = elf.u32(elf.vma_to_offset(0x420009CC) or 0)
    err = elf.read_cstr(err_ptr)
    print()
    print(f"Missing-secret log format @ {err_ptr:#x}: {err!r}")

    print()
    print("Inferred JSON contract:")
    print("  Flat path (0x4200958d): object with fields above.")
    print("  Envelope path (0x420090e0): [{\"action\":\"fwUpgrade\",\"params\":{...}}]")
    print("  fwType, version, hash, path, size, secret: JSON strings")
    print("  do_check: JSON number (not bool); default 1 if absent")
    print("  size: string, max 10 chars — a JSON number fails cJSON_IsString")
    print("  Success when internal counter a5 == 4 at 0x42009045")
    print("  Parser return 3 -> BLE start sets a2=0x112 @ 0x42009597")

    print()
    if ok:
        print("VALIDATION: PASS — ELF strings and helper pointers match expected schema.")
        return 0
    print("VALIDATION: FAIL — see mismatches above.")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--elf",
        type=Path,
        default=DEFAULT_ELF,
        help=f"firmware ELF (default: {DEFAULT_ELF.name})",
    )
    parser.add_argument(
        "--dump-asm",
        action="store_true",
        help="print annotated Xtensa listing for FUN_42008eb0",
    )
    parser.add_argument(
        "--simulate",
        type=Path,
        metavar="JSON",
        help="symbolic branch walk for a JSON object file",
    )
    parser.add_argument(
        "--ctx0",
        type=int,
        default=1,
        help="simulated ctx[0] byte for version gate (default 1)",
    )
    parser.add_argument(
        "--running-version",
        default="2.3.18",
        help="simulated running fw version at ctx base for strcmp",
    )
    args = parser.parse_args()
    if args.simulate:
        obj = json.loads(args.simulate.read_text())
        print(simulate_parse(obj, ctx0=args.ctx0, running_version=args.running_version))
        sys.exit(0)
    if not args.elf.is_file():
        print(f"ELF not found: {args.elf}", file=sys.stderr)
        sys.exit(2)
    if args.dump_asm:
        print(FUN_42008EB0_ASM)
    sys.exit(validate(args.elf))


if __name__ == "__main__":
    main()
