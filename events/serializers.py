"""
Event Ingestion API Serializers
"""

from datetime import datetime
from typing import Any

from rest_framework import serializers

from projects.models import EventSource, Project


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
