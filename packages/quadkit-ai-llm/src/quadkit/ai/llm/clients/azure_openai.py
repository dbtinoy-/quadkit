"""Azure OpenAI LLM client for the Quadkit LLM routing system.

Extends :class:`~quadkit.ai.llm.clients.openai.OpenAIClient` to target the
Azure OpenAI Service endpoint instead of ``api.openai.com``.

Azure OpenAI uses deployment-specific URLs of the form::

    https://{resource}.openai.azure.com/openai/deployments/{deployment}/

and requires an ``api-version`` query parameter on every request, so this
client overrides the ``AsyncOpenAI`` constructor to point at the correct base
URL and injects the required headers.

Configuration is sourced from ``ClientConfig.extra``:

* ``azure_resource`` — Azure resource name (required)
* ``azure_deployment`` — deployment / model name inside the resource (required)
* ``azure_api_version`` — API version string (default: ``2024-02-15-preview``)

``ClientConfig.api_key`` must carry the Azure OpenAI API key (or leave it as
``None`` to fall back on Azure AD credential injection through the ``openai``
SDK's ``azure_ad_token_provider`` mechanism — not wired here by default).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.ai.llm.clients.openai import OpenAIClient
from quadkit.contracts.core import HealthCheckResult, HealthStatus

if TYPE_CHECKING:
    from quadkit.ai.llm.config import ClientConfig

__all__ = ["AzureOpenAIClient"]

_DEFAULT_API_VERSION = "2024-02-15-preview"


class AzureOpenAIClient(OpenAIClient):
    """Azure OpenAI Service client extending the core :class:`OpenAIClient`.

    Routes all requests through the Azure OpenAI REST endpoint rather than
    the public OpenAI API.  All streaming, tool-calling, and retry semantics
    are inherited from :class:`OpenAIClient` unchanged.

    Args:
        config: LLM configuration.  ``config.extra`` must contain
            ``azure_resource`` and ``azure_deployment``.  May optionally
            contain ``azure_api_version``.
    """

    def __init__(self, config: ClientConfig) -> None:
        """Initialise the Azure OpenAI client.

        Builds the deployment-scoped Azure endpoint URL and configures the
        ``AsyncAzureOpenAI`` client from the ``openai`` SDK.

        Args:
            config: LLM configuration including Azure-specific ``extra`` keys.

        Raises:
            ImportError: If the ``openai`` package is not installed.
            ValueError: If ``azure_resource`` or ``azure_deployment`` are
                missing from ``config.extra``.
        """
        extra: dict[str, Any] = config.extra or {}
        resource: str = extra.get("azure_resource", "")
        deployment: str = extra.get("azure_deployment", "") or config.model
        api_version: str = extra.get("azure_api_version", _DEFAULT_API_VERSION)

        if not resource:
            raise ValueError(
                "AzureOpenAIClient requires 'azure_resource' in ClientConfig.extra"
            )
        if not deployment:
            raise ValueError(
                "AzureOpenAIClient requires 'azure_deployment' in ClientConfig.extra "
                "or a non-empty config.model"
            )

        self._azure_resource = resource
        self._azure_deployment = deployment
        self._azure_api_version = api_version

        # Patch config to use the Azure endpoint so AbstractLLMClient metrics
        # carry the correct base URL.
        azure_base = (
            f"https://{resource}.openai.azure.com/openai/deployments/{deployment}"
        )
        patched = config.model_copy(
            update={"api_base": azure_base, "model": deployment}
        )

        try:
            from openai import AsyncAzureOpenAI
        except ImportError as exc:
            raise ImportError(
                "AzureOpenAIClient requires the 'openai' package. "
                "Install with: pip install quadkit-ai-llm[openai]"
            ) from exc

        # Call AbstractLLMClient.__init__ directly, bypassing OpenAIClient.__init__,
        # so we can build the Azure client instead of the public OpenAI client.
        from quadkit.ai.llm.clients.base import AbstractLLMClient

        AbstractLLMClient.__init__(self, config=patched)

        api_key = config.api_key.get_secret_value() if config.api_key else None
        self.client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=f"https://{resource}.openai.azure.com",
            azure_deployment=deployment,
            api_version=api_version,
            timeout=config.timeout,
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight health check against the Azure deployment.

        Attempts to list models from the Azure endpoint as a connectivity
        probe.  A successful response (even empty) returns HEALTHY.

        Args:
            timeout: Informational — the underlying client timeout applies.

        Returns:
            Structured :class:`~quadkit.contracts.core.health.HealthCheckResult`.
        """
        try:
            await self.client.models.list()
        except Exception as exc:  # noqa: BLE001 - transport/SDK errors are provider-specific
            return HealthCheckResult(
                component="llm.azure_openai",
                status=HealthStatus.UNHEALTHY,
                error=f"Provider health check failed ({type(exc).__name__})",
            )

        return HealthCheckResult(
            component="llm.azure_openai",
            status=HealthStatus.HEALTHY,
            details={
                "resource": self._azure_resource,
                "deployment": self._azure_deployment,
                "api_version": self._azure_api_version,
            },
        )
