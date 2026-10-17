def requires_permission(permission: str):
    """Declare the permission checked by PermissionMiddleware for a route."""
    if not isinstance(permission, str) or not permission.strip():
        raise ValueError("Permission name must be a non-empty string.")

    def decorate(view):
        view.required_permission = permission
        return view

    return decorate


def allow_anonymous(view):
    """Mark an explicitly public route for AuthenticationMiddleware."""
    view.allow_anonymous = True
    return view


def emit_audit(request, outcome: str, permission: str | None = None) -> None:
    """Send metadata-only audit events through the configured audit sink."""
    from django.conf import settings

    sink = getattr(settings, "PIEDLENS_AUDIT_SINK", None)
    event = {
        "correlation_id": getattr(request, "correlation_id", None),
        "user_id": str(getattr(getattr(request, "user", None), "id", "") or ""),
        "merchant_id": str(getattr(request, "merchant_id", "") or ""),
        "permission": permission,
        "outcome": outcome,
        "route": getattr(request, "path", ""),
    }
    if sink is not None:
        sink(event)