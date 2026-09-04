
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/alerts/', views.api_alerts, name='api_alerts'),
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/zones/', views.api_zones, name='api_zones'),
    path('api/device-ingest/', views.api_device_ingest, name='api_device_ingest'),
    path('api/alerts/<uuid:alert_id>/acknowledge/', views.api_acknowledge, name='api_acknowledge'),
]
