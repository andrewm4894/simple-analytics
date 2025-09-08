"""
Event Ingestion API Serializers
"""

from datetime import datetime
from typing import Any

from rest_framework import serializers

from projects.models import EventSource, Project

from .models import Event
from .models_aggregation import (
    DailyEventAggregation,
    FiveMinuteEventAggregation,
    HourlyEventAggregation,
    ProjectDailySummary,
)


class EventIngestionSerializer(serializers.Serializer):
    """
    Serializer for event ingestion API.
    Handles flexible event data validation and enrichment.
    """

    # Optional client-provided event ID
    event_id = serializers.CharField(
        max_length=255, required=False, allow_blank=True, help_text="Client event ID"
    )

    # Core event data (required)
    event_name = serializers.CharField(
        max_length=255,
        help_text="Name of the event (e.g., 'page_view', 'button_click')",
    )

    # Event source (optional, can be created if not exists)
    event_source = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Source identifier (e.g., 'web_app', 'mobile_app')",
    )

    # User identification (optional)
    user_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="User identifier (will be auto-generated if not provided)",
    )

    # Session identification (optional, will be auto-generated)
    session_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Session identifier (will be auto-generated if not provided)",
    )

    # Flexible event properties (optional)
    properties = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Flexible event properties as JSON object",
    )

    # Timestamp (optional, defaults to current time)
    timestamp = serializers.DateTimeField(
        required=False,
        help_text="Event timestamp (ISO format, defaults to server time)",
    )

    def validate_event_name(self, value: str) -> str:
        """Validate event name format"""
        if not value or not value.strip():
            raise serializers.ValidationError("Event name cannot be empty")

        # Basic sanitization
        value = value.strip()

        # Ensure reasonable length and format
        if len(value) > 255:
            raise serializers.ValidationError(
                "Event name too long (max 255 characters)"
            )

        return value

    def validate_properties(self, value: dict[str, Any]) -> dict[str, Any]:
        """Validate event properties"""
        if value is None:
            return {}

        # Ensure it's a dictionary
        if not isinstance(value, dict):
            raise serializers.ValidationError("Properties must be a JSON object")

        # Basic size limit (prevent abuse)
        import json

        try:
            json_str = json.dumps(value)
            if len(json_str) > 64 * 1024:  # 64KB limit
                raise serializers.ValidationError(
                    "Properties too large (max 64KB when serialized)"
                )
        except (TypeError, ValueError) as e:
            raise serializers.ValidationError(
                f"Invalid properties format: {str(e)}"
            ) from e

        return value

    def validate_event_source(self, value: str) -> str:
        """Validate and sanitize event source"""
        if not value:
            return value

        value = value.strip()
        if len(value) > 255:
            raise serializers.ValidationError(
                "Event source name too long (max 255 characters)"
            )

        return value

    def to_internal_value(self, data):
        """Additional validation and preprocessing"""
        # Ensure we have the required fields
        validated_data = super().to_internal_value(data)

        # Set default timestamp if not provided
        if "timestamp" not in validated_data:
            validated_data["timestamp"] = datetime.now()

        return validated_data

    def create_or_get_event_source(
        self, project: Project, source_name: str
    ) -> EventSource:
        """
        Create or retrieve an event source for the project.
        """
        if not source_name:
            return None

        source, created = EventSource.objects.get_or_create(
            project=project,
            name=source_name,
            defaults={"description": f"Auto-created source: {source_name}"},
        )

        if created:
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Created new event source: {source_name} for {project.name}")

        return source

    def create_event_data(
        self, validated_data: dict[str, Any], project: Project
    ) -> dict[str, Any]:
        """
        Prepare event data for creation, handling source lookup and defaults.
        """
        # Handle event source
        event_source = None
        if validated_data.get("event_source"):
            event_source = self.create_or_get_event_source(
                project, validated_data["event_source"]
            )

        # Prepare event data
        event_data = {
            "project": project,
            "event_source": event_source,
            "event_name": validated_data["event_name"],
            "event_properties": validated_data.get("properties", {}),
            "user_id": validated_data.get("user_id"),
            "session_id": validated_data.get("session_id"),
            "timestamp": validated_data["timestamp"],
        }

        # Add optional event_id if provided
        if validated_data.get("event_id"):
            event_data["event_id"] = validated_data["event_id"]

        return event_data


