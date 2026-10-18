from django.urls import path

from .presentation import views


urlpatterns = [
    path("auth/register", views.register, name="identity-register"),
    path("auth/login", views.login, name="identity-login"),
    path("auth/refresh", views.refresh, name="identity-refresh"),
    path("auth/logout", views.logout, name="identity-logout"),
    path("auth/logout-all", views.logout_all, name="identity-logout-all"),
    path("merchants", views.create_merchant, name="identity-create-merchant"),
]