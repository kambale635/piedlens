"""Composition root wiring application ports to Django infrastructure adapters."""

from datetime import timedelta

from django.conf import settings
from contexts.order_detection.application.use_cases.create_order_from_promoted_detection_use_case import (
    CreateOrderFromPromotedDetectionUseCase,
)
from contexts.order_detection.application.use_cases.reassign_contact_references_from_contact_merged_use_case import (
    ReassignContactReferencesFromContactMergedUseCase,
)
from contexts.order_detection.application.use_cases.detect_order_use_case import DetectOrderUseCase
from contexts.order_detection.application.use_cases.get_dormant_money_dashboard_use_case import (
    GetDormantMoneyDashboardUseCase,
)
from contexts.order_detection.application.use_cases.list_pending_detection_candidates_use_case import (
    ListPendingDetectionCandidatesUseCase,
)
from contexts.order_detection.application.use_cases.schedule_reminder_use_case import (
    ScheduleReminderUseCase,
)
from contexts.order_detection.application.ports.reminder_policy import IReminderPolicyProvider
from contexts.order_detection.application.dto.reminder_delivery import (
    IReminderDelivery,
    IReminderDeliveryPolicy,
    IReminderMessageProvider,
    IReminderRetryPolicy,
)
from contexts.order_detection.application.use_cases.send_scheduled_reminders_use_case import (
    SendScheduledRemindersUseCase,
)
from contexts.order_detection.application.ports.detection_configuration import (
    IDetectionConfiguration,
)
from contexts.order_detection.application.use_cases.validate_or_reject_detection_use_case import (
    ValidateOrRejectDetectionUseCase,
)
from contexts.order_detection.application.use_cases.update_order_status_use_case import (
    UpdateOrderStatusUseCase,
)
from contexts.order_detection.infrastructure.persistence.django_detection_candidate_repository import (
    DjangoDetectionCandidateRepository,
)
from contexts.order_detection.infrastructure.persistence.django_contact_reference_redirect_repository import (
    DjangoContactReferenceRedirectRepository,
)
from contexts.order_detection.infrastructure.messaging.django_order_detection_outbox import (
    DjangoOrderDetectionOutbox,
)
from contexts.order_detection.infrastructure.persistence.django_order_repository import (
    DjangoOrderRepository,
)
from contexts.order_detection.infrastructure.persistence.django_processed_event_repository import (
    DjangoProcessedEventRepository,
)
from contexts.order_detection.infrastructure.persistence.django_reminder_repository import (
    DjangoReminderRepository,
)
from contexts.order_detection.infrastructure.persistence.django_unit_of_work import (
    DjangoOrderDetectionUnitOfWork,
)
from contexts.order_detection.infrastructure.adapters.system_clock import SystemClock
from contexts.crm.application.ports.contact_defaults import IContactDefaultsProvider
from contexts.crm.application.use_cases.update_contact_from_message_use_case import (
    UpdateContactFromMessageUseCase,
)
from contexts.crm.application.use_cases.update_contact_from_order_use_case import (
    UpdateContactFromOrderUseCase,
)
from contexts.crm.application.use_cases.consume_contact_merged_use_case import (
    ConsumeContactMergedUseCase,
)
from contexts.crm.application.use_cases.merge_contacts_use_case import MergeContactsUseCase
from contexts.crm.application.use_cases.send_bulk_message_use_case import SendBulkMessageUseCase
from contexts.crm.application.use_cases.process_bulk_message_campaign_use_case import (
    ProcessBulkMessageCampaignUseCase,
)
from contexts.crm.application.use_cases.detect_relationship_anomaly_use_case import (
    DetectRelationshipAnomalyUseCase,
)
from contexts.crm.application.use_cases.create_segment_use_case import CreateSegmentUseCase
from contexts.crm.application.use_cases.get_segment_members_use_case import GetSegmentMembersUseCase
from contexts.crm.infrastructure.persistence.django_contact_repository import DjangoContactRepository
from contexts.crm.infrastructure.persistence.django_segment_repository import DjangoSegmentRepository
from contexts.crm.infrastructure.persistence.django_bulk_message_campaign_repository import (
    DjangoBulkMessageCampaignRepository,
)
from contexts.crm.infrastructure.adapters.redis_segment_membership_cache import (
    RedisSegmentMembershipCache,
)
from contexts.crm.infrastructure.messaging.django_crm_outbox import DjangoCRMOutbox
from contexts.crm.infrastructure.persistence.django_processed_message_repository import (
    DjangoProcessedMessageRepository,
)
from contexts.crm.infrastructure.adapters.django_relationship_anomaly_configuration import (
    DjangoRelationshipAnomalyConfiguration,
)
from contexts.crm.infrastructure.persistence.django_relationship_anomaly_notification_repository import (
    DjangoRelationshipAnomalyNotificationRepository,
)
from contexts.crm.infrastructure.persistence.django_unit_of_work import DjangoCRMUnitOfWork
from contexts.crm.infrastructure.adapters.system_clock import SystemCRMClock
from contexts.crm.domain.services.loyalty_score_calculator import ILoyaltyScoreCalculator
from contexts.identity.application.use_cases.authenticate_user_use_case import AuthenticateUserUseCase
from contexts.identity.application.use_cases.change_subscription_plan_use_case import ChangeSubscriptionPlanUseCase
from contexts.identity.application.use_cases.create_merchant_use_case import CreateMerchantUseCase
from contexts.identity.application.use_cases.refresh_access_token_use_case import RefreshAccessTokenUseCase
from contexts.identity.application.use_cases.register_user_use_case import RegisterUserUseCase
from contexts.identity.infrastructure.adapters.django_security_services import DjangoPasswordHasher, DjangoTokenService
from contexts.identity.infrastructure.adapters.system_clock import SystemIdentityClock
from contexts.identity.infrastructure.messaging.django_identity_outbox import DjangoIdentityOutbox
from contexts.identity.infrastructure.persistence.django_identity_repositories import (
    DjangoMerchantRepository,
    DjangoUserRepository,
)
from contexts.identity.infrastructure.persistence.django_identity_unit_of_work import DjangoIdentityUnitOfWork
from contexts.access_control.application.use_cases.assign_owner_role_on_merchant_registered_use_case import (
    AssignOwnerRoleOnMerchantRegisteredUseCase,
)
from contexts.access_control.application.use_cases.assign_role_to_user_use_case import AssignRoleToUserUseCase
from contexts.access_control.application.use_cases.create_role_use_case import CreateRoleUseCase
from contexts.access_control.application.use_cases.revoke_role_from_user_use_case import RevokeRoleFromUserUseCase
from contexts.access_control.application.use_cases.update_role_permissions_use_case import (
    UpdateRolePermissionsUseCase,
)
from contexts.access_control.infrastructure.adapters.django_permission_cache import DjangoPermissionCache
from contexts.access_control.infrastructure.adapters.django_permission_catalog import DjangoPermissionCatalog
from contexts.access_control.infrastructure.adapters.system_clock import SystemAccessControlClock
from contexts.access_control.infrastructure.messaging.django_access_control_outbox import (
    DjangoAccessControlOutbox,
)
from contexts.access_control.infrastructure.persistence.django_access_control_repository import (
    DjangoAccessControlRepository,
)
from contexts.access_control.infrastructure.persistence.django_access_control_unit_of_work import (
    DjangoAccessControlUnitOfWork,
)
from contexts.access_control.infrastructure.persistence.django_processed_event_repository import (
    DjangoProcessedEventRepository,
)


