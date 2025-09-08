"""
Unit tests for API key authentication classes
"""

import pytest
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from events.authentication import (
    ApiKeyAuthentication,
    PrivateApiKeyAuthentication,
    PublicApiKeyAuthentication,
)
from tests.fixtures.test_factories import ProjectFactory


@pytest.mark.django_db
class TestPublicApiKeyAuthentication:
    """Test cases for PublicApiKeyAuthentication class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.auth = PublicApiKeyAuthentication()
        self.factory = APIRequestFactory()
        self.project = ProjectFactory()

    def test_authenticate_valid_public_key(self):
        """Test authentication with valid public API key"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.project.public_api_key}"

        user, auth = self.auth.authenticate(request)

        assert user == self.project
        assert auth == self.project.public_api_key

    def test_authenticate_no_authorization_header(self):
        """Test authentication without authorization header"""
        request = self.factory.get("/")

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_invalid_header_format(self):
        """Test authentication with malformed authorization header"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = "InvalidFormat"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid authorization header format" in str(exc_info.value)

    def test_authenticate_wrong_scheme(self):
        """Test authentication with wrong authorization scheme"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Basic {self.project.public_api_key}"

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_invalid_key_format(self):
        """Test authentication with invalid API key format"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid_key_format"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid API key format" in str(exc_info.value)

    def test_authenticate_private_key_in_public_auth(self):
        """Test that private key doesn't work with public authentication"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.project.private_api_key}"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        # Private keys pass format check but fail database lookup
        assert "Invalid API key" in str(exc_info.value)

    def test_authenticate_nonexistent_key(self):
        """Test authentication with non-existent API key"""
        request = self.factory.get("/")
        fake_key = "sa_" + "x" * 50
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {fake_key}"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid API key" in str(exc_info.value)

    def test_authenticate_inactive_project(self):
        """Test authentication with API key from inactive project"""
        self.project.is_active = False
        self.project.save()

        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.project.public_api_key}"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid API key" in str(exc_info.value)

    def test_authenticate_header_method(self):
        """Test WWW-Authenticate header for 401 responses"""
        request = self.factory.get("/")
        header = self.auth.authenticate_header(request)

        assert header == "Bearer"


@pytest.mark.django_db
class TestPrivateApiKeyAuthentication:
    """Test cases for PrivateApiKeyAuthentication class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.auth = PrivateApiKeyAuthentication()
        self.factory = APIRequestFactory()
        self.project = ProjectFactory()

    def test_authenticate_valid_private_key(self):
        """Test authentication with valid private API key"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.project.private_api_key}"

        user, auth = self.auth.authenticate(request)

        assert user == self.project
        assert auth == self.project.private_api_key

    def test_authenticate_no_authorization_header(self):
        """Test authentication without authorization header"""
        request = self.factory.get("/")

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_invalid_header_format(self):
        """Test authentication with malformed authorization header"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = "InvalidFormat"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid authorization header format" in str(exc_info.value)

    def test_authenticate_wrong_scheme(self):
        """Test authentication with wrong authorization scheme"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Basic {self.project.private_api_key}"

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_invalid_private_key_format(self):
        """Test authentication with invalid private API key format"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer sa_invalid_private_key"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid private API key format" in str(exc_info.value)

    def test_authenticate_public_key_in_private_auth(self):
        """Test that public key doesn't work with private authentication"""
        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.project.public_api_key}"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid private API key format" in str(exc_info.value)

    def test_authenticate_nonexistent_private_key(self):
        """Test authentication with non-existent private API key"""
        request = self.factory.get("/")
        fake_key = "sa_priv_" + "x" * 50
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {fake_key}"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid API key" in str(exc_info.value)

    def test_authenticate_inactive_project(self):
        """Test authentication with private key from inactive project"""
        self.project.is_active = False
        self.project.save()

        request = self.factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.project.private_api_key}"

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid API key" in str(exc_info.value)

    def test_authenticate_header_method(self):
        """Test WWW-Authenticate header for 401 responses"""
        request = self.factory.get("/")
        header = self.auth.authenticate_header(request)

        assert header == "Bearer"


@pytest.mark.django_db
class TestApiKeyAuthenticationAlias:
    """Test that ApiKeyAuthentication is properly aliased to PublicApiKeyAuthentication"""

    def test_alias_functionality(self):
        """Test that ApiKeyAuthentication works as PublicApiKeyAuthentication"""
        public_auth = PublicApiKeyAuthentication()
        alias_auth = ApiKeyAuthentication()

        project = ProjectFactory()
        factory = APIRequestFactory()
        request = factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {project.public_api_key}"

        # Both should work identically
        public_result = public_auth.authenticate(request)
        alias_result = alias_auth.authenticate(request)

        assert public_result == alias_result
        assert public_result[0] == project
        assert public_result[1] == project.public_api_key


