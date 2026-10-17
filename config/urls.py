from django.urls import include, path


urlpatterns = [
	path("api/v1/", include("contexts.identity.urls")),
	path("api/v1/", include("contexts.access_control.urls")),
	path("api/v1/", include("contexts.crm.urls")),
	path("api/v1/", include("contexts.order_detection.urls")),
	path("api/v1/", include("contexts.platform_connectors.urls")),
	path("api/v1/", include("contexts.rules_engine.urls")),
	path("api/v1/", include("contexts.backup.urls")),
]