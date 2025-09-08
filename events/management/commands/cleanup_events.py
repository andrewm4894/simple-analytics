"""
Django management command to clean up old events based on retention policies
"""
from django.core.management.base import BaseCommand
from django_rq import get_queue

from events.workers import cleanup_old_events_job


class Command(BaseCommand):
    help = "Clean up old events based on project retention policies"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Default retention period in days (default: 90)'
        )
        parser.add_argument(
            '--queue',
            type=str,
            default='default',
            help='RQ queue name to use (default: default)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        queue_name = options['queue']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No events will be deleted")
            )
            # TODO: Implement dry run logic
            self.stdout.write("Dry run mode not yet implemented")
            return

        self.stdout.write(f"Scheduling cleanup job:")
        self.stdout.write(f"  Default retention: {days} days")
        self.stdout.write(f"  Queue: {queue_name}")

        queue = get_queue(queue_name)
        
        try:
            job = queue.enqueue(
                cleanup_old_events_job,
                days=days,
                job_timeout=1800  # 30 minutes
            )
            
            self.stdout.write(
                self.style.SUCCESS(f"Enqueued cleanup job: {job.id}")
            )
            self.stdout.write(
                "Monitor job progress with: python manage.py rq_jobs"
            )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error scheduling cleanup job: {str(e)}")
            )
            raise