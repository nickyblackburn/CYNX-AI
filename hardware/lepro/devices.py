
from __future__ import annotations

from typing import Any

from .lib.lepro.bond import (
    creds_path,
    load_creds,
    normalize_mac,
)
from .lib.lepro.cli._common import connect_transport
from .lib.lepro.commands import (
    color_hsv,
    color_rgb,
    power_off,
    power_on,
)
from .lib.lepro.session import (
    LeproSession,
    bond_device,
)


class LeproDevice:
    """CYN-X representation of a physical Lepro device."""

    def __init__(
        self,
        name: str,
        mac: str,
    ):
        self.name = name
        self.mac = normalize_mac(mac)

    def has_credentials(self) -> bool:
        """Check whether this device has been bonded."""

        return load_creds(self.mac) is not None

    def credential_path(self):
        """Return the upstream credential path."""

        return creds_path(self.mac)

    async def bond(
        self,
        force: bool = False,
    ) -> Any:
        """Bond the device using lepro-local."""

        transport, client = await connect_transport(
            self.mac
        )

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

    async def connect(self):
        """Connect to the Lepro device."""

        return await connect_transport(
            self.mac
        )

    async def _run_control(
        self,
        payload: dict[str, Any] | list[str],
    ) -> Any:
        """Connect, authenticate, and send a DP control payload."""

        creds = load_creds(self.mac)

        if creds is None:
            raise RuntimeError(
                f"Lepro device '{self.name}' is not bonded."
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

    async def turn_on(
        self,
        brightness: int = 1000,
    ) -> Any:
        """Turn the lights on."""

        payload = power_on(
            brightness=brightness,
        )

        return await self._run_control(payload)

    async def turn_off(self) -> Any:
        """Turn the lights off."""

        payload = power_off()

        return await self._run_control(payload)

    async def set_color_hsv(
        self,
        hue: float,
        saturation: int = 1000,
        value: int = 1000,
        brightness: int = 1000,
    ) -> Any:
        """Set the lights using HSV color values."""

        payload = color_hsv(
            hue=hue,
            sat=saturation,
            val=value,
            brightness=brightness,
        )

        return await self._run_control(payload)

    async def set_color_rgb(
        self,
        red: int,
        green: int,
        blue: int,
        brightness: int = 1000,
    ) -> Any:
        """Set the lights using RGB color values."""

        payload = color_rgb(
            r=red,
            g=green,
            b=blue,
            brightness=brightness,
        )

        return await self._run_control(payload)
