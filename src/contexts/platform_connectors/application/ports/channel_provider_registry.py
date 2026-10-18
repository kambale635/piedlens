from typing import Protocol


class IChannelProviderRegistry(Protocol):
    """Resolve one explicitly supported capability for a configured channel."""

    def require(self, channel_code: str, capability: type): ...