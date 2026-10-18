from django.urls import include, path
from piedlens_platform import health_views


urlpatterns = [
	path("health/live", health_views.live, name="health-live"),
	path("health/ready", health_views.ready, name="health-ready"),
	path("health/metrics", health_views.metrics, name="health-metrics"),
	path("api/v1/", include("contexts.identity.urls")),
	path("api/v1/", include("contexts.access_control.urls")),
	path("api/v1/", include("contexts.crm.urls")),
	path("api/v1/", include("contexts.order_detection.urls")),
	path("api/v1/", include("contexts.platform_connectors.urls")),
	path("api/v1/", include("contexts.rules_engine.urls")),
	path("api/v1/", include("contexts.backup.urls")),
]