# Dashboard API Serializers


class EventSerializer(serializers.ModelSerializer):
    """Serializer for Event model with filtering support"""

    project_name = serializers.CharField(source="project.name", read_only=True)
    event_source_name = serializers.CharField(
        source="event_source.name", read_only=True
    )

    class Meta:
        model = Event
        fields = [
            "id",
            "event_id",
            "project_name",
            "event_source_name",
            "event_name",
            "event_properties",
            "user_id",
            "session_id",
            "ip_address",
            "user_agent",
            "timestamp",
            "created_at",
        ]
        read_only_fields = fields


class DailyAggregationSerializer(serializers.ModelSerializer):
    """Serializer for daily event aggregations"""

    project_name = serializers.CharField(source="project.name", read_only=True)
    event_source_name = serializers.CharField(
        source="event_source.name", read_only=True
    )

    class Meta:
        model = DailyEventAggregation
        fields = [
            "project_name",
            "event_source_name",
            "event_name",
            "date",
            "event_count",
            "unique_users",
            "unique_sessions",
            "created_at",
            "updated_at",
        ]


class HourlyAggregationSerializer(serializers.ModelSerializer):
    """Serializer for hourly event aggregations"""

    project_name = serializers.CharField(source="project.name", read_only=True)
    event_source_name = serializers.CharField(
        source="event_source.name", read_only=True
    )

    class Meta:
        model = HourlyEventAggregation
        fields = [
            "project_name",
            "event_source_name",
            "event_name",
            "datetime_hour",
            "event_count",
            "unique_users",
            "unique_sessions",
            "created_at",
            "updated_at",
        ]


class FiveMinuteAggregationSerializer(serializers.ModelSerializer):
    """Serializer for 5-minute event aggregations"""

    project_name = serializers.CharField(source="project.name", read_only=True)
    event_source_name = serializers.CharField(
        source="event_source.name", read_only=True
    )

    class Meta:
        model = FiveMinuteEventAggregation
        fields = [
            "project_name",
            "event_source_name",
            "event_name",
            "datetime_5min",
            "event_count",
            "unique_users",
            "unique_sessions",
            "created_at",
            "updated_at",
        ]


class ProjectDailySummarySerializer(serializers.ModelSerializer):
    """Serializer for project daily summaries"""

    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ProjectDailySummary
        fields = [
            "project_name",
            "date",
            "total_events",
            "unique_users",
            "unique_sessions",
            "unique_event_names",
            "source_breakdown",
            "top_events",
            "created_at",
            "updated_at",
        ]


class RealTimeMetricsSerializer(serializers.Serializer):
    """Serializer for real-time metrics response"""

    project_name = serializers.CharField()
    current_hour_events = serializers.IntegerField()
    current_day_events = serializers.IntegerField()
    last_24h_events = serializers.IntegerField()
    active_users_today = serializers.IntegerField()
    active_sessions_now = serializers.IntegerField()
    top_events_today = serializers.ListField()
    event_sources = serializers.ListField()
    last_updated = serializers.DateTimeField()


class TimeRangeFilterSerializer(serializers.Serializer):
    """Serializer for time range filtering"""

    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    project_id = serializers.UUIDField(required=False)
    event_name = serializers.CharField(required=False, max_length=255)
    event_source_id = serializers.UUIDField(required=False)
    user_id = serializers.CharField(required=False, max_length=255)

    def validate(self, data):
        from datetime import timedelta

        from django.utils import timezone

        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError("start_date must be before end_date")

        # Default to last 24 hours if no dates provided
        if not start_date and not end_date:
            data["end_date"] = timezone.now()
            data["start_date"] = data["end_date"] - timedelta(hours=24)
        elif not start_date:
            data["start_date"] = end_date - timedelta(hours=24)
        elif not end_date:
            data["end_date"] = start_date + timedelta(hours=24)

        return data
