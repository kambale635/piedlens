from django.urls import path

from .presentation import views


urlpatterns = [
    path("pricing", views.pricing, name="billing-pricing"),
    path("admin/plans/<str:code>", views.upsert_plan, name="billing-upsert-plan"),
    path("admin/plan-prices", views.upsert_plan_price, name="billing-upsert-plan-price"),
]