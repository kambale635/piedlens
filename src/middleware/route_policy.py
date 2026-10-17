def requires_permission(permission: str):
    """Declare the permission checked by PermissionMiddleware for a route."""
    if not isinstance(permission, str) or not permission.strip():
        raise ValueError("Permission name must be a non-empty string.")

    def decorate(view):
        view.required_permission = permission
        return view

    return decorate


def public_route(view=None, *, authentication_required: bool = False):
    """Declare an explicit public policy, optionally requiring an authenticated principal."""
    def decorate(target):
        target.public_route = True
        target.authentication_required = authentication_required
        target.allow_anonymous = not authentication_required
        return target

    return decorate(view) if view is not None else decorate


allow_anonymous = public_route


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