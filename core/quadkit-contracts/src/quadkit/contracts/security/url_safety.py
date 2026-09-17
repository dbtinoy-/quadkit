"""SSRF URL-safety primitive shared by every outbound HTTP consumer.

Pure standard-library only (``ipaddress``, ``socket``, ``urllib.parse``) so
that any extension package — including ``the optional provider``, ``the optional provider``
and ``the optional provider``, which may not import ``quadkit.security`` — can
consume it directly. Keep this file stdlib-only (import-linter Contract 1).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import ipaddress
import socket
import urllib.parse

_PRIVATE_IPV4_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.IPv4Network("0.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("100.64.0.0/10"),
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("224.0.0.0/4"),
    ipaddress.IPv4Network("240.0.0.0/4"),
)

_PRIVATE_IPV6_NETWORKS: tuple[ipaddress.IPv6Network, ...] = (
    ipaddress.IPv6Network("::/128"),
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("fc00::/7"),
    ipaddress.IPv6Network("fe80::/10"),
)

HostResolver = Callable[[str], Sequence[ipaddress.IPv4Address | ipaddress.IPv6Address]]


def resolve_hostname(
    hostname: str,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a hostname to all its address records via the system resolver.

    Args:
        hostname: DNS name to resolve.

    Returns:
        List of resolved addresses (A/AAAA records).

    Raises:
        OSError: If the hostname cannot be resolved.
    """
    infos = socket.getaddrinfo(
        hostname, None, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
    )
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for _family, _stype, _proto, _canonname, sockaddr in infos:
        try:
            addresses.append(ipaddress.ip_address(sockaddr[0]))
        except ValueError:
            continue
    return addresses


def collect_safe_addresses(
    url: str,
    *,
    resolver: HostResolver | None = None,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Return the validated, publicly reachable address set for ``url``.

    The companion of :func:`is_safe_url_for_request` that also returns the
    validated addresses so callers can PIN the connection to exactly the
    addresses this function approved. This closes the check-then-connect
    DNS-rebinding window: an attacker controlling DNS cannot answer a
    public IP at validation time and a private one at connect time, because
    the connector only ever uses the pinned (validated) set.

    Checks the scheme (http/https only), rejects literal private/reserved IP
    hostnames, and — for DNS hostnames — resolves via ``resolver`` (defaults
    to the system ``getaddrinfo``) and rejects when ANY resolved address is
    private/reserved. Fails closed: an unresolvable or empty resolution is
    rejected.

    Args:
        url: Candidate absolute URL.
        resolver: Optional hostname resolver for hermetic tests. Defaults to
            the system resolver via :func:`resolve_hostname`.

    Returns:
        The validated address list (never empty).

    Raises:
        ValueError: When the URL is malformed, non-http(s), hostless,
            unresolvable, or resolves (even partially) to a private/reserved
            address.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError as exc:
        raise ValueError(f"Malformed URL: {url!r}") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError(f"URL scheme not allowed: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"URL has no hostname: {url!r}")

    hostname = hostname.strip("[]")
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        return _collect_public_addresses(hostname, resolver)

    if _is_private(addr):
        raise ValueError(f"Literal IP host is private/reserved: {hostname}")
    return [addr]


def _collect_public_addresses(
    hostname: str,
    resolver: HostResolver | None,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve *hostname* and return its addresses when all are public."""
    try:
        addresses = (
            resolve_hostname(hostname) if resolver is None else resolver(hostname)
        )
    except OSError as exc:
        raise ValueError(f"Host could not be resolved: {hostname!r}") from exc
    if not addresses:
        raise ValueError(f"Host resolved to no addresses: {hostname!r}")
    private = [str(a) for a in addresses if _is_private(a)]
    if private:
        raise ValueError(
            f"Host resolves to private/reserved address(es): {', '.join(private)}"
        )
    return list(addresses)


def is_safe_url_for_request(
    url: str,
    *,
    resolver: HostResolver | None = None,
) -> bool:
    """Return False when requesting ``url`` could reach a private/reserved host.

    Boolean facade over :func:`collect_safe_addresses`; see that function
    for the full check description.

    Args:
        url: Candidate absolute URL.
        resolver: Optional hostname resolver for hermetic tests. Defaults to
            the system resolver via :func:`resolve_hostname`.

    Returns:
        True only when a request to ``url`` cannot reach a private/reserved IP.
    """
    try:
        collect_safe_addresses(url, resolver=resolver)
    except ValueError:
        return False
    return True


def _hostname_is_public(hostname: str, resolver: HostResolver | None) -> bool:
    try:
        addresses = (
            resolve_hostname(hostname) if resolver is None else resolver(hostname)
        )
    except OSError:
        return False
    if not addresses:
        return False
    return all(not _is_private(address) for address in addresses)


def _is_private(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> bool:
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    if isinstance(addr, ipaddress.IPv4Address):
        return any(addr in network for network in _PRIVATE_IPV4_NETWORKS)
    return any(addr in network for network in _PRIVATE_IPV6_NETWORKS)


__all__ = ["HostResolver", "is_safe_url_for_request", "resolve_hostname"]
