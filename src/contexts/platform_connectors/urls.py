from django.urls import path

from .presentation import views


urlpatterns = [
    path("platform-connections", views.connect_platform, name="platform-connect"),
    path("webhooks/whatsapp", views.whatsapp_webhook, name="whatsapp-webhook"),
    path("webhooks/instagram", views.instagram_webhook, name="instagram-webhook"),
]