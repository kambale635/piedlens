"""Select the configured platform adapter without introducing Meta credentials here."""

from django.conf import settings

from .mock_platform_gateway import MockPlatformGateway


def configured_platform_gateway(platform_type: str):
    """Return the mock gateway or fail closed until the real provider is supplied."""
    adapter = settings.PLATFORM_ADAPTERS.get(platform_type, "mock")
    if adapter == "mock":
        return MockPlatformGateway()
    if adapter == "real":
        raise RuntimeError(
            f"The real {platform_type} adapter is not implemented; configure credentials "
            "and install the provider adapter before selecting WHATSAPP_ADAPTER=real."
        )
    raise RuntimeError(f"Unsupported {platform_type} adapter: {adapter}")