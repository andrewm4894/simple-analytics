"""
Django management command to run event aggregation jobs
"""
from datetime import datetime, date
from django.core.management.base import BaseCommand
from django_rq import get_queue

from events.workers import aggregate_daily_events_job, aggregate_hourly_events_job, aggregate_5min_events_job


class Command(BaseCommand):
    help = "Run event aggregation jobs for daily, hourly, and 5-minute summaries"

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['daily', 'hourly', '5min', 'all'],
            default='all',
            help='Type of aggregation to run (default: all)'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Date to aggregate (YYYY-MM-DD format, defaults to yesterday for daily)'
        )
        parser.add_argument(
            '--hour',
            type=str,
            help='Hour to aggregate (YYYY-MM-DD HH format, defaults to previous hour)'
        )
        parser.add_argument(
            '--5min',
            type=str,
            help='5-minute window to aggregate (YYYY-MM-DD HH:MM format, defaults to previous 5-min window)'
        )
        parser.add_argument(
            '--queue',
            type=str,
            default='default',
            help='RQ queue name to use (default: default)'
        )

    def handle(self, *args, **options):
        agg_type = options['type']
        date_str = options['date']
        hour_str = options['hour']
        fivemin_str = options['5min']
        queue_name = options['queue']

        self.stdout.write(f"Running {agg_type} aggregation jobs")
        self.stdout.write(f"Queue: {queue_name}")

        queue = get_queue(queue_name)
        jobs_enqueued = []

        try:
            if agg_type in ['daily', 'all']:
                # Daily aggregation
                target_date = None
                if date_str:
                    target_date = date.fromisoformat(date_str)
                
                job = queue.enqueue(
                    aggregate_daily_events_job,
                    date=target_date,
                    job_timeout=1800  # 30 minutes
                )
                jobs_enqueued.append(('daily', job.id))
                
                date_display = target_date.isoformat() if target_date else 'yesterday'
                self.stdout.write(f"✓ Daily aggregation job enqueued for {date_display}: {job.id}")

            if agg_type in ['hourly', 'all']:
                # Hourly aggregation
                target_hour = None
                if hour_str:
                    target_hour = datetime.fromisoformat(hour_str + ':00:00')
                
                job = queue.enqueue(
                    aggregate_hourly_events_job,
                    datetime_hour=target_hour,
                    job_timeout=900  # 15 minutes
                )
                jobs_enqueued.append(('hourly', job.id))
                
                hour_display = target_hour.isoformat() if target_hour else 'previous hour'
                self.stdout.write(f"✓ Hourly aggregation job enqueued for {hour_display}: {job.id}")

            if agg_type in ['5min', 'all']:
                # 5-minute aggregation
                target_5min = None
                if fivemin_str:
                    target_5min = datetime.fromisoformat(fivemin_str + ':00')
                
                job = queue.enqueue(
                    aggregate_5min_events_job,
                    datetime_5min=target_5min,
                    job_timeout=300  # 5 minutes
                )
                jobs_enqueued.append(('5min', job.id))
                
                fivemin_display = target_5min.isoformat() if target_5min else 'previous 5-min window'
                self.stdout.write(f"✓ 5-minute aggregation job enqueued for {fivemin_display}: {job.id}")

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"Enqueued {len(jobs_enqueued)} aggregation jobs"))
            self.stdout.write("Monitor progress with: python manage.py rq_jobs")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error enqueuing aggregation jobs: {str(e)}")
            )
            raise