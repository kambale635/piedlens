# Access Control

Owns configurable roles, permissions, assignments, and access scopes.

Reference: [docs/20-context-access-control.md](../../../docs/20-context-access-control.md).

Use Cases: CreateRoleUseCase, UpdateRolePermissionsUseCase, AssignRoleToUserUseCase, RevokeRoleFromUserUseCase, and CheckPermissionUseCase (internal), documented in the context reference.

Tests: `docker compose run --rm django python manage.py test tests.unit.access_control`.