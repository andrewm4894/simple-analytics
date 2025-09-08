"""
Unit tests for Dashboard API endpoints
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.fixtures.test_factories import (
    EventFactory,
    EventSourceFactory,
    ProjectFactory,
)


@pytest.mark.django_db
class TestDashboardAPIAuthentication:
    """Test authentication for Dashboard API endpoints"""

    def setup_method(self):
        self.client = APIClient()
        self.project = ProjectFactory()

    def test_query_endpoint_requires_private_key(self):
        """Test that query endpoint requires private API key"""
        url = reverse("events:query")

        # No authentication
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Wrong key type (public instead of private)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.project.public_api_key}"
        )
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Correct private key
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.project.private_api_key}"
        )
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_aggregation_endpoints_require_private_key(self):
        """Test that aggregation endpoints require private API key"""
        endpoints = [
            "events:daily_aggregations",
            "events:hourly_aggregations",
            "events:fivemin_aggregations",
            "events:daily_summaries",
        ]

        for endpoint_name in endpoints:
            url = reverse(endpoint_name)

            # Clear any existing credentials
            self.client.credentials()

            # No authentication
            response = self.client.get(url)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

            # Wrong key type (public key where private expected)
            self.client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {self.project.public_api_key}"
            )
            response = self.client.get(url)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

            # Correct private key
            self.client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {self.project.private_api_key}"
            )
            response = self.client.get(url)
            assert response.status_code == status.HTTP_200_OK

    def test_function_based_views_require_private_key(self):
        """Test that function-based views require private API key"""
        endpoints = [
            "events:realtime_metrics",
            "events:event_names",
            "events:event_sources",
        ]

        for endpoint_name in endpoints:
            url = reverse(endpoint_name)

            # Clear any existing credentials
            self.client.credentials()

            # No authentication
            response = self.client.get(url)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

            # Correct private key
            self.client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {self.project.private_api_key}"
            )
            response = self.client.get(url)
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestEventQueryView:
    """Test the EventQueryView endpoint"""

    def setup_method(self):
        self.client = APIClient()
        self.project = ProjectFactory()
        self.event_source = EventSourceFactory(project=self.project)

        # Authenticate with private key
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.project.private_api_key}"
        )

    def test_query_empty_project(self):
        """Test querying project with no events"""
        url = reverse("events:query")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_query_with_events(self):
        """Test querying project with events"""
        # Create test events
        events = []
        for i in range(5):
            event = EventFactory(
                project=self.project,
                event_source=self.event_source,
                event_name=f"test_event_{i}",
            )
            events.append(event)

        url = reverse("events:query")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 5
        assert len(data["results"]) == 5

        # Check serialized data
        first_result = data["results"][0]
        assert "id" in first_result
        assert "event_name" in first_result
        assert "project_name" in first_result
        assert "event_source_name" in first_result
        assert "timestamp" in first_result

    def test_project_isolation(self):
        """Test that users only see events from their project"""
        # Create events for our project
        EventFactory(project=self.project, event_name="our_event_1")
        EventFactory(project=self.project, event_name="our_event_2")

        # Create events for another project
        other_project = ProjectFactory()
        EventFactory(project=other_project, event_name="other_event_1")
        EventFactory(project=other_project, event_name="other_event_2")

        url = reverse("events:query")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2  # Only our events

        event_names = [event["event_name"] for event in data["results"]]
        assert "our_event_1" in event_names
        assert "our_event_2" in event_names
        assert "other_event_1" not in event_names
        assert "other_event_2" not in event_names

    def test_time_filtering(self):
        """Test filtering events by time range"""
        now = timezone.now()

        # Create events at different times
        EventFactory(
            project=self.project,
            timestamp=now - timedelta(hours=48),
            event_name="old_event",
        )
        EventFactory(
            project=self.project,
            timestamp=now - timedelta(hours=2),
            event_name="recent_event",
        )

        # Query last 24 hours (should only get recent_event)
        url = reverse("events:query")
        start_time = (now - timedelta(hours=24)).isoformat()
        response = self.client.get(url, {"start_date": start_time})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["event_name"] == "recent_event"

    def test_event_name_filtering(self):
        """Test filtering events by event name"""
        EventFactory(project=self.project, event_name="page_view")
        EventFactory(project=self.project, event_name="button_click")
        EventFactory(project=self.project, event_name="page_view")

        url = reverse("events:query")
        response = self.client.get(url, {"event_name": "page_view"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2
        for event in data["results"]:
            assert event["event_name"] == "page_view"

    def test_user_id_filtering(self):
        """Test filtering events by user ID"""
        EventFactory(project=self.project, user_id="user_123")
        EventFactory(project=self.project, user_id="user_456")
        EventFactory(project=self.project, user_id="user_123")

        url = reverse("events:query")
        response = self.client.get(url, {"user_id": "user_123"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2
        for event in data["results"]:
            assert event["user_id"] == "user_123"

    def test_pagination(self):
        """Test pagination functionality"""
        # Create 25 events
        for i in range(25):
            EventFactory(project=self.project, event_name=f"event_{i:02d}")

        url = reverse("events:query")

        # First page (default page size is 50)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 25
        assert len(data["results"]) == 25

        # Test custom page size
        response = self.client.get(url, {"page_size": 10})
        data = response.json()
        assert data["count"] == 25
        assert len(data["results"]) == 10
        assert data["next"] is not None

        # Second page
        response = self.client.get(url, {"page": 2, "page_size": 10})
        data = response.json()
        assert len(data["results"]) == 10
        assert data["previous"] is not None

    def test_ordering(self):
        """Test that events are ordered by timestamp descending"""
        now = timezone.now()

        # Create events with specific timestamps
        EventFactory(
            project=self.project,
            timestamp=now - timedelta(hours=3),
            event_name="oldest",
        )
        EventFactory(
            project=self.project,
            timestamp=now - timedelta(hours=1),
            event_name="newest",
        )
        EventFactory(
            project=self.project,
            timestamp=now - timedelta(hours=2),
            event_name="middle",
        )

        url = reverse("events:query")
        response = self.client.get(url)

        data = response.json()
        event_names = [event["event_name"] for event in data["results"]]

        # Should be ordered newest to oldest
        assert event_names == ["newest", "middle", "oldest"]


@pytest.mark.django_db
class TestRealTimeMetricsView:
    """Test the real-time metrics endpoint"""

    def setup_method(self):
        self.client = APIClient()
        self.project = ProjectFactory()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.project.private_api_key}"
        )

    def test_empty_project_metrics(self):
        """Test metrics for project with no events"""
        url = reverse("events:realtime_metrics")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["project_name"] == self.project.name
        assert data["current_hour_events"] == 0
        assert data["current_day_events"] == 0
        assert data["last_24h_events"] == 0
        assert data["active_users_today"] == 0
        assert data["active_sessions_now"] == 0
        assert data["top_events_today"] == []
        assert "last_updated" in data

    def test_metrics_with_events(self):
        """Test metrics calculation with events"""
        now = timezone.now()

        # Create events at different times
        # Current hour event
        EventFactory(
            project=self.project,
            timestamp=now - timedelta(minutes=30),
            user_id="user1",
            session_id="session1",
            event_name="page_view",
        )

        # Today but not current hour
        EventFactory(
            project=self.project,
            timestamp=now - timedelta(hours=3),
            user_id="user2",
            session_id="session2",
            event_name="button_click",
        )

        # Yesterday event (should count for 24h but not today)
        EventFactory(
            project=self.project,
            timestamp=now - timedelta(hours=25),
            user_id="user3",
            session_id="session3",
            event_name="page_view",
        )

        url = reverse("events:realtime_metrics")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["current_hour_events"] == 1
        assert data["current_day_events"] == 2  # Both today events
        assert data["last_24h_events"] == 2  # Both recent events
        assert data["active_users_today"] == 2  # user1 and user2
        assert len(data["top_events_today"]) > 0

    def test_project_isolation_in_metrics(self):
        """Test that metrics only include events from authenticated project"""
        other_project = ProjectFactory()

        # Events for our project
        EventFactory(project=self.project, event_name="our_event")

        # Events for other project
        EventFactory(project=other_project, event_name="other_event")

        url = reverse("events:realtime_metrics")
        response = self.client.get(url)

        data = response.json()
        assert data["current_day_events"] == 1  # Only our event


@pytest.mark.django_db
class TestEventNamesAndSourcesViews:
    """Test event names and sources listing endpoints"""

    def setup_method(self):
        self.client = APIClient()
        self.project = ProjectFactory()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.project.private_api_key}"
        )

    def test_event_names_empty(self):
        """Test event names endpoint with no events"""
        url = reverse("events:event_names")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["event_names"] == []
        assert data["count"] == 0

    def test_event_names_with_events(self):
        """Test event names endpoint with events"""
        # Create events with different names
        EventFactory(project=self.project, event_name="page_view")
        EventFactory(project=self.project, event_name="button_click")
        EventFactory(project=self.project, event_name="page_view")  # Duplicate

        url = reverse("events:event_names")
        response = self.client.get(url)

        data = response.json()
        assert len(data["event_names"]) == 2  # Unique names only
        assert "page_view" in data["event_names"]
        assert "button_click" in data["event_names"]
        assert data["count"] == 2

    def test_event_names_project_isolation(self):
        """Test that event names are isolated by project"""
        other_project = ProjectFactory()

        EventFactory(project=self.project, event_name="our_event")
        EventFactory(project=other_project, event_name="other_event")

        url = reverse("events:event_names")
        response = self.client.get(url)

        data = response.json()
        assert data["event_names"] == ["our_event"]
        assert "other_event" not in data["event_names"]

    def test_event_sources_empty(self):
        """Test event sources endpoint with no sources"""
        url = reverse("events:event_sources")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["event_sources"] == []
        assert data["count"] == 0

    def test_event_sources_with_sources(self):
        """Test event sources endpoint with sources"""
        EventSourceFactory(project=self.project, name="web_app")
        EventSourceFactory(project=self.project, name="mobile_app")

        # Inactive source (should not be included)
        EventSourceFactory(project=self.project, name="inactive", is_active=False)

        url = reverse("events:event_sources")
        response = self.client.get(url)

        data = response.json()
        assert len(data["event_sources"]) == 2  # Only active sources
        assert data["count"] == 2

        source_names = [source["name"] for source in data["event_sources"]]
        assert "web_app" in source_names
        assert "mobile_app" in source_names
        assert "inactive" not in source_names


@pytest.mark.django_db
class TestDashboardAPIErrorHandling:
    """Test error handling in Dashboard API"""

    def setup_method(self):
        self.client = APIClient()
        self.project = ProjectFactory()

    def test_invalid_private_key(self):
        """Test response with invalid private API key"""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer sa_priv_invalid_key")

        url = reverse("events:query")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_inactive_project(self):
        """Test response when project is inactive"""
        self.project.is_active = False
        self.project.save()

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.project.private_api_key}"
        )

        url = reverse("events:query")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_date_format(self):
        """Test response with invalid date format"""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.project.private_api_key}"
        )

        url = reverse("events:query")
        response = self.client.get(url, {"start_date": "invalid-date-format"})

        # Should return 400 Bad Request for invalid date format
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_start_date_after_end_date(self):
        """Test validation when start_date is after end_date"""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.project.private_api_key}"
        )

        now = timezone.now()
        start = now.isoformat()
        end = (now - timedelta(hours=1)).isoformat()

        url = reverse("events:query")
        response = self.client.get(url, {"start_date": start, "end_date": end})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "start_date must be before end_date" in str(data)