class ApplicationContainer:
    """Construct Order Detection use cases with production Django adapters.

    This is the only module that directly instantiates infrastructure adapters.
    Django repositories, outbox, and processed-event records use the default DB
    connection managed by `DjangoOrderDetectionUnitOfWork`.
    """

    @staticmethod
    def _crm_segment_cache() -> RedisSegmentMembershipCache:
        """Build the CRM cache adapter from the configured Redis URL and bounded TTL."""
        import redis

        return RedisSegmentMembershipCache(
            redis_client=redis.Redis.from_url(settings.REDIS_URL, decode_responses=True),
            ttl_seconds=settings.CRM_SEGMENT_CACHE_TTL_SECONDS,
        )

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
            contact_redirects=DjangoContactReferenceRedirectRepository(),
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
        )

    @staticmethod
    def reassign_contact_references_from_contact_merged() -> ReassignContactReferencesFromContactMergedUseCase:
        """Wire the ContactMerged consumer to Order Detection-owned persistence."""
        return ReassignContactReferencesFromContactMergedUseCase(
            order_repository=DjangoOrderRepository(),
            candidate_repository=DjangoDetectionCandidateRepository(),
            processed_events=DjangoProcessedEventRepository(),
            redirects=DjangoContactReferenceRedirectRepository(),
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
        )

    @staticmethod
    def detect_order(
        configuration: IDetectionConfiguration,
    ) -> DetectOrderUseCase:
        """Wire detection while requiring Rules Engine configuration from its owner."""
        return DetectOrderUseCase(
            processed_events=DjangoProcessedEventRepository(),
            contact_redirects=DjangoContactReferenceRedirectRepository(),
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
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            defaults_provider=defaults_provider,
            processed_messages=DjangoProcessedMessageRepository(),
            unit_of_work=DjangoCRMUnitOfWork(),
        )

    @staticmethod
    def update_contact_from_order(
        loyalty_score_calculator: ILoyaltyScoreCalculator,
        defaults_provider: IContactDefaultsProvider,
    ) -> UpdateContactFromOrderUseCase:
        """Wire delivered-order CRM updates and require a configured loyalty calculator."""
        return UpdateContactFromOrderUseCase(
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            loyalty_score_calculator=loyalty_score_calculator,
            defaults_provider=defaults_provider,
            processed_messages=DjangoProcessedMessageRepository(),
            unit_of_work=DjangoCRMUnitOfWork(),
        )

    @staticmethod
    def consume_contact_merged() -> ConsumeContactMergedUseCase:
        """Wire the idempotent ContactMerged consumer to CRM transaction adapters."""
        return ConsumeContactMergedUseCase(
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            processed_events=DjangoProcessedMessageRepository(),
            unit_of_work=DjangoCRMUnitOfWork(),
        )

    @staticmethod
    def merge_contacts() -> MergeContactsUseCase:
        """Wire the manual CRM tombstone command to its transactional Outbox."""
        return MergeContactsUseCase(
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            unit_of_work=DjangoCRMUnitOfWork(),
            outbox=DjangoCRMOutbox(),
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

    @staticmethod
    def create_crm_segment() -> CreateSegmentUseCase:
        """Wire dynamic segment creation to the CRM segment repository."""
        return CreateSegmentUseCase(segment_repository=DjangoSegmentRepository())

    @staticmethod
    def get_crm_segment_members() -> GetSegmentMembersUseCase:
        """Wire dynamic membership evaluation to CRM-owned Contact and Segment repositories."""
        return GetSegmentMembersUseCase(
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            segment_repository=DjangoSegmentRepository(),
            membership_cache=ApplicationContainer._crm_segment_cache(),
        )

    @staticmethod
    def send_bulk_message() -> SendBulkMessageUseCase:
        """Wire durable campaign creation without constructing external senders."""
        return SendBulkMessageUseCase(
            segment_repository=DjangoSegmentRepository(),
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            campaign_repository=DjangoBulkMessageCampaignRepository(),
            unit_of_work=DjangoCRMUnitOfWork(),
            outbox=DjangoCRMOutbox(),
        )

    @staticmethod
    def process_bulk_message_campaign(
        rate_limiter,
        message_sender,
    ) -> ProcessBulkMessageCampaignUseCase:
        """Wire the campaign consumer while receiving platform adapters externally."""
        return ProcessBulkMessageCampaignUseCase(
            campaign_repository=DjangoBulkMessageCampaignRepository(),
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            processed_events=DjangoProcessedMessageRepository(),
            rate_limiter=rate_limiter,
            message_sender=message_sender,
            unit_of_work=DjangoCRMUnitOfWork(),
            outbox=DjangoCRMOutbox(),
        )

    @staticmethod
    def register_user() -> RegisterUserUseCase:
        return RegisterUserUseCase(
            DjangoUserRepository(), DjangoPasswordHasher(), DjangoIdentityUnitOfWork(),
            DjangoIdentityOutbox(), SystemIdentityClock(),
        )

    @staticmethod
    def authenticate_user() -> AuthenticateUserUseCase:
        return AuthenticateUserUseCase(DjangoUserRepository(), DjangoPasswordHasher(), DjangoTokenService())

    @staticmethod
    def refresh_access_token() -> RefreshAccessTokenUseCase:
        return RefreshAccessTokenUseCase(DjangoTokenService(), DjangoUserRepository())

    @staticmethod
    def create_merchant() -> CreateMerchantUseCase:
        return CreateMerchantUseCase(
            DjangoMerchantRepository(), DjangoIdentityUnitOfWork(), DjangoIdentityOutbox(),
            SystemIdentityClock(),
        )

    @staticmethod
    def change_subscription_plan(usage_provider) -> ChangeSubscriptionPlanUseCase:
        return ChangeSubscriptionPlanUseCase(
            DjangoMerchantRepository(), usage_provider, DjangoIdentityUnitOfWork(),
            DjangoIdentityOutbox(), SystemIdentityClock(),
        )

    @staticmethod
    def create_role() -> CreateRoleUseCase:
        return CreateRoleUseCase(
            DjangoAccessControlRepository(), DjangoPermissionCatalog(), SystemAccessControlClock()
        )

    @staticmethod
    def update_role_permissions() -> UpdateRolePermissionsUseCase:
        return UpdateRolePermissionsUseCase(
            DjangoAccessControlRepository(), DjangoPermissionCatalog(), DjangoPermissionCache(),
            DjangoAccessControlOutbox(), DjangoAccessControlUnitOfWork(),
        )

    @staticmethod
    def assign_role_to_user() -> AssignRoleToUserUseCase:
        return AssignRoleToUserUseCase(
            DjangoAccessControlRepository(), SystemAccessControlClock(), DjangoPermissionCache(),
            DjangoAccessControlOutbox(), DjangoAccessControlUnitOfWork(),
        )

    @staticmethod
    def revoke_role_from_user() -> RevokeRoleFromUserUseCase:
        return RevokeRoleFromUserUseCase(
            DjangoAccessControlRepository(), SystemAccessControlClock(), DjangoPermissionCache(),
            DjangoAccessControlOutbox(), DjangoAccessControlUnitOfWork(),
        )

    @staticmethod
    def assign_owner_role_on_merchant_registered() -> AssignOwnerRoleOnMerchantRegisteredUseCase:
        return AssignOwnerRoleOnMerchantRegisteredUseCase(
            DjangoAccessControlRepository(), SystemAccessControlClock(), DjangoPermissionCache(),
            DjangoAccessControlOutbox(), DjangoAccessControlUnitOfWork(),
            DjangoProcessedEventRepository(),
        )