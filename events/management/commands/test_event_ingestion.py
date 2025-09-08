"""
Django management command to test the event ingestion API.
Usage: python manage.py test_event_ingestion --project-name "Test Project"
"""

import json
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

from django.core.management.base import BaseCommand

import requests

from projects.models import Project


class Command(BaseCommand):
    help = "Test the event ingestion API with sample data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--project-name",
            type=str,
            help="Name of the project to test with (will be created if doesn't exist)",
            default="Test Project",
        )
        parser.add_argument(
            "--base-url",
            type=str,
            help="Base URL for the API",
            default="http://localhost:8000",
        )
        parser.add_argument(
            "--num-events", type=int, help="Number of test events to send", default=5
        )
        parser.add_argument(
            "--delay", type=float, help="Delay between events in seconds", default=0.5
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Show detailed output"
        )

    def handle(self, *args, **options):
        project_name = options["project_name"]
        base_url = options["base_url"].rstrip("/")
        num_events = options["num_events"]
        delay = options["delay"]
        verbose = options["verbose"]

        # Get or create test project
        project = self.get_or_create_project(project_name)

        self.stdout.write(
            self.style.SUCCESS(
                f"Using project: {project.name} (API Key: {project.api_key})"
            )
        )

        # Test endpoint URL
        endpoint = f"{base_url}/api/events/ingest/"

        # Test data templates
        event_templates = [
            {
                "event_name": "page_view",
                "event_source": "web_app",
                "properties": {
                    "page": "/dashboard",
                    "referrer": "https://google.com",
                    "screen_resolution": "1920x1080",
                },
            },
            {
                "event_name": "button_click",
                "event_source": "web_app",
                "properties": {
                    "button_id": "signup_btn",
                    "section": "header",
                    "experiment_variant": "blue_button",
                },
            },
            {
                "event_name": "user_signup",
                "event_source": "web_app",
                "properties": {
                    "signup_method": "email",
                    "plan": "free",
                    "utm_source": "google",
                },
            },
            {
                "event_name": "api_request",
                "event_source": "backend",
                "properties": {
                    "endpoint": "/api/users",
                    "method": "GET",
                    "response_time_ms": 45,
                    "status_code": 200,
                },
            },
            {
                "event_name": "mobile_app_open",
                "event_source": "mobile_app",
                "properties": {
                    "app_version": "1.2.3",
                    "os": "iOS",
                    "os_version": "17.1",
                    "is_first_open": False,
                },
            },
        ]

        # Send test events
        success_count = 0
        error_count = 0

        self.stdout.write(f"Sending {num_events} test events to {endpoint}")
        self.stdout.write("-" * 60)

        for i in range(num_events):
            # Select event template cyclically
            template = event_templates[i % len(event_templates)]

            # Create event data with some variation
            event_data = self.create_event_data(template, i)

            # Send event
            success, response_data, status_code = self.send_event(
                endpoint, project.api_key, event_data
            )

            if success:
                success_count += 1
                if verbose:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Event {i + 1}: {event_data['event_name']}"
                        )
                    )
                else:
                    self.stdout.write(self.style.SUCCESS("."), ending="")
            else:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Event {i + 1} failed ({status_code}): {response_data}"
                    )
                )

            if delay > 0 and i < num_events - 1:
                time.sleep(delay)

        # Summary
        if not verbose:
            self.stdout.write("")  # New line after dots

        self.stdout.write("-" * 60)
        self.stdout.write(f"Results: {success_count} successful, {error_count} failed")

        if success_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ Successfully sent {success_count} events!")
            )

        if error_count > 0:
            self.stdout.write(self.style.ERROR(f"✗ {error_count} events failed"))

    def get_or_create_project(self, project_name: str) -> Project:
        """Get or create a test project"""
        try:
            project = Project.objects.get(name=project_name)
            self.stdout.write(f"Found existing project: {project_name}")
        except Project.DoesNotExist:
            from django.contrib.auth.models import User

            # Get or create a test user (owner)
            owner, created = User.objects.get_or_create(
                username="test_owner",
                defaults={
                    "email": "test@example.com",
                    "first_name": "Test",
                    "last_name": "Owner",
                },
            )

            # Create project
            project = Project.objects.create(
                name=project_name,
                description="Test project created by management command",
                owner=owner,
                sampling_enabled=True,
                sampling_rate=1.0,  # Don't sample out any events for testing
                sampling_strategy="random",
                rate_limit_per_minute=1000,  # High limit for testing
            )

            self.stdout.write(
                self.style.SUCCESS(f"Created new project: {project_name}")
            )

        return project

    def create_event_data(self, template: dict[str, Any], index: int) -> dict[str, Any]:
        """Create event data based on template with some variation"""
        event_data = template.copy()

        # Add some variation
        event_data["event_id"] = f"test_event_{index}_{uuid4().hex[:8]}"
        event_data["user_id"] = f"test_user_{(index % 3) + 1}"  # Cycle through 3 users
        event_data["session_id"] = (
            f"test_session_{(index // 2) + 1}"  # New session every 2 events
        )

        # Add index to properties for uniqueness
        if "properties" not in event_data:
            event_data["properties"] = {}
        event_data["properties"]["test_index"] = index
        event_data["properties"]["timestamp"] = datetime.now().isoformat()

        return event_data

    def send_event(
        self, url: str, api_key: str, event_data: dict[str, Any]
    ) -> tuple[bool, dict[str, Any] | None, int]:
        """Send a single event to the API"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, headers=headers, json=event_data, timeout=10)

            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"error": "Invalid JSON response"}

            if response.status_code in [200, 201, 202]:
                return True, response_data, response.status_code
            else:
                return False, response_data, response.status_code

        except requests.RequestException as e:
            return False, {"error": str(e)}, 0
