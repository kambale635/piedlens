"""Composition root wiring application ports to Django infrastructure adapters."""

from datetime import timedelta

from contexts.order_detection.application.create_order_from_promoted_detection_use_case import (
    CreateOrderFromPromotedDetectionUseCase,
)
from contexts.order_detection.application.detect_order_use_case import DetectOrderUseCase
from contexts.order_detection.application.get_dormant_money_dashboard_use_case import (
    GetDormantMoneyDashboardUseCase,
)
from contexts.order_detection.application.list_pending_detection_candidates_use_case import (
    ListPendingDetectionCandidatesUseCase,
)
from contexts.order_detection.application.schedule_reminder_use_case import (
    ScheduleReminderUseCase,
)
from contexts.order_detection.application.reminder_policy import IReminderPolicyProvider
from contexts.order_detection.application.reminder_delivery import (
    IReminderDelivery,
    IReminderDeliveryPolicy,
    IReminderMessageProvider,
    IReminderRetryPolicy,
)
from contexts.order_detection.application.send_scheduled_reminders_use_case import (
    SendScheduledRemindersUseCase,
)
from contexts.order_detection.application.detection_configuration import (
    IDetectionConfiguration,
)
from contexts.order_detection.application.validate_or_reject_detection_use_case import (
    ValidateOrRejectDetectionUseCase,
)
from contexts.order_detection.application.update_order_status_use_case import (
    UpdateOrderStatusUseCase,
)
from contexts.order_detection.infrastructure.django_detection_candidate_repository import (
    DjangoDetectionCandidateRepository,
)
from contexts.order_detection.infrastructure.django_order_detection_outbox import (
    DjangoOrderDetectionOutbox,
)
from contexts.order_detection.infrastructure.django_order_repository import (
    DjangoOrderRepository,
)
from contexts.order_detection.infrastructure.django_processed_event_repository import (
    DjangoProcessedEventRepository,
)
from contexts.order_detection.infrastructure.django_reminder_repository import (
    DjangoReminderRepository,
)
from contexts.order_detection.infrastructure.django_unit_of_work import (
    DjangoOrderDetectionUnitOfWork,
)
from contexts.order_detection.infrastructure.system_clock import SystemClock
from contexts.crm.application.contact_defaults import IContactDefaultsProvider
from contexts.crm.application.update_contact_from_message_use_case import (
    UpdateContactFromMessageUseCase,
)
from contexts.crm.application.update_contact_from_order_use_case import (
    UpdateContactFromOrderUseCase,
)
from contexts.crm.application.detect_relationship_anomaly_use_case import (
    DetectRelationshipAnomalyUseCase,
)
from contexts.crm.infrastructure.django_contact_repository import DjangoContactRepository
from contexts.crm.infrastructure.django_crm_outbox import DjangoCRMOutbox
from contexts.crm.infrastructure.django_processed_message_repository import (
    DjangoProcessedMessageRepository,
)
from contexts.crm.infrastructure.django_relationship_anomaly_configuration import (
    DjangoRelationshipAnomalyConfiguration,
)
from contexts.crm.infrastructure.django_relationship_anomaly_notification_repository import (
    DjangoRelationshipAnomalyNotificationRepository,
)
from contexts.crm.infrastructure.django_unit_of_work import DjangoCRMUnitOfWork
from contexts.crm.infrastructure.system_clock import SystemCRMClock
from contexts.crm.domain.loyalty_score_calculator import ILoyaltyScoreCalculator


