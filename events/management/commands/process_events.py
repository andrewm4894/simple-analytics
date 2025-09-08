"""
Django management command to process events from Redis streams using RQ
"""
import time
from django.core.management.base import BaseCommand
from django_rq import get_queue

from events.workers import process_events_job


class Command(BaseCommand):
    help = "Process events from Redis stream to PostgreSQL using RQ workers"

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of events to process per batch (default: 50)'
        )
        parser.add_argument(
            '--max-batches',
            type=int,
            default=10,
            help='Maximum batches to process per job (default: 10)'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=5,
            help='Seconds to wait between job enqueues (default: 5)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process once and exit (default: continuous)'
        )
        parser.add_argument(
            '--queue',
            type=str,
            default='default',
            help='RQ queue name to use (default: default)'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        max_batches = options['max_batches']
        interval = options['interval']
        once = options['once']
        queue_name = options['queue']

        self.stdout.write(f"Starting event processor with:")
        self.stdout.write(f"  Batch size: {batch_size}")
        self.stdout.write(f"  Max batches: {max_batches}")
        self.stdout.write(f"  Queue: {queue_name}")
        
        if once:
            self.stdout.write(f"  Mode: Single run")
        else:
            self.stdout.write(f"  Mode: Continuous (interval: {interval}s)")

        queue = get_queue(queue_name)
        
        try:
            if once:
                # Single run
                job = queue.enqueue(
                    process_events_job,
                    batch_size=batch_size,
                    max_batches=max_batches,
                    job_timeout=300  # 5 minutes
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Enqueued job: {job.id}")
                )
            else:
                # Continuous mode
                self.stdout.write("Press Ctrl+C to stop")
                job_count = 0
                
                while True:
                    job = queue.enqueue(
                        process_events_job,
                        batch_size=batch_size,
                        max_batches=max_batches,
                        job_timeout=300  # 5 minutes
                    )
                    job_count += 1
                    
                    self.stdout.write(
                        f"Enqueued job #{job_count}: {job.id}"
                    )
                    
                    time.sleep(interval)
                    
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\nStopping event processor...")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error: {str(e)}")
            )
            raise