from django.urls import path

from .presentation import views


urlpatterns = [
    path("pricing", views.pricing, name="billing-pricing"),
    path("trials", views.start_trial, name="billing-start-trial"),
    path("coupons/apply", views.apply_coupon, name="billing-apply-coupon"),
    path("referrals/redeem", views.redeem_referral, name="billing-redeem-referral"),
    path("admin/trial-policy", views.upsert_trial_policy, name="billing-upsert-trial-policy"),
    path("admin/referral-policy", views.upsert_referral_policy, name="billing-upsert-referral-policy"),
    path("admin/coupons", views.upsert_coupon, name="billing-upsert-coupon"),
    path("admin/outbound-rates", views.upsert_outbound_rate, name="billing-upsert-outbound-rate"),
    path("outbound/estimate", views.estimate_outbound, name="billing-estimate-outbound"),
    path("outbound/usage", views.outbound_usage, name="billing-outbound-usage"),
    path("admin/plans/<str:code>", views.upsert_plan, name="billing-upsert-plan"),
    path("admin/plan-prices", views.upsert_plan_price, name="billing-upsert-plan-price"),
]