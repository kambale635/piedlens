from django.core.management.base import BaseCommand

from contexts.platform_connectors.infrastructure.persistence.models import ImportFormatRecord


FORMATS = (
    ("json_messages_v1", "json_messages_v1", "en", {}),
    ("chat_text_fr_v1", "configured_lines_v1", "fr", {"line_pattern": r"^(?P<timestamp>\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2})\s+-\s+(?P<sender>[^:]+):\s*(?P<text>.*)$", "timestamp_formats": ["%d/%m/%y, %H:%M", "%d/%m/%Y, %H:%M", "%d/%m/%y %H:%M", "%d/%m/%Y %H:%M"]}),
    ("chat_text_en_v1", "configured_lines_v1", "en", {"line_pattern": r"^(?P<timestamp>\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2})\s+-\s+(?P<sender>[^:]+):\s*(?P<text>.*)$", "timestamp_formats": ["%m/%d/%y, %H:%M", "%m/%d/%Y, %H:%M", "%m/%d/%y %H:%M", "%m/%d/%Y %H:%M"]}),
    ("chat_text_sw_v1", "configured_lines_v1", "sw", {"line_pattern": r"^(?P<timestamp>\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2})\s+-\s+(?P<sender>[^:]+):\s*(?P<text>.*)$", "timestamp_formats": ["%d/%m/%y, %H:%M", "%d/%m/%Y, %H:%M", "%d/%m/%y %H:%M", "%d/%m/%Y %H:%M"]}),
)


class Command(BaseCommand):
    help = "Seed configurable manual conversation import formats without overwriting admin changes."

    def handle(self, *args, **options):
        created_count = 0
        for code, parser_key, language, config in FORMATS:
            _, created = ImportFormatRecord.objects.get_or_create(
                code=code,
                defaults={"parser_key": parser_key, "language": language, "config": config},
            )
            created_count += int(created)
        self.stdout.write(f"Added {created_count} import format(s).")
