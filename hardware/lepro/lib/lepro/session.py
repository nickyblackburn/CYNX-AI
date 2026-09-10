#!/usr/bin/env python3
"""
Async BLE session state machine: discovery → bond → auth → dpValue → commit.

Pure protocol logic; transport is injected (bleak or dry-run).
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Protocol

from lepro.commands import DpPayload

from lepro.bond import (
    BOND_ERR_ALREADY,
    BOND_ERR_INVALID,
    BondCredentials,
    BondHarvestError,
    BondTokens,
    is_bond_success,
    load_creds,
    save_creds,
    tokens_from_bond_frames,
)
from lepro.frame import parse_bond_result
from lepro.commands import (
    build_dp_ciphertext_packets,
    build_dp_value_packets,
    build_get_dp_state_packet,
    build_raw_cmd_packet,
)
from lepro.crypto import encrypt_bond_request, encrypt_search_hello
from lepro.frame import DecryptedFrame, OP_BOND_RESP_ALT, RxAssembler
from lepro.protocol import (
    OP_BOND,
    OP_BOND_RESP,
    OP_DP_ACK,
    OP_DP_CMD,
    OP_DP_RESP,
    OP_DP_VALUE,
    OP_SEARCH,
    OP_SEARCH_RESP,
    build_packet_opcode,
)

# CMD_HS ack: 0x1003 or encrypted 0xaaaa; later steps use 0x1103
_AUTH_RESP_OPCODES = frozenset({OP_BOND_RESP, OP_BOND_RESP_ALT, OP_DP_RESP})


@dataclass
class SessionConfig:
    send_delay: float = 0.4
    bulk_delay: float = 1.1
    notify_timeout: float = 2.5
    discovery_wait: float = 1.5
    bond_wait: float = 3.0
    ctrl_rounds: int = 3
    dry_run: bool = False


@dataclass
class DeviceInfo:
    raw_payload: bytes
    cert_payload: bytes | None = None

    @property
    def prov_state(self) -> int | None:
        """OTA/provisioning state-machine value (device-info byte[1] = ota_ctx+0x10)."""
        return self.raw_payload[1] if len(self.raw_payload) > 1 else None

    @property
    def prov_slot(self) -> int | None:
        """
        Retained provisioning flag (device-info byte[2], from ota_ctx slot 0x42000b3c).

        Verified in ZB1 v2.3.18 build_device_info_reply: 6 = addable/onboarding
        (slot unset or factory), 7 = provisioned. NOTE: a power-cycle reset re-enters
        onboarding via the reboot counter WITHOUT clearing this slot, so a 7 here does
        NOT prove the CDN cert fetch is disabled — it is only conclusive when 6.
        """
        return self.raw_payload[2] if len(self.raw_payload) > 2 else None

    def provisioning_summary(self) -> str:
        """One-line human-readable provisioning/cert-fetch status for CLI output."""
        state, slot = self.prov_state, self.prov_slot
        if slot is None:
            return "Provisioning: unknown (no device-info payload received)"
        if slot == 6:
            mode = "ADDABLE/onboarding — CDN cert (re)fetch ENABLED on next provision"
        elif slot == 7:
            mode = (
                "PROVISIONED — CDN cert fetch gated OFF unless the bulb was "
                "power-cycle-reset into onboarding (not detectable over BLE)"
            )
        else:
            mode = f"unknown slot value {slot}"
        return f"Provisioning: {mode} [state byte={state}, slot byte={slot}]"


class Transport(Protocol):
    async def send(self, data: bytes, label: str = "") -> None: ...
    async def recv(self, timeout: float) -> bytes | None: ...
    async def drain(self, timeout: float) -> list[bytes]: ...


@dataclass
class DryRunTransport:
    """Collect TX packets without BLE."""

    sent: list[tuple[str, bytes]] = field(default_factory=list)

    async def send(self, data: bytes, label: str = "") -> None:
        self.sent.append((label, data))

    async def recv(self, timeout: float) -> bytes | None:
        return None

    async def drain(self, timeout: float) -> list[bytes]:
        return []


@dataclass
class BleakTransport:
    client: object
    cmd_char: str
    rsp_char: str
    _queue: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue)
    debug_rx: bool = False

    def on_notify(self, _sender: object, data: bytearray) -> None:
        raw = bytes(data)
        if self.debug_rx:
            print(f"  ← LIGHT: {raw.hex()}")
        self._queue.put_nowait(raw)

    async def send(self, data: bytes, label: str = "") -> None:
        if label:
            print(f"  → PHONE [{label}]: {data.hex()}")
        await self.client.write_gatt_char(self.cmd_char, data, response=False)  # type: ignore[attr-defined]

    async def recv(self, timeout: float) -> bytes | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def drain(self, timeout: float) -> list[bytes]:
        deadline = time.monotonic() + timeout
        out: list[bytes] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=min(0.3, remaining))
                out.append(item)
            except asyncio.TimeoutError:
                break
        return out


class LeproSession:
    def __init__(
        self,
        mac: str,
        transport: Transport,
        *,
        config: SessionConfig | None = None,
    ) -> None:
        self.mac = mac
        self.transport = transport
        self.config = config or SessionConfig()
        self.seq = 0
        self.session_rand: int | None = None
        self._rx_asm = RxAssembler(mac)
        self._rx_frames: list[DecryptedFrame] = []
        self._rx_raw: list[bytes] = []

    def _require_session_rand(self) -> int:
        if self.session_rand is None:
            raise RuntimeError("session_rand not set — call run_phase_discovery() first")
        return self.session_rand

    async def _send(self, pkt: bytes, label: str = "") -> None:
        await self.transport.send(pkt, label)
        await asyncio.sleep(self.config.send_delay)

    async def _next_seq(self) -> int:
        s = self.seq
        self.seq += 1
        return s

    def _ingest_rx(self, raw: bytes) -> list[DecryptedFrame]:
        self._rx_raw.append(raw)
        frames = self._rx_asm.feed(raw)
        self._rx_frames.extend(frames)
        return frames

    async def _wait_opcode(self, opcode: int, timeout: float | None = None) -> DecryptedFrame:
        if self.config.dry_run:
            return DecryptedFrame(seq=0, opcode=opcode, payload=b"", raw=b"")
        timeout = timeout or self.config.notify_timeout
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = await self.transport.recv(deadline - time.monotonic())
            if raw is None:
                continue
            for frame in self._ingest_rx(raw):
                if frame.opcode == opcode:
                    return frame
        raise TimeoutError(f"timeout waiting for opcode {opcode:#06x}")

    async def _wait_any(self, opcodes: set[int], timeout: float) -> DecryptedFrame:
        if self.config.dry_run:
            opcode = next(iter(opcodes))
            return DecryptedFrame(seq=0, opcode=opcode, payload=b"", raw=b"")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = await self.transport.recv(deadline - time.monotonic())
            if raw is None:
                continue
            for frame in self._ingest_rx(raw):
                if frame.opcode in opcodes:
                    return frame
        raise TimeoutError(f"timeout waiting for {opcodes}")

    async def run_phase_discovery(self) -> DeviceInfo:
        # bleInit() rand() → search-hello ctx1; same value seeds the session AES key.
        self.session_rand = secrets.randbits(32)
        self._rx_asm.set_session_rand(self.session_rand)

        # Light may NOTIFY 0x2100 before search on connect (live device + captures).
        pre = await self.transport.drain(0.3)
        for raw in pre:
            self._ingest_rx(raw)

        hello = encrypt_search_hello(self.mac, ctx1=self.session_rand)
        await self._send(
            build_packet_opcode(await self._next_seq(), OP_SEARCH, hello),
            "searchDeviceInfo",
        )

        # Captures require RX 0x1001 (+ optional 0x2000 cert) before 0x1102 auth.
        try:
            await self._wait_opcode(OP_SEARCH_RESP, timeout=self.config.discovery_wait)
        except TimeoutError:
            extra = await self.transport.drain(self.config.discovery_wait)
            for raw in extra:
                self._ingest_rx(raw)

        cert_wait = await self.transport.drain(1.0)
        for raw in cert_wait:
            self._ingest_rx(raw)

        dev_info = DeviceInfo(raw_payload=b"")
        cert: bytes | None = None
        for frame in self._rx_frames:
            if frame.opcode == OP_SEARCH_RESP:
                dev_info = DeviceInfo(raw_payload=frame.payload)
            elif frame.opcode == 0x2000:
                cert = frame.payload
        dev_info.cert_payload = cert
        return dev_info

    async def _wait_new_auth_resp(self, after_count: int, timeout: float) -> DecryptedFrame:
        if self.config.dry_run:
            return DecryptedFrame(seq=0, opcode=OP_BOND_RESP, payload=b"", raw=b"")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for frame in self._rx_frames[after_count:]:
                if frame.opcode in _AUTH_RESP_OPCODES:
                    return frame
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            raw = await self.transport.recv(remaining)
            if raw is not None:
                self._ingest_rx(raw)
        raise TimeoutError(f"timeout waiting for auth resp after frame {after_count}")

    async def _request_bond(self, payload: bytes, label: str) -> DecryptedFrame:
        before = len(self._rx_frames)
        await self._send(build_packet_opcode(await self._next_seq(), OP_BOND, payload), label)
        return await self._wait_new_auth_resp(before, timeout=5.0)

    async def run_phase_bond(self, *, fallback_hs: bytes | None = None) -> BondTokens:
        session_rand = self._require_session_rand()
        magic_ct = encrypt_bond_request(self.mac, session_rand=session_rand)

        before_bond = len(self._rx_frames)
        bond_resp = await self._request_bond(magic_ct, "requestBond(magic)")
        bond_path = "magic"
        if not is_bond_success(bond_resp):
            result = parse_bond_result(bond_resp)
            if result in (BOND_ERR_ALREADY, BOND_ERR_INVALID) and fallback_hs:
                bond_resp = await self._request_bond(fallback_hs, "requestBond(CMD_HS)")
                bond_path = "cmd_hs"
            if not is_bond_success(bond_resp):
                result = parse_bond_result(bond_resp)
                raise BondHarvestError(
                    f"requestBond rejected ({bond_path}): result={result:#x}"
                    if result is not None
                    else f"requestBond rejected ({bond_path})"
                )

        bond_resp_idx = next(
            (i for i, f in enumerate(self._rx_frames) if f is bond_resp),
            before_bond,
        )

        extra = await self.transport.drain(self.config.bond_wait)
        for raw in extra:
            self._ingest_rx(raw)

        return tokens_from_bond_frames(self._rx_frames, after_index=bond_resp_idx)

    async def _wait_auth_resp(self, timeout: float | None = None) -> DecryptedFrame:
        return await self._wait_any(_AUTH_RESP_OPCODES, timeout or self.config.notify_timeout)

    async def run_phase_auth(self, creds: BondCredentials) -> None:
        t = creds.tokens
        auth_timeout = max(self.config.notify_timeout, 5.0)
        before_hs = len(self._rx_frames)
        await self._send(build_raw_cmd_packet(await self._next_seq(), t.hs), "CMD_HS")
        await self._wait_new_auth_resp(before_hs, auth_timeout)

        before_auth32 = len(self._rx_frames)
        await self._send(build_raw_cmd_packet(await self._next_seq(), t.auth_32), "CMD_AUTH_32")
        try:
            await self._wait_new_auth_resp(before_auth32, auth_timeout)
        except TimeoutError:
            # Live device sometimes skips the second 0xaaaa ack; getDpState still works.
            pass

    async def send_dp_ciphertext(self, ciphertext: bytes) -> None:
        packets, self.seq = build_dp_ciphertext_packets(self.seq, ciphertext)
        for i, pkt in enumerate(packets):
            await self._send(pkt, f"dpValue[{i}]")
            await self._wait_opcode(OP_DP_ACK)

    async def send_dp_payload(self, payload: DpPayload) -> None:
        packets, self.seq = build_dp_value_packets(
            self.mac, self.seq, payload, session_rand=self._require_session_rand()
        )
        for i, pkt in enumerate(packets):
            await self._send(pkt, f"dpValue[{i}]")
            await self._wait_opcode(OP_DP_ACK)

    async def send_get_dp_state(self, payload: DpPayload) -> DecryptedFrame:
        pkt = build_get_dp_state_packet(
            self.mac, await self._next_seq(), payload, session_rand=self._require_session_rand()
        )
        await self._send(pkt, "getDpState")
        return await self._wait_opcode(OP_DP_RESP)

    async def commit_control(self, creds: BondCredentials) -> None:
        t = creds.tokens
        await self._send(build_raw_cmd_packet(await self._next_seq(), t.auth_16), "CMD_AUTH_16")
        await self._wait_auth_resp(timeout=1.0)
        await self._send(build_raw_cmd_packet(await self._next_seq(), t.auth_32), "CMD_AUTH_32")
        await self._wait_auth_resp(timeout=1.0)

        for r in range(self.config.ctrl_rounds):
            await self._send(build_raw_cmd_packet(await self._next_seq(), t.ctrl_c), "CMD_CTRL_C")
            try:
                await self._wait_auth_resp(timeout=1.0)
            except TimeoutError:
                pass
            await self._send(build_raw_cmd_packet(await self._next_seq(), t.ctrl_d), "CMD_CTRL_D")
            try:
                await self._wait_auth_resp(timeout=1.0)
            except TimeoutError:
                pass

    async def run_control(
        self,
        creds: BondCredentials,
        dp_payload: DpPayload,
        *,
        pre_bulk_pages: list[bytes] | None = None,
    ) -> None:
        """Full control session. pre_bulk_pages is only for large scene uploads (capture 11:17 colour)."""
        await self.run_phase_discovery()
        await self.run_phase_auth(creds)
        if pre_bulk_pages:
            for i, page in enumerate(pre_bulk_pages):
                await self._send(
                    build_packet_opcode(await self._next_seq(), OP_DP_VALUE, page),
                    f"pre-bulk[{i}]",
                )
                await self._wait_opcode(OP_DP_ACK)
                await asyncio.sleep(self.config.bulk_delay)
        await self.send_dp_payload(dp_payload)
        await self.commit_control(creds)


async def bond_device(session: LeproSession, mac: str, *, force: bool = False) -> BondCredentials:
    existing = load_creds(mac)
    if existing and not force:
        return existing

    session._rx_frames.clear()
    session._rx_raw.clear()
    session.seq = 0
    session.session_rand = None

    await session.run_phase_discovery()
    fallback_hs = existing.tokens.hs if existing else None
    tokens = await session.run_phase_bond(fallback_hs=fallback_hs)
    creds = BondCredentials(mac=mac, tokens=tokens)
    # Auth (0x1102) fails in the bond session (error 3); verified on live device.
    save_creds(creds)
    return creds
