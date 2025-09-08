"""
Django management command to check event processing status
"""
import redis
from django.core.management.base import BaseCommand
from django.conf import settings
from django_rq import get_queue

from events.models import Event
from projects.models import Project


class Command(BaseCommand):
    help = "Check event processing system status"

    def add_arguments(self, parser):
        parser.add_argument(
            '--queue',
            type=str,
            default='default',
            help='RQ queue name to check (default: default)'
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed project-level statistics'
        )

    def handle(self, *args, **options):
        queue_name = options['queue']
        detailed = options['detailed']

        self.stdout.write(self.style.SUCCESS("=== Event Processing Status ==="))
        self.stdout.write("")

        # Check Redis connection
        try:
            redis_client = redis.from_url(settings.REDIS_URL)
            redis_info = redis_client.info()
            self.stdout.write(f"✓ Redis: Connected (version {redis_info['redis_version']})")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Redis: Connection failed - {e}"))
            return

        # Check Redis stream
        try:
            stream_key = "events:queue"
            stream_length = redis_client.xlen(stream_key)
            self.stdout.write(f"✓ Event Stream: {stream_length} events pending")
            
            # Check consumer group
            try:
                groups = redis_client.xinfo_groups(stream_key)
                for group in groups:
                    if group['name'] == b'event_processors':
                        pending = group['pending']
                        consumers = group['consumers']
                        self.stdout.write(f"✓ Consumer Group: {consumers} consumers, {pending} pending")
                        break
                else:
                    self.stdout.write(self.style.WARNING("⚠ Consumer Group: Not found"))
            except redis.ResponseError:
                self.stdout.write(self.style.WARNING("⚠ Consumer Group: Stream does not exist"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Event Stream: Error checking - {e}"))

        # Check RQ queue
        try:
            queue = get_queue(queue_name)
            job_count = len(queue.jobs)
            self.stdout.write(f"✓ RQ Queue ({queue_name}): {job_count} jobs queued")
            
            # Check for failed jobs
            failed_queue = get_queue('failed')
            failed_count = len(failed_queue.jobs)
            if failed_count > 0:
                self.stdout.write(self.style.WARNING(f"⚠ Failed Jobs: {failed_count}"))
            else:
                self.stdout.write("✓ Failed Jobs: None")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ RQ Queue: Error checking - {e}"))

        self.stdout.write("")

        # Database statistics
        try:
            total_events = Event.objects.count()
            self.stdout.write(f"📊 Total Events: {total_events:,}")
            
            if total_events > 0:
                # Recent events
                from django.utils import timezone
                from datetime import timedelta
                
                now = timezone.now()
                last_hour = Event.objects.filter(timestamp__gte=now - timedelta(hours=1)).count()
                last_day = Event.objects.filter(timestamp__gte=now - timedelta(days=1)).count()
                
                self.stdout.write(f"📊 Events (last hour): {last_hour:,}")
                self.stdout.write(f"📊 Events (last 24h): {last_day:,}")
                
                # Latest event
                latest_event = Event.objects.latest('timestamp')
                self.stdout.write(f"📊 Latest Event: {latest_event.timestamp}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Database Stats: Error - {e}"))

        if detailed:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=== Project Details ==="))
            
            try:
                for project in Project.objects.filter(is_active=True):
                    event_count = Event.objects.filter(project=project).count()
                    self.stdout.write(f"📁 {project.name}: {event_count:,} events")
                    
                    if event_count > 0:
                        latest = Event.objects.filter(project=project).latest('timestamp')
                        self.stdout.write(f"   Latest: {latest.timestamp}")
                        
                        # Event sources
                        sources = Event.objects.filter(project=project).values_list(
                            'event_source__name', flat=True
                        ).distinct()
                        source_list = [s for s in sources if s]
                        if source_list:
                            self.stdout.write(f"   Sources: {', '.join(source_list)}")
                            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Project Details: Error - {e}"))

        self.stdout.write("")
        self.stdout.write("Commands:")
        self.stdout.write("  Start worker:    python manage.py rqworker")
        self.stdout.write("  Process events:  python manage.py process_events")
        self.stdout.write("  View RQ status:  python manage.py rq_jobs")
        self.stdout.write("  Cleanup events:  python manage.py cleanup_events")