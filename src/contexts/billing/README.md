# Billing

Billing owns plan definitions, prices, entitlements, trials, coupons, referrals, paid-period attribution, and its transactional Outbox. Other contexts read plan limits only through shared-kernel ports.

Use Cases: `UpsertPlanUseCase`, `UpsertPlanPriceUseCase`, `ListPricingUseCase`, `StartTrialUseCase`, `ApplyCouponUseCase`, `RedeemReferralUseCase`, `RecordFirstPaidPeriodUseCase`, `UpsertTrialPolicyUseCase`, `UpsertReferralPolicyUseCase`, and `UpsertCouponUseCase`; contracts are in `docs/15-use-cases-catalog.md`.

Run tests: `./venv/bin/python manage.py test tests.integration.billing --settings=config.test_settings -v 2`.

Provisional defaults, editable with `plan.manage`: 14-day Starter trial without a required card; referral reward 10% for 30 days, capped at 10 referred merchants per referrer. They are operational defaults, not finalized commercial terms.

Outbound rates are editable per country, category, currency, and validity window. No Meta rate is seeded until a verified country tariff is supplied; missing rates fail estimation explicitly. `OutboundMessageUsage` tracks idempotent API reservations only; manual links do not consume quota. Meta charges the seller directly (`chargeProcessor=meta_direct`), never Billing. WhatsApp mock onboarding rejects `externalAccountId="not-business-account"` with `NOT_A_BUSINESS_ACCOUNT`.