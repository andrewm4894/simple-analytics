"""
Models for storing aggregated event data
"""
from django.db import models
from projects.models import Project, EventSource


class EventAggregation(models.Model):
    """
    Base model for event aggregations with common fields
    """
    project = models.ForeignKey(
        Project, 
        on_delete=models.CASCADE,
        related_name='%(class)s_aggregations'
    )
    event_source = models.ForeignKey(
        EventSource,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='%(class)s_aggregations'
    )
    event_name = models.CharField(max_length=255, db_index=True)
    
    # Aggregated metrics
    event_count = models.PositiveIntegerField(default=0)
    unique_users = models.PositiveIntegerField(default=0)
    unique_sessions = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DailyEventAggregation(EventAggregation):
    """
    Daily aggregation of events by project, source, and event name
    """
    date = models.DateField(db_index=True)
    
    class Meta:
        unique_together = ['project', 'event_source', 'event_name', 'date']
        indexes = [
            models.Index(fields=['project', 'date']),
            models.Index(fields=['project', 'event_name', 'date']),
            models.Index(fields=['date', 'event_count']),
        ]
    
    def __str__(self):
        source_name = self.event_source.name if self.event_source else "None"
        return f"{self.project.name} - {source_name} - {self.event_name} ({self.date})"


class FiveMinuteEventAggregation(EventAggregation):
    """
    5-minute aggregation of events by project, source, and event name
    For near real-time dashboard updates
    """
    datetime_5min = models.DateTimeField(db_index=True)  # Truncated to 5-minute intervals
    
    class Meta:
        unique_together = ['project', 'event_source', 'event_name', 'datetime_5min']
        indexes = [
            models.Index(fields=['project', 'datetime_5min']),
            models.Index(fields=['project', 'event_name', 'datetime_5min']),
            models.Index(fields=['datetime_5min', 'event_count']),
            # Optimized for recent data queries (last 24-48 hours)
            models.Index(fields=['-datetime_5min', 'project']),
        ]
    
    def __str__(self):
        source_name = self.event_source.name if self.event_source else "None"
        return f"{self.project.name} - {source_name} - {self.event_name} ({self.datetime_5min})"


class HourlyEventAggregation(EventAggregation):
    """
    Hourly aggregation of events by project, source, and event name
    """
    datetime_hour = models.DateTimeField(db_index=True)  # Truncated to hour
    
    class Meta:
        unique_together = ['project', 'event_source', 'event_name', 'datetime_hour']
        indexes = [
            models.Index(fields=['project', 'datetime_hour']),
            models.Index(fields=['project', 'event_name', 'datetime_hour']),
            models.Index(fields=['datetime_hour', 'event_count']),
        ]
    
    def __str__(self):
        source_name = self.event_source.name if self.event_source else "None"
        return f"{self.project.name} - {source_name} - {self.event_name} ({self.datetime_hour})"


class ProjectDailySummary(models.Model):
    """
    Daily summary statistics per project
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='daily_summaries'
    )
    date = models.DateField(db_index=True)
    
    # Overall metrics
    total_events = models.PositiveIntegerField(default=0)
    unique_users = models.PositiveIntegerField(default=0)
    unique_sessions = models.PositiveIntegerField(default=0)
    unique_event_names = models.PositiveIntegerField(default=0)
    
    # Source breakdown (stored as JSON)
    source_breakdown = models.JSONField(default=dict)
    
    # Top events (stored as JSON)
    top_events = models.JSONField(default=list)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['project', 'date']
        indexes = [
            models.Index(fields=['date', 'total_events']),
            models.Index(fields=['project', 'date']),
        ]
    
    def __str__(self):
        return f"{self.project.name} Summary ({self.date})"