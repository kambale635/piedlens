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
from contexts.order_detection.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase as PurgeOrderDetectionMerchantDataUseCase,
)
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
from contexts.order_detection.application.use_cases.reconcile_order_status_from_message_use_case import (
    ReconcileOrderStatusFromMessageUseCase,
)
from contexts.order_detection.infrastructure.adapters.django_order_status_intent_configuration import (
    DjangoOrderStatusIntentConfiguration,
)
from contexts.rules_engine.infrastructure.adapters.django_order_status_intent_reader import (
    DjangoOrderStatusIntentReader,
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
    DjangoProcessedEventRepository as DjangoOrderDetectionProcessedEventRepository,
)
from contexts.order_detection.infrastructure.persistence.django_merchant_data_purger import (
    DjangoOrderDetectionMerchantPurger,
)
from contexts.order_detection.infrastructure.persistence.django_reminder_repository import (
    DjangoReminderRepository,
)
from contexts.order_detection.infrastructure.persistence.django_unit_of_work import (
    DjangoOrderDetectionUnitOfWork,
)
from contexts.order_detection.infrastructure.adapters.system_clock import SystemClock
from contexts.order_detection.infrastructure.adapters.django_reminder_policy_provider import (
    DjangoReminderPolicyProvider,
)
from contexts.order_detection.infrastructure.adapters.django_reminder_delivery_policy import (
    DjangoReminderDeliveryPolicy,
)
from contexts.crm.infrastructure.adapters.django_manual_message_link_builder import (
    DjangoManualMessageLinkBuilder,
)
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
from contexts.crm.application.use_cases.purge_merchant_data_use_case import PurgeMerchantDataUseCase as PurgeCRMMerchantDataUseCase
from contexts.crm.application.use_cases.send_bulk_message_use_case import SendBulkMessageUseCase
from contexts.crm.application.use_cases.process_bulk_message_campaign_use_case import (
    ProcessBulkMessageCampaignUseCase,
)
from contexts.crm.application.use_cases.detect_relationship_anomaly_use_case import (
    DetectRelationshipAnomalyUseCase,
)
from contexts.crm.application.use_cases.create_segment_use_case import CreateSegmentUseCase
from contexts.crm.application.use_cases.get_segment_members_use_case import GetSegmentMembersUseCase
from contexts.crm.application.use_cases.list_contacts_use_case import ListContactsUseCase
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
from contexts.crm.infrastructure.persistence.django_merchant_data_purger import (
    DjangoCRMMerchantPurger,
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
from contexts.identity.application.use_cases.logout_user_use_case import LogoutUserUseCase
from contexts.identity.application.use_cases.revoke_all_sessions_use_case import RevokeAllSessionsUseCase
from contexts.identity.application.use_cases.register_user_use_case import RegisterUserUseCase
from contexts.identity.application.use_cases.purge_merchant_data_use_case import PurgeMerchantDataUseCase
from contexts.identity.infrastructure.adapters.django_security_services import (
    DjangoLoginBackoff,
    DjangoPasswordHasher,
    DjangoTokenService,
)
from contexts.identity.infrastructure.adapters.system_clock import SystemIdentityClock
from contexts.identity.infrastructure.messaging.django_identity_outbox import DjangoIdentityOutbox
from contexts.identity.infrastructure.persistence.django_identity_repositories import (
    DjangoMerchantRepository,
    DjangoIdentityProcessedEventRepository,
    DjangoUserRepository,
)
from contexts.identity.infrastructure.persistence.django_identity_unit_of_work import DjangoIdentityUnitOfWork
from contexts.access_control.application.use_cases.assign_owner_role_on_merchant_registered_use_case import (
    AssignOwnerRoleOnMerchantRegisteredUseCase,
)
from contexts.access_control.application.use_cases.assign_role_to_user_use_case import AssignRoleToUserUseCase
from contexts.access_control.application.use_cases.create_role_use_case import CreateRoleUseCase
from contexts.access_control.application.use_cases.revoke_role_from_user_use_case import RevokeRoleFromUserUseCase
from contexts.access_control.application.use_cases.purge_merchant_data_use_case import PurgeMerchantDataUseCase as PurgeAccessControlMerchantDataUseCase
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
    DjangoProcessedEventRepository as DjangoAccessControlProcessedEventRepository,
)
from contexts.access_control.infrastructure.persistence.django_merchant_data_purger import (
    DjangoAccessControlMerchantPurger,
)
from contexts.billing.infrastructure.adapters.django_entitlement_reader import (
    DjangoEntitlementReader,
)
from contexts.billing.infrastructure.adapters.django_plan_catalog_reader import (
    DjangoPlanCatalogReader,
)
from contexts.billing.infrastructure.adapters.django_outbound_services import (
    DjangoMerchantOutboundUsageReader,
    DjangoOutboundCostEstimator,
)
from contexts.billing.application.use_cases.generate_value_report_use_case import (
    GenerateValueReportUseCase,
)
from contexts.identity.infrastructure.adapters.django_merchant_country_reader import (
    DjangoMerchantCountryReader,
)
from contexts.billing.application.use_cases.estimate_outbound_cost_use_case import (
    EstimateOutboundCostUseCase,
)
from contexts.platform_connectors.infrastructure.adapters.platform_campaign_sender import (
    PlatformCampaignSender,
)
from contexts.identity.infrastructure.adapters.django_merchant_plan_reader import (
    DjangoMerchantPlanReader,
)
from contexts.identity.infrastructure.adapters.django_merchant_currency_reader import (
    DjangoMerchantCurrencyReader,
)
from contexts.crm.infrastructure.adapters.django_contact_defaults_provider import (
    DjangoContactDefaultsProvider,
)
from contexts.platform_connectors.application.use_cases.connect_platform_use_case import (
    ConnectPlatformUseCase,
)
from contexts.platform_connectors.application.ports.channel_capabilities import (
    IChannelHealthChecker,
    IMessageSender,
    IMediaFetcher,
    IMessageRetriever,
    IOAuthCodeExchanger,
    ITokenRefresher,
    IWebhookMessageNormalizer,
    IWebhookSignatureVerifier,
)
from contexts.platform_connectors.application.ports.channel_config import IChannelAvailability
from contexts.platform_connectors.application.services.channel_provider_registry import (
    ChannelProviderRegistry,
)
from contexts.platform_connectors.application.use_cases.handle_incoming_webhook_use_case import (
    HandleIncomingWebhookUseCase,
)
from contexts.platform_connectors.application.use_cases.refresh_tokens_use_case import (
    RefreshTokensUseCase,
)
from contexts.platform_connectors.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase as PurgePlatformConnectorsMerchantDataUseCase,
)
from contexts.platform_connectors.application.use_cases.sync_messages_use_case import (
    SyncMessagesUseCase,
)
from contexts.platform_connectors.application.use_cases.sync_active_connections_job import (
    SyncActiveConnectionsJob,
)
from contexts.platform_connectors.infrastructure.adapters.django_aes_token_cipher import (
    DjangoAesTokenCipher,
)
from contexts.platform_connectors.infrastructure.adapters.django_connection_usage_reader import (
    DjangoConnectionUsageReader,
)
from contexts.platform_connectors.infrastructure.adapters.django_webhook_signature_verifier import (
    DjangoWebhookSignatureVerifier,
)
from contexts.platform_connectors.infrastructure.adapters.django_webhook_replay_cache import (
    DjangoWebhookReplayCache,
)
from contexts.platform_connectors.infrastructure.adapters.mock_channel_capabilities import (
    MockChannelHealthChecker,
    MockMediaFetcher,
    MockMessageRetriever,
    MockMessageSender,
    MockOAuthCodeExchanger,
    MockTokenRefresher,
)
from contexts.platform_connectors.infrastructure.adapters.mock_webhook_payload_mapper import (
    MockWebhookPayloadMapper,
)
from contexts.platform_connectors.infrastructure.persistence.django_channel_config_reader import (
    DjangoChannelConfigReader,
)
from contexts.identity.infrastructure.adapters.django_merchant_plan_reader import (
    DjangoMerchantPlanReader,
)
from contexts.platform_connectors.infrastructure.adapters.system_platform_clock import (
    SystemPlatformClock,
)
from contexts.platform_connectors.infrastructure.persistence.django_message_repository import (
    DjangoMessageRepository,
)
from contexts.platform_connectors.infrastructure.persistence.django_platform_connection_repository import (
    DjangoPlatformConnectionRepository,
)
from contexts.platform_connectors.infrastructure.persistence.django_platform_outbox import (
    DjangoPlatformConnectorsOutbox,
)
from contexts.platform_connectors.infrastructure.persistence.django_merchant_data_purger import (
    DjangoPlatformConnectorsMerchantPurger,
)
from contexts.platform_connectors.infrastructure.persistence.django_processed_event_repository import (
    DjangoPlatformConnectorsProcessedEventRepository,
)
from contexts.platform_connectors.infrastructure.persistence.django_unit_of_work import (
    DjangoPlatformConnectorsUnitOfWork,
)
from contexts.identity.infrastructure.adapters.django_merchant_country_reader import (
    DjangoMerchantCountryReader,
)
from contexts.rules_engine.application.use_cases.adjust_rule_weight_from_correction_use_case import (
    AdjustRuleWeightFromCorrectionUseCase,
)
from contexts.rules_engine.application.use_cases.evaluate_message_use_case import (
    EvaluateMessageUseCase,
)
from contexts.rules_engine.application.use_cases.update_rule_set_use_case import (
    UpdateRuleSetUseCase,
)
from contexts.rules_engine.application.use_cases.purge_merchant_data_use_case import (
    PurgeMerchantDataUseCase as PurgeRulesEngineMerchantDataUseCase,
)
from contexts.rules_engine.domain.value_objects.rule_type import RuleType
from contexts.rules_engine.domain.services.rule_evaluators import (
    AmountPatternEvaluator,
    EmojiMatchEvaluator,
    KeywordMatchEvaluator,
    MediaPresenceEvaluator,
)
from contexts.rules_engine.infrastructure.messaging.django_rules_engine_outbox import (
    DjangoRulesEngineOutbox,
)
from contexts.rules_engine.infrastructure.persistence.django_processed_event_repository import (
    DjangoProcessedEventRepository as DjangoRulesProcessedEventRepository,
)
from contexts.rules_engine.infrastructure.persistence.django_rule_set_repository import (
    DjangoRuleSetRepository,
)
from contexts.rules_engine.infrastructure.persistence.django_unit_of_work import (
    DjangoRulesEngineUnitOfWork,
)
from contexts.rules_engine.infrastructure.persistence.django_merchant_data_purger import (
    DjangoRulesEngineMerchantPurger,
)
from contexts.backup.application.use_cases.check_account_health_use_case import (
    CheckAccountHealthUseCase,
)
from contexts.backup.application.use_cases.create_snapshot_use_case import CreateSnapshotUseCase
from contexts.backup.application.use_cases.delete_all_merchant_data_use_case import (
    DeleteAllMerchantDataUseCase,
)
from contexts.backup.application.use_cases.request_merchant_deletion_use_case import (
    RequestMerchantDeletionUseCase,
)
from contexts.backup.application.use_cases.get_backup_export_use_case import GetBackupExportUseCase
from contexts.backup.application.use_cases.list_backups_use_case import ListBackupsUseCase
from contexts.backup.application.use_cases.restore_from_snapshot_use_case import (
    RestoreFromSnapshotUseCase,
)
from contexts.backup.infrastructure.adapters.django_confirmation_token_verifier import (
    DjangoConfirmationTokenVerifier,
)
from contexts.backup.infrastructure.adapters.system_backup_clock import SystemBackupClock
from contexts.backup.infrastructure.messaging.django_backup_outbox import DjangoBackupOutbox
from contexts.backup.infrastructure.persistence.django_backup_repository import (
    DjangoBackupRepository,
)
from contexts.backup.infrastructure.persistence.s3_object_storage import configured_object_storage
from contexts.backup.infrastructure.persistence.django_deletion_token_store import DjangoDeletionTokenStore
from contexts.identity.infrastructure.adapters.django_reauthentication_verifier import (
    DjangoReauthenticationVerifier,
)
from contexts.backup.infrastructure.persistence.django_unit_of_work import DjangoBackupUnitOfWork
from contexts.crm.infrastructure.adapters.django_backup_contact_reader import DjangoBackupContactReader
from contexts.platform_connectors.infrastructure.adapters.django_account_health_checker import (
    DjangoAccountHealthChecker,
)
from contexts.platform_connectors.infrastructure.adapters.django_backup_message_reader import (
    DjangoBackupMessageReader,
)
from contexts.platform_connectors.infrastructure.adapters.django_connection_consent_reader import (
    DjangoConnectionConsentReader,
)


