from django.urls import path

from .presentation import views


urlpatterns = [
    path("platform-connections", views.connect_platform, name="platform-connect"),
    path("imports", views.submit_conversation_import, name="conversation-import-submit"),
    path("imports/<uuid:import_id>", views.get_conversation_import, name="conversation-import-status"),
    path("webhooks/whatsapp", views.whatsapp_webhook, name="whatsapp-webhook"),
    path("webhooks/instagram", views.instagram_webhook, name="instagram-webhook"),
]