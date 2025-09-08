import secrets
import uuid

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # API Authentication
    public_api_key = models.CharField(max_length=64, unique=True, editable=False)
    private_api_key = models.CharField(max_length=64, unique=True, editable=False)

    # Project Settings
    rate_limit_per_minute = models.PositiveIntegerField(
        default=1000,
        validators=[MinValueValidator(1), MaxValueValidator(100000)],
        help_text="Maximum events per minute allowed for this project",
    )
    retention_days = models.PositiveIntegerField(
        default=90,
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
        help_text="Number of days to retain raw event data",
    )
    aggregation_retention_days = models.PositiveIntegerField(
        default=365,
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
        help_text="Number of days to retain aggregated data",
    )

    # CORS Configuration
    cors_allowed_origins = models.JSONField(
        default=list, help_text="List of allowed origins for CORS, or ['*'] for all"
    )

    # Sampling Configuration
    sampling_enabled = models.BooleanField(default=False)
    sampling_rate = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Sampling rate (0.0-1.0). 0.1 = 10% of events, 1.0 = 100% (no sampling)",
    )
    sampling_strategy = models.CharField(
        max_length=20,
        choices=[
            ("random", "Random sampling"),
            ("deterministic", "Deterministic sampling (based on user_id hash)"),
            ("time_window", "Time window sampling (sample within time periods)"),
        ],
        default="random",
        help_text="Strategy for event sampling",
    )

    # Project Status
    is_active = models.BooleanField(default=True)

    # Ownership
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="owned_projects"
    )
    team_members = models.ManyToManyField(User, blank=True, related_name="projects")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects"
        indexes = [
            models.Index(fields=["public_api_key"]),
            models.Index(fields=["private_api_key"]),
            models.Index(fields=["owner", "created_at"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.id})"

    def save(self, *args, **kwargs):
        # Generate API keys if not set
        if not self.public_api_key:
            self.public_api_key = self.generate_public_api_key()
        if not self.private_api_key:
            self.private_api_key = self.generate_private_api_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_public_api_key():
        """Generate a secure public API key for event ingestion"""
        return f"sa_{secrets.token_urlsafe(40)}"

    @staticmethod
    def generate_private_api_key():
        """Generate a secure private API key for dashboard access"""
        return f"sa_priv_{secrets.token_urlsafe(40)}"

    def regenerate_public_api_key(self):
        """Regenerate the public API key for this project"""
        self.public_api_key = self.generate_public_api_key()
        self.save(update_fields=["public_api_key", "updated_at"])
        return self.public_api_key

    def regenerate_private_api_key(self):
        """Regenerate the private API key for this project"""
        self.private_api_key = self.generate_private_api_key()
        self.save(update_fields=["private_api_key", "updated_at"])
        return self.private_api_key

    def regenerate_all_api_keys(self):
        """Regenerate both API keys for this project"""
        self.public_api_key = self.generate_public_api_key()
        self.private_api_key = self.generate_private_api_key()
        self.save(update_fields=["public_api_key", "private_api_key", "updated_at"])
        return {
            "public_api_key": self.public_api_key,
            "private_api_key": self.private_api_key,
        }

    def get_event_count(self):
        """Get total event count for this project"""
        return self.events.count()

    def get_active_sources(self):
        """Get active event sources for this project"""
        return self.event_sources.filter(is_active=True)

    def should_sample_event(self, event_source=None, user_id=None):
        """
        Determine if an event should be sampled based on project/source settings
        """
        import hashlib
        import random

        # Get effective sampling settings (source overrides project)
        if event_source and event_source.sampling_enabled is not None:
            enabled = event_source.sampling_enabled
            rate = event_source.sampling_rate or 1.0
            strategy = event_source.sampling_strategy or "random"
        else:
            enabled = self.sampling_enabled
            rate = self.sampling_rate
            strategy = self.sampling_strategy

        # If sampling disabled or rate is 100%, accept all events
        if not enabled or rate >= 1.0:
            return True

        # If rate is 0%, reject all events
        if rate <= 0.0:
            return False

        # Apply sampling strategy
        if strategy == "random":
            return random.random() < rate

        elif strategy == "deterministic" and user_id:
            # Consistent sampling based on user_id hash (not cryptographic)
            hash_val = int(
                hashlib.md5(
                    f"{user_id}_{self.id}".encode(), usedforsecurity=False
                ).hexdigest(),
                16,
            )  # nosec B324
            return (hash_val % 1000) / 1000.0 < rate

        elif strategy == "time_window":
            # Simple time-based sampling (could be enhanced)
            from django.utils import timezone

            now = timezone.now()
            # Sample based on current second within the minute
            current_second = now.second
            return (current_second / 60.0) < rate

        else:
            # Default to random if strategy unknown
            return random.random() < rate


class EventSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="event_sources"
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Source Configuration
    is_active = models.BooleanField(default=True)
    rate_limit_per_minute = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="Optional rate limit override for this source",
    )

    # Source-level Sampling Override
    sampling_enabled = models.BooleanField(
        null=True,
        blank=True,
        help_text="Override project sampling settings (null = inherit from project)",
    )
    sampling_rate = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Source-specific sampling rate override",
    )
    sampling_strategy = models.CharField(
        max_length=20,
        choices=[
            ("random", "Random sampling"),
            ("deterministic", "Deterministic sampling (based on user_id hash)"),
            ("time_window", "Time window sampling (sample within time periods)"),
        ],
        null=True,
        blank=True,
        help_text="Source-specific sampling strategy override",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_event_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "event_sources"
        unique_together = [["project", "name"]]
        indexes = [
            models.Index(fields=["project", "is_active"]),
            models.Index(fields=["project", "name"]),
            models.Index(fields=["last_event_at"]),
        ]

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    def get_event_count(self):
        """Get event count for this source"""
        return self.events.count()

    def update_last_event_time(self):
        """Update the last event timestamp"""
        from django.utils import timezone

        self.last_event_at = timezone.now()
        self.save(update_fields=["last_event_at"])
