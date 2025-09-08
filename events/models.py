import hashlib
import uuid
from django.db import models
from django.utils import timezone
from projects.models import Project, EventSource


class Event(models.Model):
    # Primary identifiers
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.CharField(max_length=255, null=True, blank=True, help_text="Client-provided event ID")
    
    # Project and Source relationships
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='events')
    event_source = models.ForeignKey(
        EventSource, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='events'
    )
    
    # Core event data
    event_name = models.CharField(max_length=255, db_index=True)
    event_properties = models.JSONField(default=dict, help_text="Flexible event data storage")
    
    # User identification
    user_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    session_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    
    # Request metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    # Timestamps
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Processing metadata
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'events'
        indexes = [
            # Primary query indexes
            models.Index(fields=['project', 'timestamp']),
            models.Index(fields=['project', 'event_name', 'timestamp']),
            models.Index(fields=['project', 'event_source', 'timestamp']),
            models.Index(fields=['project', 'user_id', 'timestamp']),
            models.Index(fields=['project', 'session_id', 'timestamp']),
            
            # Analytics indexes
            models.Index(fields=['project', 'event_name']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['created_at']),
            models.Index(fields=['processed_at']),
        ]
        
        # Partition-ready for future scaling
        # When we scale, we can partition by (project_id, timestamp)
        
    def __str__(self):
        return f"{self.project.name} - {self.event_name} - {self.timestamp}"
    
    def save(self, *args, **kwargs):
        # Generate user_id if not provided
        if not self.user_id:
            self.user_id = self._generate_user_id()
        
        # Generate session_id if not provided
        if not self.session_id and self.user_id:
            self.session_id = self._generate_session_id()
        
        # Update event source last activity
        if self.event_source and not self.pk:  # Only on creation
            self.event_source.update_last_event_time()
        
        super().save(*args, **kwargs)
    
    def _generate_user_id(self):
        """
        Generate a fallback user ID based on IP + User Agent + project salt
        This provides reasonable user tracking without cookies
        """
        if not self.ip_address or not self.user_agent:
            return f"anonymous_{uuid.uuid4().hex[:12]}"
        
        # Create a hash of IP + User Agent + project ID for consistency
        data = f"{self.ip_address}|{self.user_agent}|{self.project.id}"
        hash_obj = hashlib.sha256(data.encode())
        return f"hash_{hash_obj.hexdigest()[:16]}"
    
    def _generate_session_id(self):
        """
        Generate session ID: user_id + 60-minute time window
        """
        if not self.user_id:
            return None
        
        # Round timestamp to 60-minute windows
        ts = self.timestamp or timezone.now()
        window_start = ts.replace(minute=0, second=0, microsecond=0)
        
        # If we're past 60 minutes, round to next hour
        if ts.minute >= 60:
            window_start = window_start.replace(hour=window_start.hour + 1)
        
        window_str = window_start.strftime('%Y%m%d%H')
        return f"{self.user_id}_session_{window_str}"
    
    @classmethod
    def get_events_for_project(cls, project, **filters):
        """
        Get events for a project with optional filtering
        """
        queryset = cls.objects.filter(project=project)
        
        if 'event_name' in filters:
            queryset = queryset.filter(event_name=filters['event_name'])
        if 'event_source' in filters:
            queryset = queryset.filter(event_source=filters['event_source'])
        if 'user_id' in filters:
            queryset = queryset.filter(user_id=filters['user_id'])
        if 'start_date' in filters:
            queryset = queryset.filter(timestamp__gte=filters['start_date'])
        if 'end_date' in filters:
            queryset = queryset.filter(timestamp__lte=filters['end_date'])
        
        return queryset.order_by('-timestamp')
    
    @classmethod
    def get_event_counts_by_name(cls, project, start_date=None, end_date=None):
        """
        Get event counts grouped by event name for analytics
        """
        queryset = cls.objects.filter(project=project)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset.values('event_name').annotate(
            count=models.Count('id')
        ).order_by('-count')
    
    def mark_processed(self):
        """Mark this event as processed"""
        self.processed_at = timezone.now()
        self.save(update_fields=['processed_at'])
