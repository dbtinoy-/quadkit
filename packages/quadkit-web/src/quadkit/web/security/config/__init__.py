"""Web security configuration facade.

Re-exports every public name so that
``from quadkit.web.security.config import X`` continues to work unchanged.
"""

from quadkit.web.security.config.cors import CORSConfig as CORSConfig
from quadkit.web.security.config.csp import CSPConfig as CSPConfig
from quadkit.web.security.config.csrf import CSRFConfig as CSRFConfig
from quadkit.web.security.config.headers import (
    CrossOriginConfig as CrossOriginConfig,
)
from quadkit.web.security.config.headers import (
    HSTSConfig as HSTSConfig,
)
from quadkit.web.security.config.headers import (
    SecurityHeadersConfig as SecurityHeadersConfig,
)
from quadkit.web.security.config.top_level import SecurityConfig as SecurityConfig

__all__ = [
    "CORSConfig",
    "CSPConfig",
    "CSRFConfig",
    "CrossOriginConfig",
    "HSTSConfig",
    "SecurityConfig",
    "SecurityHeadersConfig",
]
