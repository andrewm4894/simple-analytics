"""
Test configuration and fixtures for pytest
"""

from django.test import override_settings

import pytest
from rest_framework.test import APIClient

from tests.fixtures.test_factories import (
    EventFactory,
    EventSourceFactory,
    ProjectFactory,
    UserFactory,
)


@pytest.fixture
def api_client():
    """API client for testing REST endpoints"""
    return APIClient()


@pytest.fixture
def user():
    """Create a test user"""
    return UserFactory()


@pytest.fixture
def project(user):
    """Create a test project with owner"""
    return ProjectFactory(owner=user)


@pytest.fixture
def event_source(project):
    """Create a test event source"""
    return EventSourceFactory(project=project)


@pytest.fixture
def sample_event(project, event_source):
    """Create a sample event"""
    return EventFactory(project=project, event_source=event_source)


@pytest.fixture
def authenticated_client(api_client, project):
    """API client authenticated with public API key"""
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {project.public_api_key}")
    return api_client


@pytest.fixture
def dashboard_client(api_client, project):
    """API client authenticated with private API key for dashboard"""
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {project.private_api_key}")
    return api_client


@pytest.fixture
def multiple_projects():
    """Create multiple projects for isolation testing"""
    user1 = UserFactory()
    user2 = UserFactory()
    project1 = ProjectFactory(owner=user1, name="Project Alpha")
    project2 = ProjectFactory(owner=user2, name="Project Beta")
    return [project1, project2]


@pytest.fixture
def events_with_different_timestamps(project, event_source):
    """Create events with various timestamps for time-based testing"""
    from datetime import timedelta

    from django.utils import timezone

    now = timezone.now()
    events = []

    # Create events from different time periods
    for i in range(10):
        timestamp = now - timedelta(hours=i)
        event = EventFactory(
            project=project,
            event_source=event_source,
            timestamp=timestamp,
            event_name=f"test_event_{i}",
        )
        events.append(event)

    return events


@pytest.fixture
def redis_client():
    """Redis client for testing background processing"""
    from django.conf import settings

    import redis

    client = redis.from_url(settings.REDIS_URL)
    # Clean up test keys before and after
    test_keys = client.keys("test:*")
    if test_keys:
        client.delete(*test_keys)

    yield client

    # Cleanup after test
    test_keys = client.keys("test:*")
    if test_keys:
        client.delete(*test_keys)


# Test database settings
@pytest.fixture
def transactional_db():
    """Enable transactional database access for tests that need it"""
    pass


# Override settings for testing
@pytest.fixture
def test_settings():
    """Override settings for consistent testing"""
    with override_settings(
        # Use in-memory cache for testing
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        },
        # Disable rate limiting in tests by default
        ENABLE_RATE_LIMITING=False,
        # Use test Redis database
        RQ_QUEUES={
            "default": {
                "HOST": "localhost",
                "PORT": 6379,
                "DB": 1,  # Use DB 1 for tests
                "DEFAULT_TIMEOUT": 360,
            }
        },
    ):
        yield


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis for unit tests that don't need actual Redis"""
    mock_client = mocker.MagicMock()
    mocker.patch("redis.from_url", return_value=mock_client)
    return mock_client
