
import json
import logging
import threading
import time
from typing import Any, Dict

import paho.mqtt.client as mqtt
from django.conf import settings
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import FiberAlert, SystemStatus, Zone

logger = logging.getLogger('dashboard')


def normalize_sensor_payload(topic: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize device payloads from MQTT, USB serial, or gateway data into dashboard format."""
    if not isinstance(payload, dict):
        return {
            'topic': topic,
            'status': 'ALARM',
            'distance_meters': 0,
            'danger': 'Unrecognized sensor payload',
            'device_id': None,
            'raw_payload': payload,
        }

    normalized = dict(payload)
    normalized['topic'] = topic
    normalized['status'] = str(normalized.get('status', normalized.get('severity', 'ALARM'))).upper()

    if normalized['status'] not in {'ALARM', 'WARNING', 'NORMAL', 'OFFLINE'}:
        normalized['status'] = 'ALARM'

    normalized['distance_meters'] = (
        normalized.get('distance_meters')
        or normalized.get('distance')
        or normalized.get('distance_m')
        or 0
    )
    normalized['danger'] = normalized.get('danger') or normalized.get('message') or normalized.get('event') or 'Sensor update received'
    normalized['device_id'] = normalized.get('device_id') or normalized.get('sensor_id') or normalized.get('node_id') or 'unknown-device'

    location = normalized.get('location') or {}
    gps = location.get('gps_estimated') if isinstance(location, dict) else {}
    if not isinstance(gps, dict):
        gps = {}

    normalized['latitude'] = normalized.get('latitude')
    normalized['longitude'] = normalized.get('longitude')

    if normalized['latitude'] is None and isinstance(gps, dict):
        normalized['latitude'] = gps.get('latitude')
    if normalized['longitude'] is None and isinstance(gps, dict):
        normalized['longitude'] = gps.get('longitude')

    if normalized['latitude'] is None and isinstance(location, dict):
        normalized['latitude'] = location.get('latitude')
    if normalized['longitude'] is None and isinstance(location, dict):
        normalized['longitude'] = location.get('longitude')

    if normalized['latitude'] is not None and normalized['longitude'] is not None:
        normalized['location_label'] = f"Lat {normalized['latitude']}, Lon {normalized['longitude']}"
    else:
        normalized['location_label'] = 'Location unavailable'

    signal_values = normalized.get('signals') or {}
    signal_count = sum(
        1 for value in signal_values.values()
        if isinstance(value, (int, float)) and value > 0
    ) if isinstance(signal_values, dict) else 0
    base_score = {'ALARM': 85, 'WARNING': 55, 'NORMAL': 5, 'OFFLINE': 35}[normalized['status']]
    normalized['risk_score'] = min(100, base_score + signal_count * 5)
    normalized['source'] = normalized.get('source') or topic.split('/', 1)[0] or 'mqtt'

    return normalized

class FiberMQTTClient:
    """MQTT client for fiber optic sensor monitoring."""

    def __init__(self):
        self.client = None
        self.connected = False
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        self.running = False
        self.thread = None

    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker."""
        if rc == 0:
            self.connected = True
            self.reconnect_delay = 5
            logger.info(f"Connected to MQTT broker: {settings.MQTT_BROKER}:{settings.MQTT_PORT}")

            # Subscribe to all active zone topics
            zones = Zone.objects.filter(is_active=True)
            for zone in zones:
                client.subscribe(zone.topic)
                logger.info(f"Subscribed to topic: {zone.topic}")

            # Also subscribe to default topic
            client.subscribe(settings.MQTT_TOPIC)
            logger.info(f"Subscribed to default topic: {settings.MQTT_TOPIC}")

            # Update system status
            self._update_status(True)
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
            self.connected = False

    def on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker."""
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker, return code: {rc}")
        self._update_status(False)

    def on_message(self, client, userdata, msg):
        """Callback when message received from MQTT broker."""
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            logger.info(f"Message received on {msg.topic}: {payload}")
            self._process_message(msg.topic, normalize_sensor_payload(msg.topic, payload))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON payload: {e}")
            # Try to process as plain text
            self._process_message(msg.topic, normalize_sensor_payload(msg.topic, {
                'status': 'ALARM',
                'danger': msg.payload.decode('utf-8'),
                'distance_meters': 0,
                'device_id': 'mqtt-text-payload',
            }))
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def _process_message(self, topic, payload):
        """Process incoming MQTT message and save to database."""
        try:
            # Find zone by topic
            zone = Zone.objects.filter(topic=topic).first()

            if not zone and topic:
                zone_name = payload.get('zone') or payload.get('zone_name') or 'Zone 1'
                zone, _ = Zone.objects.get_or_create(
                    topic=topic,
                    defaults={
                        'name': zone_name,
                        'max_distance_meters': 2500,
                        'description': 'Auto-created from device telemetry',
                    },
                )

            # Extract data
            status = str(payload.get('status', 'ALARM')).upper()
            distance = payload.get('distance_meters') or payload.get('distance') or 0
            danger = payload.get('danger', 'Unknown threat detected')
            device_id = payload.get('device_id') or 'unknown-device'

            # Validate status
            valid_statuses = ['ALARM', 'WARNING', 'NORMAL', 'OFFLINE']
            if status not in valid_statuses:
                status = 'ALARM'

            # Create alert
            alert = FiberAlert.objects.create(
                zone=zone,
                status=status,
                distance_meters=distance,
                danger=danger,
                raw_payload={**payload, 'device_id': device_id},
            )

            logger.info(f"Alert created: {alert}")

            # Broadcast to WebSocket clients via channel layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'fiber_alerts',
                {
                    'type': 'alert_message',
                    'data': {
                        'id': str(alert.id),
                        'status': alert.status,
                        'distance_meters': alert.distance_meters,
                        'danger': alert.danger,
                        'timestamp': alert.timestamp.isoformat(),
                        'zone': alert.zone.name if alert.zone else 'Unknown',
                        'acknowledged': alert.acknowledged,
                        'topic': topic,
                        'device_id': device_id,
                        'risk_score': payload.get('risk_score', 0),
                        'source': payload.get('source', 'mqtt'),
                        'latitude': payload.get('latitude'),
                        'longitude': payload.get('longitude'),
                        'location_label': payload.get('location_label', 'Location unavailable'),
                    }
                }
            )

            # Update system status
            self._update_status(True)

        except Exception as e:
            logger.error(f"Error saving alert: {e}")

    def _update_status(self, is_online):
        """Update system status in database."""
        try:
            status, created = SystemStatus.objects.get_or_create(
                name='MQTT Broker',
                defaults={
                    'broker_host': settings.MQTT_BROKER,
                    'broker_port': settings.MQTT_PORT,
                }
            )
            status.is_online = is_online
            status.last_seen = timezone.now()
            status.broker_host = settings.MQTT_BROKER
            status.broker_port = settings.MQTT_PORT
            status.save()
        except Exception as e:
            logger.error(f"Error updating system status: {e}")

    def connect(self):
        """Connect to MQTT broker."""
        try:
            self.client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID, clean_session=True)
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message

            logger.info(f"Connecting to {settings.MQTT_BROKER}:{settings.MQTT_PORT}")
            self.client.connect(
                settings.MQTT_BROKER,
                settings.MQTT_PORT,
                settings.MQTT_KEEPALIVE
            )
            self.client.loop_start()
            self.running = True
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.connected = False

    def disconnect(self):
        """Disconnect from MQTT broker."""
        self.running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        logger.info("MQTT client disconnected")

    def run(self):
        """Run the MQTT client with auto-reconnect."""
        self.running = True
        while self.running:
            if not self.connected:
                try:
                    self.connect()
                except Exception as e:
                    logger.error(f"Reconnection failed: {e}")
                    time.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
            time.sleep(1)

    def start(self):
        """Start the MQTT client in a background thread."""
        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        logger.info("MQTT client started in background thread")

    def stop(self):
        """Stop the MQTT client."""
        self.running = False
        self.disconnect()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        logger.info("MQTT client stopped")

# Singleton instance
mqtt_client = FiberMQTTClient()
