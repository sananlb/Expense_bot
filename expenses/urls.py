"""
URL configuration for expenses app
"""
from django.urls import path
from .views import HealthCheckView, MetricsView

app_name = 'expenses'

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health_check'),
    path('metrics/', MetricsView.as_view(), name='metrics'),
]