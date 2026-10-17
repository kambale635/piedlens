from dataclasses import dataclass
from uuid import UUID

from contexts.identity.domain.value_objects.identity_values import UserStatus
from contexts.identity.infrastructure.adapters.django_security_services import DjangoTokenService
from contexts.identity.infrastructure.persistence.django_identity_repositories import DjangoUserRepository


@dataclass(frozen=True)
class IdentityPrincipal:
    id: UUID
    is_authenticated: bool = True
    merchant_id: UUID | None = None


def authenticate_request(request):
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        user_id = DjangoTokenService().decode_access_token(token)
    except Exception:
        return None
    user = DjangoUserRepository().find_by_id(user_id)
    if user is None or user.status is not UserStatus.ACTIVE:
        return None
    merchant_header = request.headers.get("X-Merchant-ID")
    try:
        merchant_id = UUID(merchant_header) if merchant_header else None
    except ValueError:
        return None
    return IdentityPrincipal(user.id, merchant_id=merchant_id)