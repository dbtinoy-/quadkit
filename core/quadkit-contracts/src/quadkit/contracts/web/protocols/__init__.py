"""HTTP web protocol definitions.

Structural protocols for the HTTP request/response lifecycle, middleware,
rate limiting, exception filtering, and web provider integration.
"""

from __future__ import annotations

from quadkit.contracts.core.middleware import (
    ExceptionFilterChainProtocol as ExceptionFilterChainProtocol,
)
from quadkit.contracts.web.protocols.app import (
    BackgroundTaskRunnerProtocol as BackgroundTaskRunnerProtocol,
)
from quadkit.contracts.web.protocols.app import (
    ConnectionManagerProtocol as ConnectionManagerProtocol,
)
from quadkit.contracts.web.protocols.app import (
    CRUDServiceProtocol as CRUDServiceProtocol,
)
from quadkit.contracts.web.protocols.app import (
    CSRFProtectionProtocol as CSRFProtectionProtocol,
)
from quadkit.contracts.web.protocols.app import (
    HTTPApplicationProtocol as HTTPApplicationProtocol,
)
from quadkit.contracts.web.protocols.app import (
    WebContributorProtocol as WebContributorProtocol,
)
from quadkit.contracts.web.protocols.app import (
    WebProviderProtocol as WebProviderProtocol,
)
from quadkit.contracts.web.protocols.http import (
    CORSPolicyProtocol as CORSPolicyProtocol,
)
from quadkit.contracts.web.protocols.http import (
    HttpRequestLoggerProtocol as HttpRequestLoggerProtocol,
)
from quadkit.contracts.web.protocols.http import RequestProtocol as RequestProtocol
from quadkit.contracts.web.protocols.http import (
    ResponseFactoryProtocol as ResponseFactoryProtocol,
)
from quadkit.contracts.web.protocols.http import ResponseProtocol as ResponseProtocol
from quadkit.contracts.web.protocols.http import (
    WebRateLimiterProtocol as WebRateLimiterProtocol,
)
from quadkit.contracts.web.protocols.middleware import (
    ExceptionFilterProtocol as ExceptionFilterProtocol,
)
from quadkit.contracts.web.protocols.middleware import (
    WebMiddlewareProtocol as WebMiddlewareProtocol,
)

__all__ = [
    "BackgroundTaskRunnerProtocol",
    "CORSPolicyProtocol",
    "CRUDServiceProtocol",
    "CSRFProtectionProtocol",
    "ConnectionManagerProtocol",
    "ExceptionFilterChainProtocol",
    "ExceptionFilterProtocol",
    "HTTPApplicationProtocol",
    "HttpRequestLoggerProtocol",
    "RequestProtocol",
    "ResponseFactoryProtocol",
    "ResponseProtocol",
    "WebContributorProtocol",
    "WebMiddlewareProtocol",
    "WebProviderProtocol",
    "WebRateLimiterProtocol",
]
