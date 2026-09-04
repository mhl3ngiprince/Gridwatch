
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import FiberAlert

class AlertConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'fiber_alerts'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to Fiber Monitoring Dashboard'
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle messages from client."""
        try:
            data = json.loads(text_data)
            action = data.get('action')

            if action == 'acknowledge':
                alert_id = data.get('alert_id')
                # Handle acknowledgment via API instead
                await self.send(text_data=json.dumps({
                    'type': 'info',
                    'message': f'Use POST /api/alerts/{alert_id}/acknowledge/ to acknowledge'
                }))
            elif action == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))

    async def alert_message(self, event):
        """Handle alert messages from MQTT client."""
        await self.send(text_data=json.dumps({
            'type': 'alert',
            'data': event['data']
        }))

    async def status_update(self, event):
        """Handle status updates."""
        await self.send(text_data=json.dumps({
            'type': 'status',
            'data': event['data']
        }))
