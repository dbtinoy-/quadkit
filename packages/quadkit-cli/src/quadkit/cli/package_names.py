"""Resolve optional Quadkit package and module names at runtime.

The CLI is shared by the complete private workspace and the smaller public
installation. Hard-coding every optional distribution here would make the
public CLI advertise packages that are not part of its release. Entry points
provide the installed package name when an optional provider is present; the
fallback is constructed only when an operator explicitly requests a feature.
"""

from __future__ import annotations

from importlib.metadata import distributions, entry_points

PUBLIC_DISTRIBUTIONS = frozenset(
    {
        "quadkit",
        "quadkit-contracts",
        "quadkit-web",
        "quadkit-testing",
        "quadkit-cli",
    }
)


_PROVIDER_ALIASES = {
    "sql": "database",
    "monitoring": "monitor",
    "notification": "mailer",
    "messaging": "mailer",
}


def provider_available(feature: str) -> bool:
    """Return whether an installed provider advertises ``feature``."""

    names = {feature, _PROVIDER_ALIASES.get(feature, feature)}
    return any(point.name in names for point in entry_points(group="quadkit.providers"))


def package_for(feature: str, default: str | None = None) -> str:
    """Return the installed distribution providing ``feature`` when available."""

    names = {feature, _PROVIDER_ALIASES.get(feature, feature)}
    for point in entry_points(group="quadkit.providers"):
        if point.name in names and point.dist is not None:
            return point.dist.name
    if feature in {"core", "contracts"}:
        return "quadkit" if feature == "core" else "quadkit-contracts"
    if default is not None:
        return default
    return f"quadkit-{feature}"


def packages_for(*features: str) -> list[str]:
    """Return core plus the optional provider distributions that are installed."""

    public_features = {"web", "testing", "resilience", "http"}
    names = ["quadkit"]
    names.extend(
        package_for(feature)
        for feature in features
        if feature in public_features or provider_available(feature)
    )
    return list(dict.fromkeys(names))


def module_for(feature: str, suffix: str = "") -> str:
    """Build an optional module path without embedding a private name."""

    module = f"quadkit.{feature}"
    return f"{module}.{suffix}" if suffix else module


def installed_quadkit_distributions() -> tuple[str, ...]:
    """Return installed Quadkit distributions for version and diagnostics."""

    names = {
        str(dist.metadata["Name"])
        for dist in distributions()
        if dist.metadata.get("Name", "").lower().startswith("quadkit")
    }
    return tuple(sorted(names))
