from django.urls import path

from .presentation import views


urlpatterns = [
    path("dashboard/dormant-money", views.dormant_money_dashboard,
         name="order-detection-dormant-money"),
    path("orders/<uuid:order_id>/status", views.update_order_status,
         name="order-detection-update-status"),
    path("orders/<uuid:order_id>/reminders", views.schedule_reminder,
         name="order-detection-schedule-reminder"),
    path("detection-candidates", views.list_pending_detection_candidates,
         name="order-detection-list-candidates"),
    path("detection-candidates/<uuid:candidate_id>/decision", views.decide_detection_candidate,
         name="order-detection-candidate-decision"),
]