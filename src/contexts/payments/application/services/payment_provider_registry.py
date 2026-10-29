class PaymentCapabilityUnavailable(Exception):
    """Raised when a configured payment provider lacks a requested capability (INV-PAY-04)."""


class PaymentProviderRegistry:
    """Resolve payment adapters by configured provider code and capability (INV-PAY-04)."""

    def __init__(self, providers=None):
        self._providers = {}
        for code, capabilities in (providers or {}).items():
            self.register(code, capabilities)

    def register(self, code, capabilities):
        normalized = code.strip().lower()
        if not normalized or normalized in self._providers:
            raise ValueError("Payment provider code must be unique and non-empty.")
        self._providers[normalized] = dict(capabilities)

    def require(self, code, capability):
        provider = self._providers.get(code.strip().lower())
        if provider is None or capability not in provider:
            raise PaymentCapabilityUnavailable(f"Payment provider '{code}' lacks {capability.__name__}.")
        return provider[capability]
