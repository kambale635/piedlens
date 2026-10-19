# Billing

Billing owns plan definitions, prices, entitlements, trials, coupons, referrals, paid-period attribution, and its transactional Outbox. Other contexts read plan limits only through shared-kernel ports.

Use Cases: `UpsertPlanUseCase`, `UpsertPlanPriceUseCase`, `ListPricingUseCase`, `StartTrialUseCase`, `ApplyCouponUseCase`, `RedeemReferralUseCase`, `RecordFirstPaidPeriodUseCase`, `UpsertTrialPolicyUseCase`, `UpsertReferralPolicyUseCase`, and `UpsertCouponUseCase`; contracts are in `docs/15-use-cases-catalog.md`.

Run tests: `./venv/bin/python manage.py test tests.integration.billing --settings=config.test_settings -v 2`.

Provisional defaults, editable with `plan.manage`: 14-day Starter trial without a required card; referral reward 10% for 30 days, capped at 10 referred merchants per referrer. They are operational defaults, not finalized commercial terms.