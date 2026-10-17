from django.urls import path

from .presentation import views


urlpatterns = [
    path("auth/register", views.register, name="identity-register"),
    path("auth/login", views.login, name="identity-login"),
    path("auth/refresh", views.refresh, name="identity-refresh"),
    path("merchants", views.create_merchant, name="identity-create-merchant"),
]