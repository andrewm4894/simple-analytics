"""
API Key Authentication for Event Ingestion and Dashboard API
"""

import logging

from rest_framework import authentication, exceptions

from projects.models import Project

logger = logging.getLogger(__name__)


class PublicApiKeyAuthentication(authentication.BaseAuthentication):
    """
    Authentication for event ingestion using public API keys.
    Expects public API key in Authorization header: "Bearer sa_<token>"
    """

    def authenticate(self, request):
        """
        Authenticate the request based on public API key.
        Returns (project, None) tuple if authentication succeeds.
        """
        auth_header = request.headers.get("authorization")

        if not auth_header:
            return None

        try:
            scheme, api_key = auth_header.split(" ", 1)
        except ValueError as e:
            raise exceptions.AuthenticationFailed(
                "Invalid authorization header format"
            ) from e

        if scheme.lower() != "bearer":
            return None

        if not api_key.startswith("sa_"):
            raise exceptions.AuthenticationFailed("Invalid API key format")

        try:
            project = Project.objects.select_related("owner").get(
                public_api_key=api_key, is_active=True
            )
        except Project.DoesNotExist as e:
            logger.warning(f"Invalid public API key attempted: {api_key[:10]}...")
            raise exceptions.AuthenticationFailed("Invalid API key") from e

        logger.debug(
            f"Authenticated project for ingestion: {project.name} ({project.id})"
        )

        # Return (user, auth) tuple - we use project as "user" for this endpoint
        # The project object will be available as request.user in views
        return (project, api_key)

    def authenticate_header(self, request):
        """
        Return the WWW-Authenticate header value for 401 responses
        """
        return "Bearer"


class PrivateApiKeyAuthentication(authentication.BaseAuthentication):
    """
    Authentication for dashboard API using private API keys.
    Expects private API key in Authorization header: "Bearer sa_priv_<token>"
    """

    def authenticate(self, request):
        """
        Authenticate the request based on private API key.
        Returns (project, None) tuple if authentication succeeds.
        """
        auth_header = request.headers.get("authorization")

        if not auth_header:
            return None

        try:
            scheme, api_key = auth_header.split(" ", 1)
        except ValueError as e:
            raise exceptions.AuthenticationFailed(
                "Invalid authorization header format"
            ) from e

        if scheme.lower() != "bearer":
            return None

        if not api_key.startswith("sa_priv_"):
            raise exceptions.AuthenticationFailed("Invalid private API key format")

        try:
            project = Project.objects.select_related("owner").get(
                private_api_key=api_key, is_active=True
            )
        except Project.DoesNotExist as e:
            logger.warning(f"Invalid private API key attempted: {api_key[:10]}...")
            raise exceptions.AuthenticationFailed("Invalid API key") from e

        logger.debug(
            f"Authenticated project for dashboard: {project.name} ({project.id})"
        )

        # Return (user, auth) tuple - we use project as "user" for this endpoint
        # The project object will be available as request.user in views
        return (project, api_key)

    def authenticate_header(self, request):
        """
        Return the WWW-Authenticate header value for 401 responses
        """
        return "Bearer"


# Backward compatibility alias
ApiKeyAuthentication = PublicApiKeyAuthentication
