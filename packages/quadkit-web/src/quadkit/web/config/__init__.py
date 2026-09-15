"""Web configuration facade.

Re-exports every public name so that
``from quadkit.web.config import X`` continues to work unchanged.
"""

from quadkit.web.config.api_docs import (
    APIDocsConfig as APIDocsConfig,
)
from quadkit.web.config.api_docs import (
    StaticFileConfig as StaticFileConfig,
)
from quadkit.web.config.provider import WebProviderConfig as WebProviderConfig
from quadkit.web.config.rate_limit import (
    RateLimitConfig as RateLimitConfig,
)
from quadkit.web.config.rate_limit import (
    RateLimitRuleConfig as RateLimitRuleConfig,
)
from quadkit.web.config.rate_limit import (
    RoleGuardConfig as RoleGuardConfig,
)
from quadkit.web.config.rate_limit import (
    RoleGuardRuleConfig as RoleGuardRuleConfig,
)
from quadkit.web.config.server import ServerConfig as ServerConfig
from quadkit.web.config.top_level import WebConfig as WebConfig
from quadkit.web.security.config import (
    CORSConfig as CORSConfig,
)
from quadkit.web.security.config import (
    CrossOriginConfig as CrossOriginConfig,
)
from quadkit.web.security.config import (
    CSPConfig as CSPConfig,
)
from quadkit.web.security.config import (
    CSRFConfig as CSRFConfig,
)
from quadkit.web.security.config import (
    HSTSConfig as HSTSConfig,
)
from quadkit.web.security.config import (
    SecurityConfig as SecurityConfig,
)


def __getattr__(name: str) -> object:  # noqa: ANN001
    if name == "VersioningStrategy":
        from quadkit.web.routing.versioning import VersioningStrategy

        return VersioningStrategy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CORSConfig",
    "CrossOriginConfig",
    "CSPConfig",
    "CSRFConfig",
    "HSTSConfig",
    "RateLimitConfig",
    "RateLimitRuleConfig",
    "RoleGuardConfig",
    "RoleGuardRuleConfig",
    "SecurityConfig",
    "ServerConfig",
    "StaticFileConfig",
    "VersioningStrategy",
    "WebConfig",
    "WebProviderConfig",
]
