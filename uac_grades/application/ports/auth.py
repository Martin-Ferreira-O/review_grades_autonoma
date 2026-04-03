from typing import Protocol


class AuthPort(Protocol):
    async def ensure_session(self) -> None:
        """Ensure there is a reusable authenticated session."""

    async def persist_session(self) -> None:
        """Persist the authenticated session state for future runs."""
