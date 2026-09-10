#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
LP String Light BLE Protocol - Reverse Engineered

GATT Service:  1e2aa501-7292-4263-a8f1-be907f039a1f
CMD char:      1e2aa502-7292-4263-a8f1-be907f039a1f  (phone → light, WRITE_WITHOUT_RESPONSE)
RSP char:      1e2aa503-7292-4263-a8f1-be907f039a1f  (light → phone, NOTIFY)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WIRE FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Offset  Size  Field       Notes
──────  ────  ─────────   ────────────────────────────────────────────────
 0       2    crc16       Native table CRC @ 0x14a758 (libiot-core.so) over bytes[2:]
 2       2    magic       0x5A 0x50 single; 0x51/0x52/0x53 fragmented TX
 4       2    seq         uint16 big-endian, per-direction counter
 6       1    opcode_hi   Native uint16 opcode, big-endian on wire (0x1100 → 11 00)
 7       1    opcode_lo
 8       1    unk         Always 0x00 observed (non-fragment)
 9       1    length      Payload byte count
10+    var    payload     Encrypted or plaintext content

Native opcode → wire mapping (byte-swapped uint16):
  0x1000 → 0x10/0x00  searchDeviceInfo   (SEARCH_IV, not MAIN_IV)
  0x1001 → 0x10/0x01  device info response
  0x1002 → 0x10/0x02  requestBond
  0x1003 → 0x10/0x03  bond response
  0x1100 → 0x11/0x00  dpValue data page
  0x1101 → 0x11/0x01  dpValue ACK
  0x1102 → 0x11/0x02  getDpState / static auth tokens
  0x1103 → 0x11/0x03  encrypted DP response

Static pairing tokens (device-specific, not MAC-key ciphertext):
  CMD_HS, CMD_AUTH_16, CMD_AUTH_32, CMD_CTRL_C, CMD_CTRL_D — see constants below.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# CRC-16 lookup table @ 0x14a758 in libiot-core.so (le_msg_tx_data_ext / FUN_0x18cb58)
_CRC_TABLE_HEX = (
    "0000c1c081c1400101c3c003800241c201c6c006800741c70005c1c581c4400401"
    "ccc00c800d41cd000fc1cf81ce400e000ac1ca81cb400b01c9c009800841c801d8"
    "c018801941d9001bc1db81da401a001ec1de81df401f01ddc01d801c41dc0014c1"
    "d481d5401501d7c017801641d601d2c012801341d30011c1d181d0401001f0c030"
    "803141f10033c1f381f240320036c1f681f7403701f5c035803441f4003cc1fc81"
    "fd403d01ffc03f803e41fe01fac03a803b41fb0039c1f981f840380028c1e881e9"
    "402901ebc02b802a41ea01eec02e802f41ef002dc1ed81ec402c01e4c02480254"
    "1e50027c1e781e640260022c1e281e3402301e1c021802041e001a0c060806141a"
    "10063c1a381a240620066c1a681a7406701a5c065806441a4006cc1ac81ad406d0"
    "1afc06f806e41ae01aac06a806b41ab0069c1a981a840680078c1b881b9407901"
    "bbc07b807a41ba01bec07e807f41bf007dc1bd81bc407c01b4c074807541b50077c"
    "1b781b640760072c1b281b3407301b1c071807041b00050c190819140510193c05"
    "3805241920196c056805741970055c19581944054019cc05c805d419d005fc19f819"
    "e405e005ac19a819b405b0199c059805841980188c04880494189004bc18b818a40"
    "4a004ec18e818f404f018dc04d804c418c0044c184818540450187c047804641860"
    "182c042804341830041c18181804040"
)
CRC_TABLE: tuple[int, ...] = struct.unpack("<" + "H" * 256, bytes.fromhex(_CRC_TABLE_HEX))

# Native opcodes (uint16)
OP_SEARCH      = 0x1000
OP_SEARCH_RESP = 0x1001
OP_BOND        = 0x1002
OP_BOND_RESP   = 0x1003
OP_WIFI_MQTT       = 0x1008
OP_WIFI_MQTT_RESP  = 0x1009
OP_WIFI_PROGRESS   = 0x100B
OP_OTA_START       = 0x1010
OP_OTA_START_RESP  = 0x1011
OP_OTA_DATA        = 0x1012
OP_OTA_DATA_RESP   = 0x1013
OP_DP_VALUE    = 0x1100
OP_DP_ACK      = 0x1101
OP_DP_CMD      = 0x1102
OP_DP_RESP     = 0x1103

