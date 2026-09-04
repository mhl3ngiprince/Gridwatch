
from django.db import models
from django.contrib.auth.models import User
import uuid

class Zone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    topic = models.CharField(max_length=255, unique=True, help_text="MQTT topic for this zone")
    max_distance_meters = models.PositiveIntegerField(default=2500)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Monitoring Zone'
        verbose_name_plural = 'Monitoring Zones'

    def __str__(self):
        return f"{self.name} ({self.topic})"

class FiberAlert(models.Model):
    STATUS_CHOICES = [
        ('ALARM', 'Alarm'),
        ('WARNING', 'Warning'),
        ('NORMAL', 'Normal'),
        ('OFFLINE', 'Offline'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='alerts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NORMAL')
    distance_meters = models.PositiveIntegerField(null=True, blank=True)
    danger = models.CharField(max_length=255, blank=True)
    raw_payload = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="Operator notes about this alert")

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Fiber Alert'
        verbose_name_plural = 'Fiber Alerts'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['status']),
            models.Index(fields=['zone']),
        ]

    def __str__(self):
        return f"[{self.status}] {self.danger or 'No danger info'} at {self.distance_meters}m"

class SystemStatus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, default='MQTT Broker')
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    broker_host = models.CharField(max_length=255, default='broker.hivemq.com')
    broker_port = models.PositiveIntegerField(default=1883)
    connected_clients = models.PositiveIntegerField(default=0)
    total_alerts_today = models.PositiveIntegerField(default=0)
    total_alerts_this_week = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Status'
        verbose_name_plural = 'System Statuses'

    def __str__(self):
        return f"{self.name} - {'Online' if self.is_online else 'Offline'}"
