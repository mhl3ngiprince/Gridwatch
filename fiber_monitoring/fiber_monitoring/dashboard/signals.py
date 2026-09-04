
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from asgiref.sync import async_to_sync

try:
    from channels.layers import get_channel_layer
except ImportError:
    # Handle case where channels is not properly configured
    get_channel_layer = None

from .models import FiberAlert

@receiver(post_save, sender=FiberAlert)
def alert_saved(sender, instance, created, **kwargs):
    """Broadcast new alerts to WebSocket clients."""
    if created and get_channel_layer:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'fiber_alerts',
                {
                    'type': 'alert_message',
                    'data': {
                        'id': str(instance.id),
                        'status': instance.status,
                        'distance_meters': instance.distance_meters,
                        'danger': instance.danger,
                        'timestamp': instance.timestamp.isoformat(),
                        'zone': instance.zone.name if instance.zone else 'Unknown',
                        'acknowledged': instance.acknowledged,
                        'device_id': instance.raw_payload.get('device_id', 'unknown-device'),
                        'risk_score': instance.raw_payload.get('risk_score', 0),
                        'source': instance.raw_payload.get('source', 'mqtt'),
                    }
                }
            )
