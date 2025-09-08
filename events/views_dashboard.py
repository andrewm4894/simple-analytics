"""
Dashboard API Views for analytics data querying
"""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from rest_framework import generics
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from projects.models import Project

from .authentication import PrivateApiKeyAuthentication
from .models import Event
from .models_aggregation import (
    DailyEventAggregation,
    FiveMinuteEventAggregation,
    HourlyEventAggregation,
    ProjectDailySummary,
)
from .serializers import (
    DailyAggregationSerializer,
    EventSerializer,
    FiveMinuteAggregationSerializer,
    HourlyAggregationSerializer,
    ProjectDailySummarySerializer,
    RealTimeMetricsSerializer,
    TimeRangeFilterSerializer,
)


class IsProjectAuthenticated(BasePermission):
    """
    Custom permission that allows access if request.user is a Project object
    (which means authentication succeeded via our API key authentication)
    """

    def has_permission(self, request, view):
        return request.user and isinstance(request.user, Project)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for dashboard API"""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 1000


class EventQueryView(generics.ListAPIView):
    """
    Query raw events with filtering, pagination, and project isolation

    GET /api/events/query/

    Query Parameters:
    - start_date: ISO datetime (default: 24h ago)
    - end_date: ISO datetime (default: now)
    - event_name: Filter by event name
    - event_source_id: Filter by event source
    - user_id: Filter by user
    - page: Page number
    - page_size: Results per page (max 1000)
    """

    serializer_class = EventSerializer
    authentication_classes = [PrivateApiKeyAuthentication]
    permission_classes = [IsProjectAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # Get project from API key authentication
        project = self.request.user  # Project is set as user in APIKeyAuthentication

        # Start with project-isolated queryset
        queryset = (
            Event.objects.filter(project=project)
            .select_related("project", "event_source")
            .order_by("-timestamp")
        )

        # Apply filters from query parameters
        filter_serializer = TimeRangeFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data

            # Time range filtering
            if filters.get("start_date"):
                queryset = queryset.filter(timestamp__gte=filters["start_date"])
            if filters.get("end_date"):
                queryset = queryset.filter(timestamp__lte=filters["end_date"])

            # Additional filters
            if filters.get("event_name"):
                queryset = queryset.filter(event_name=filters["event_name"])
            if filters.get("event_source_id"):
                queryset = queryset.filter(event_source_id=filters["event_source_id"])
            if filters.get("user_id"):
                queryset = queryset.filter(user_id=filters["user_id"])
        else:
            # Raise validation error if filter parameters are invalid
            from rest_framework.exceptions import ValidationError

            raise ValidationError(filter_serializer.errors)

        return queryset


class DailyAggregationView(generics.ListAPIView):
    """
    Daily aggregation data with filtering and project isolation

    GET /api/events/aggregations/daily/
    """

    serializer_class = DailyAggregationSerializer
    authentication_classes = [PrivateApiKeyAuthentication]
    permission_classes = [IsProjectAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        project = self.request.user

        queryset = (
            DailyEventAggregation.objects.filter(project=project)
            .select_related("project", "event_source")
            .order_by("-date", "-event_count")
        )

        # Apply time filters
        filter_serializer = TimeRangeFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data

            if filters.get("start_date"):
                queryset = queryset.filter(date__gte=filters["start_date"].date())
            if filters.get("end_date"):
                queryset = queryset.filter(date__lte=filters["end_date"].date())
            if filters.get("event_name"):
                queryset = queryset.filter(event_name=filters["event_name"])

        return queryset


class HourlyAggregationView(generics.ListAPIView):
    """
    Hourly aggregation data with filtering and project isolation

    GET /api/events/aggregations/hourly/
    """

    serializer_class = HourlyAggregationSerializer
    authentication_classes = [PrivateApiKeyAuthentication]
    permission_classes = [IsProjectAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        project = self.request.user

        queryset = (
            HourlyEventAggregation.objects.filter(project=project)
            .select_related("project", "event_source")
            .order_by("-datetime_hour", "-event_count")
        )

        # Apply time filters
        filter_serializer = TimeRangeFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data

            if filters.get("start_date"):
                queryset = queryset.filter(datetime_hour__gte=filters["start_date"])
            if filters.get("end_date"):
                queryset = queryset.filter(datetime_hour__lte=filters["end_date"])
            if filters.get("event_name"):
                queryset = queryset.filter(event_name=filters["event_name"])

        return queryset


class FiveMinuteAggregationView(generics.ListAPIView):
    """
    5-minute aggregation data for near real-time analytics

    GET /api/events/aggregations/5min/
    """

    serializer_class = FiveMinuteAggregationSerializer
    authentication_classes = [PrivateApiKeyAuthentication]
    permission_classes = [IsProjectAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        project = self.request.user

        # Default to last 24 hours for 5-minute data (high volume)
        default_start = timezone.now() - timedelta(hours=24)

        queryset = (
            FiveMinuteEventAggregation.objects.filter(
                project=project, datetime_5min__gte=default_start
            )
            .select_related("project", "event_source")
            .order_by("-datetime_5min", "-event_count")
        )

        # Apply time filters
        filter_serializer = TimeRangeFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data

            if filters.get("start_date"):
                queryset = queryset.filter(datetime_5min__gte=filters["start_date"])
            if filters.get("end_date"):
                queryset = queryset.filter(datetime_5min__lte=filters["end_date"])
            if filters.get("event_name"):
                queryset = queryset.filter(event_name=filters["event_name"])

        return queryset


class ProjectSummaryView(generics.ListAPIView):
    """
    Project daily summaries with top events and source breakdown

    GET /api/events/summaries/daily/
    """

    serializer_class = ProjectDailySummarySerializer
    authentication_classes = [PrivateApiKeyAuthentication]
    permission_classes = [IsProjectAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        project = self.request.user

        queryset = ProjectDailySummary.objects.filter(project=project).order_by("-date")

        # Apply time filters
        filter_serializer = TimeRangeFilterSerializer(data=self.request.query_params)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data

            if filters.get("start_date"):
                queryset = queryset.filter(date__gte=filters["start_date"].date())
            if filters.get("end_date"):
                queryset = queryset.filter(date__lte=filters["end_date"].date())

        return queryset


@api_view(["GET"])
@authentication_classes([PrivateApiKeyAuthentication])
@permission_classes([IsProjectAuthenticated])
def real_time_metrics(request):
    """
    Real-time metrics endpoint for dashboard widgets

    GET /api/events/metrics/realtime/

    Returns current stats for the authenticated project:
    - Current hour events
    - Today's total events
    - Last 24h events
    - Active users today
    - Current active sessions
    - Top events today
    - Event sources list
    """
    project = request.user
    now = timezone.now()

    # Current time windows
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_24h = now - timedelta(hours=24)

    # Get project events for different time windows
    current_hour_events = Event.objects.filter(
        project=project, timestamp__gte=current_hour
    ).count()

    today_events = Event.objects.filter(project=project, timestamp__gte=today).count()

    last_24h_events = Event.objects.filter(
        project=project, timestamp__gte=last_24h
    ).count()

    # Active users and sessions today
    today_events_qs = Event.objects.filter(project=project, timestamp__gte=today)

    active_users_today = today_events_qs.values("user_id").distinct().count()

    # Current active sessions (last 60 minutes)
    session_window = now - timedelta(minutes=60)
    active_sessions_now = (
        Event.objects.filter(project=project, timestamp__gte=session_window)
        .values("session_id")
        .distinct()
        .count()
    )

    # Top events today
    top_events_today = list(
        today_events_qs.values("event_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
        .values_list("event_name", "count")
    )

    # Event sources
    event_sources = list(
        project.event_sources.filter(is_active=True).values("id", "name", "description")
    )

    metrics_data = {
        "project_name": project.name,
        "current_hour_events": current_hour_events,
        "current_day_events": today_events,
        "last_24h_events": last_24h_events,
        "active_users_today": active_users_today,
        "active_sessions_now": active_sessions_now,
        "top_events_today": top_events_today,
        "event_sources": event_sources,
        "last_updated": now,
    }

    serializer = RealTimeMetricsSerializer(data=metrics_data)
    serializer.is_valid(raise_exception=True)

    return Response(serializer.validated_data)


@api_view(["GET"])
@authentication_classes([PrivateApiKeyAuthentication])
@permission_classes([IsProjectAuthenticated])
def event_names_list(request):
    """
    List all unique event names for the project

    GET /api/events/names/
    """
    project = request.user

    # Get unique event names from recent events (last 30 days)
    recent_cutoff = timezone.now() - timedelta(days=30)

    event_names = list(
        Event.objects.filter(project=project, timestamp__gte=recent_cutoff)
        .values_list("event_name", flat=True)
        .distinct()
        .order_by("event_name")
    )

    return Response({"event_names": event_names, "count": len(event_names)})


@api_view(["GET"])
@authentication_classes([PrivateApiKeyAuthentication])
@permission_classes([IsProjectAuthenticated])
def event_sources_list(request):
    """
    List all event sources for the project

    GET /api/events/sources/
    """
    project = request.user

    sources = list(
        project.event_sources.filter(is_active=True)
        .values("id", "name", "description", "created_at")
        .order_by("name")
    )

    return Response({"event_sources": sources, "count": len(sources)})
