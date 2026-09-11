from __future__ import annotations

from typing import Any

from .lib.lepro.bond import (
    creds_path,
    load_creds,
    normalize_mac,
)
from .lib.lepro.cli._common import connect_transport
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