# Wire magic bytes (byte index 3)
MAGIC_SINGLE   = 0x50
MAGIC_FRAG_FIRST  = 0x51
MAGIC_FRAG_MID    = 0x52
MAGIC_FRAG_LAST   = 0x53
MAGIC_SINGLE_ENC  = 0x54
MAGIC_FRAG_FIRST_ENC = 0xD1
MAGIC_FRAG_MID_ENC   = 0xD2

# Legacy PDU aliases (ptype/subtype)
PDU_DATA      = 0x10
PDU_SESSION   = 0x11
PDU_CERT      = 0x20
PDU_HEARTBEAT = 0x21
PDU_FRAGMENT  = 0x00

SUB_REQ  = 0x00
SUB_RESP = 0x01
SUB_CMD  = 0x02
SUB_ACK  = 0x03

GATT_SERVICE = "1e2aa501-7292-4263-a8f1-be907f039a1f"
GATT_CMD     = "1e2aa502-7292-4263-a8f1-be907f039a1f"
GATT_RSP     = "1e2aa503-7292-4263-a8f1-be907f039a1f"


def opcode_to_wire(opcode: int) -> tuple[int, int]:
    """Convert native uint16 opcode to (ptype, subtype) wire bytes."""
    return (opcode >> 8) & 0xFF, opcode & 0xFF


def wire_to_opcode(ptype: int, subtype: int) -> int:
    return (ptype << 8) | subtype


def crc16_lepro(data: bytes, init: int = 0) -> int:
    """Native CRC from le_msg_tx_data_ext (table @ 0x14a758, init=0)."""
    crc = init
    for b in data:
        crc = CRC_TABLE[(crc & 0xFF) ^ b] ^ (crc >> 8)
    return crc & 0xFFFF


def crc16_ibm(data: bytes) -> int:
    """CRC-16/IBM — matches native table for all captured CMD/RSP packets."""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


@dataclass(frozen=True)
class PacketHeader:
    crc: int
    magic: tuple[int, int]
    seq: int
    opcode: int
    ptype: int
    subtype: int
    length: int
    payload: bytes
    raw: bytes


def parse_packet(raw: bytes) -> PacketHeader | None:
    """Parse a captured BLE packet. Returns None if too short."""
    if len(raw) < 10:
        return None
    crc = struct.unpack(">H", raw[0:2])[0]
    magic = (raw[2], raw[3])
    seq = struct.unpack(">H", raw[4:6])[0]
    ptype, subtype = raw[6], raw[7]
    # byte 8 is 0x00 for normal frames; for payloads >255 it holds length high byte
    length = raw[9] if raw[8] == 0 else (raw[8] << 8) | raw[9]
    payload = raw[10 : 10 + length]
    return PacketHeader(
        crc=crc,
        magic=magic,
        seq=seq,
        opcode=wire_to_opcode(ptype, subtype),
        ptype=ptype,
        subtype=subtype,
        length=length,
        payload=payload,
        raw=raw,
    )


def _build_body(
    seq: int,
    magic2: int,
    field6: int,
    field7: int,
    payload: bytes,
) -> bytes:
    if len(payload) > 0xFFFF:
        raise ValueError(f"payload too large for single packet: {len(payload)} bytes")
    return bytes([
        0x5A,
        magic2,
        (seq >> 8) & 0xFF,
        seq & 0xFF,
        field6,
        field7,
        (len(payload) >> 8) & 0xFF,
        len(payload) & 0xFF,
    ]) + payload


def build_packet(seq: int, ptype: int, subtype: int, payload: bytes) -> bytes:
    """Construct a valid LP-light BLE packet (single 0x5A 0x50 frame)."""
    body = _build_body(seq, MAGIC_SINGLE, ptype, subtype, payload)
    return struct.pack(">H", crc16_lepro(body)) + body


def build_packet_opcode(seq: int, opcode: int, payload: bytes) -> bytes:
    """Build packet from native uint16 opcode."""
    ptype, subtype = opcode_to_wire(opcode)
    return build_packet(seq, ptype, subtype, payload)


