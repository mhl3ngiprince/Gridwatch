
from django.core.management.base import BaseCommand
from dashboard.mqtt_client import mqtt_client
import time
import signal
import sys

class Command(BaseCommand):
    help = 'Run the MQTT client to listen for fiber sensor alerts'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting MQTT client...'))

        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING('Shutting down MQTT client...'))
            mqtt_client.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        mqtt_client.run()