class ApplicationContainer:
    @staticmethod
    def generate_billing_value_report() -> GenerateValueReportUseCase:
        """Assemble Billing's report with Identity read ports at the system boundary."""
        return GenerateValueReportUseCase(
            DjangoMerchantCountryReader(),
            DjangoMerchantCurrencyReader(),
            DjangoMerchantOutboundUsageReader(),
            DjangoOutboundCostEstimator(),
        )

    @staticmethod
    def estimate_outbound_cost() -> EstimateOutboundCostUseCase:
        """Compose Billing's estimator with Identity's country reader at the system boundary."""
        return EstimateOutboundCostUseCase(
            DjangoMerchantCountryReader(),
            DjangoMerchantCurrencyReader(),
            DjangoOutboundCostEstimator(),
        )

    @staticmethod
    def channel_provider_registry() -> ChannelProviderRegistry:
        """Build configured channel adapters and reject unimplemented real providers."""
        channel_codes = ("whatsapp", "instagram", "facebook")
        for channel_code in channel_codes:
            adapter = settings.PLATFORM_ADAPTERS.get(channel_code, "mock")
            if adapter != "mock":
                variable_name = f"{channel_code.upper()}_ADAPTER"
                if adapter == "real":
                    raise RuntimeError(
                        f"The real {channel_code} adapter is not implemented; "
                        f"{variable_name}=real cannot be used yet."
                    )
                raise RuntimeError(
                    f"Unsupported {channel_code} adapter '{adapter}' in {variable_name}."
                )

        oauth_exchanger = MockOAuthCodeExchanger()
        message_retriever = MockMessageRetriever()
        token_refresher = MockTokenRefresher()
        message_sender = MockMessageSender()
        media_fetcher = MockMediaFetcher()
        health_checker = MockChannelHealthChecker()
        webhook_mapper = MockWebhookPayloadMapper()
        signature_verifier = DjangoWebhookSignatureVerifier()
        return ChannelProviderRegistry(
            {
                channel_code: {
                    IOAuthCodeExchanger: oauth_exchanger,
                    IMessageRetriever: message_retriever,
                    ITokenRefresher: token_refresher,
                    IMessageSender: message_sender,
                    IMediaFetcher: media_fetcher,
                    IChannelHealthChecker: health_checker,
                    IWebhookSignatureVerifier: signature_verifier,
                    IWebhookMessageNormalizer: webhook_mapper,
                }
                for channel_code in channel_codes
            }
        )

    @staticmethod
    def channel_availability() -> DjangoChannelConfigReader:
        """Resolve configured plan/country availability through shared Identity ports."""
        return DjangoChannelConfigReader(
            merchant_plans=DjangoMerchantPlanReader(),
            merchant_countries=DjangoMerchantCountryReader(),
        )
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
            processed_events=DjangoOrderDetectionProcessedEventRepository(),
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
            processed_events=DjangoOrderDetectionProcessedEventRepository(),
            redirects=DjangoContactReferenceRedirectRepository(),
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
        )

    @staticmethod
    def detect_order(
        configuration: IDetectionConfiguration,
    ) -> DetectOrderUseCase:
        """Wire detection while requiring Rules Engine configuration from its owner."""
        return DetectOrderUseCase(
            processed_events=DjangoOrderDetectionProcessedEventRepository(),
            contact_redirects=DjangoContactReferenceRedirectRepository(),
            order_repository=DjangoOrderRepository(),
            candidate_repository=DjangoDetectionCandidateRepository(),
            configuration=configuration,
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
        )

    @staticmethod
    def purge_order_detection_merchant_data() -> PurgeOrderDetectionMerchantDataUseCase:
        """Wire local order/candidate/reminder cleanup with transactional completion (INV-OD-08)."""
        return PurgeOrderDetectionMerchantDataUseCase(
            purger=DjangoOrderDetectionMerchantPurger(),
            processed_events=DjangoOrderDetectionProcessedEventRepository(),
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
    def reconcile_order_status(configuration) -> ReconcileOrderStatusFromMessageUseCase:
        """Wire the message status consumer to Order-owned persistence and Outbox (INV-OD-09)."""
        return ReconcileOrderStatusFromMessageUseCase(
            order_repository=DjangoOrderRepository(),
            processed_events=DjangoOrderDetectionProcessedEventRepository(),
            configuration=configuration,
            intent_reader=DjangoOrderStatusIntentReader(),
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
        )

    @staticmethod
    def get_dormant_money_dashboard() -> GetDormantMoneyDashboardUseCase:
        """Wire the dashboard query to the Order Detection read repository."""
        return GetDormantMoneyDashboardUseCase(
            order_repository=DjangoOrderRepository(),
        )

    @staticmethod
    def schedule_reminder(
        policy_provider: IReminderPolicyProvider | None = None,
    ) -> ScheduleReminderUseCase:
        """Wire Reminder persistence while requiring policy from its owning context/config."""
        return ScheduleReminderUseCase(
            order_repository=DjangoOrderRepository(),
            reminder_repository=DjangoReminderRepository(),
            policy_provider=policy_provider or DjangoReminderPolicyProvider(),
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
            processed_events=DjangoOrderDetectionProcessedEventRepository(),
            delivery_policy=delivery_policy or DjangoReminderDeliveryPolicy(
                ApplicationContainer._billing_entitlements()
            ),
            message_provider=message_provider,
            delivery=delivery,
            retry_policy=retry_policy,
            unit_of_work=DjangoOrderDetectionUnitOfWork(),
            outbox=DjangoOrderDetectionOutbox(),
            clock=SystemClock(),
            batch_limit=batch_limit,
            lease_duration=lease_duration,
            manual_link_builder=DjangoManualMessageLinkBuilder(),
            outbound_usage=ApplicationContainer._billing_outbound_usage(),
        )

    @staticmethod
    def list_pending_detection_candidates() -> ListPendingDetectionCandidatesUseCase:
        """Wire merchant-scoped manual-review listing to the Django candidate repository."""
        return ListPendingDetectionCandidatesUseCase(
            candidate_repository=DjangoDetectionCandidateRepository(),
        )

    @staticmethod
    def update_contact_from_message(
        defaults_provider: IContactDefaultsProvider | None = None,
    ) -> UpdateContactFromMessageUseCase:
        """Wire CRM message processing with injected merchant defaults and Django adapters."""
        return UpdateContactFromMessageUseCase(
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            defaults_provider=defaults_provider or DjangoContactDefaultsProvider(
                DjangoMerchantCurrencyReader()
            ),
            processed_messages=DjangoProcessedMessageRepository(),
            unit_of_work=DjangoCRMUnitOfWork(),
        )

    @staticmethod
    def update_contact_from_order(
        loyalty_score_calculator: ILoyaltyScoreCalculator | None = None,
        defaults_provider: IContactDefaultsProvider | None = None,
    ) -> UpdateContactFromOrderUseCase:
        """Wire delivered-order CRM updates and require a configured loyalty calculator."""
        return UpdateContactFromOrderUseCase(
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            loyalty_score_calculator=loyalty_score_calculator,
            defaults_provider=defaults_provider or DjangoContactDefaultsProvider(
                DjangoMerchantCurrencyReader()
            ),
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
    def purge_crm_merchant_data() -> PurgeCRMMerchantDataUseCase:
        """Wire CRM-local deletion, processed-event tracking and completion Outbox (INV-CRM-09)."""
        return PurgeCRMMerchantDataUseCase(
            purger=DjangoCRMMerchantPurger(),
            processed_events=DjangoProcessedMessageRepository(),
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
        return CreateSegmentUseCase(
            segment_repository=DjangoSegmentRepository(),
            entitlements=ApplicationContainer._billing_entitlements(),
        )

    @staticmethod
    def _billing_entitlements() -> DjangoEntitlementReader:
        """Build the Billing reader with Identity's plan-code port."""
        return DjangoEntitlementReader(DjangoMerchantPlanReader())

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
    def list_crm_contacts() -> ListContactsUseCase:
        """Wire merchant-scoped CRM contact listing to CRM-owned read repositories."""
        return ListContactsUseCase(
            contact_repository=DjangoContactRepository(),
            segment_repository=DjangoSegmentRepository(),
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
            entitlements=ApplicationContainer._billing_entitlements(),
            cost_estimator=DjangoOutboundCostEstimator(),
            merchant_country_reader=DjangoMerchantCountryReader(),
            merchant_currency_reader=DjangoMerchantCurrencyReader(),
        )

    @staticmethod
    def process_bulk_message_campaign(
        rate_limiter,
        message_sender=None,
    ) -> ProcessBulkMessageCampaignUseCase:
        """Wire the campaign consumer while receiving platform adapters externally."""
        return ProcessBulkMessageCampaignUseCase(
            campaign_repository=DjangoBulkMessageCampaignRepository(),
            contact_repository=DjangoContactRepository(
                segment_membership_cache=ApplicationContainer._crm_segment_cache()
            ),
            processed_events=DjangoProcessedMessageRepository(),
            rate_limiter=rate_limiter,
            message_sender=message_sender or PlatformCampaignSender(
                ApplicationContainer.channel_provider_registry()
            ),
            unit_of_work=DjangoCRMUnitOfWork(),
            outbox=DjangoCRMOutbox(),
            outbound_usage=ApplicationContainer._billing_outbound_usage(),
            outbound_cost_estimator=DjangoOutboundCostEstimator(),
            merchant_country_reader=DjangoMerchantCountryReader(),
            merchant_currency_reader=DjangoMerchantCurrencyReader(),
        )

    @staticmethod
    def _billing_outbound_usage():
        from contexts.billing.infrastructure.adapters.django_outbound_services import (
            DjangoOutboundUsageRecorder,
        )

        return DjangoOutboundUsageRecorder(ApplicationContainer._billing_entitlements())

    @staticmethod
    def register_user() -> RegisterUserUseCase:
        return RegisterUserUseCase(
            DjangoUserRepository(), DjangoPasswordHasher(), DjangoIdentityUnitOfWork(),
            DjangoIdentityOutbox(), SystemIdentityClock(),
        )

    @staticmethod
    def authenticate_user() -> AuthenticateUserUseCase:
        return AuthenticateUserUseCase(
            DjangoUserRepository(),
            DjangoPasswordHasher(),
            DjangoTokenService(),
            DjangoLoginBackoff(),
        )

    @staticmethod
    def refresh_access_token() -> RefreshAccessTokenUseCase:
        return RefreshAccessTokenUseCase(DjangoTokenService(), DjangoUserRepository())

    @staticmethod
    def logout_user() -> LogoutUserUseCase:
        return LogoutUserUseCase(DjangoTokenService())

    @staticmethod
    def revoke_all_sessions() -> RevokeAllSessionsUseCase:
        return RevokeAllSessionsUseCase(DjangoTokenService())

    @staticmethod
    def create_merchant() -> CreateMerchantUseCase:
        return CreateMerchantUseCase(
            DjangoMerchantRepository(), DjangoIdentityUnitOfWork(), DjangoIdentityOutbox(),
            SystemIdentityClock(),
        )

    @staticmethod
    def purge_identity_merchant_data() -> PurgeMerchantDataUseCase:
        """Wire Identity-owned merchant deletion with its transactional Outbox (INV-BK-06)."""
        return PurgeMerchantDataUseCase(
            merchants=DjangoMerchantRepository(),
            processed_events=DjangoIdentityProcessedEventRepository(),
            unit_of_work=DjangoIdentityUnitOfWork(),
            outbox=DjangoIdentityOutbox(),
        )

    @staticmethod
    def change_subscription_plan(usage_provider=None) -> ChangeSubscriptionPlanUseCase:
        return ChangeSubscriptionPlanUseCase(
            merchants=DjangoMerchantRepository(),
            usage=usage_provider or DjangoConnectionUsageReader(),
            plan_catalog=DjangoPlanCatalogReader(),
            entitlements=ApplicationContainer._billing_entitlements(),
            unit_of_work=DjangoIdentityUnitOfWork(),
            outbox=DjangoIdentityOutbox(),
            clock=SystemIdentityClock(),
        )

    @staticmethod
    def connect_platform() -> ConnectPlatformUseCase:
        """Wire capability-based providers and shared plan/configuration ports for channels."""
        return ConnectPlatformUseCase(
            connections=DjangoPlatformConnectionRepository(),
            providers=ApplicationContainer.channel_provider_registry(),
            channel_availability=ApplicationContainer.channel_availability(),
            cipher=DjangoAesTokenCipher(),
            usage_reader=DjangoConnectionUsageReader(),
            entitlement_reader=ApplicationContainer._billing_entitlements(),
            unit_of_work=DjangoPlatformConnectorsUnitOfWork(),
            outbox=DjangoPlatformConnectorsOutbox(),
            clock=SystemPlatformClock(),
        )

    @staticmethod
    def handle_incoming_webhook() -> HandleIncomingWebhookUseCase:
        """Wire signature validation before mapping, idempotent persistence and Outbox."""
        return HandleIncomingWebhookUseCase(
            connections=DjangoPlatformConnectionRepository(),
            messages=DjangoMessageRepository(),
            providers=ApplicationContainer.channel_provider_registry(),
            replay_cache=DjangoWebhookReplayCache(),
            replay_ttl_seconds=2 * settings.PLATFORM_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS,
            unit_of_work=DjangoPlatformConnectorsUnitOfWork(),
            outbox=DjangoPlatformConnectorsOutbox(),
        )

    @staticmethod
    def purge_platform_connectors_merchant_data() -> PurgePlatformConnectorsMerchantDataUseCase:
        """Wire local credential/message deletion, event idempotency and Outbox completion (INV-PC-05)."""
        return PurgePlatformConnectorsMerchantDataUseCase(
            purger=DjangoPlatformConnectorsMerchantPurger(),
            processed_events=DjangoPlatformConnectorsProcessedEventRepository(),
            unit_of_work=DjangoPlatformConnectorsUnitOfWork(),
            outbox=DjangoPlatformConnectorsOutbox(),
            clock=SystemPlatformClock(),
        )

    @staticmethod
    def sync_platform_messages() -> SyncMessagesUseCase:
        """Wire one-connection sync so scheduled callers can isolate failures per connection."""
        return SyncMessagesUseCase(
            connections=DjangoPlatformConnectionRepository(),
            messages=DjangoMessageRepository(),
            providers=ApplicationContainer.channel_provider_registry(),
            unit_of_work=DjangoPlatformConnectorsUnitOfWork(),
            outbox=DjangoPlatformConnectorsOutbox(),
            clock=SystemPlatformClock(),
        )

    @staticmethod
    def sync_active_platform_connections() -> SyncActiveConnectionsJob:
        """Build the per-merchant job that isolates each connection's sync outcome."""
        return SyncActiveConnectionsJob(
            connections=DjangoPlatformConnectionRepository(),
            sync_use_case=ApplicationContainer.sync_platform_messages(),
        )

    @staticmethod
    def refresh_platform_tokens() -> RefreshTokensUseCase:
        """Wire token refresh while keeping plaintext credentials inside adapters."""
        return RefreshTokensUseCase(
            connections=DjangoPlatformConnectionRepository(),
            providers=ApplicationContainer.channel_provider_registry(),
            cipher=DjangoAesTokenCipher(),
            unit_of_work=DjangoPlatformConnectorsUnitOfWork(),
            outbox=DjangoPlatformConnectorsOutbox(),
            clock=SystemPlatformClock(),
        )

    @staticmethod
    def evaluate_message() -> EvaluateMessageUseCase:
        """Wire configured Rule strategies and the shared merchant-country port."""
        return EvaluateMessageUseCase(
            rule_sets=DjangoRuleSetRepository(),
            country_reader=DjangoMerchantCountryReader(),
            evaluators={
                RuleType.KEYWORD_MATCH: KeywordMatchEvaluator(),
                RuleType.CONFIGURED_INTENT: KeywordMatchEvaluator(),
                RuleType.AMOUNT_PATTERN: AmountPatternEvaluator(),
                RuleType.PAYMENT_PROOF_SIGNAL: MediaPresenceEvaluator(),
                RuleType.EMOJI_SIGNAL: EmojiMatchEvaluator(),
            },
            processed_events=DjangoRulesProcessedEventRepository(),
            unit_of_work=DjangoRulesEngineUnitOfWork(),
            outbox=DjangoRulesEngineOutbox(),
        )

    @staticmethod
    def update_rule_set() -> UpdateRuleSetUseCase:
        """Wire RuleSet configuration to its repository and context transaction."""
        return UpdateRuleSetUseCase(
            rule_sets=DjangoRuleSetRepository(),
            unit_of_work=DjangoRulesEngineUnitOfWork(),
        )

    @staticmethod
    def purge_rules_engine_merchant_data() -> PurgeRulesEngineMerchantDataUseCase:
        """Wire merchant RuleSet cleanup and transactional completion (INV-RE-05)."""
        return PurgeRulesEngineMerchantDataUseCase(
            purger=DjangoRulesEngineMerchantPurger(),
            processed_events=DjangoRulesProcessedEventRepository(),
            unit_of_work=DjangoRulesEngineUnitOfWork(),
            outbox=DjangoRulesEngineOutbox(),
        )

    @staticmethod
    def adjust_rule_weight_from_correction() -> AdjustRuleWeightFromCorrectionUseCase:
        """Wire merchant-only rule feedback with event idempotency protection."""
        return AdjustRuleWeightFromCorrectionUseCase(
            rule_sets=DjangoRuleSetRepository(),
            processed_events=DjangoRulesProcessedEventRepository(),
            unit_of_work=DjangoRulesEngineUnitOfWork(),
        )

    @staticmethod
    def create_backup_snapshot() -> CreateSnapshotUseCase:
        """Wire snapshot creation to the shared consent and owner-context data ports."""
        return CreateSnapshotUseCase(
            backups=DjangoBackupRepository(),
            storage=configured_object_storage(),
            consent_reader=DjangoConnectionConsentReader(),
            message_reader=DjangoBackupMessageReader(),
            contact_reader=DjangoBackupContactReader(),
            unit_of_work=DjangoBackupUnitOfWork(),
            outbox=DjangoBackupOutbox(),
            clock=SystemBackupClock(),
        )

    @staticmethod
    def list_backups() -> ListBackupsUseCase:
        """Wire merchant-scoped snapshot listing to Backup persistence."""
        return ListBackupsUseCase(DjangoBackupRepository())

    @staticmethod
    def restore_from_snapshot() -> RestoreFromSnapshotUseCase:
        """Wire snapshot export and configured signed URL lifetime."""
        return RestoreFromSnapshotUseCase(
            backups=DjangoBackupRepository(),
            storage=configured_object_storage(),
            unit_of_work=DjangoBackupUnitOfWork(),
            clock=SystemBackupClock(),
            export_ttl_minutes=settings.BACKUP_EXPORT_TTL_MINUTES,
        )

    @staticmethod
    def get_backup_export() -> GetBackupExportUseCase:
        """Wire export polling to merchant-scoped Backup persistence."""
        return GetBackupExportUseCase(DjangoBackupRepository())

    @staticmethod
    def check_account_health() -> CheckAccountHealthUseCase:
        """Wire scheduled health checks through the shared Platform Connectors port."""
        return CheckAccountHealthUseCase(
            health_checker=DjangoAccountHealthChecker(),
            unit_of_work=DjangoBackupUnitOfWork(),
            outbox=DjangoBackupOutbox(),
            clock=SystemBackupClock(),
        )

    @staticmethod
    def delete_all_merchant_data() -> DeleteAllMerchantDataUseCase:
        """Wire irreversible merchant purge behind the configured confirmation verifier."""
        return DeleteAllMerchantDataUseCase(
            backups=DjangoBackupRepository(),
            storage=configured_object_storage(),
            token_verifier=DjangoConfirmationTokenVerifier(),
            unit_of_work=DjangoBackupUnitOfWork(),
            outbox=DjangoBackupOutbox(),
            clock=SystemBackupClock(),
        )

    @staticmethod
    def request_merchant_deletion() -> RequestMerchantDeletionUseCase:
        """Wire reauthentication through Identity and token persistence through Backup."""
        return RequestMerchantDeletionUseCase(
            reauthentication=DjangoReauthenticationVerifier(),
            tokens=DjangoDeletionTokenStore(),
            clock=SystemBackupClock(),
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
            DjangoAccessControlProcessedEventRepository(),
        )

    @staticmethod
    def purge_access_control_merchant_data() -> PurgeAccessControlMerchantDataUseCase:
        """Wire local assignment deletion, idempotency and Outbox completion (INV-AC-06)."""
        return PurgeAccessControlMerchantDataUseCase(
            purger=DjangoAccessControlMerchantPurger(),
            processed_events=DjangoAccessControlProcessedEventRepository(),
            unit_of_work=DjangoAccessControlUnitOfWork(),
            outbox=DjangoAccessControlOutbox(),
        )