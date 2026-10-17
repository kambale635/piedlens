from django.urls import path

from .presentation import views


urlpatterns = [
    path("roles", views.create_role, name="access-control-create-role"),
    path("roles/<uuid:role_id>/permissions", views.update_role_permissions,
         name="access-control-update-role"),
    path("role-assignments", views.assign_role, name="access-control-assign-role"),
    path("role-assignments/<uuid:role_assignment_id>", views.revoke_role,
         name="access-control-revoke-role"),
]