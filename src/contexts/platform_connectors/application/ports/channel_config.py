from typing import Protocol


class IChannelAvailability(Protocol):
    """Check channel activation against merchant plan and country configuration."""

    def is_enabled_for_merchant(self, channel_code: str, merchant_id) -> bool: ...