@pytest.mark.django_db
class TestAuthenticationSecurity:
    """Security-focused tests for authentication classes"""

    def test_key_isolation(self):
        """Test that public and private keys are properly isolated"""
        project1 = ProjectFactory()

        public_auth = PublicApiKeyAuthentication()
        private_auth = PrivateApiKeyAuthentication()
        factory = APIRequestFactory()

        # Test that project1's public key doesn't work with private auth
        request1 = factory.get("/")
        request1.META["HTTP_AUTHORIZATION"] = f"Bearer {project1.public_api_key}"

        # Should fail with private auth (wrong format)
        with pytest.raises(AuthenticationFailed):
            private_auth.authenticate(request1)

        # Test that project1's private key doesn't work with public auth
        request2 = factory.get("/")
        request2.META["HTTP_AUTHORIZATION"] = f"Bearer {project1.private_api_key}"

        # Should fail with public auth (key not found in public_api_key field)
        with pytest.raises(AuthenticationFailed):
            public_auth.authenticate(request2)

    def test_cross_project_key_validation(self):
        """Test that keys from one project don't work for another"""
        project1 = ProjectFactory()
        project2 = ProjectFactory()

        public_auth = PublicApiKeyAuthentication()
        factory = APIRequestFactory()

        # Use project1's key, should get project1
        request1 = factory.get("/")
        request1.META["HTTP_AUTHORIZATION"] = f"Bearer {project1.public_api_key}"

        user, auth = public_auth.authenticate(request1)
        assert user == project1
        assert user != project2

        # Use project2's key, should get project2
        request2 = factory.get("/")
        request2.META["HTTP_AUTHORIZATION"] = f"Bearer {project2.public_api_key}"

        user, auth = public_auth.authenticate(request2)
        assert user == project2
        assert user != project1

    def test_regenerated_key_invalidates_old_key(self):
        """Test that regenerating keys invalidates the old ones"""
        project = ProjectFactory()
        old_public_key = project.public_api_key
        old_private_key = project.private_api_key

        public_auth = PublicApiKeyAuthentication()
        private_auth = PrivateApiKeyAuthentication()
        factory = APIRequestFactory()

        # Old keys should work before regeneration
        request1 = factory.get("/")
        request1.META["HTTP_AUTHORIZATION"] = f"Bearer {old_public_key}"
        result = public_auth.authenticate(request1)
        assert result is not None

        request2 = factory.get("/")
        request2.META["HTTP_AUTHORIZATION"] = f"Bearer {old_private_key}"
        result = private_auth.authenticate(request2)
        assert result is not None

        # Regenerate keys
        new_keys = project.regenerate_all_api_keys()

        # Old keys should no longer work
        request3 = factory.get("/")
        request3.META["HTTP_AUTHORIZATION"] = f"Bearer {old_public_key}"
        with pytest.raises(AuthenticationFailed):
            public_auth.authenticate(request3)

        request4 = factory.get("/")
        request4.META["HTTP_AUTHORIZATION"] = f"Bearer {old_private_key}"
        with pytest.raises(AuthenticationFailed):
            private_auth.authenticate(request4)

        # New keys should work
        request5 = factory.get("/")
        request5.META["HTTP_AUTHORIZATION"] = f"Bearer {new_keys['public_api_key']}"
        result = public_auth.authenticate(request5)
        assert result[0] == project

        request6 = factory.get("/")
        request6.META["HTTP_AUTHORIZATION"] = f"Bearer {new_keys['private_api_key']}"
        result = private_auth.authenticate(request6)
        assert result[0] == project

    def test_case_sensitive_keys(self):
        """Test that API keys are case-sensitive"""
        project = ProjectFactory()
        public_auth = PublicApiKeyAuthentication()
        factory = APIRequestFactory()

        # Original key should work
        request1 = factory.get("/")
        request1.META["HTTP_AUTHORIZATION"] = f"Bearer {project.public_api_key}"
        result = public_auth.authenticate(request1)
        assert result is not None

        # Uppercase key should fail
        uppercase_key = project.public_api_key.upper()
        request2 = factory.get("/")
        request2.META["HTTP_AUTHORIZATION"] = f"Bearer {uppercase_key}"
        with pytest.raises(AuthenticationFailed):
            public_auth.authenticate(request2)

        # Lowercase key should fail
        lowercase_key = project.public_api_key.lower()
        if lowercase_key != project.public_api_key:  # Only test if different
            request3 = factory.get("/")
            request3.META["HTTP_AUTHORIZATION"] = f"Bearer {lowercase_key}"
            with pytest.raises(AuthenticationFailed):
                public_auth.authenticate(request3)

    def test_empty_and_whitespace_keys(self):
        """Test handling of empty and whitespace-only keys"""
        public_auth = PublicApiKeyAuthentication()
        factory = APIRequestFactory()

        test_cases = [
            "Bearer ",  # Empty key
            "Bearer   ",  # Whitespace key
            "Bearer\t",  # Tab key
            "Bearer\n",  # Newline key
        ]

        for auth_header in test_cases:
            request = factory.get("/")
            request.META["HTTP_AUTHORIZATION"] = auth_header

            with pytest.raises(AuthenticationFailed):
                public_auth.authenticate(request)
