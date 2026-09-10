#!/usr/bin/env python3
"""Convert an ESP-IDF application .bin (esptool image) to ELF for Ghidra import.

Ghidra's raw-binary import loads everything at base 0. ESP32-S3 firmware uses
multiple load regions (IROM ~0x42000020, IRAM ~0x40378000, DRAM, DROM, etc.).
This script rebuilds a minimal ET_EXEC ELF with PT_LOAD segments at the correct VMAs.

Usage:
    uv run esp_idf_bin_to_elf.py firmware/3_le_light_zb1_pid_55_v2.2.13.bin
    uv run esp_idf_bin_to_elf.py firmware/foo.bin -o firmware/foo.elf
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

IMAGE_MAGIC = 0xE9
EM_XTENSA = 0x5E
ET_EXEC = 2
PT_LOAD = 1

PF_X = 1
PF_W = 2
PF_R = 4

SHT_NULL = 0
SHT_PROGBITS = 1
SHT_STRTAB = 3

SHF_WRITE = 0x1
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4

SEG_NAMES = (".drom", ".dram", ".iram0", ".irom0", ".iram1", ".rtc")


@dataclass(frozen=True)
class Segment:
    load_addr: int
    data: bytes
    name: str

    @property
    def p_flags(self) -> int:
        addr = self.load_addr
        if 0x42000000 <= addr < 0x43000000:
            return PF_R | PF_X
        if 0x40370000 <= addr < 0x40400000:
            return PF_R | PF_X
        if 0x3C000000 <= addr < 0x3D000000:
            return PF_R
        if 0x3FC00000 <= addr < 0x3FE00000:
            return PF_R | PF_W
        if 0x60000000 <= addr:
            return PF_R | PF_W
        return PF_R | PF_W

    @property
    def sh_flags(self) -> int:
        flags = SHF_ALLOC
        if self.p_flags & PF_X:
            flags |= SHF_EXECINSTR
        if self.p_flags & PF_W:
            flags |= SHF_WRITE
        return flags


def _align4(n: int) -> int:
    return (n + 3) & ~3


def parse_esp_image(data: bytes) -> tuple[int, list[Segment]]:
    if len(data) < 24 or data[0] != IMAGE_MAGIC:
        raise ValueError("not an ESP image (expected magic 0xE9)")

    seg_count = data[1]
    entry = struct.unpack_from("<I", data, 4)[0]
    pos = 24  # standard header; S3 extended fields are inside first segment gap

    segments: list[Segment] = []
    for _ in range(seg_count):
        if pos + 8 > len(data):
            raise ValueError("truncated segment header")
        load_addr, length = struct.unpack_from("<II", data, pos)
        pos += 8
        if pos + length > len(data):
            raise ValueError(f"truncated segment payload @ 0x{load_addr:08x}")
        payload = data[pos : pos + length]
        pos += _align4(length)
        name = SEG_NAMES[len(segments)] if len(segments) < len(SEG_NAMES) else f".seg{len(segments)}"
        segments.append(Segment(load_addr, payload, name))

    return entry, segments


def _build_shstrtab(segments: list[Segment]) -> bytes:
    parts = [b"\0"]
    for seg in segments:
        parts.append(seg.name.encode() + b"\0")
    parts.append(b".shstrtab\0")
    return b"".join(parts)


def build_elf(entry: int, segments: list[Segment]) -> bytes:
    if not segments:
        raise ValueError("no segments")

    ehdr_size = 52
    phdr_size = 32
    shdr_size = 40
    phnum = len(segments)
    shnum = phnum + 2  # NULL + segments + .shstrtab
    shstrndx = phnum + 1
    phoff = ehdr_size
    headers_size = ehdr_size + phnum * phdr_size

    offset = headers_size
    layout: list[tuple[Segment, int]] = []
    for seg in segments:
        layout.append((seg, offset))
        offset += len(seg.data)

    shstrtab = _build_shstrtab(segments)
    shstr_off = offset
    shoff = shstr_off + len(shstrtab)

    name_offsets = [0]
    cursor = 1
    for seg in segments:
        name_offsets.append(cursor)
        cursor += len(seg.name) + 1
    shstrtab_name_off = cursor

    ehdr = struct.pack(
        "<4sBBBB8xHHIIIIIHHHHHH",
        b"\x7fELF",
        1,
        1,
        1,
        0,
        ET_EXEC,
        EM_XTENSA,
        1,
        entry,
        phoff,
        shoff,
        0,
        ehdr_size,
        phdr_size,
        phnum,
        shdr_size,
        shnum,
        shstrndx,
    )

    phdrs = bytearray()
    for seg, file_off in layout:
        phdrs += struct.pack(
            "<IIIIIIII",
            PT_LOAD,
            file_off,
            seg.load_addr,
            seg.load_addr,
            len(seg.data),
            len(seg.data),
            seg.p_flags,
            0x4,
        )

    body = bytearray(ehdr + phdrs)
    for seg, file_off in layout:
        if file_off != len(body):
            raise RuntimeError("ELF layout mismatch")
        body += seg.data

    body += shstrtab

    shdrs = bytearray()
    shdrs += struct.pack("<IIIIIIIIII", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    for (seg, file_off), name_off in zip(layout, name_offsets[1:], strict=True):
        shdrs += struct.pack(
            "<IIIIIIIIII",
            name_off,
            SHT_PROGBITS,
            seg.sh_flags,
            seg.load_addr,
            file_off,
            len(seg.data),
            0,
            0,
            0x4,
            0,
        )
    shdrs += struct.pack(
        "<IIIIIIIIII",
        shstrtab_name_off,
        SHT_STRTAB,
        0,
        0,
        shstr_off,
        len(shstrtab),
        0,
        0,
        0x1,
        0,
    )
    if len(shdrs) != shnum * shdr_size:
        raise RuntimeError("section header table size mismatch")
    if shoff != len(body):
        raise RuntimeError("section header offset mismatch")

    body += shdrs
    return bytes(body)


def convert(src: Path, dst: Path) -> None:
    data = src.read_bytes()
    entry, segments = parse_esp_image(data)
    elf = build_elf(entry, segments)
    dst.write_bytes(elf)

    print(f"source:   {src}")
    print(f"output:   {dst}")
    print(f"entry:    0x{entry:08x}")
    print(f"segments: {len(segments)}")
    for i, seg in enumerate(segments):
        print(
            f"  [{i}] vma=0x{seg.load_addr:08x} "
            f"size=0x{len(seg.data):x} flags=0x{seg.p_flags:x} ({seg.name})"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bin", type=Path, help="ESP-IDF application .bin")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output .elf (default: same name with .elf suffix)",
    )
    args = parser.parse_args(argv)

    src: Path = args.bin
    if not src.is_file():
        print(f"error: file not found: {src}", file=sys.stderr)
        return 1

    dst = args.output or src.with_suffix(".elf")
    convert(src, dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
