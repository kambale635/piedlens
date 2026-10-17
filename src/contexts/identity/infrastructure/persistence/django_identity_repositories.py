from django.db import IntegrityError

from contexts.identity.domain.entities.merchant import Merchant
from contexts.identity.domain.entities.user import User
from contexts.identity.domain.value_objects.identity_values import (
    CountryCode,
    CurrencyCode,
    EmailAddress,
    LanguageCode,
    PhoneNumber,
    SubscriptionPlan,
    UserStatus,
)
from contexts.identity.application.exceptions.identity_exceptions import PhoneAlreadyRegistered
from .models import MerchantRecord, UserRecord


class DjangoUserRepository:
    def find_by_phone(self, phone_number: str) -> User | None:
        record = UserRecord.objects.filter(phone_number=phone_number).first()
        return self._to_domain(record) if record else None

    def find_by_id(self, user_id) -> User | None:
        record = UserRecord.objects.filter(id=user_id).first()
        return self._to_domain(record) if record else None

    def save(self, user: User) -> None:
        try:
            UserRecord.objects.update_or_create(
                id=user.id,
                defaults={
                    "phone_number": user.phone_number.value,
                    "email": user.email.value if user.email else None,
                    "password_hash": user.password_hash,
                    "status": user.status.value,
                    "created_at": user.created_at,
                },
            )
        except IntegrityError as error:
            raise PhoneAlreadyRegistered() from error

    @staticmethod
    def _to_domain(record: UserRecord) -> User:
        return User(
            record.id,
            PhoneNumber(record.phone_number),
            EmailAddress(record.email) if record.email else None,
            record.password_hash,
            UserStatus(record.status),
            record.created_at,
        )


class DjangoMerchantRepository:
    def find_by_id(self, merchant_id) -> Merchant | None:
        record = MerchantRecord.objects.filter(id=merchant_id).first()
        return self._to_domain(record) if record else None

    def save(self, merchant: Merchant) -> None:
        MerchantRecord.objects.update_or_create(
            id=merchant.id,
            defaults={
                "name": merchant.name,
                "country": merchant.country.value,
                "preferred_language": merchant.preferred_language.value,
                "currency": merchant.currency.value,
                "subscription_plan": merchant.subscription_plan.value,
                "created_at": merchant.created_at,
            },
        )

    @staticmethod
    def _to_domain(record: MerchantRecord) -> Merchant:
        return Merchant(
            record.id,
            record.name,
            CountryCode(record.country),
            LanguageCode(record.preferred_language),
            CurrencyCode(record.currency),
            SubscriptionPlan(record.subscription_plan),
            record.created_at,
        )