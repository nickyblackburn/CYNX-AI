#!/usr/bin/env python3
"""
RX path: CRC verify, fragment reassembly (FUN_0x18cb58), MAC-key decrypt (FUN_0x1925a8).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from lepro.crypto import MAIN_IV, decrypt_cbc, derive_aes_key, derive_session_key
from lepro.protocol import (
    MAGIC_FRAG_FIRST,
    MAGIC_FRAG_FIRST_ENC,
    MAGIC_FRAG_LAST,
    MAGIC_FRAG_MID,
    MAGIC_FRAG_MID_ENC,
    MAGIC_SINGLE,
    MAGIC_SINGLE_ENC,
    OP_BOND_RESP,
    OP_DP_RESP,
    OP_OTA_DATA_RESP,
    OP_OTA_START_RESP,
    OP_SEARCH_RESP,
    parse_packet,
    verify_packet,
    wire_to_opcode,
)

# Opcodes native RX dispatch decrypts with MAC key + MAIN_IV
OP_BOND_RESP_ALT = 0xAAAA  # encrypted bond failure/success on some firmware paths

_DECRYPT_OPCODES = frozenset({
    OP_SEARCH_RESP,
    OP_BOND_RESP,
    OP_BOND_RESP_ALT,
    OP_DP_RESP,
    0x1005,
    0x1007,
    0x1009,
    0x100B,
    0x1011,
    0x1013,
    0x1051,
    0x2000,
    0x2100,
})


@dataclass
class DecryptedFrame:
    seq: int
    opcode: int
    payload: bytes
    raw: bytes
    decrypted: bool = False


def _magic_byte(magic: tuple[int, int]) -> int:
    return magic[1]


def _is_fragment_magic(magic2: int) -> bool:
    return magic2 in (
        MAGIC_FRAG_FIRST,
        MAGIC_FRAG_MID,
        MAGIC_FRAG_LAST,
        MAGIC_FRAG_FIRST_ENC,
        MAGIC_FRAG_MID_ENC,
    )


class RxAssembler:
    """Reassemble fragmented RX packets and optionally decrypt."""

    def __init__(self, mac: str, *, session_rand: int | None = None) -> None:
        self._mac = mac
        self._session_rand = session_rand
        self._key = (
            derive_session_key(mac, session_rand)
            if session_rand is not None
            else derive_aes_key(mac)
        )
        self._frag_buf: bytearray | None = None
        self._frag_total: int = 0
        self._frag_filled: int = 0
        self._frag_seq_base: int = 0
        self._frag_last_magic: int = 0

    def set_session_rand(self, session_rand: int) -> None:
        """Update key after 0x1000 hello reveals bleInit rand() in ctx1."""
        self._session_rand = session_rand
        self._key = derive_session_key(self._mac, session_rand)

    def feed(self, raw: bytes) -> list[DecryptedFrame]:
        if len(raw) < 10:
            return []
        if raw[2] != 0x5A:
            return []

        if not verify_packet(raw):
            return []

        magic2 = raw[3]
        if _is_fragment_magic(magic2):
            return self._feed_fragment(raw, magic2)

        self._reset_fragment()
        return self._dispatch_single(raw)

    def _reset_fragment(self) -> None:
        self._frag_buf = None
        self._frag_total = 0
        self._frag_filled = 0

    def _feed_fragment(self, raw: bytes, magic2: int) -> list[DecryptedFrame]:
        hdr = parse_packet(raw)
        if hdr is None:
            return []

        chunk = hdr.payload

        if magic2 in (MAGIC_FRAG_FIRST, MAGIC_FRAG_FIRST_ENC):
            self._frag_total = (raw[6] << 8) | raw[7]
            self._frag_buf = bytearray(self._frag_total)
            self._frag_filled = 0
            self._frag_seq_base = hdr.seq
            self._frag_last_magic = magic2
            end = self._frag_filled + len(chunk)
            self._frag_buf[self._frag_filled : end] = chunk
            self._frag_filled = end
            return []

        if self._frag_buf is None:
            return []

        if magic2 in (MAGIC_FRAG_MID, MAGIC_FRAG_MID_ENC):
            end = self._frag_filled + len(chunk)
            if end > self._frag_total:
                self._reset_fragment()
                return []
            self._frag_buf[self._frag_filled : end] = chunk
            self._frag_filled = end
            self._frag_last_magic = magic2
            return []

        if magic2 == MAGIC_FRAG_LAST:
            end = self._frag_filled + len(chunk)
            if end > self._frag_total:
                self._reset_fragment()
                return []
            self._frag_buf[self._frag_filled : end] = chunk
            self._frag_filled = end
            if self._frag_filled != self._frag_total:
                self._reset_fragment()
                return []

            ptype, subtype = raw[6], raw[7]
            opcode = wire_to_opcode(ptype, subtype)
            seq = self._frag_seq_base
            payload = bytes(self._frag_buf)
            self._reset_fragment()

            body = self._synthetic_body(seq, MAGIC_SINGLE, ptype, subtype, payload)
            synthetic = struct.pack(">H", 0) + body
            frame = DecryptedFrame(
                seq=seq,
                opcode=opcode,
                payload=payload,
                raw=synthetic,
            )
            return [self._maybe_decrypt(frame)]

        return []

    def _dispatch_single(self, raw: bytes) -> list[DecryptedFrame]:
        hdr = parse_packet(raw)
        if hdr is None:
            return []
        frame = DecryptedFrame(
            seq=hdr.seq,
            opcode=hdr.opcode,
            payload=hdr.payload,
            raw=raw,
        )
        return [self._maybe_decrypt(frame)]

    def _maybe_decrypt(self, frame: DecryptedFrame) -> DecryptedFrame:
        if frame.opcode not in _DECRYPT_OPCODES:
            return frame
        if not frame.payload or len(frame.payload) % 16 != 0:
            return frame
        try:
            plain = decrypt_cbc(frame.payload, self._key, iv=MAIN_IV)
        except (ValueError, KeyError):
            return frame
        return DecryptedFrame(
            seq=frame.seq,
            opcode=frame.opcode,
            payload=plain,
            raw=frame.raw,
            decrypted=True,
        )

    @staticmethod
    def _synthetic_body(
        seq: int,
        magic2: int,
        ptype: int,
        subtype: int,
        payload: bytes,
    ) -> bytes:
        return bytes([
            0x5A,
            magic2,
            (seq >> 8) & 0xFF,
            seq & 0xFF,
            ptype,
            subtype,
            0x00,
            len(payload) & 0xFF,
        ]) + payload


@dataclass(frozen=True)
class OtaStartResponse:
    ack_sn: int
    code: int
    offset: int


@dataclass(frozen=True)
class OtaDataResponse:
    ack_sn: int
    result: int


def parse_ota_start_resp(frame: DecryptedFrame) -> OtaStartResponse | None:
    """0x1011 OTA start response.

    v2.3.18 returns compact big-endian u32 status + u32 offset. Older traces used
    an 8-byte wrapper with ackSn/code at +4/+6.
    """
    if frame.opcode != OP_OTA_START_RESP:
        return None
    data = frame.payload
    if len(data) == 8 and data[:2] == b"\x00\x00" and data[2:4] != b"\x00\x00":
        return OtaStartResponse(
            ack_sn=0,
            code=int.from_bytes(data[:4], "big"),
            offset=int.from_bytes(data[4:8], "big"),
        )
    if len(data) < 8:
        return None
    ack_sn = int.from_bytes(data[4:6], "big")
    code = int.from_bytes(data[6:8], "big")
    offset = int.from_bytes(data[14:18], "little") if len(data) >= 18 else 0
    return OtaStartResponse(ack_sn=ack_sn, code=code, offset=offset)


def parse_ota_data_resp(frame: DecryptedFrame) -> OtaDataResponse | None:
    """0x1013 per-chunk data response."""
    if frame.opcode != OP_OTA_DATA_RESP:
        return None
    data = frame.payload
    if len(data) == 4:
        return OtaDataResponse(ack_sn=0, result=int.from_bytes(data, "big"))
    if len(data) < 8:
        return None
    ack_sn = int.from_bytes(data[4:6], "big")
    result = int.from_bytes(data[6:8], "big")
    return OtaDataResponse(ack_sn=ack_sn, result=result)


def parse_bond_result(frame: DecryptedFrame) -> int | None:
    """0x1003 / 0xaaaa bond response → uint32 result code (big-endian)."""
    if frame.opcode not in (OP_BOND_RESP, OP_BOND_RESP_ALT):
        return None
    data = frame.payload
    if len(data) < 4:
        return None
    return struct.unpack(">I", data[:4])[0]


def load_capture_packets(path: str | Path | None = None) -> list[bytes]:
    import re
    from pathlib import Path

    from lepro.paths import repo_path

    log_path = Path(path) if path is not None else repo_path("captures.log")
    packets: list[bytes] = []
    log_re = re.compile(r"hex=([0-9a-f]+)")
    for line in log_path.read_text().splitlines():
        m = log_re.search(line)
        if m:
            packets.append(bytes.fromhex(m.group(1)))
    return packets


if __name__ == "__main__":
    mac = "10:20:BA:31:B2:BA"
    asm = RxAssembler(mac)
    packets = load_capture_packets()
    ok_crc = sum(1 for p in packets if verify_packet(p))
    print(f"CRC verify: {ok_crc}/{len(packets)}")

    frames = 0
    for pkt in packets:
        for f in asm.feed(pkt):
            frames += 1
    print(f"Parsed frames: {frames}")

    # 11:17 session spot-check
    session = [p for p in packets if len(p) > 10 and p[6:8] in (b"\x10\x01", b"\x11\x03", b"\x20\x00")]
    for pkt in session[:3]:
        f = asm.feed(pkt)
        if f:
            print(f"  opcode={f[0].opcode:#06x} len={len(f[0].payload)} dec={f[0].decrypted}")
    print("frame.py self-test: OK")
