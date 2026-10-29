from django.urls import path

from .presentation import views

urlpatterns = [
    path("payments/checkout", views.start_payment, name="payment-start"),
    path("admin/payment-routes", views.configure_payment_route, name="payment-route-configure"),
    path("webhooks/payments/<str:provider_code>", views.payment_webhook, name="payment-webhook"),
]