class ApplicationContainer:
    """Construct Order Detection use cases with production Django adapters.

    This is the only module that directly instantiates infrastructure adapters.
    Django repositories, outbox, and processed-event records use the default DB
    connection managed by `DjangoOrderDetectionUnitOfWork`.
    """

    @staticmethod
    def validate_or_reject_detection() -> ValidateOrRejectDetectionUseCase:
        """Wire candidate review to its repository and transactional outbox."""
        return ValidateOrRejectDetectionUseCase(
            candidate_repository=DjangoDetectionCandidateRepository(),
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
        )

    @staticmethod
    def create_order_from_promoted_detection() -> CreateOrderFromPromotedDetectionUseCase:
        """Wire the idempotent promotion consumer to the same PostgreSQL connection."""
        return CreateOrderFromPromotedDetectionUseCase(
            order_repository=DjangoOrderRepository(),
            processed_events=DjangoProcessedEventRepository(),
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
        )

    @staticmethod
    def detect_order(
        configuration: IDetectionConfiguration,
    ) -> DetectOrderUseCase:
        """Wire detection while requiring Rules Engine configuration from its owner."""
        return DetectOrderUseCase(
            order_repository=DjangoOrderRepository(),
            candidate_repository=DjangoDetectionCandidateRepository(),
            configuration=configuration,
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
        )

    @staticmethod
    def update_order_status() -> UpdateOrderStatusUseCase:
        """Wire status changes to PostgreSQL locking, transaction, and outbox adapters."""
        return UpdateOrderStatusUseCase(
            order_repository=DjangoOrderRepository(),
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
            clock=SystemClock(),
        )

    @staticmethod
    def get_dormant_money_dashboard() -> GetDormantMoneyDashboardUseCase:
        """Wire the dashboard query to the Order Detection read repository."""
        return GetDormantMoneyDashboardUseCase(
            order_repository=DjangoOrderRepository(),
        )

    @staticmethod
    def schedule_reminder(
        policy_provider: IReminderPolicyProvider,
    ) -> ScheduleReminderUseCase:
        """Wire Reminder persistence while requiring policy from its owning context/config."""
        return ScheduleReminderUseCase(
            order_repository=DjangoOrderRepository(),
            reminder_repository=DjangoReminderRepository(),
            policy_provider=policy_provider,
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
            clock=SystemClock(),
        )

    @staticmethod
    def send_scheduled_reminders(
        delivery_policy: IReminderDeliveryPolicy,
        message_provider: IReminderMessageProvider,
        delivery: IReminderDelivery,
        retry_policy: IReminderRetryPolicy,
        batch_limit: int,
        lease_duration: timedelta,
    ) -> SendScheduledRemindersUseCase:
        """Wire the scheduled worker while receiving plan and platform policies externally."""
        return SendScheduledRemindersUseCase(
            order_repository=DjangoOrderRepository(),
            reminder_repository=DjangoReminderRepository(),
            processed_events=DjangoProcessedEventRepository(),
            delivery_policy=delivery_policy,
            message_provider=message_provider,
            delivery=delivery,
            retry_policy=retry_policy,
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
            clock=SystemClock(),
            batch_limit=batch_limit,
            lease_duration=lease_duration,
        )

    @staticmethod
    def list_pending_detection_candidates() -> ListPendingDetectionCandidatesUseCase:
        """Wire merchant-scoped manual-review listing to the Django candidate repository."""
        return ListPendingDetectionCandidatesUseCase(
            candidate_repository=DjangoDetectionCandidateRepository(),
        )

    @staticmethod
    def update_contact_from_message(
        defaults_provider: IContactDefaultsProvider,
    ) -> UpdateContactFromMessageUseCase:
        """Wire CRM message processing with injected merchant defaults and Django adapters."""
        return UpdateContactFromMessageUseCase(
            contact_repository=DjangoContactRepository(),
            defaults_provider=defaults_provider,
            processed_messages=DjangoProcessedMessageRepository(),
            unit_of_work=DjangoCRMUnitOfWork(),
        )

    @staticmethod
    def update_contact_from_order(
        loyalty_score_calculator: ILoyaltyScoreCalculator,
    ) -> UpdateContactFromOrderUseCase:
        """Wire delivered-order CRM updates and require a configured loyalty calculator."""
        return UpdateContactFromOrderUseCase(
            contact_repository=DjangoContactRepository(),
            loyalty_score_calculator=loyalty_score_calculator,
            processed_messages=DjangoProcessedMessageRepository(),
            unit_of_work=DjangoCRMUnitOfWork(),
        )

    @staticmethod
    def detect_relationship_anomalies() -> DetectRelationshipAnomalyUseCase:
        """Wire the CRM scheduled anomaly job with settings and transactional adapters."""
        return DetectRelationshipAnomalyUseCase(
            contact_repository=DjangoContactRepository(),
            configuration=DjangoRelationshipAnomalyConfiguration(),
            notification_repository=DjangoRelationshipAnomalyNotificationRepository(),
            outbox=DjangoCRMOutbox(),
            unit_of_work=DjangoCRMUnitOfWork(),
            clock=SystemCRMClock(),
        )