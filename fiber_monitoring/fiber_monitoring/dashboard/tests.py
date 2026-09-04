import os
from unittest.mock import patch

from django.test import SimpleTestCase

from dashboard.mqtt_client import normalize_sensor_payload
from fiber_monitoring import settings as settings_module


class SensorPayloadNormalizationTests(SimpleTestCase):
    def test_normalizes_usb_payloads_to_dashboard_format(self):
        payload = {
            'device_id': 'USB-OLT-01',
            'device': 'fiber_probe',
            'zone': 'Zone 1',
            'status': 'warning',
            'distance': 1520,
            'danger': 'Vibration anomaly detected',
            'source': 'usb',
        }

        normalized = normalize_sensor_payload('usb/zone1', payload)

        self.assertEqual(normalized['topic'], 'usb/zone1')
        self.assertEqual(normalized['status'], 'WARNING')
        self.assertEqual(normalized['distance_meters'], 1520)
        self.assertEqual(normalized['danger'], 'Vibration anomaly detected')
        self.assertEqual(normalized['device_id'], 'USB-OLT-01')

    def test_extracts_location_coordinates_from_nested_mqtt_payload(self):
        payload = {
            'status': 'CRITICAL',
            'distance_meters': 1425,
            'danger': 'Fiber cut detected',
            'location': {
                'chainage_meters': 1425.0,
                'gps_estimated': {
                    'latitude': -28.7324,
                    'longitude': 24.7578,
                },
            },
            'source': 'mqtt',
        }

        normalized = normalize_sensor_payload('eskom/alerts/zone1', payload)

        self.assertEqual(normalized['latitude'], -28.7324)
        self.assertEqual(normalized['longitude'], 24.7578)
        self.assertEqual(normalized['location_label'], 'Lat -28.7324, Lon 24.7578')


class ChannelLayerConfigurationTests(SimpleTestCase):
    def test_uses_in_memory_channel_layer_by_default(self):
        config = settings_module.get_channel_layer_config()
        self.assertEqual(config['default']['BACKEND'], 'channels.layers.InMemoryChannelLayer')

    def test_uses_redis_channel_layer_when_enabled(self):
        with patch.dict(os.environ, {'USE_REDIS': 'true', 'REDIS_HOST': 'redis', 'REDIS_PORT': '6379'}, clear=False):
            config = settings_module.get_channel_layer_config()

        self.assertEqual(config['default']['BACKEND'], 'channels_redis.core.RedisChannelLayer')
        self.assertEqual(config['default']['CONFIG']['hosts'], [('redis', 6379)])
