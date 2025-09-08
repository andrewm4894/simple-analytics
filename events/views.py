"""
Event Ingestion API Views
"""

import json
import logging
from typing import Any

from django.conf import settings
from django.http import HttpRequest

import redis
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project

from .authentication import ApiKeyAuthentication
from .serializers import EventIngestionSerializer
from .throttling import EventIngestionThrottle

logger = logging.getLogger(__name__)


class EventIngestionView(APIView):
    """
    High-performance event ingestion endpoint.

    POST /api/events/ingest/

    Accepts events with flexible schema, applies sampling, and queues for processing.
    """

    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [AllowAny]  # Authentication handled by API key
    throttle_classes = [EventIngestionThrottle]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.redis_client = redis.from_url(settings.REDIS_URL)

    def get_client_ip(self, request: HttpRequest) -> str:
        """Extract client IP address from request"""
        # Check for forwarded IP first (load balancer/proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check for real IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to remote addr
        return request.META.get("REMOTE_ADDR", "unknown")

    def get_user_agent(self, request: HttpRequest) -> str:
        """Extract user agent from request"""
        return request.headers.get("user-agent", "")

    def apply_sampling_decision(
        self, project: Project, event_data: dict[str, Any]
    ) -> bool:
        """
        Apply sampling logic to determine if event should be processed.
        Returns True if event should be processed, False if dropped.
        """
        event_source = event_data.get("event_source")
        user_id = event_data.get("user_id")

        # Use project's sampling logic
        should_process = project.should_sample_event(
            event_source=event_source, user_id=user_id
        )

        if not should_process:
            logger.debug(
                f"Event sampled out for project {project.name}: "
                f"rate={project.sampling_rate}, strategy={project.sampling_strategy}"
            )

        return should_process

    def queue_event_for_processing(self, event_data: dict[str, Any]) -> bool:
        """
        Queue event in Redis for background processing.
        Returns True if successful, False otherwise.
        """
        try:
            # Prepare serializable event data for Redis
            serializable_data = {
                "project_id": str(event_data["project"].id),
                "event_source_id": (
                    str(event_data["event_source"].id)
                    if event_data["event_source"]
                    else None
                ),
                "event_name": event_data["event_name"],
                "event_properties": event_data["event_properties"],
                "user_id": event_data["user_id"],
                "session_id": event_data["session_id"],
                "ip_address": event_data["ip_address"],
                "user_agent": event_data["user_agent"],
                "timestamp": event_data["timestamp"].isoformat(),
            }

            # Add optional event_id if present
            if "event_id" in event_data:
                serializable_data["event_id"] = event_data["event_id"]

            # Create Redis stream payload
            event_payload = {
                "event_data": json.dumps(serializable_data),
                "queued_at": serializable_data["timestamp"],
            }

            # Use Redis stream for reliable queuing
            stream_key = "events:queue"
            self.redis_client.xadd(stream_key, event_payload)

            logger.debug(f"Queued event for processing: {event_data['event_name']}")
            return True

        except Exception as e:
            logger.error(f"Failed to queue event: {str(e)}")
            return False

    def post(self, request):
        """
        Handle event ingestion POST request.
        """
        # Get authenticated project (from API key authentication)
        project = request.user
        if not isinstance(project, Project):
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Extract client metadata
        client_ip = self.get_client_ip(request)
        user_agent = self.get_user_agent(request)

        # Validate request data
        serializer = EventIngestionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                f"Invalid event data from project {project.name}: {serializer.errors}"
            )
            return Response(
                {"error": "Invalid event data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prepare event data
        validated_data = serializer.validated_data
        event_data = serializer.create_event_data(validated_data, project)

        # Add client metadata
        event_data["ip_address"] = client_ip
        event_data["user_agent"] = user_agent

        # Apply sampling decision
        if not self.apply_sampling_decision(project, event_data):
            # Event was sampled out - return success but don't process
            return Response(
                {"status": "accepted", "sampled": True}, status=status.HTTP_202_ACCEPTED
            )

        # Queue event for background processing
        if self.queue_event_for_processing(event_data):
            logger.info(
                f"Event ingested successfully: {event_data['event_name']} "
                f"from project {project.name}"
            )
            return Response(
                {"status": "accepted", "sampled": False},
                status=status.HTTP_202_ACCEPTED,
            )
        else:
            logger.error(
                f"Failed to queue event: {event_data['event_name']} "
                f"from project {project.name}"
            )
            return Response(
                {"error": "Failed to process event"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
