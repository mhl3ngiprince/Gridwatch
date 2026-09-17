# Fiber Optic Monitoring Dashboard (Django)

A production-ready Industrial IoT dashboard built with Django, Django Channels, and MQTT for real-time fiber optic cable monitoring.

## Features

- **Real-time WebSocket alerts** via Django Channels + Redis
- **MQTT Broker integration** with auto-reconnect and multi-zone support
- **Persistent database** (SQLite default, PostgreSQL ready)
- **Django Admin** for alert management, filtering, search, and bulk acknowledge actions
- **REST API** for stats, alerts, zones, and acknowledgments
- **Multi-zone support** with per-zone MQTT topics and max distance tracking
- **Modern dark UI** with live visualizer, toast notifications, sound alerts, and filterable tables
- **Docker & Docker Compose** support for one-command deployment
- **Environment configuration** via `.env` file

## Architecture

```
Fiber Sensor / MQTTX  -->  MQTT Broker (HiveMQ)  -->  Django MQTT Client
                                                          |
                                                          v
                                                    Django Channels
                                                    (WebSocket)
                                                          |
                                                          v
                                                   Browser Dashboard
                                                          |
                                                          v
                                              SQLite / PostgreSQL DB
```

## Quick Start

### 1. Clone & Setup

```bash
cd fiber_monitoring
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment (optional)

```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Initialize Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Start Redis (required for Channels)

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# Docker
docker run -d -p 6379:6379 redis:alpine
```

### 5. Start the MQTT Listener

In a separate terminal:

```bash
python manage.py runmqtt
```

### 6. Start the Django Server

```bash
python manage.py runserver
```

### 7. Open Browser

Navigate to: **http://127.0.0.1:8000**

Admin panel: **http://127.0.0.1:8000/admin**

## Test with MQTTX

1. Download [MQTTX](https://mqttx.app/) or use any MQTT client
2. Connect to `broker.hivemq.com:1883`
3. Publish to `eskom/alerts/zone1`:

```json
{
  "status": "ALARM",
  "distance_meters": 1420,
  "danger": "Cable Cutting detected"
}
```

4. Watch the dashboard update instantly with the alert

## Docker Deployment

```bash
docker-compose up --build
```

This starts Redis, Django, and the MQTT listener in one command.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/alerts/` | GET | List recent alerts (filter by `status`, `zone`, `limit`) |
| `/api/stats/` | GET | Dashboard statistics & distributions |
| `/api/zones/` | GET | Active monitoring zones |
| `/api/alerts/<uuid>/acknowledge/` | POST | Acknowledge an alert |

## Project Structure

```
fiber_monitoring/
├── fiber_monitoring/      # Django project config
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py           # ASGI + Channels routing
│   └── wsgi.py
├── dashboard/             # Main app
│   ├── models.py          # Zone, FiberAlert, SystemStatus
│   ├── admin.py           # Django admin customization
│   ├── views.py           # Dashboard & API views
│   ├── consumers.py       # WebSocket consumers
│   ├── mqtt_client.py     # MQTT listener with auto-reconnect
│   ├── signals.py         # Auto-broadcast on alert save
│   ├── routing.py         # WebSocket URL routing
│   ├── urls.py            # URL patterns
│   └── templates/
│       └── dashboard/
│           └── index.html # Main dashboard UI
├── static/
│   ├── css/style.css      # Dark industrial theme
│   └── js/app.js          # Frontend WebSocket & UI logic
├── manage.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `django-insecure-change-me` | Django secret key |
| `DEBUG` | `True` | Debug mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Allowed hosts |
| `MQTT_BROKER` | `broker.hivemq.com` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC` | `eskom/alerts/zone1` | Default subscription topic |
| `REDIS_HOST` | `localhost` | Redis host for Channels |
| `REDIS_PORT` | `6379` | Redis port |

## Production Notes

- Change `SECRET_KEY` and set `DEBUG=False`
- Use PostgreSQL instead of SQLite
- Run behind Nginx with SSL
- Use `daphne` or `uvicorn` as ASGI server
- Set up proper logging and monitoring

## License

MIT
