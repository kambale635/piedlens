from contexts.identity.infrastructure.adapters.django_security_services import DjangoPasswordHasher
from contexts.identity.infrastructure.persistence.models import UserRecord


class DjangoReauthenticationVerifier:
    """Verify a current user's password through Identity-owned persistence."""

    def verify(self, user_id, password: str) -> bool:
        """Return false for absent, disabled or mismatched credentials without logging input."""
        record = UserRecord.objects.filter(id=user_id, status="active").only("password_hash").first()
        return bool(record and DjangoPasswordHasher().verify(password, record.password_hash))