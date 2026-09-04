const APP = {
    ws: null,
    reconnectInterval: 3000,
    soundEnabled: true,
    currentAlert: null,
    audioCtx: null,
    devices: new Set(),
    deviceSources: { mqtt: 0, usb: 0 },

    init() {
        this.initSparklines();
        this.connectWebSocket();
        this.startClock();
        this.setupEventListeners();
        this.initAudio();
        this.updateStats();
    },

    initSparklines() {
        if (typeof initSparklines === 'function') {
            initSparklines();
            console.log('Sparklines initialized');
        } else {
            console.warn('Sparklines library not loaded');
        }
    },

    initAudio() {
        try {
            this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        } catch(e) { console.warn('Audio not supported'); }
    },

    playAlertSound() {
        if (!this.soundEnabled || !this.audioCtx) return;
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.connect(gain);
        gain.connect(this.audioCtx.destination);
        osc.type = 'square';
        osc.frequency.setValueAtTime(880, this.audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(440, this.audioCtx.currentTime + 0.3);
        gain.gain.setValueAtTime(0.1, this.audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.3);
        osc.start();
        osc.stop(this.audioCtx.currentTime + 0.3);
    },

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/alerts/`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
            this.pingLoop();
        };

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            this.handleMessage(msg);
        };

        this.ws.onclose = () => {
            console.warn('WebSocket closed, reconnecting...');
            this.updateConnectionStatus(false);
            setTimeout(() => this.connectWebSocket(), this.reconnectInterval);
        };

        this.ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };
    },

    pingLoop() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'ping', timestamp: Date.now() }));
        }
        setTimeout(() => this.pingLoop(), 30000);
    },

    handleMessage(msg) {
        if (msg.type === 'alert') {
            this.handleAlert(msg.data);
        } else if (msg.type === 'status') {
            this.updateSystemStatus(msg.data);
        } else if (msg.type === 'connection_established') {
            console.log(msg.message);
        }
    },

    handleAlert(data) {
        this.currentAlert = data;
        this.recordDevice(data);
        this.playAlertSound();
        this.showToast(data);
        this.updateMonitorDisplay(data);
        this.updateLocation(data);
        this.updateStats();
        this.addEventToLog(data);
    },

    updateLocation(data) {
        const latitude = Number(data.latitude);
        const longitude = Number(data.longitude);
        const readout = document.getElementById('location-readout');
        const coords = document.getElementById('location-coords');
        const label = document.getElementById('location-label');
        const pin = document.getElementById('map-pin');

        if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
            const mapPin = pin || document.getElementById('map-pin');
            if (mapPin) {
                mapPin.style.display = 'block';
                mapPin.style.left = `${50 + (longitude / 180) * 35}%`;
                mapPin.style.top = `${50 - (latitude / 90) * 35}%`;
            }
            if (readout) readout.textContent = data.location_label || 'Cut location';
            if (coords) coords.textContent = `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
            if (label) label.textContent = 'GPS fix';
        } else {
            if (readout) readout.textContent = 'No coordinates';
            if (coords) coords.textContent = '--';
            if (label) label.textContent = 'GPS offline';
            if (pin) pin.style.display = 'none';
        }
    },

    recordDevice(data) {
        const deviceId = data.device_id || 'unknown-device';
        this.devices.add(deviceId);
        const source = (data.source || 'mqtt').toLowerCase();
        if (source.includes('usb') || source.includes('serial')) {
            this.deviceSources.usb += 1;
        } else {
            this.deviceSources.mqtt += 1;
        }
        const risk = Number(data.risk_score || (data.status === 'ALARM' ? 85 : data.status === 'WARNING' ? 55 : 5));
        const riskIndex = document.getElementById('risk-index');
        const riskLabel = document.getElementById('risk-label');
        if (riskIndex) riskIndex.textContent = `${risk}/100`;
        if (riskLabel) {
            riskLabel.textContent = risk >= 80 ? 'Immediate response' : risk >= 50 ? 'Investigate' : 'Low exposure';
            riskLabel.className = `kpi-trend ${risk >= 80 ? 'critical' : risk >= 50 ? 'warning' : 'healthy'}`;
        }
        const mqttCount = document.getElementById('mqtt-device-count');
        const usbCount = document.getElementById('usb-device-count');
        const lastDevice = document.getElementById('last-device');
        if (mqttCount) mqttCount.textContent = this.deviceSources.mqtt;
        if (usbCount) usbCount.textContent = this.deviceSources.usb;
        if (lastDevice) lastDevice.textContent = deviceId;
    },

    updateMonitorDisplay(data) {
        const display = document.getElementById('alert-display');
        const monitorPanel = display.closest('.monitor-panel');
        const line = document.getElementById('fiber-line');
        const marker = document.getElementById('breach-marker');
        const readout = document.getElementById('distance-readout');

        // Update status icon styling
        const statusIcon = display.querySelector('.status-icon');
        if (statusIcon) {
            if (data.status === 'ALARM') {
                statusIcon.style.borderColor = 'var(--status-critical)';
                statusIcon.style.color = 'var(--status-critical)';
                statusIcon.style.boxShadow = '0 0 20px rgba(255, 0, 85, 0.3)';
            } else {
                statusIcon.style.borderColor = 'var(--status-warning)';
                statusIcon.style.color = 'var(--status-warning)';
                statusIcon.style.boxShadow = '0 0 20px rgba(255, 170, 0, 0.3)';
            }
        }

        // Update live indicator
        const liveIndicator = monitorPanel.querySelector('.live-indicator');
        if (liveIndicator) {
            if (data.status === 'ALARM') {
                liveIndicator.classList.add('critical');
                liveIndicator.textContent = 'CRITICAL';
            } else {
                liveIndicator.classList.remove('critical');
                liveIndicator.textContent = 'WARNING';
            }
        }

        // Update route visualization
        line.classList.add('alarm');
        const zoneSelect = document.getElementById('zone-select');
        const maxDist = parseInt(zoneSelect.selectedOptions[0]?.dataset.max || 2500);
        const pct = Math.min(Math.max((data.distance_meters || 0) / maxDist * 100, 0), 100);
        marker.style.left = pct + '%';
        marker.classList.remove('hidden');
        readout.textContent = (data.distance_meters || 0) + ' m';
    },

    addEventToLog(data) {
        const eventsList = document.getElementById('alerts-tbody');
        const placeholder = eventsList.querySelector('.event-placeholder');
        if (placeholder) placeholder.remove();

        const eventItem = document.createElement('div');
        const statusClass = data.status === 'ALARM' ? 'critical' : 'warning';
        eventItem.className = `event-item ${statusClass}`;
        eventItem.dataset.status = data.status;
        eventItem.innerHTML = `
            <div class="event-time">${new Date(data.timestamp).toLocaleTimeString()}</div>
            <div class="event-message">${data.danger || 'Threat detected'} @ ${data.distance_meters}m</div>
        `;
        eventsList.insertBefore(eventItem, eventsList.firstChild);

        // Keep only last 20 events
        while (eventsList.children.length > 20) {
            eventsList.removeChild(eventsList.lastChild);
        }
    },

    showToast(data) {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        const isAlarm = (data.status || '').toUpperCase() === 'ALARM';
        toast.className = `toast ${isAlarm ? 'critical' : 'warning'}`;
        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px; width: 100%;">
                <div style="font-size: 1.2rem;">
                    ${isAlarm ? '!' : '•'}
                </div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 0.85rem;">${data.status} - ${data.zone || 'Unknown'}</div>
                    <div style="font-size: 0.75rem; opacity: 0.8;">${data.danger || 'Threat detected'} at ${data.distance_meters}m</div>
                </div>
            </div>
        `;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 5000);
    },

    updateConnectionStatus(connected) {
        const dot = document.getElementById('connection-dot');
        const text = document.getElementById('connection-text');
        const wsStatus = document.getElementById('ws-status');
        if (connected) {
            dot.classList.remove('offline');
            dot.classList.add('online');
            text.textContent = 'CONNECTED';
            if (wsStatus) wsStatus.textContent = 'Connected';
        } else {
            dot.classList.remove('online');
            dot.classList.add('offline');
            text.textContent = 'CONNECTING';
            if (wsStatus) wsStatus.textContent = 'Disconnected';
        }
    },

    updateStats() {
        fetch('/api/stats/')
            .then(r => r.json())
            .then(data => {
                document.getElementById('total-alerts').textContent = data.total_alerts;
                document.getElementById('active-alarms').textContent = data.active_alarms;
                document.getElementById('active-warnings').textContent = data.active_warnings;
                document.getElementById('unacknowledged').textContent = data.unacknowledged;
            })
            .catch(e => console.error('Stats fetch failed:', e));
    },

    startClock() {
        const update = () => {
            const now = new Date();
            document.getElementById('clock').textContent = now.toLocaleTimeString();
        };
        update();
        setInterval(update, 1000);
    },

    setupEventListeners() {
        // Sound toggle
        const soundToggle = document.getElementById('sound-toggle');
        if (soundToggle) {
            soundToggle.addEventListener('click', () => {
                this.soundEnabled = !this.soundEnabled;
                soundToggle.style.opacity = this.soundEnabled ? '1' : '0.5';
                soundToggle.style.borderColor = this.soundEnabled ? 'var(--status-pending)' : 'rgba(0,204,255,0.2)';
            });
        }

        // Zone selector
        const zoneSelect = document.getElementById('zone-select');
        if (zoneSelect) {
            zoneSelect.addEventListener('change', () => {
                const max = zoneSelect.selectedOptions[0].dataset.max || 2500;
                const label = document.getElementById('max-distance-label');
                if (label) label.textContent = max + 'm';
            });
        }

        // Filter tabs
        document.querySelectorAll('.filter-tab').forEach(tab => {
            tab.addEventListener('click', function() {
                document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
                this.classList.add('active');
                const filter = this.dataset.filter;
                const eventsList = document.getElementById('alerts-tbody');
                if (eventsList) {
                    Array.from(eventsList.children).forEach(item => {
                        if (item.classList.contains('event-placeholder')) return;
                        if (filter === 'all' || item.dataset.status === filter) {
                            item.style.display = '';
                        } else {
                            item.style.display = 'none';
                        }
                    });
                }
            });
        });
    }
};

function acknowledgeAlert(alertId, btn) {
    fetch(`/api/alerts/${alertId}/acknowledge/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            btn.outerHTML = '<span class="ack-label">&#10003; Ack</span>';
            APP.updateStats();
        }
    });
}

function acknowledgeCurrent() {
    if (APP.currentAlert) {
        acknowledgeAlert(APP.currentAlert.id, document.getElementById('btn-ack'));
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', () => APP.init());