def build_packets_fragmented(
    seq: int,
    opcode: int,
    payload: bytes,
    max_payload: int = 128,
    *,
    encrypted: bool = False,
) -> list[bytes]:
    """
    Split payload across 0x51/0x52/0x53 frames per le_msg_tx_data_ext.

    max_payload: max bytes per fragment (native ctx+0x14 MTU chunk size).
    """
    if max_payload < 1:
        raise ValueError("max_payload must be >= 1")
    if len(payload) <= max_payload:
        magic = MAGIC_SINGLE_ENC if encrypted else MAGIC_SINGLE
        ptype, subtype = opcode_to_wire(opcode)
        body = _build_body(seq, magic, ptype, subtype, payload)
        return [struct.pack(">H", crc16_lepro(body)) + body]

    chunks: list[bytes] = []
    offset = 0
    total = len(payload)
    first_magic = MAGIC_FRAG_FIRST_ENC if encrypted else MAGIC_FRAG_FIRST
    mid_magic = MAGIC_FRAG_MID_ENC if encrypted else MAGIC_FRAG_MID

    while offset < total:
        chunk = payload[offset : offset + max_payload]
        offset += len(chunk)
        is_first = not chunks
        is_last = offset >= total

        if is_first and is_last:
            raise RuntimeError("unreachable: single-chunk path should have returned")

        if is_first:
            magic2 = first_magic
            field6 = (total >> 8) & 0xFF
            field7 = total & 0xFF
        elif is_last:
            magic2 = MAGIC_FRAG_LAST
            ptype, subtype = opcode_to_wire(opcode)
            field6, field7 = ptype, subtype
        else:
            magic2 = mid_magic
            field6 = 0x00
            field7 = 0x00

        body = bytes([
            0x5A,
            magic2,
            (seq >> 8) & 0xFF,
            seq & 0xFF,
            field6,
            field7,
            0x00,
            len(chunk) & 0xFF,
        ]) + chunk
        chunks.append(struct.pack(">H", crc16_lepro(body)) + body)
        if not is_last:
            seq += 1

    return chunks


def verify_packet(raw: bytes) -> bool:
    """Verify the CRC of a captured packet."""
    if len(raw) < 10:
        return False
    stored = struct.unpack(">H", raw[0:2])[0]
    return stored == crc16_lepro(raw[2:])


# ── Known static command tokens (device-specific, session-invariant) ──────────

CMD_AUTH_16 = bytes.fromhex("5878cc0961bee4fab7850288e9da39db")
CMD_AUTH_32 = bytes.fromhex(
    "701b29a0c9befcb57a09225a5bf5d22afb882aa67cf9720c7f61c92690b00157"
)
CMD_CTRL_C = bytes.fromhex("e0788f862bc140b66db47649259858c9")
CMD_CTRL_D = bytes.fromhex("f1fd846e7c047935d806dbab5df90939")
CMD_HS = bytes.fromhex("b0dd700ab89869f9e0bc7a095fb28430")
LIGHT_ACK = bytes.fromhex("a3a27817fb8b866af077db02350603f0")
RESP_CTRL_C = bytes.fromhex("de3941453a9562c5cbb47698918532c8")
RESP_CTRL_D = bytes.fromhex(
    "02fb6890b0b71cb505fcc9d288ff0cc1"
    "c0afe15c9a13e16b43aea6776dff27d6"
    "ed8b1f060b7fa81f44a794c448d3bf5d"
    "ee4d24dd34de994151920ea75b75dab8"
)


def _load_capture_packets(path: str = "captures.log") -> list[bytes]:
    import re
    from pathlib import Path

    packets: list[bytes] = []
    log_re = re.compile(r"hex=([0-9a-f]+)")
    for line in Path(path).read_text().splitlines():
        m = log_re.search(line)
        if m:
            packets.append(bytes.fromhex(m.group(1)))
    return packets


if __name__ == "__main__":
    captured = bytes.fromhex(
        "91685a5000001000002031a1ada35f81"
        "c18875101c01e23dad21ea7846913567"
        "b577ad6bdb1b0a36e3d7"
    )
    assert verify_packet(captured), "beacon CRC failed"
    print("Native CRC self-test: PASS")

    hello = bytes.fromhex(
        "8a015a50000010000020c4012a79a0dd031c727eea6cf7c736dc45a764086a2bd4ce293aea2f0264a166"
    )
    assert verify_packet(hello), "hello CRC failed"
    hdr = parse_packet(hello)
    assert hdr is not None and hdr.opcode == OP_SEARCH
    print(f"Hello parse: seq={hdr.seq} opcode={hdr.opcode:#06x} len={hdr.length}")

    ok = sum(1 for p in _load_capture_packets() if verify_packet(p))
    total = len(_load_capture_packets())
    print(f"captures.log CRC: {ok}/{total} packets verify")

    pkt = build_packet_opcode(seq=0, opcode=OP_SEARCH, payload=bytes(32))
    assert verify_packet(pkt)
    print(f"Built hello ({len(pkt)}B): {pkt[:12].hex()}…")
