"""
Unit tests for Project and EventSource models
"""

from django.db import IntegrityError

import pytest

from projects.models import EventSource
from tests.fixtures.test_factories import (
    DeterministicSamplingProjectFactory,
    EventSourceFactory,
    ProjectFactory,
    SamplingProjectFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestProjectModel:
    """Test cases for the Project model"""

    def test_project_creation(self):
        """Test basic project creation"""
        user = UserFactory()
        project = ProjectFactory(owner=user, name="Test Analytics Project")

        assert project.id is not None
        assert project.name == "Test Analytics Project"
        assert project.owner == user
        assert project.is_active is True
        assert str(project) == f"Test Analytics Project ({project.id})"

    def test_api_keys_auto_generation(self):
        """Test that API keys are automatically generated"""
        project = ProjectFactory()

        # Both API keys should be generated
        assert project.public_api_key is not None
        assert project.private_api_key is not None

        # Keys should have correct prefixes
        assert project.public_api_key.startswith("sa_")
        assert project.private_api_key.startswith("sa_priv_")

        # Keys should be different
        assert project.public_api_key != project.private_api_key

        # Keys should be of reasonable length
        assert len(project.public_api_key) > 40
        assert len(project.private_api_key) > 40

    def test_api_keys_uniqueness(self):
        """Test that API keys are unique across projects"""
        project1 = ProjectFactory()
        project2 = ProjectFactory()

        # All keys should be unique
        assert project1.public_api_key != project2.public_api_key
        assert project1.private_api_key != project2.private_api_key
        assert project1.public_api_key != project1.private_api_key
        assert project2.public_api_key != project2.private_api_key

    def test_regenerate_public_api_key(self):
        """Test public API key regeneration"""
        project = ProjectFactory()
        original_public_key = project.public_api_key
        original_private_key = project.private_api_key

        new_key = project.regenerate_public_api_key()

        # Refresh from database
        project.refresh_from_db()

        assert new_key == project.public_api_key
        assert project.public_api_key != original_public_key
        assert project.private_api_key == original_private_key  # Unchanged
        assert new_key.startswith("sa_")

    def test_regenerate_private_api_key(self):
        """Test private API key regeneration"""
        project = ProjectFactory()
        original_public_key = project.public_api_key
        original_private_key = project.private_api_key

        new_key = project.regenerate_private_api_key()

        # Refresh from database
        project.refresh_from_db()

        assert new_key == project.private_api_key
        assert project.private_api_key != original_private_key
        assert project.public_api_key == original_public_key  # Unchanged
        assert new_key.startswith("sa_priv_")

    def test_regenerate_all_api_keys(self):
        """Test regeneration of both API keys"""
        project = ProjectFactory()
        original_public_key = project.public_api_key
        original_private_key = project.private_api_key

        result = project.regenerate_all_api_keys()

        # Refresh from database
        project.refresh_from_db()

        assert "public_api_key" in result
        assert "private_api_key" in result
        assert result["public_api_key"] == project.public_api_key
        assert result["private_api_key"] == project.private_api_key

        # Both keys should have changed
        assert project.public_api_key != original_public_key
        assert project.private_api_key != original_private_key

        # Keys should have correct prefixes
        assert project.public_api_key.startswith("sa_")
        assert project.private_api_key.startswith("sa_priv_")

    def test_sampling_configuration(self):
        """Test sampling configuration options"""
        # Test random sampling project
        project = SamplingProjectFactory()
        assert project.sampling_enabled is True
        assert project.sampling_rate == 0.5
        assert project.sampling_strategy == "random"

        # Test deterministic sampling project
        det_project = DeterministicSamplingProjectFactory()
        assert det_project.sampling_enabled is True
        assert det_project.sampling_rate == 0.3
        assert det_project.sampling_strategy == "deterministic"

    def test_should_sample_event_disabled(self):
        """Test event sampling when disabled"""
        project = ProjectFactory(sampling_enabled=False)

        # Should always return True when sampling disabled
        assert project.should_sample_event() is True
        assert project.should_sample_event(user_id="test_user") is True

    def test_should_sample_event_full_rate(self):
        """Test event sampling at 100% rate"""
        project = ProjectFactory(sampling_enabled=True, sampling_rate=1.0)

        # Should always return True at 100% rate
        assert project.should_sample_event() is True
        assert project.should_sample_event(user_id="test_user") is True

    def test_should_sample_event_zero_rate(self):
        """Test event sampling at 0% rate"""
        project = ProjectFactory(sampling_enabled=True, sampling_rate=0.0)

        # Should always return False at 0% rate
        assert project.should_sample_event() is False
        assert project.should_sample_event(user_id="test_user") is False

    def test_should_sample_event_deterministic(self):
        """Test deterministic sampling consistency"""
        project = ProjectFactory(
            sampling_enabled=True, sampling_rate=0.5, sampling_strategy="deterministic"
        )

        user_id = "consistent_user_123"

        # Should return the same result for the same user
        result1 = project.should_sample_event(user_id=user_id)
        result2 = project.should_sample_event(user_id=user_id)
        result3 = project.should_sample_event(user_id=user_id)

        assert result1 == result2 == result3

        # Different users should potentially have different results
        different_results = []
        for i in range(20):
            result = project.should_sample_event(user_id=f"user_{i}")
            different_results.append(result)

        # At 50% rate, we should see both True and False (with high probability)
        assert True in different_results
        assert False in different_results

    def test_should_sample_event_time_window(self):
        """Test time window sampling"""
        project = ProjectFactory(
            sampling_enabled=True, sampling_rate=0.5, sampling_strategy="time_window"
        )

        # Time window sampling should return consistent results
        result = project.should_sample_event()
        assert isinstance(result, bool)

    def test_should_sample_event_with_event_source_override(self):
        """Test sampling with event source override"""
        project = ProjectFactory(
            sampling_enabled=False,  # Project sampling disabled
            sampling_rate=1.0,
        )

        # Create event source with sampling enabled
        event_source = EventSourceFactory(
            project=project,
            sampling_enabled=True,
            sampling_rate=0.8,
            sampling_strategy="random",
        )

        # Should use event source settings, not project settings
        # We can't test the exact boolean result due to randomness,
        # but we can test that it doesn't fail
        result = project.should_sample_event(event_source=event_source)
        assert isinstance(result, bool)

    def test_default_settings(self):
        """Test default project settings"""
        project = ProjectFactory()

        assert project.rate_limit_per_minute == 1000
        assert project.retention_days == 90
        assert project.aggregation_retention_days == 365
        assert project.cors_allowed_origins == ["*"]
        assert project.sampling_enabled is False
        assert project.sampling_rate == 1.0
        assert project.sampling_strategy == "random"

    def test_get_event_count_empty(self):
        """Test event count for project with no events"""
        project = ProjectFactory()
        assert project.get_event_count() == 0

    def test_get_active_sources_empty(self):
        """Test active sources for project with no sources"""
        project = ProjectFactory()
        assert list(project.get_active_sources()) == []


@pytest.mark.django_db
class TestEventSourceModel:
    """Test cases for the EventSource model"""

    def test_event_source_creation(self):
        """Test basic event source creation"""
        project = ProjectFactory()
        event_source = EventSourceFactory(
            project=project, name="web_app", description="Main web application"
        )

        assert event_source.id is not None
        assert event_source.project == project
        assert event_source.name == "web_app"
        assert event_source.description == "Main web application"
        assert event_source.is_active is True
        assert str(event_source) == f"{project.name} - web_app"

    def test_unique_source_name_per_project(self):
        """Test that source names must be unique within a project"""
        project = ProjectFactory()
        EventSourceFactory(project=project, name="web_app")

        # Creating another source with the same name should fail
        with pytest.raises(IntegrityError):
            EventSourceFactory(project=project, name="web_app")

    def test_same_source_name_different_projects(self):
        """Test that source names can be same across different projects"""
        project1 = ProjectFactory()
        project2 = ProjectFactory()

        source1 = EventSourceFactory(project=project1, name="web_app")
        source2 = EventSourceFactory(project=project2, name="web_app")

        assert source1.name == source2.name == "web_app"
        assert source1.project != source2.project

    def test_sampling_override_settings(self):
        """Test event source sampling override functionality"""
        project = ProjectFactory(
            sampling_enabled=True, sampling_rate=0.5, sampling_strategy="random"
        )

        # Source with override settings
        source = EventSourceFactory(
            project=project,
            sampling_enabled=False,  # Override project setting
            sampling_rate=0.8,  # Override project setting
            sampling_strategy="deterministic",  # Override project setting
        )

        assert source.sampling_enabled is False
        assert source.sampling_rate == 0.8
        assert source.sampling_strategy == "deterministic"

        # Source inheriting project settings (None values)
        inherited_source = EventSourceFactory(
            project=project,
            sampling_enabled=None,
            sampling_rate=None,
            sampling_strategy=None,
        )

        assert inherited_source.sampling_enabled is None
        assert inherited_source.sampling_rate is None
        assert inherited_source.sampling_strategy is None

    def test_get_event_count_empty(self):
        """Test event count for source with no events"""
        event_source = EventSourceFactory()
        assert event_source.get_event_count() == 0

    def test_update_last_event_time(self):
        """Test updating last event timestamp"""
        from django.utils import timezone

        event_source = EventSourceFactory()
        original_time = event_source.last_event_at

        # Should initially be None
        assert original_time is None

        # Update timestamp
        before_update = timezone.now()
        event_source.update_last_event_time()
        after_update = timezone.now()

        # Refresh from database
        event_source.refresh_from_db()

        assert event_source.last_event_at is not None
        assert before_update <= event_source.last_event_at <= after_update

    def test_rate_limit_override(self):
        """Test rate limit override functionality"""
        project = ProjectFactory(rate_limit_per_minute=1000)

        # Source with override
        source = EventSourceFactory(project=project, rate_limit_per_minute=500)

        assert source.rate_limit_per_minute == 500

        # Source without override
        inherited_source = EventSourceFactory(
            project=project, rate_limit_per_minute=None
        )

        assert inherited_source.rate_limit_per_minute is None


@pytest.mark.django_db
class TestModelIntegration:
    """Integration tests between Project and EventSource models"""

    def test_project_with_multiple_sources(self):
        """Test project with multiple event sources"""
        project = ProjectFactory()
        sources = []

        # Create multiple sources
        for i in range(3):
            source = EventSourceFactory(
                project=project, name=f"source_{i}", description=f"Test source {i}"
            )
            sources.append(source)

        # Test relationships
        project_sources = list(project.event_sources.all())
        assert len(project_sources) == 3

        for source in sources:
            assert source in project_sources
            assert source.project == project

    def test_project_active_sources_filtering(self):
        """Test filtering active sources"""
        project = ProjectFactory()

        # Create mix of active and inactive sources
        active_source1 = EventSourceFactory(project=project, is_active=True)
        active_source2 = EventSourceFactory(project=project, is_active=True)
        inactive_source = EventSourceFactory(project=project, is_active=False)

        active_sources = list(project.get_active_sources())

        assert len(active_sources) == 2
        assert active_source1 in active_sources
        assert active_source2 in active_sources
        assert inactive_source not in active_sources

    def test_cascade_delete(self):
        """Test that deleting project deletes associated sources"""
        project = ProjectFactory()
        source1 = EventSourceFactory(project=project)
        source2 = EventSourceFactory(project=project)

        source_ids = [source1.id, source2.id]

        # Delete project
        project.delete()

        # Sources should be deleted too
        remaining_sources = EventSource.objects.filter(id__in=source_ids)
        assert not remaining_sources.exists()

    def test_project_sampling_with_source_override(self):
        """Test sampling logic with source override"""
        project = ProjectFactory(
            sampling_enabled=True, sampling_rate=0.7, sampling_strategy="random"
        )

        # Source that overrides project settings
        source = EventSourceFactory(
            project=project,
            sampling_enabled=False,  # Disable sampling for this source
            sampling_rate=0.9,
            sampling_strategy="deterministic",
        )

        # Test with source override (should be disabled)
        result_with_override = project.should_sample_event(event_source=source)
        assert result_with_override is True  # Disabled sampling = always accept

        # Test without source (should use project settings)
        # Can't test exact result due to randomness, but shouldn't error
        result_without_override = project.should_sample_event()
        assert isinstance(result_without_override, bool)
