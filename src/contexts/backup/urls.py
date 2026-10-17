from django.urls import path

from .presentation import views


urlpatterns = [
    path("backups", views.list_backups, name="backup-list"),
    path("backups/<uuid:platform_connection_id>/restore", views.restore_from_snapshot,
         name="backup-restore"),
    path("backups/exports/<uuid:export_job_id>", views.get_backup_export,
         name="backup-export-status"),
    path("backups/objects/<uuid:reference>", views.download_backup_object,
         name="backup-object-download"),
    path("merchants/<uuid:merchant_id>/data", views.delete_all_merchant_data,
         name="merchant-delete-data"),
]