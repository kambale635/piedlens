import json
import logging
from datetime import datetime, timezone


class JsonLogFormatter(logging.Formatter):
    """Serialize allowlisted log metadata and correlation IDs as one JSON record."""

    def format(self, record: logging.LogRecord) -> str:
        """Emit stable structured fields without exception bodies or arbitrary extras."""
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlationId"] = str(correlation_id)
        for field_name in ("user_id", "merchant_id", "route", "status_code"):
            value = getattr(record, field_name, None)
            if value is not None:
                payload[field_name] = value
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
