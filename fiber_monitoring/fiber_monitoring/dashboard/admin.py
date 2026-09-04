
from django.contrib import admin
from .models import FiberAlert, SystemStatus, Zone

@admin.register(FiberAlert)
class FiberAlertAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'status', 'danger', 'distance_meters', 'zone', 'acknowledged', 'acknowledged_by')
    list_filter = ('status', 'zone', 'acknowledged', 'timestamp')
    search_fields = ('danger', 'raw_payload', 'acknowledged_by__username')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp', 'raw_payload', 'received_at')
    list_editable = ('acknowledged',)
    actions = ['mark_acknowledged', 'mark_unacknowledged']

    def mark_acknowledged(self, request, queryset):
        queryset.update(acknowledged=True, acknowledged_by=request.user)
    mark_acknowledged.short_description = "Mark selected alerts as acknowledged"

    def mark_unacknowledged(self, request, queryset):
        queryset.update(acknowledged=False, acknowledged_by=None)
    mark_unacknowledged.short_description = "Mark selected alerts as unacknowledged"

@admin.register(SystemStatus)
class SystemStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_online', 'last_seen', 'broker_host', 'broker_port')
    list_editable = ('is_online',)

@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'topic', 'max_distance_meters', 'is_active', 'created_at')
    list_editable = ('is_active',)
    search_fields = ('name', 'topic')
