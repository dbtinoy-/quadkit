"""OAuth provider config helpers for provider presets.

Provider configurations are declared under ``auth.oauth2_providers`` in
``application.yaml`` and are loaded by the config system.  Call
:func:`detect_oauth_providers_from_config` to filter a pre-loaded
:attr:`~quadkit.auth.config.AuthConfig.oauth2_providers` mapping before
passing it to a provider.
"""

from __future__ import annotations


def detect_oauth_providers_from_config(
    oauth2_providers: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Return valid OAuth2 providers from a pre-loaded config mapping.

    This is the config-based replacement for env-variable auto-detection.
    Providers are declared under ``auth.oauth2_providers`` in
    ``application.yaml`` (or via the ``QK_AUTH__OAUTH2_PROVIDERS__*``
    env-var hierarchy processed by the config system), so no direct
    ``os.environ`` reads are needed here.

    Args:
        oauth2_providers: Raw provider mapping from
            :attr:`~quadkit.auth.config.AuthConfig.oauth2_providers`.

    Returns:
        A copy of the mapping filtered to non-empty entries.
    """
    return {name: cfg for name, cfg in oauth2_providers.items() if name and cfg}


__all__ = [
    "detect_oauth_providers_from_config",
]
