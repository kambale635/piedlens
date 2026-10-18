class ChannelCapabilityUnavailableException(Exception):
    """Raised when a channel is not registered or does not support a requested capability."""


class ChannelProviderRegistry:
    """Index channel adapters by code and the small capabilities each adapter supports."""

    def __init__(self, providers=None) -> None:
        self._providers = {}
        for channel_code, capabilities in (providers or {}).items():
            self.register(channel_code, capabilities)

    def register(self, channel_code: str, capabilities: dict[type, object]) -> None:
        """Register one adapter's supported capability instances for a channel code."""
        normalized_code = channel_code.strip().lower()
        if not normalized_code or normalized_code in self._providers:
            raise ValueError("Channel code must be non-empty and registered only once.")
        self._providers[normalized_code] = dict(capabilities)

    def require(self, channel_code: str, capability: type):
        """Return one registered capability or fail clearly without a concrete adapter fallback."""
        channel = self._providers.get(channel_code.strip().lower())
        if channel is None or capability not in channel:
            raise ChannelCapabilityUnavailableException(
                f"Channel '{channel_code}' does not provide {capability.__name__}."
            )
        return channel[capability]