
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
from .models import FiberAlert, SystemStatus, Zone
from .mqtt_client import normalize_sensor_payload
import json


def _latest_status_context():
    status = SystemStatus.objects.first()
    return {
        'mqtt_broker': getattr(status, 'broker_host', 'localhost') if status else 'localhost',
        'mqtt_port': getattr(status, 'broker_port', 1883) if status else 1883,
    }

def dashboard(request):
    """Main dashboard view."""
    zones = Zone.objects.filter(is_active=True)
    recent_alerts = FiberAlert.objects.all()[:10]
    status = SystemStatus.objects.first()
    mqtt_context = _latest_status_context()

    # Statistics
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    stats = {
        'total_alerts_today': FiberAlert.objects.filter(timestamp__gte=today_start).count(),
        'total_alerts_week': FiberAlert.objects.filter(timestamp__gte=week_start).count(),
        'total_alerts': FiberAlert.objects.count(),
        'unacknowledged': FiberAlert.objects.filter(acknowledged=False).count(),
        'active_alarms': FiberAlert.objects.filter(status='ALARM', acknowledged=False).count(),
        'active_warnings': FiberAlert.objects.filter(status='WARNING', acknowledged=False).count(),
    }

    context = {
        'zones': zones,
        'recent_alerts': recent_alerts,
        'status': status,
        'stats': stats,
        'mqtt_broker': mqtt_context['mqtt_broker'],
        'mqtt_port': mqtt_context['mqtt_port'],
    }
    return render(request, 'dashboard/index.html', context)

@require_http_methods(["GET"])
def api_alerts(request):
    """API endpoint for recent alerts."""
    limit = int(request.GET.get('limit', 50))
    status_filter = request.GET.get('status', None)
    zone_id = request.GET.get('zone', None)

    alerts = FiberAlert.objects.all()

    if status_filter:
        alerts = alerts.filter(status=status_filter.upper())
    if zone_id:
        alerts = alerts.filter(zone_id=zone_id)

    alerts = alerts[:limit]

    data = []
    for alert in alerts:
        data.append({
            'id': str(alert.id),
            'status': alert.status,
            'distance_meters': alert.distance_meters,
            'danger': alert.danger,
            'timestamp': alert.timestamp.isoformat(),
            'zone': alert.zone.name if alert.zone else 'Unknown',
            'acknowledged': alert.acknowledged,
            'acknowledged_by': alert.acknowledged_by.username if alert.acknowledged_by else None,
            'device_id': alert.raw_payload.get('device_id', 'unknown-device'),
            'risk_score': alert.raw_payload.get('risk_score', 0),
            'source': alert.raw_payload.get('source', 'mqtt'),
        })

    return JsonResponse({'alerts': data, 'count': len(data)})

@require_http_methods(["GET"])
def api_stats(request):
    """API endpoint for dashboard statistics."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    # Hourly distribution for today
    hourly = []
    for hour in range(24):
        hour_start = today_start + timedelta(hours=hour)
        hour_end = hour_start + timedelta(hours=1)
        count = FiberAlert.objects.filter(timestamp__gte=hour_start, timestamp__lt=hour_end).count()
        hourly.append({'hour': hour, 'count': count})

    # Status distribution
    status_dist = list(FiberAlert.objects.values('status').annotate(count=Count('id')))

    # Zone distribution
    zone_dist = list(FiberAlert.objects.exclude(zone=None).values('zone__name').annotate(count=Count('id')))

    data = {
        'total_alerts_today': FiberAlert.objects.filter(timestamp__gte=today_start).count(),
        'total_alerts_week': FiberAlert.objects.filter(timestamp__gte=week_start).count(),
        'total_alerts': FiberAlert.objects.count(),
        'unacknowledged': FiberAlert.objects.filter(acknowledged=False).count(),
        'active_alarms': FiberAlert.objects.filter(status='ALARM', acknowledged=False).count(),
        'active_warnings': FiberAlert.objects.filter(status='WARNING', acknowledged=False).count(),
        'hourly_distribution': hourly,
        'status_distribution': status_dist,
        'zone_distribution': zone_dist,
    }
    return JsonResponse(data)

@require_http_methods(["POST"])
def api_acknowledge(request, alert_id):
    """API endpoint to acknowledge an alert."""
    try:
        alert = FiberAlert.objects.get(id=alert_id)
        alert.acknowledged = True
        alert.acknowledged_by = request.user if request.user.is_authenticated else None
        alert.acknowledged_at = timezone.now()
        alert.save()
        return JsonResponse({'success': True, 'message': 'Alert acknowledged'})
    except FiberAlert.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Alert not found'}, status=404)

@require_http_methods(["GET"])
def api_zones(request):
    """API endpoint for zones."""
    zones = Zone.objects.filter(is_active=True)
    data = []
    for zone in zones:
        latest_alert = zone.alerts.first()
        data.append({
            'id': str(zone.id),
            'name': zone.name,
            'topic': zone.topic,
            'max_distance': zone.max_distance_meters,
            'description': zone.description,
            'alert_count': zone.alerts.count(),
            'latest_alert': {
                'status': latest_alert.status,
                'distance': latest_alert.distance_meters,
                'danger': latest_alert.danger,
                'timestamp': latest_alert.timestamp.isoformat(),
            } if latest_alert else None,
        })
    return JsonResponse({'zones': data})


@csrf_exempt
@require_http_methods(["POST"])
def api_device_ingest(request):
    """Receive sensor telemetry from USB, serial, gateway, or MQTT adapters."""
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid JSON payload'}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({'success': False, 'message': 'Payload must be a JSON object'}, status=400)

    topic = payload.get('topic') or payload.get('source') or 'usb/local-device'
    normalized = normalize_sensor_payload(topic, payload)

    zone_name = payload.get('zone') or payload.get('zone_name') or 'Zone 1'
    zone = Zone.objects.filter(topic=topic).first()
    if not zone:
        zone, _ = Zone.objects.get_or_create(
            topic=topic,
            defaults={
                'name': zone_name,
                'max_distance_meters': payload.get('max_distance_meters') or 2500,
                'description': f"Auto-created from {payload.get('source') or 'device'} telemetry",
            },
        )

    alert = FiberAlert.objects.create(
        zone=zone,
        status=normalized['status'],
        distance_meters=normalized['distance_meters'],
        danger=normalized['danger'],
        raw_payload=normalized,
    )

    return JsonResponse({
        'success': True,
        'alert_id': str(alert.id),
        'status': alert.status,
        'zone': zone.name,
        'distance_meters': alert.distance_meters,
        'danger': alert.danger,
    })
