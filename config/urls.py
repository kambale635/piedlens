from django.urls import include, path


urlpatterns = [
	path("api/v1/", include("contexts.identity.urls")),
	path("api/v1/", include("contexts.access_control.urls")),
]