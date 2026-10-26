from .models import ImportFormatRecord


class DjangoImportFormatReader:
    """Expose active versioned import formats as configuration data (INV-IMP-04)."""

    def find_active(self, code):
        record = ImportFormatRecord.objects.filter(code=code, active=True).first()
        if record is None:
            return None
        return {
            "version": record.version,
            "parser_key": record.parser_key,
            "language": record.language,
            "config": record.config,
        }
