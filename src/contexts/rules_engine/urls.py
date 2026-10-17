from django.urls import path

from .presentation import views


urlpatterns = [
    path("rule-sets/<str:scope>", views.update_rule_set, name="rules-engine-update-rule-set"),
]