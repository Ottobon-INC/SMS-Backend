"""Authentication and access-context exceptions."""


class AuthenticationError(Exception):
    """Base authentication-domain error."""


class CredentialStoreNotConfiguredError(AuthenticationError):
    """Raised when password login is requested before credential storage exists."""


class InvalidLoginCredentialsError(AuthenticationError):
    """Raised when username/password credentials are invalid."""


class SignupRequestStoreNotConfiguredError(AuthenticationError):
    """Raised when signup requests are requested before storage exists."""


class ApplicationUserNotMappedError(AuthenticationError):
    """Raised when an authenticated principal has no sms_users profile."""


class ApplicationUserInactiveError(AuthenticationError):
    """Raised when the mapped application user is not active for login."""


class NoActiveAssignmentError(AuthenticationError):
    """Raised when the user has no valid access assignment."""


class InvalidAccessContextError(AuthenticationError):
    """Raised when a requested assignment cannot be used by the user."""


class PermissionDeniedError(AuthenticationError):
    """Raised when an operation is outside the validated context."""
