#!/usr/bin/env python3
"""
Lepro LP string-light AES-128-CBC crypto (from libiot-core.so via Ghidra).

Key material is set in init_msg() when bleInit(mac, mtu) runs:
  - Parse MAC string "AA:BB:CC:DD:EE:FF" into 6 bytes
  - Start from two 8-byte rodata templates
  - Patch bytes 0..2 of the 16-byte AES key with MAC[3], MAC[4], MAC[5]

Native encrypt paths:
  searchDeviceInfo (0x1000)  → ctx+0x08 key, SEARCH_IV @ 0x14cc32
  dpValue, sendWifiMqttInfo, RX decrypt (FUN_0x925a8) → ctx+0x19 key, MAIN_IV @ 0x14cc42

Two AES keys per bleInit() (init_msg @ libiot-core.so):
  - Search key (ctx+8):  MAC-derived only — used for 0x1000 hello
  - Session key (ctx+0x19): MAC-derived but bytes [3:7] replaced with rand()
    from bleInit. rand() is sent in the hello plaintext as ctx1 (2nd u32).
"""

from __future__ import annotations

import struct
import time

from Crypto.Cipher import AES

# .rodata templates (libiot-core.so)
_KEY_TEMPLATE_A = bytes.fromhex("34aeb43522130ecf")
_KEY_TEMPLATE_B = bytes.fromhex("f4d2525e6c290bf9")

# searchDeviceInfo @ 0x192ef0 uses DAT_0x14cc32
SEARCH_IV = bytes.fromhex("2c7eefe2947e635de09c73bd32edf3e3")

# dpValue / getDpState / requestBond / native RX decrypt use DAT_0x14cc42
MAIN_IV = bytes.fromhex("50e23b111cc0ae8731f5f3e773abc476")
AES_IV = MAIN_IV  # backward-compatible alias

HELLO_MAGIC = bytes.fromhex("5a5aa5a5")
BOND_PLAINTEXT = bytes.fromhex("5a5aa5a500000000")


def mac_string_to_bytes(mac: str) -> bytes:
    """'10:20:BA:31:B2:BA' -> 6 bytes."""
    parts = mac.replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError(f"expected 6 MAC octets, got {mac!r}")
    return bytes(int(p, 16) for p in parts)


def derive_session_key(mac: str | bytes, session_rand: int) -> bytes:
    """
    Session AES key at le_msg_ctx+0x19 (dpValue, sendWifiMqttInfo, RX decrypt).

    init_msg() patches bytes [3:7] of the MAC template key with bleInit's rand().
    The rand value is also stored in search-hello plaintext field ctx1.
    """
    key = bytearray(derive_aes_key(mac))
    key[3:7] = struct.pack("<I", session_rand & 0xFFFFFFFF)
    return bytes(key)


def derive_aes_key(mac: str | bytes) -> bytes:
    """
    Replicate init_msg() key setup for a light MAC.

    For 10:20:BA:31:B2:BA the key is:
        31b2ba3522130ecff4d2525e6c290bf9
    """
    if isinstance(mac, str):
        mac_b = mac_string_to_bytes(mac)
    else:
        mac_b = bytes(mac)
    if len(mac_b) != 6:
        raise ValueError("MAC must be 6 bytes")

    first = bytearray(_KEY_TEMPLATE_A)
    first[0], first[1], first[2] = mac_b[3], mac_b[4], mac_b[5]
    return bytes(first) + _KEY_TEMPLATE_B


def _lepro_pad(data: bytes) -> bytes:
    """
    Padding used inside FUN_0x18d244 (le_aes_128_encrypt_cbc core).

    pad_len = ((len & ~0xF) - len) + 16
    Append pad_len bytes each equal to pad_len.
    """
    n = len(data)
    pad_len = ((n & 0xFFFF_FFF0) - n) + 16
    return data + bytes([pad_len]) * pad_len


def _lepro_unpad(data: bytes) -> bytes:
    if not data:
        raise ValueError("empty data")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > len(data):
        raise ValueError("invalid padding")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("invalid padding bytes")
    return data[:-pad_len]


def encrypt_cbc(plaintext: bytes, key: bytes, iv: bytes = MAIN_IV) -> bytes:
    """Encrypt with Lepro's CBC + custom padding."""
    if len(key) != 16:
        raise ValueError("AES-128 key must be 16 bytes")
    padded = _lepro_pad(plaintext)
    return AES.new(key, AES.MODE_CBC, iv=iv).encrypt(padded)


def decrypt_cbc(ciphertext: bytes, key: bytes, iv: bytes = MAIN_IV) -> bytes:
    """Decrypt and strip Lepro padding."""
    if len(key) != 16:
        raise ValueError("AES-128 key must be 16 bytes")
    plain = AES.new(key, AES.MODE_CBC, iv=iv).decrypt(ciphertext)
    return _lepro_unpad(plain)


