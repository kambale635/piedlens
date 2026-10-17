from django.urls import path

from .presentation import views


urlpatterns = [
    path("contacts", views.list_contacts, name="crm-list-contacts"),
    path("contacts/merge", views.merge_contacts, name="crm-merge-contacts"),
    path("segments", views.create_segment, name="crm-create-segment"),
    path("segments/<uuid:segment_id>/members", views.get_segment_members,
         name="crm-segment-members"),
    path("segments/<uuid:segment_id>/bulk-message", views.send_bulk_message,
         name="crm-send-bulk-message"),
]