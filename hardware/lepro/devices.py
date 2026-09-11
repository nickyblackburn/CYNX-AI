
from __future__ import annotations

from typing import Any

from .lib.lepro.bond import (
    creds_path,
    load_creds,
    normalize_mac,
)
from .lib.lepro.cli._common import connect_transport
from .lib.lepro.commands import (
    color_rgb,
    color_hsv,
    power_off,
    power_on,
    status_query,
)
from .lib.lepro.crypto import decrypt_dp_json
from .lib.lepro.session import (
    LeproSession,
    bond_device,
)


class LeproDevice:
    """CYN-X interface for a physical Lepro Bluetooth device."""

    def __init__(self, name: str, mac: str):
        self.name = name
        self.mac = normalize_mac(mac)

    # ------------------------------------------------------------------
    # Device information
    # ------------------------------------------------------------------

    def has_credentials(self) -> bool:
        """Return True if this device has been bonded."""
        return load_creds(self.mac) is not None

    def credential_path(self):
        """Return the path where Lepro stores this device's credentials."""
        return creds_path(self.mac)

    # ------------------------------------------------------------------
    # Bluetooth connection
    # ------------------------------------------------------------------

    async def connect(self):
        """Connect to the physical Lepro device."""
        return await connect_transport(self.mac)

    # ------------------------------------------------------------------
    # Bonding
    # ------------------------------------------------------------------

    async def bond(self, force: bool = False) -> Any:
        """Bond this device with CYN-X."""
        transport, client = await self.connect()

        try:
            session = LeproSession(
                self.mac,
                transport,
            )

            return await bond_device(
                session,
                self.mac,
                force=force,
            )

        finally:
            await client.disconnect()

    # ------------------------------------------------------------------
    # Internal control helper
    # ------------------------------------------------------------------

    async def _run_control(
        self,
        payload: dict[str, Any] | list[str],
    ) -> Any:
        """Send a datapoint control payload to the device."""

        creds = load_creds(self.mac)

        if creds is None:
            raise RuntimeError(
                f"Lepro device '{self.name}' is not bonded. "
                f"Credentials expected at {creds_path(self.mac)}."
            )

        transport, client = await self.connect()

        try:
            session = LeproSession(
                self.mac,
                transport,
            )

            return await session.run_control(
                creds,
                payload,
            )

        finally:
            await client.disconnect()

    # ------------------------------------------------------------------
    # Power
    # ------------------------------------------------------------------

    async def turn_on(
        self,
        brightness: int = 1000,
    ) -> Any:
        """Turn the light on."""

        payload = power_on(
            brightness=brightness,
        )

        return await self._run_control(payload)

    async def turn_off(self) -> Any:
        """Turn the light off."""

        payload = power_off()

        return await self._run_control(payload)

    # ------------------------------------------------------------------
    # Color
    # ------------------------------------------------------------------

    async def set_color_rgb(
        self,
        red: int,
        green: int,
        blue: int,
        brightness: int = 1000,
    ) -> Any:
        """Set the light color using RGB values."""

        payload = color_rgb(
            r=red,
            g=green,
            b=blue,
            brightness=brightness,
        )

        return await self._run_control(payload)

    async def set_color_hsv(
        self,
        hue: float,
        saturation: int = 1000,
        value: int = 1000,
        brightness: int = 1000,
    ) -> Any:
        """Set the light color using HSV values."""

        payload = color_hsv(
            hue=hue,
            sat=saturation,
            val=value,
            brightness=brightness,
        )

        return await self._run_control(payload)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> dict[str, Any]:
        """
        Query the current datapoint state of the light.

        This uses the upstream Lepro protocol directly without
        modifying the upstream library.
        """

        creds = load_creds(self.mac)

        if creds is None:
            raise RuntimeError(
                f"Lepro device '{self.name}' is not bonded. "
                f"Credentials expected at {creds_path(self.mac)}."
            )

        query = status_query()

        transport, client = await self.connect()

        try:
            session = LeproSession(
                self.mac,
                transport,
            )

            # Discover the device first so we can report useful
            # device information alongside the datapoint state.
            dev_info = await session.run_phase_discovery()

            # Authenticate using the stored bonding credentials.
            await session.run_phase_auth(creds)

            # Ask the device for its current datapoint state.
            frame = await session.send_get_dp_state(query)

            # Decode the response.
            try:
                if frame.decrypted:
                    text = frame.payload.rstrip(
                        b"\x00"
                    ).decode("utf-8")

                else:
                    text = decrypt_dp_json(
                        frame.payload,
                        self.mac,
                        session_rand=session.session_rand,
                    )

                return {
                    "device": self.name,
                    "mac": self.mac,
                    "provisioning": dev_info.provisioning_summary(),
                    "status": text,
                    "raw": False,
                }

            except Exception:
                return {
                    "device": self.name,
                    "mac": self.mac,
                    "provisioning": dev_info.provisioning_summary(),
                    "status": None,
                    "raw": True,
                    "raw_response": frame.payload.hex(),
                }

        finally:
            await client.disconnect()
