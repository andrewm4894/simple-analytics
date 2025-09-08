"""
Background workers for processing events from Redis streams
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any

import redis
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from projects.models import Project, EventSource
from .models import Event

logger = logging.getLogger(__name__)


class EventProcessor:
    """
    Processes events from Redis streams and stores them in PostgreSQL
    """
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.stream_key = "events:queue"
        self.consumer_group = "event_processors"
        self.consumer_name = "worker_1"
        
    def ensure_consumer_group(self):
        """Ensure the consumer group exists"""
        try:
            self.redis_client.xgroup_create(
                self.stream_key, 
                self.consumer_group, 
                id='0', 
                mkstream=True
            )
            logger.info(f"Created consumer group: {self.consumer_group}")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Group already exists
                logger.debug(f"Consumer group already exists: {self.consumer_group}")
            else:
                logger.error(f"Error creating consumer group: {e}")
                raise

    def process_event_batch(self, count: int = 10, timeout: int = 5000) -> int:
        """
        Process a batch of events from Redis stream
        Returns number of events processed
        """
        try:
            # Read events from stream
            messages = self.redis_client.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_key: '>'},
                count=count,
                block=timeout
            )
            
            processed_count = 0
            
            for _, stream_messages in messages:
                for message_id, fields in stream_messages:
                    try:
                        success = self.process_single_event(message_id, fields)
                        if success:
                            # Acknowledge successful processing
                            self.redis_client.xack(
                                self.stream_key, 
                                self.consumer_group, 
                                message_id
                            )
                            processed_count += 1
                        else:
                            logger.warning(f"Failed to process event {message_id}")
                            
                    except Exception as e:
                        logger.error(f"Error processing event {message_id}: {e}", exc_info=True)
            
            if processed_count > 0:
                logger.info(f"Processed {processed_count} events successfully")
            
            return processed_count
            
        except redis.TimeoutError:
            # No messages available - this is normal
            logger.debug("No events available in stream")
            return 0
        except Exception as e:
            logger.error(f"Error reading from stream: {e}", exc_info=True)
            return 0

    def process_single_event(self, message_id: str, fields: Dict[str, Any]) -> bool:
        """
        Process a single event and store it in PostgreSQL
        Returns True if successful, False otherwise
        """
        try:
            # Parse event data from Redis fields (handle bytes keys from Redis)
            event_data_json = fields.get('event_data') or fields.get(b'event_data')
            if not event_data_json:
                logger.error(f"No event_data in message {message_id}")
                return False
            
            # Convert bytes to string if necessary
            if isinstance(event_data_json, bytes):
                event_data_json = event_data_json.decode('utf-8')
                
            event_data = json.loads(event_data_json)
            
            # Create the event record
            return self.create_event_record(event_data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in event data: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing single event: {e}", exc_info=True)
            return False

    @transaction.atomic
    def create_event_record(self, event_data: Dict[str, Any]) -> bool:
        """
        Create an Event record in PostgreSQL from processed event data
        """
        try:
            # Get project
            project = Project.objects.select_related('owner').get(
                id=event_data['project_id'],
                is_active=True
            )
            
            # Get event source (if specified)
            event_source = None
            if event_data.get('event_source_id'):
                try:
                    event_source = EventSource.objects.get(
                        id=event_data['event_source_id'],
                        project=project
                    )
                except EventSource.DoesNotExist:
                    logger.warning(f"Event source {event_data['event_source_id']} not found")
            
            # Parse timestamp
            timestamp = timezone.now()
            if event_data.get('timestamp'):
                try:
                    timestamp = datetime.fromisoformat(event_data['timestamp'].replace('Z', '+00:00'))
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid timestamp format: {e}, using current time")
            
            # Generate user_id if not provided
            user_id = event_data.get('user_id')
            if not user_id:
                user_id = self.generate_fallback_user_id(
                    event_data.get('ip_address', ''),
                    event_data.get('user_agent', ''),
                    project
                )
            
            # Generate session_id if not provided
            session_id = event_data.get('session_id')
            if not session_id and user_id:
                session_id = self.generate_session_id(user_id, timestamp)
            
            # Create the Event record
            event = Event.objects.create(
                project=project,
                event_source=event_source,
                event_name=event_data['event_name'],
                event_properties=event_data.get('event_properties', {}),
                user_id=user_id,
                session_id=session_id,
                ip_address=event_data.get('ip_address', ''),
                user_agent=event_data.get('user_agent', ''),
                timestamp=timestamp,
                event_id=event_data.get('event_id')  # Optional client-provided ID
            )
            
            logger.debug(f"Created event: {event.id} for project {project.name}")
            return True
            
        except Project.DoesNotExist:
            logger.error(f"Project {event_data['project_id']} not found or inactive")
            return False
        except Exception as e:
            logger.error(f"Error creating event record: {e}", exc_info=True)
            return False

    def generate_fallback_user_id(self, ip_address: str, user_agent: str, project: Project) -> str:
        """Generate fallback user ID using IP + User Agent + project salt"""
        if not ip_address and not user_agent:
            # Generate anonymous user ID
            from uuid import uuid4
            return f"anonymous_{uuid4().hex[:12]}"
        
        import hashlib
        # Use project ID as salt for user ID generation
        data = f"{ip_address}|{user_agent}|{project.id}"
        hash_obj = hashlib.sha256(data.encode())
        return f"hash_{hash_obj.hexdigest()[:16]}"

    def generate_session_id(self, user_id: str, timestamp: datetime) -> str:
        """Generate session ID based on user ID and 60-minute time window"""
        import hashlib
        
        # Round timestamp to 60-minute windows
        window_start = timestamp.replace(minute=0 if timestamp.minute < 30 else 30, second=0, microsecond=0)
        
        # Create session ID from user + time window
        session_data = f"{user_id}_{window_start.isoformat()}"
        hash_obj = hashlib.md5(session_data.encode())
        return f"sess_{hash_obj.hexdigest()[:16]}"

    def get_pending_message_count(self) -> int:
        """Get count of pending messages in the consumer group"""
        try:
            info = self.redis_client.xpending(self.stream_key, self.consumer_group)
            return info['pending']
        except Exception as e:
            logger.error(f"Error getting pending count: {e}")
            return 0

    def get_stream_length(self) -> int:
        """Get total length of the stream"""
        try:
            return self.redis_client.xlen(self.stream_key)
        except Exception as e:
            logger.error(f"Error getting stream length: {e}")
            return 0


# RQ Job functions
def process_events_job(batch_size: int = 50, max_batches: int = 10) -> Dict[str, Any]:
    """
    RQ job to process events from Redis stream
    
    Args:
        batch_size: Number of events to process per batch
        max_batches: Maximum number of batches to process in one job
    
    Returns:
        Dictionary with processing statistics
    """
    processor = EventProcessor()
    
    # Ensure consumer group exists
    processor.ensure_consumer_group()
    
    total_processed = 0
    batches_processed = 0
    
    start_time = timezone.now()
    
    try:
        for batch_num in range(max_batches):
            processed_count = processor.process_event_batch(count=batch_size)
            
            if processed_count == 0:
                # No more events available
                break
                
            total_processed += processed_count
            batches_processed += 1
            
            logger.info(f"Batch {batch_num + 1}: processed {processed_count} events")
    
    except Exception as e:
        logger.error(f"Error in process_events_job: {e}", exc_info=True)
        raise
    
    end_time = timezone.now()
    duration = (end_time - start_time).total_seconds()
    
    stats = {
        'total_processed': total_processed,
        'batches_processed': batches_processed,
        'duration_seconds': duration,
        'events_per_second': total_processed / duration if duration > 0 else 0,
        'pending_messages': processor.get_pending_message_count(),
        'stream_length': processor.get_stream_length(),
        'completed_at': end_time.isoformat()
    }
    
    logger.info(f"Event processing job completed: {stats}")
    return stats


def cleanup_old_events_job(days: int = 90) -> Dict[str, Any]:
    """
    RQ job to clean up old events based on project retention policies
    
    Args:
        days: Default retention period in days
        
    Returns:
        Dictionary with cleanup statistics
    """
    from django.utils import timezone
    from datetime import timedelta
    
    start_time = timezone.now()
    cutoff_date = start_time - timedelta(days=days)
    
    total_deleted = 0
    projects_processed = 0
    
    try:
        # Process each project individually based on their retention settings
        for project in Project.objects.filter(is_active=True):
            project_days = getattr(project, 'retention_days', days)
            project_cutoff = start_time - timedelta(days=project_days)
            
            # Count and delete old events for this project
            old_events = Event.objects.filter(
                project=project,
                timestamp__lt=project_cutoff
            )
            
            count = old_events.count()
            if count > 0:
                deleted_count, _ = old_events.delete()
                total_deleted += deleted_count
                logger.info(f"Deleted {deleted_count} events for project {project.name} (older than {project_days} days)")
            
            projects_processed += 1
    
    except Exception as e:
        logger.error(f"Error in cleanup_old_events_job: {e}", exc_info=True)
        raise
    
    end_time = timezone.now()
    duration = (end_time - start_time).total_seconds()
    
    stats = {
        'total_deleted': total_deleted,
        'projects_processed': projects_processed,
        'duration_seconds': duration,
        'cutoff_date': cutoff_date.isoformat(),
        'completed_at': end_time.isoformat()
    }
    
    logger.info(f"Cleanup job completed: {stats}")
    return stats


def aggregate_daily_events_job(date=None) -> Dict[str, Any]:
    """
    RQ job to aggregate events into daily summaries
    
    Args:
        date: Date to aggregate (defaults to yesterday)
        
    Returns:
        Dictionary with aggregation statistics
    """
    from django.utils import timezone
    from django.db.models import Count
    from datetime import timedelta, date as date_class
    from events.models import Event
    from events.models_aggregation import DailyEventAggregation, ProjectDailySummary
    
    # Default to yesterday if no date provided
    if date is None:
        date = (timezone.now() - timedelta(days=1)).date()
    elif isinstance(date, str):
        date = date_class.fromisoformat(date)
    
    start_time = timezone.now()
    logger.info(f"Starting daily aggregation for {date}")
    
    aggregations_created = 0
    summaries_created = 0
    projects_processed = 0
    
    try:
        # Process each project
        for project in Project.objects.filter(is_active=True):
            # Get all events for this project on this date
            events_qs = Event.objects.filter(
                project=project,
                timestamp__date=date
            )
            
            if not events_qs.exists():
                continue  # Skip projects with no events for this date
            
            projects_processed += 1
            
            # Aggregate by event_source and event_name
            aggregated_data = events_qs.values(
                'event_source', 'event_name'
            ).annotate(
                event_count=Count('id'),
                unique_users=Count('user_id', distinct=True),
                unique_sessions=Count('session_id', distinct=True)
            )
            
            project_total_events = 0
            project_event_names = set()
            source_breakdown = {}
            event_breakdown = []
            
            for data in aggregated_data:
                # Create or update daily aggregation record
                daily_agg, created = DailyEventAggregation.objects.get_or_create(
                    project=project,
                    event_source_id=data['event_source'],
                    event_name=data['event_name'],
                    date=date,
                    defaults={
                        'event_count': data['event_count'],
                        'unique_users': data['unique_users'],
                        'unique_sessions': data['unique_sessions']
                    }
                )
                
                if not created:
                    # Update existing record
                    daily_agg.event_count = data['event_count']
                    daily_agg.unique_users = data['unique_users']
                    daily_agg.unique_sessions = data['unique_sessions']
                    daily_agg.save()
                
                aggregations_created += 1 if created else 0
                
                # Accumulate project-level stats
                project_total_events += data['event_count']
                project_event_names.add(data['event_name'])
                
                # Source breakdown
                if data['event_source']:
                    source_name = daily_agg.event_source.name
                    if source_name not in source_breakdown:
                        source_breakdown[source_name] = 0
                    source_breakdown[source_name] += data['event_count']
                
                # Event breakdown for top events
                event_breakdown.append({
                    'event_name': data['event_name'],
                    'event_count': data['event_count'],
                    'unique_users': data['unique_users']
                })
            
            # Get actual unique users and sessions for the project
            project_users = events_qs.values_list('user_id', flat=True).distinct()
            project_sessions = events_qs.values_list('session_id', flat=True).distinct()
            
            # Sort top events by count
            event_breakdown.sort(key=lambda x: x['event_count'], reverse=True)
            top_events = event_breakdown[:10]  # Top 10 events
            
            # Create or update project daily summary
            summary, created = ProjectDailySummary.objects.get_or_create(
                project=project,
                date=date,
                defaults={
                    'total_events': project_total_events,
                    'unique_users': len([u for u in project_users if u]),
                    'unique_sessions': len([s for s in project_sessions if s]),
                    'unique_event_names': len(project_event_names),
                    'source_breakdown': source_breakdown,
                    'top_events': top_events
                }
            )
            
            if not created:
                # Update existing summary
                summary.total_events = project_total_events
                summary.unique_users = len([u for u in project_users if u])
                summary.unique_sessions = len([s for s in project_sessions if s])
                summary.unique_event_names = len(project_event_names)
                summary.source_breakdown = source_breakdown
                summary.top_events = top_events
                summary.save()
            
            summaries_created += 1 if created else 0
            
            logger.info(f"Aggregated {project_total_events} events for project {project.name}")
    
    except Exception as e:
        logger.error(f"Error in aggregate_daily_events_job: {e}", exc_info=True)
        raise
    
    end_time = timezone.now()
    duration = (end_time - start_time).total_seconds()
    
    stats = {
        'date': date.isoformat(),
        'projects_processed': projects_processed,
        'aggregations_created': aggregations_created,
        'summaries_created': summaries_created,
        'duration_seconds': duration,
        'completed_at': end_time.isoformat()
    }
    
    logger.info(f"Daily aggregation completed: {stats}")
    return stats


def aggregate_hourly_events_job(datetime_hour=None) -> Dict[str, Any]:
    """
    RQ job to aggregate events into hourly summaries
    
    Args:
        datetime_hour: Hour to aggregate (defaults to previous hour)
        
    Returns:
        Dictionary with aggregation statistics
    """
    from django.utils import timezone
    from django.db.models import Count
    from datetime import timedelta
    from events.models import Event
    from events.models_aggregation import HourlyEventAggregation
    
    # Default to previous hour if not provided
    if datetime_hour is None:
        now = timezone.now()
        datetime_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    elif isinstance(datetime_hour, str):
        from datetime import datetime
        datetime_hour = datetime.fromisoformat(datetime_hour.replace('Z', '+00:00'))
    
    start_time = timezone.now()
    logger.info(f"Starting hourly aggregation for {datetime_hour}")
    
    aggregations_created = 0
    projects_processed = 0
    next_hour = datetime_hour + timedelta(hours=1)
    
    try:
        # Process each project
        for project in Project.objects.filter(is_active=True):
            # Get all events for this project in this hour
            events_qs = Event.objects.filter(
                project=project,
                timestamp__gte=datetime_hour,
                timestamp__lt=next_hour
            )
            
            if not events_qs.exists():
                continue
            
            projects_processed += 1
            
            # Aggregate by event_source and event_name
            aggregated_data = events_qs.values(
                'event_source', 'event_name'
            ).annotate(
                event_count=Count('id'),
                unique_users=Count('user_id', distinct=True),
                unique_sessions=Count('session_id', distinct=True)
            )
            
            for data in aggregated_data:
                # Create or update hourly aggregation record
                hourly_agg, created = HourlyEventAggregation.objects.get_or_create(
                    project=project,
                    event_source_id=data['event_source'],
                    event_name=data['event_name'],
                    datetime_hour=datetime_hour,
                    defaults={
                        'event_count': data['event_count'],
                        'unique_users': data['unique_users'],
                        'unique_sessions': data['unique_sessions']
                    }
                )
                
                if not created:
                    # Update existing record
                    hourly_agg.event_count = data['event_count']
                    hourly_agg.unique_users = data['unique_users']
                    hourly_agg.unique_sessions = data['unique_sessions']
                    hourly_agg.save()
                
                aggregations_created += 1 if created else 0
    
    except Exception as e:
        logger.error(f"Error in aggregate_hourly_events_job: {e}", exc_info=True)
        raise
    
    end_time = timezone.now()
    duration = (end_time - start_time).total_seconds()
    
    stats = {
        'datetime_hour': datetime_hour.isoformat(),
        'projects_processed': projects_processed,
        'aggregations_created': aggregations_created,
        'duration_seconds': duration,
        'completed_at': end_time.isoformat()
    }
    
    logger.info(f"Hourly aggregation completed: {stats}")
    return stats


def aggregate_5min_events_job(datetime_5min=None) -> Dict[str, Any]:
    """
    RQ job to aggregate events into 5-minute summaries for near real-time dashboards
    
    Args:
        datetime_5min: 5-minute window to aggregate (defaults to previous 5-minute window)
        
    Returns:
        Dictionary with aggregation statistics
    """
    from django.utils import timezone
    from django.db.models import Count
    from datetime import timedelta
    from events.models import Event
    from events.models_aggregation import FiveMinuteEventAggregation
    
    # Default to previous 5-minute window if not provided
    if datetime_5min is None:
        now = timezone.now()
        # Round down to nearest 5-minute interval
        minute_rounded = (now.minute // 5) * 5
        datetime_5min = now.replace(minute=minute_rounded, second=0, microsecond=0) - timedelta(minutes=5)
    elif isinstance(datetime_5min, str):
        from datetime import datetime
        datetime_5min = datetime.fromisoformat(datetime_5min.replace('Z', '+00:00'))
    
    # Ensure datetime_5min is rounded to 5-minute boundary
    minute_rounded = (datetime_5min.minute // 5) * 5
    datetime_5min = datetime_5min.replace(minute=minute_rounded, second=0, microsecond=0)
    
    start_time = timezone.now()
    logger.info(f"Starting 5-minute aggregation for {datetime_5min}")
    
    aggregations_created = 0
    projects_processed = 0
    next_5min = datetime_5min + timedelta(minutes=5)
    
    try:
        # Process each project
        for project in Project.objects.filter(is_active=True):
            # Get all events for this project in this 5-minute window
            events_qs = Event.objects.filter(
                project=project,
                timestamp__gte=datetime_5min,
                timestamp__lt=next_5min
            )
            
            if not events_qs.exists():
                continue
            
            projects_processed += 1
            
            # Aggregate by event_source and event_name
            aggregated_data = events_qs.values(
                'event_source', 'event_name'
            ).annotate(
                event_count=Count('id'),
                unique_users=Count('user_id', distinct=True),
                unique_sessions=Count('session_id', distinct=True)
            )
            
            for data in aggregated_data:
                # Create or update 5-minute aggregation record
                fivemin_agg, created = FiveMinuteEventAggregation.objects.get_or_create(
                    project=project,
                    event_source_id=data['event_source'],
                    event_name=data['event_name'],
                    datetime_5min=datetime_5min,
                    defaults={
                        'event_count': data['event_count'],
                        'unique_users': data['unique_users'],
                        'unique_sessions': data['unique_sessions']
                    }
                )
                
                if not created:
                    # Update existing record
                    fivemin_agg.event_count = data['event_count']
                    fivemin_agg.unique_users = data['unique_users']
                    fivemin_agg.unique_sessions = data['unique_sessions']
                    fivemin_agg.save()
                
                aggregations_created += 1 if created else 0
    
    except Exception as e:
        logger.error(f"Error in aggregate_5min_events_job: {e}", exc_info=True)
        raise
    
    end_time = timezone.now()
    duration = (end_time - start_time).total_seconds()
    
    stats = {
        'datetime_5min': datetime_5min.isoformat(),
        'projects_processed': projects_processed,
        'aggregations_created': aggregations_created,
        'duration_seconds': duration,
        'completed_at': end_time.isoformat()
    }
    
    logger.info(f"5-minute aggregation completed: {stats}")
    return stats