def build_search_hello_plaintext(ctx0: int = 0, ctx1: int = 0, timestamp: int | None = None) -> bytes:
    """Plaintext for searchDeviceInfo (0x1000) before encryption."""
    if timestamp is None:
        timestamp = int(time.time())
    return HELLO_MAGIC + struct.pack(
        "<III",
        ctx0 & 0xFFFFFFFF,
        ctx1 & 0xFFFFFFFF,
        timestamp & 0xFFFFFFFF,
    )


def encrypt_search_hello(
    mac: str | bytes,
    ctx0: int = 0,
    ctx1: int = 0,
    timestamp: int | None = None,
) -> bytes:
    """Encrypt a 0x10/0x00 searchDeviceInfo hello (32-byte ciphertext)."""
    key = derive_aes_key(mac)
    plain = build_search_hello_plaintext(ctx0, ctx1, timestamp)
    return encrypt_cbc(plain, key, iv=SEARCH_IV)


def decrypt_search_hello(ciphertext: bytes, mac: str | bytes) -> tuple[bytes, int, int, int]:
    """
    Decrypt a 0x10/0x00 hello payload.

    Returns (magic, ctx0, ctx1, timestamp).
    """
    key = derive_aes_key(mac)
    plain = decrypt_cbc(ciphertext, key, iv=SEARCH_IV)
    if len(plain) < 16:
        raise ValueError(f"hello plaintext too short ({len(plain)}B)")
    magic = plain[0:4]
    ctx0, ctx1, ts = struct.unpack("<III", plain[4:16])
    return magic, ctx0, ctx1, ts


def encrypt_bond_request(mac: str | bytes, *, session_rand: int | None = None) -> bytes:
    """Encrypt requestBond() plaintext (16-byte ciphertext).

    After bleInit/search, native code uses the session key (ctx+0x19), not the MAC key.
    """
    key = (
        derive_session_key(mac, session_rand)
        if session_rand is not None
        else derive_aes_key(mac)
    )
    return encrypt_cbc(BOND_PLAINTEXT, key, iv=MAIN_IV)


def encrypt_dp_json(
    mac: str | bytes,
    json_text: str,
    *,
    session_rand: int | None = None,
    null_terminated: bool = True,
) -> bytes:
    """
    Encrypt a DP JSON body the same way dpValue()/getDpState() do.

    Native code passes strlen(json)+1 bytes (includes the NUL).
    Use session_rand from search-hello ctx1; MAC-only key is not sufficient.
    """
    data = json_text.encode("utf-8")
    if null_terminated:
        data += b"\x00"
    key = (
        derive_session_key(mac, session_rand)
        if session_rand is not None
        else derive_aes_key(mac)
    )
    return encrypt_cbc(data, key, iv=MAIN_IV)


def decrypt_dp_json(
    ciphertext: bytes,
    mac: str | bytes,
    *,
    session_rand: int | None = None,
) -> str:
    """Decrypt a dpValue/getDpState payload and return UTF-8 JSON text."""
    key = (
        derive_session_key(mac, session_rand)
        if session_rand is not None
        else derive_aes_key(mac)
    )
    plain = decrypt_cbc(ciphertext, key, iv=MAIN_IV)
    return plain.rstrip(b"\x00").decode("utf-8")


if __name__ == "__main__":
    mac = "10:20:BA:31:B2:BA"
    key = derive_aes_key(mac)
    print(f"MAC:       {mac}")
    print(f"Key:       {key.hex()}")
    print(f"SEARCH_IV: {SEARCH_IV.hex()}")
    print(f"MAIN_IV:   {MAIN_IV.hex()}")

    sample = '["d1","d2","d3","d4","d5"]'
    session_rand = 0x67458B6B
    ct = encrypt_dp_json(mac, sample, session_rand=session_rand)
    pt = decrypt_dp_json(ct, mac, session_rand=session_rand)
    assert pt == sample, f"DP round-trip failed: {pt!r}"
    print(f"\nDP JSON round-trip (session key): OK ({len(ct)}B ciphertext)")

    bond_ct = encrypt_bond_request(mac, session_rand=session_rand)
    bond_pt = decrypt_cbc(bond_ct, derive_session_key(mac, session_rand), iv=MAIN_IV)
    assert bond_pt == BOND_PLAINTEXT, f"bond round-trip failed: {bond_pt.hex()}"
    print(f"Bond request round-trip (session key): OK")

    # Verify against 11:17 session hello from captures.log
    captured_hello = bytes.fromhex(
        "c4012a79a0dd031c727eea6cf7c736dc45a764086a2bd4ce293aea2f0264a166"
    )
    magic, ctx0, _, ts = decrypt_search_hello(captured_hello, mac)
    assert magic == HELLO_MAGIC, f"hello magic mismatch: {magic.hex()}"
    print(f"\nCaptured hello decrypt: magic={magic.hex()} ctx0={ctx0:#x} ts={ts}")

    # Round-trip a fresh hello
    fresh = encrypt_search_hello(mac, ctx0=0, timestamp=ts)
    magic2, ctx0_2, _, ts2 = decrypt_search_hello(fresh, mac)
    assert (magic2, ctx0_2, ts2) == (HELLO_MAGIC, 0, ts)
    print("Search hello round-trip: OK")
