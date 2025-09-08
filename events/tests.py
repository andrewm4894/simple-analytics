"""
Tests for the Event Ingestion API
"""

from datetime import datetime
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import EventSource, Project


class EventIngestionTestCase(APITestCase):
    """Test cases for the event ingestion API endpoint"""

    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create test project
        self.project = Project.objects.create(
            name="Test Project",
            description="Test project for API testing",
            owner=self.user,
            sampling_enabled=False,  # Disable sampling for most tests
            sampling_rate=1.0,
            sampling_strategy="random",
            rate_limit_per_minute=100,
        )

        # Create test event source
        self.event_source = EventSource.objects.create(
            project=self.project, name="test_source", description="Test event source"
        )

        # API endpoint
        self.url = reverse("events:ingest")

        # Valid test event data
        self.valid_event_data = {
            "event_name": "test_event",
            "event_source": "test_source",
            "user_id": "test_user_123",
            "session_id": "test_session_456",
            "properties": {"page": "/test", "action": "click", "value": 42},
        }

    def test_authentication_valid_api_key(self):
        """Test authentication with valid API key"""
        response = self.client.post(
            self.url,
            data=self.valid_event_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn("status", response.data)
        self.assertEqual(response.data["status"], "accepted")

    def test_authentication_invalid_api_key(self):
        """Test authentication with invalid API key"""
        response = self.client.post(
            self.url,
            data=self.valid_event_data,
            headers={"authorization": "Bearer sa_invalid_key_12345"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authentication_missing_api_key(self):
        """Test authentication without API key"""
        response = self.client.post(self.url, data=self.valid_event_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authentication_wrong_bearer_format(self):
        """Test authentication with wrong bearer format"""
        response = self.client.post(
            self.url,
            data=self.valid_event_data,
            headers={"authorization": "Token invalid_format"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authentication_invalid_api_key_format(self):
        """Test authentication with API key not starting with sa_"""
        response = self.client.post(
            self.url,
            data=self.valid_event_data,
            headers={"authorization": "Bearer invalid_key_format"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_event_validation_valid_data(self):
        """Test event validation with valid data"""
        response = self.client.post(
            self.url,
            data=self.valid_event_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_event_validation_missing_event_name(self):
        """Test event validation with missing event_name"""
        invalid_data = self.valid_event_data.copy()
        del invalid_data["event_name"]

        response = self.client.post(
            self.url,
            data=invalid_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_event_validation_empty_event_name(self):
        """Test event validation with empty event_name"""
        invalid_data = self.valid_event_data.copy()
        invalid_data["event_name"] = ""

        response = self.client.post(
            self.url,
            data=invalid_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_event_validation_long_event_name(self):
        """Test event validation with event_name too long"""
        invalid_data = self.valid_event_data.copy()
        invalid_data["event_name"] = "x" * 256  # Over 255 character limit

        response = self.client.post(
            self.url,
            data=invalid_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_event_validation_large_properties(self):
        """Test event validation with properties too large"""
        invalid_data = self.valid_event_data.copy()
        # Create properties > 64KB
        large_value = "x" * (65 * 1024)  # 65KB string
        invalid_data["properties"] = {"large_field": large_value}

        response = self.client.post(
            self.url,
            data=invalid_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_event_validation_invalid_properties_type(self):
        """Test event validation with invalid properties type"""
        invalid_data = self.valid_event_data.copy()
        invalid_data["properties"] = "not a dictionary"

        response = self.client.post(
            self.url,
            data=invalid_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_event_auto_creation_of_source(self):
        """Test that event sources are auto-created if they don't exist"""
        event_data = self.valid_event_data.copy()
        event_data["event_source"] = "new_auto_source"

        response = self.client.post(
            self.url,
            data=event_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Verify the source was created
        self.assertTrue(
            EventSource.objects.filter(
                project=self.project, name="new_auto_source"
            ).exists()
        )

    def test_event_optional_fields(self):
        """Test event ingestion with minimal required fields only"""
        minimal_data = {"event_name": "minimal_event"}

        response = self.client.post(
            self.url,
            data=minimal_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    @patch("events.views.redis.from_url")
    def test_redis_failure_handling(self, mock_redis):
        """Test handling of Redis failures during event queuing"""
        # Mock Redis to raise an exception
        mock_redis_client = Mock()
        mock_redis_client.xadd.side_effect = Exception("Redis connection failed")
        mock_redis.return_value = mock_redis_client

        response = self.client.post(
            self.url,
            data=self.valid_event_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)


class SamplingTestCase(APITestCase):
    """Test cases for sampling logic"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="samplinguser",
            email="sampling@example.com",
            password="testpass123",
        )

        # Create project with sampling enabled
        self.project = Project.objects.create(
            name="Sampling Test Project",
            description="Project for testing sampling",
            owner=self.user,
            sampling_enabled=True,
            sampling_rate=0.5,  # 50% sampling
            sampling_strategy="random",
            rate_limit_per_minute=100,
        )

        self.url = reverse("events:ingest")
        self.event_data = {"event_name": "sampling_test", "user_id": "test_user_123"}

    def test_sampling_disabled_project(self):
        """Test that events are not sampled when sampling is disabled"""
        # Create project with sampling disabled
        no_sampling_project = Project.objects.create(
            name="No Sampling Project",
            owner=self.user,
            sampling_enabled=False,
            sampling_rate=0.1,  # Low rate, but disabled
        )

        response = self.client.post(
            self.url,
            data=self.event_data,
            headers={"authorization": f"Bearer {no_sampling_project.api_key}"}, 
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["sampled"], False)

    def test_sampling_zero_rate(self):
        """Test that all events are rejected with 0% sampling rate"""
        self.project.sampling_rate = 0.0
        self.project.save()

        response = self.client.post(
            self.url,
            data=self.event_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["sampled"], True)

    def test_sampling_full_rate(self):
        """Test that all events are accepted with 100% sampling rate"""
        self.project.sampling_rate = 1.0
        self.project.save()

        response = self.client.post(
            self.url,
            data=self.event_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["sampled"], False)

    def test_deterministic_sampling_consistency(self):
        """Test that deterministic sampling returns consistent results for same user"""
        self.project.sampling_strategy = "deterministic"
        self.project.save()

        # Send same event multiple times
        results = []
        for _ in range(5):
            response = self.client.post(
                self.url,
                data=self.event_data,
                headers={"authorization": f"Bearer {self.project.api_key}"}, 
                format="json",
            )
            results.append(response.data["sampled"])

        # All results should be the same (consistent sampling)
        self.assertTrue(all(r == results[0] for r in results))


class RateLimitingTestCase(APITestCase):
    """Test cases for rate limiting functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="ratelimituser",
            email="ratelimit@example.com",
            password="testpass123",
        )

        # Create project with low rate limit for testing
        self.project = Project.objects.create(
            name="Rate Limit Test Project",
            description="Project for testing rate limits",
            owner=self.user,
            sampling_enabled=False,
            rate_limit_per_minute=5,  # Very low for testing
        )

        self.url = reverse("events:ingest")
        self.event_data = {"event_name": "rate_limit_test"}

    @patch("events.throttling.redis.from_url")
    def test_rate_limiting_redis_failure(self, mock_redis):
        """Test that rate limiting fails open when Redis is unavailable"""
        # Mock Redis to raise an exception
        mock_redis_client = Mock()
        mock_redis_client.pipeline.side_effect = Exception("Redis connection failed")
        mock_redis.return_value = mock_redis_client

        # Request should still succeed (fail open)
        response = self.client.post(
            self.url,
            data=self.event_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_rate_limiting_within_limits(self):
        """Test that requests within rate limits are accepted"""
        response = self.client.post(
            self.url,
            data=self.event_data,
            headers={"authorization": f"Bearer {self.project.api_key}"}, 
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)


class EventDataProcessingTestCase(TestCase):
    """Test cases for event data processing and serialization"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="datauser", email="data@example.com", password="testpass123"
        )

        self.project = Project.objects.create(
            name="Data Processing Test Project", owner=self.user, sampling_enabled=False
        )

    def test_client_ip_extraction(self):
        """Test client IP extraction from various headers"""
        from django.test import RequestFactory

        from events.views import EventIngestionView

        view = EventIngestionView()
        factory = RequestFactory()

        # Test X-Forwarded-For header
        request = factory.post("/test")
        request.META["HTTP_X_FORWARDED_FOR"] = "192.168.1.100, 10.0.0.1"
        self.assertEqual(view.get_client_ip(request), "192.168.1.100")

        # Test X-Real-IP header
        request = factory.post("/test")
        request.META["HTTP_X_REAL_IP"] = "192.168.1.200"
        self.assertEqual(view.get_client_ip(request), "192.168.1.200")

        # Test REMOTE_ADDR fallback
        request = factory.post("/test")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        self.assertEqual(view.get_client_ip(request), "127.0.0.1")

        # Test unknown fallback (when no IP headers are present)
        request = factory.post("/test")
        # RequestFactory sets REMOTE_ADDR by default, so remove it for this test
        if "REMOTE_ADDR" in request.META:
            del request.META["REMOTE_ADDR"]
        self.assertEqual(view.get_client_ip(request), "unknown")

    def test_user_agent_extraction(self):
        """Test user agent extraction"""
        from django.test import RequestFactory

        from events.views import EventIngestionView

        view = EventIngestionView()
        factory = RequestFactory()

        request = factory.post("/test")
        request.META["HTTP_USER_AGENT"] = "Mozilla/5.0 Test Browser"
        self.assertEqual(view.get_user_agent(request), "Mozilla/5.0 Test Browser")

        # Test missing user agent
        request = factory.post("/test")
        self.assertEqual(view.get_user_agent(request), "")


class EventSerializerTestCase(TestCase):
    """Test cases for event serialization logic"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username="serializeruser",
            email="serializer@example.com",
            password="testpass123",
        )

        self.project = Project.objects.create(
            name="Serializer Test Project", owner=self.user
        )

    def test_timestamp_default(self):
        """Test that timestamp defaults to current time when not provided"""
        from events.serializers import EventIngestionSerializer

        serializer = EventIngestionSerializer(data={"event_name": "test_event"})
        self.assertTrue(serializer.is_valid())

        # Timestamp should be set automatically
        self.assertIn("timestamp", serializer.validated_data)
        self.assertIsInstance(serializer.validated_data["timestamp"], datetime)

    def test_event_source_creation(self):
        """Test automatic event source creation"""
        from events.serializers import EventIngestionSerializer

        serializer = EventIngestionSerializer()
        source = serializer.create_or_get_event_source(self.project, "new_source")

        self.assertIsNotNone(source)
        self.assertEqual(source.name, "new_source")
        self.assertEqual(source.project, self.project)

        # Test that existing source is returned
        source2 = serializer.create_or_get_event_source(self.project, "new_source")
        self.assertEqual(source.id, source2.id)

    def test_event_data_creation(self):
        """Test event data creation with all fields"""
        from events.serializers import EventIngestionSerializer

        serializer = EventIngestionSerializer()
        validated_data = {
            "event_name": "test_event",
            "event_source": "test_source",
            "user_id": "user_123",
            "session_id": "session_456",
            "properties": {"key": "value"},
            "timestamp": datetime.now(),
            "event_id": "event_789",
        }

        event_data = serializer.create_event_data(validated_data, self.project)

        self.assertEqual(event_data["project"], self.project)
        self.assertEqual(event_data["event_name"], "test_event")
        self.assertEqual(event_data["user_id"], "user_123")
        self.assertEqual(event_data["session_id"], "session_456")
        self.assertEqual(event_data["event_properties"], {"key": "value"})
        self.assertEqual(event_data["event_id"], "event_789")
