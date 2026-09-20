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


_DISTRIBUTION_PREFIX = "quadkit-"


def _feature_names(feature: str) -> tuple[str, ...]:
    """Return the feature name first, then its provider alias."""

    alias = _PROVIDER_ALIASES.get(feature)
    if alias is None or alias == feature:
        return (feature,)
    return (feature, alias)


def provider_packages() -> dict[str, str]:
    """Return every feature this installation provides, with its distribution.

    Provider plugins advertise their feature through the ``quadkit.providers``
    entry point. Packages that register a module (``quadkit.modules``) instead
    of a provider class are picked up from their installed distribution name
    (``quadkit-<feature>``), so ``quadkit add`` and the template gating offer
    every feature that is actually installed.
    """

    packages: dict[str, str] = {}
    for point in entry_points(group="quadkit.providers"):
        if point.dist is not None:
            packages.setdefault(point.name, point.dist.name)
    for dist in distributions():
        name = dist.metadata["Name"] or ""
        if not name.lower().startswith(_DISTRIBUTION_PREFIX):
            continue
        packages.setdefault(name[len(_DISTRIBUTION_PREFIX) :].lower(), name)
    return packages


def provider_available(feature: str) -> bool:
    """Return whether ``feature`` is provided in this installation."""

    packages = provider_packages()
    return any(name in packages for name in _feature_names(feature))


def package_for(feature: str, default: str | None = None) -> str:
    """Return the installed distribution providing ``feature`` when available."""

    packages = provider_packages()
    for name in _feature_names(feature):
        if name in packages:
            return packages[name]
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
        if (dist.metadata["Name"] or "").lower().startswith("quadkit")
    }
    return tuple(sorted(names))
