"""
Rate limiting for Event Ingestion API
"""

import time

from django.conf import settings

import redis
from rest_framework.throttling import BaseThrottle

from projects.models import Project


class EventIngestionThrottle(BaseThrottle):
    """
    Custom throttle for event ingestion with per-project and per-IP limits.
    Uses Redis for distributed rate limiting.
    """

    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.window_size = 60  # 1 minute window

    def get_client_identifier(self, request, view) -> str:
        """Get client IP address"""
        # Use the same logic as in the view
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return request.META.get("REMOTE_ADDR", "unknown")

    def get_project_rate_limit(self, project: Project) -> int:
        """Get rate limit for the project"""
        return project.rate_limit_per_minute

    def get_ip_rate_limit(self) -> int:
        """Get global IP-based rate limit"""
        # Default IP rate limit (can be made configurable)
        return 1000  # requests per minute per IP

    def check_rate_limit(
        self, key: str, limit: int, window: int = 60
    ) -> tuple[bool, int | None]:
        """
        Check if rate limit is exceeded using sliding window.
        Returns (allowed, retry_after_seconds)
        """
        try:
            current_time = int(time.time())
            pipe = self.redis_client.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, current_time - window)

            # Count current requests in the window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiration for cleanup
            pipe.expire(key, window + 10)

            results = pipe.execute()
            current_count = results[1]

            if current_count >= limit:
                # Rate limit exceeded
                # Calculate retry after time
                oldest_in_window = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_in_window:
                    oldest_time = int(oldest_in_window[0][1])
                    retry_after = window - (current_time - oldest_time)
                    return False, max(1, retry_after)
                return False, window

            return True, None

        except Exception as e:
            # If Redis fails, allow the request (fail open)
            import logging

            logging.getLogger(__name__).error(f"Rate limiting Redis error: {e}")
            return True, None

    def allow_request(self, request, view) -> bool:
        """
        Check if the request should be allowed based on rate limits.
        """
        # Get project from authentication
        project = getattr(request, "user", None)
        if not isinstance(project, Project):
            return True  # Let authentication handle this

        client_ip = self.get_client_identifier(request, view)

        # Check project-level rate limit
        project_key = f"rate_limit:project:{project.id}"
        project_limit = self.get_project_rate_limit(project)

        project_allowed, project_retry = self.check_rate_limit(
            project_key, project_limit, self.window_size
        )

        if not project_allowed:
            self.wait = project_retry
            return False

        # Check IP-level rate limit
        ip_key = f"rate_limit:ip:{client_ip}"
        ip_limit = self.get_ip_rate_limit()

        ip_allowed, ip_retry = self.check_rate_limit(ip_key, ip_limit, self.window_size)

        if not ip_allowed:
            self.wait = ip_retry
            return False

        return True

    def wait(self) -> int | None:
        """
        Return the recommended retry-after time in seconds.
        """
        return getattr(self, "wait", None)
