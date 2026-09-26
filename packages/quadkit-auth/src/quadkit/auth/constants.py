"""Constants for quadkit-auth."""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__ = importlib.metadata.version("quadkit-auth")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"

# -- Environment Variable Prefixes -------------------------------------------

ENV_PREFIX: str = "QK_AUTH__"
ENV_NESTED_DELIMITER: str = "__"

# -- Token Defaults ----------------------------------------------------------

DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
DEFAULT_TOKEN_ALGORITHM: str = "HS256"  # noqa: S105  # config default, not a credential
DEFAULT_TOKEN_TYPE: str = "Bearer"  # noqa: S105  # config default, not a credential

# Grace period (seconds) during which tokens signed by a rotated-out key
# remain accepted. Prevents immediate user logout on rotation.
DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS: int = 3600

# -- Password Policy Defaults ------------------------------------------------

DEFAULT_MIN_PASSWORD_LENGTH: int = 8
DEFAULT_MAX_PASSWORD_LENGTH: int = 128
DEFAULT_PASSWORD_HASH_ROUNDS: int = 12

# -- Auth Endpoint Paths -----------------------------------------------------

# The two routes this package serves itself. They must appear in the
# middleware's exclusion list: the auth middleware runs before routing, so a
# login route that is not exempt 401s every caller and no credential could
# ever satisfy it. Keeping the paths here, next to the controller that serves
# them, is what stops the exemption list and the route table drifting apart.
AUTH_LOGIN_PATH: str = "/auth/login"
AUTH_REGISTER_PATH: str = "/auth/register"

# Everything the auth middleware skips by default. The login/register pair is
# unauthenticated by definition; the docs paths are static assets; health is
# a liveness probe that must not require a session.
DEFAULT_EXCLUDED_PATHS: tuple[str, ...] = (
    AUTH_LOGIN_PATH,
    AUTH_REGISTER_PATH,
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
)

# -- Session Defaults --------------------------------------------------------

DEFAULT_SESSION_TIMEOUT_MINUTES: int = 60
DEFAULT_SESSION_COOKIE_NAME: str = "session"
DEFAULT_SESSION_COOKIE_SECURE: bool = True
DEFAULT_SESSION_COOKIE_HTTPONLY: bool = True

# -- MFA Defaults ------------------------------------------------------------

DEFAULT_TOTP_DIGITS: int = 6
DEFAULT_TOTP_INTERVAL: int = 30
DEFAULT_TOTP_VALID_WINDOW: int = 1
DEFAULT_MFA_ISSUER: str = "quadkit"
DEFAULT_BACKUP_CODE_COUNT: int = 10
DEFAULT_BACKUP_CODE_LENGTH: int = 8
DEFAULT_MAX_CHALLENGE_ATTEMPTS: int = 3

__all__ = [
    "AUTH_LOGIN_PATH",
    "AUTH_REGISTER_PATH",
    "DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "DEFAULT_BACKUP_CODE_COUNT",
    "DEFAULT_BACKUP_CODE_LENGTH",
    "DEFAULT_EXCLUDED_PATHS",
    "DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS",
    "DEFAULT_MAX_CHALLENGE_ATTEMPTS",
    "DEFAULT_MAX_PASSWORD_LENGTH",
    "DEFAULT_MFA_ISSUER",
    "DEFAULT_MIN_PASSWORD_LENGTH",
    "DEFAULT_PASSWORD_HASH_ROUNDS",
    "DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS",
    "DEFAULT_SESSION_COOKIE_HTTPONLY",
    "DEFAULT_SESSION_COOKIE_NAME",
    "DEFAULT_SESSION_COOKIE_SECURE",
    "DEFAULT_SESSION_TIMEOUT_MINUTES",
    "DEFAULT_TOKEN_ALGORITHM",
    "DEFAULT_TOKEN_TYPE",
    "DEFAULT_TOTP_DIGITS",
    "DEFAULT_TOTP_INTERVAL",
    "DEFAULT_TOTP_VALID_WINDOW",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
]
