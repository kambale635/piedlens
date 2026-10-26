"""Parse configured manual conversation formats without channel-specific dependencies (INV-IMP-04)."""

import json
import re
from datetime import datetime, timezone


class ImportFormatParser:
    """Parse a configured JSON or line-based format into normalized messages (INV-IMP-04)."""

    def parse(self, content: str, parser_key: str, config: dict) -> list[dict]:
        """Return normalized message dictionaries or reject unknown/malformed formats."""
        if parser_key == "json_messages_v1":
            value = json.loads(content)
            messages = value.get("messages") if isinstance(value, dict) else None
            if not isinstance(messages, list):
                raise ValueError("Import JSON must contain a messages array.")
            return [self._normalize(item, index) for index, item in enumerate(messages)]
        if parser_key == "configured_lines_v1":
            pattern = config.get("line_pattern")
            if not isinstance(pattern, str):
                raise ValueError("Configured line format is missing line_pattern.")
            compiled = re.compile(pattern)
            parsed = []
            for index, line in enumerate(content.splitlines()):
                if not line.strip():
                    continue
                match = compiled.match(line)
                if match is None or not {"timestamp", "sender", "text"} <= match.groupdict().keys():
                    raise ValueError(f"Import line {index + 1} does not match its configured format.")
                parsed.append(self._normalize(match.groupdict(), index, config))
            return parsed
        raise ValueError("Unknown or inactive import format.")

    @staticmethod
    def _normalize(item: dict, index: int, config: dict | None = None) -> dict:
        if not isinstance(item, dict):
            raise ValueError(f"Import message {index + 1} must be an object.")
        text = item.get("text") or item.get("text_content")
        sender = item.get("sender") or item.get("external_sender_id")
        timestamp = item.get("timestamp") or item.get("received_at")
        if not isinstance(text, str) or not text.strip() or not isinstance(sender, str) or not sender.strip():
            raise ValueError(f"Import message {index + 1} is missing text or sender.")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                formats = (config or {}).get("timestamp_formats", [])
                for timestamp_format in formats:
                    try:
                        timestamp = datetime.strptime(timestamp, timestamp_format)
                        break
                    except ValueError:
                        continue
                if isinstance(timestamp, str):
                    raise ValueError(f"Import message {index + 1} has an invalid timestamp.")
        if not isinstance(timestamp, datetime):
            raise ValueError(f"Import message {index + 1} has an invalid timestamp.")
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        message_id = item.get("id") or item.get("external_message_id") or f"import-line-{index + 1}"
        return {
            "external_message_id": str(message_id),
            "external_sender_id": sender.strip(),
            "display_name": str(item.get("display_name") or ""),
            "text_content": text.strip(),
            "received_at": timestamp.astimezone(timezone.utc),
        }
