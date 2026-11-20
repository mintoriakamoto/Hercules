"""URL safety checks — blocks requests to private/internal network addresses.

Prevents SSRF (Server-Side Request Forgery) where a malicious prompt or
skill could trick the agent into fetching internal resources like cloud
metadata endpoints (169.254.169.254), localhost services, or private
network hosts.

The check can be globally disabled via ``security.allow_private_urls: true``
in config.yaml for environments where DNS resolves external domains to
private/benchmark-range IPs (OpenWrt routers, corporate proxies, VPNs
that use 198.18.0.0/15 or 100.64.0.0/10).  Even when disabled, cloud
metadata hostnames (metadata.google.internal, 169.254.169.254) are
**always** blocked — those are never legitimate agent targets.

Limitations (documented, not fixable at pre-flight level):
  - DNS rebinding (TOCTOU): an attacker-controlled DNS server with TTL=0
    can return a public IP for the check, then a private IP for the actual
    connection. Fixing this requires connection-level validation (e.g.
    Python's Champion library or an egress proxy like Stripe's Smokescreen).
  - Redirect-based bypass is mitigated by httpx event hooks that re-validate
    each redirect target in vision_tools, gateway platform adapters, and
    media cache helpers. Web tools use third-party SDKs (Firecrawl/Tavily)
    where redirect handling is on their servers.
"""

import ipaddress
import logging
import os
import re
import socket
from typing import Any, Iterable, Optional
from urllib.parse import (
    parse_qsl,
    quote,
    unquote,
    urljoin,
    urlparse,
    urlsplit,
    urlunsplit,
)

from utils import is_truthy_value

logger = logging.getLogger(__name__)


def normalize_url_for_request(url: str) -> str:
    """Return an ASCII-safe HTTP URL for Hercules-owned URL tools.

    Browsers and HTTP clients expect URIs, but users and models often provide
    IRIs such as ``https://wttr.in/Köln``.  Preserve URL syntax and existing
    percent escapes while encoding non-ASCII host/path/query/fragment text.
    This is intentionally for URL tool inputs only; arbitrary shell commands
    must not be rewritten.
    """
    if not isinstance(url, str):
        return url

    raw = url.strip()
    if not raw:
        return raw

    # Models sometimes emit otherwise valid URLs with whitespace between the
    # scheme separator and authority (``https:// docs.example``). That position
    # is never meaningful in HTTP(S) URLs, and repairing it before parsing keeps
    # web tools from failing on a formatting artifact while leaving path/query
    # whitespace to the normal percent-encoding path below.
    raw = re.sub(r"^([A-Za-z][A-Za-z0-9+.-]*://)\s+", r"\1", raw)

    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw

    if parsed.scheme.lower() not in {"http", "https"}:
        return raw

    netloc = parsed.netloc
    hostname = parsed.hostname
    if hostname:
        try:
            ascii_host = hostname.encode("idna").decode("ascii")
        except UnicodeError:
            ascii_host = hostname
        if ascii_host != hostname:
            netloc = netloc.replace(hostname, ascii_host, 1)

    path = quote(parsed.path, safe="/%:@!$&'()*+,;=")
    query = quote(parsed.query, safe="/%:@!$&'()*+,;=?")
    fragment = quote(parsed.fragment, safe="/%:@!$&'()*+,;=?")

    return urlunsplit((parsed.scheme, netloc, path, query, fragment))


# Query parameter names that are unambiguously credential-bearing. Kept
# deliberately narrow: bare English words that double as normal page facets
# (``code`` on promo/challenge pages, ``key``/``auth``/``session``/``sig`` as
# search or routing params) are intentionally EXCLUDED to avoid blocking
# ordinary browsing. Prefix-based token redaction (``is_safe_url``) still
# catches recognizable vendor key shapes; this set is the belt-and-suspenders
# for opaque secrets that carry an explicit credential-named parameter.
_SENSITIVE_QUERY_PARAM_NAMES = frozenset({
    "access_token",
    "api_key",
    "apikey",
    "auth_token",
    "authorization",
    "awsaccesskeyid",
    "client_secret",
    "credential",
    "credentials",
    "jwt",
    "password",
    "passwd",
    "secret",
    "session_id",
    "signature",
    "token",
    "x_amz_security_token",
    "x_amz_signature",
    "x-amz-security-token",
    "x-amz-signature",
})


def sensitive_query_param_name(url: str) -> Optional[str]:
    """Return the first sensitive query parameter name in ``url``, if any.

    Used before handing URLs to third-party fetch/browser backends. Prefix-based
    token redaction catches known credential shapes; this catches opaque magic
    links, OAuth codes, signed URL signatures, and custom ``?token=...`` values
    that do not have a recognizable vendor prefix.
    """
    if not isinstance(url, str) or "?" not in url:
        return None
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.query:
        return None
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if value and unquote(key).lower() in _SENSITIVE_QUERY_PARAM_NAMES:
            return key
    return None


def has_sensitive_query_params(url: str) -> bool:
    """Return True when ``url`` carries likely credential-bearing query params."""
    return sensitive_query_param_name(url) is not None


# Hostnames that should always be blocked regardless of IP resolution
# or any config toggle.  These are cloud metadata endpoints that an
# attacker could use to steal instance credentials.
_BLOCKED_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata.goog",
})

# IPs and networks that should always be blocked regardless of the
# allow_private_urls toggle.  These are cloud metadata / credential
# endpoints — the #1 SSRF target — and the link-local range where
# they all live.
#
# IPv4-mapped IPv6 variants are included because DNS resolvers may
# return ``::ffff:x.x.x.x`` for IPv4-only hosts, and Python's
# ipaddress module treats these as distinct from the plain IPv4
# address (they won't match ``ip in frozenset`` or ``ip in network``).
_ALWAYS_BLOCKED_IPS = frozenset({
    ipaddress.ip_address("169.254.169.254"),  # AWS/GCP/Azure/DO/Oracle metadata
    ipaddress.ip_address("169.254.170.2"),  # AWS ECS task metadata (task IAM creds)
    ipaddress.ip_address("169.254.169.253"),  # Azure IMDS wire server
    ipaddress.ip_address("fd00:ec2::254"),  # AWS metadata (IPv6)
    ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud metadata
    # IPv4-mapped IPv6 variants — same endpoints reachable via ::ffff:x.x.x.x
    ipaddress.ip_address("::ffff:169.254.169.254"),
    ipaddress.ip_address("::ffff:169.254.170.2"),
    ipaddress.ip_address("::ffff:169.254.169.253"),
    ipaddress.ip_address("::ffff:100.100.100.200"),
})
_ALWAYS_BLOCKED_NETWORKS = (
    ipaddress.ip_network(
        "169.254.0.0/16"
    ),  # Entire link-local range (no legit agent target)
    ipaddress.ip_network("::ffff:169.254.0.0/112"),  # IPv4-mapped link-local range
)

# Exact HTTPS hostnames allowed to resolve to private/benchmark-space IPs.
# This is intentionally narrow: QQ media downloads can legitimately resolve
# to 198.18.0.0/15 behind local proxy/benchmark infrastructure.
_TRUSTED_PRIVATE_IP_HOSTS = frozenset({
    "multimedia.nt.qq.com.cn",
})

# 100.64.0.0/10 (CGNAT / Shared Address Space, RFC 6598) is NOT covered by
# ipaddress.is_private — it returns False for both is_private and is_global.
# Must be blocked explicitly. Used by carrier-grade NAT, Tailscale/WireGuard
# VPNs, and some cloud internal networks.
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

# ---------------------------------------------------------------------------
# Global toggle: allow private/internal IP resolution
# ---------------------------------------------------------------------------
# Cached after first read so we don't hit the filesystem on every URL check.
_allow_private_resolved = False
_cached_allow_private: bool = False


def _global_allow_private_urls() -> bool:
    """Return True when the user has opted out of private-IP blocking.

    Checks (in priority order):
    1. ``HERCULES_ALLOW_PRIVATE_URLS`` env var  (``true``/``1``/``yes``)
    2. ``security.allow_private_urls`` in config.yaml
    3. ``browser.allow_private_urls`` in config.yaml  (legacy / backward compat)

    Result is cached for the process lifetime.
    """
    global _allow_private_resolved, _cached_allow_private
    if _allow_private_resolved:
        return _cached_allow_private

    _allow_private_resolved = True
    _cached_allow_private = False  # safe default

    # 1. Env var override (highest priority)
    env_val = os.getenv("HERCULES_ALLOW_PRIVATE_URLS", "").strip().lower()
    if env_val in {"true", "1", "yes"}:
        _cached_allow_private = True
        return _cached_allow_private
    if env_val in {"false", "0", "no"}:
        # Explicit false — don't fall through to config
        return _cached_allow_private

    # 2. Config file
    try:
        from hercules_cli.config import read_raw_config

        cfg = read_raw_config()
        # security.allow_private_urls (preferred)
        sec = cfg.get("security", {})
        if isinstance(sec, dict) and is_truthy_value(
            sec.get("allow_private_urls"), default=False
        ):
            _cached_allow_private = True
            return _cached_allow_private
        # browser.allow_private_urls (legacy fallback)
        browser = cfg.get("browser", {})
        if isinstance(browser, dict) and is_truthy_value(
            browser.get("allow_private_urls"), default=False
        ):
            _cached_allow_private = True
            return _cached_allow_private
    except Exception as exc:
        # Config unavailable or unreadable (e.g. tests, early import) — keep
        # the safe default (private URLs blocked) rather than crashing.
        logger.debug("allow_private_urls config read failed: %s", exc)

    return _cached_allow_private


def _reset_allow_private_cache() -> None:
    """Reset the cached toggle — only for tests."""
    global _allow_private_resolved, _cached_allow_private
    _allow_private_resolved = False
    _cached_allow_private = False


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if the IP should be blocked for SSRF protection."""
    # IPv4-mapped IPv6 addresses (``::ffff:x.x.x.x``) should be checked
    # by their embedded IPv4 address, not as IPv6
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        embedded_ip = ip.ipv4_mapped
        return (
            embedded_ip.is_private
            or embedded_ip.is_loopback
            or embedded_ip.is_link_local
            or embedded_ip.is_reserved
            or embedded_ip.is_multicast
            or embedded_ip.is_unspecified
            or embedded_ip in _CGNAT_NETWORK
        )

    # Standard IPv4/IPv6 address checking
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    # CGNAT range not covered by is_private
    if ip in _CGNAT_NETWORK:
        return True
    return False


def _parse_resolved_ip(
    ip_str: Any,
) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Parse an address string from ``getaddrinfo``, stripping any IPv6 scope.

    ``ipaddress.ip_address`` rejects scope-ID suffixes such as ``fe80::1%eth0``,
    so the scope must be removed before classification — skipping such an
    address would let a scoped link-local/loopback result bypass the guard.
    Returns ``None`` when the address is still unparseable.
    """
    if not isinstance(ip_str, str):
        return None
    candidate = ip_str.split("%", 1)[0].strip()
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _is_always_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True for cloud-metadata IPs and the link-local range."""
    if ip in _ALWAYS_BLOCKED_IPS:
        return True
    if any(ip in net for net in _ALWAYS_BLOCKED_NETWORKS if ip.version == net.version):
        return True
    # Also classify IPv4-mapped IPv6 by its embedded IPv4 address.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        embedded = ip.ipv4_mapped
        if embedded in _ALWAYS_BLOCKED_IPS:
            return True
        if any(
            embedded in net
            for net in _ALWAYS_BLOCKED_NETWORKS
            if embedded.version == net.version
        ):
            return True
    return False


def _parse_target(url: str) -> tuple[str, str]:
    """Return ``(scheme, hostname)`` normalised to lower case, or None."""
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").strip().lower()
    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    return scheme, hostname


def _resolve(hostname: str) -> list:
    return socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)


def is_always_blocked_url(url: str) -> bool:
    """Return True when ``url`` targets a cloud-metadata / link-local endpoint.

    This is the unconditional floor: it ignores ``allow_private_urls`` and is
    deliberately narrower than :func:`is_safe_url` — ordinary private,
    loopback and CGNAT targets are NOT reported here.  Blocks by hostname
    (``metadata.google.internal`` etc.), by literal IP, and by any resolved
    address in the always-blocked set.  Malformed URLs and DNS failures do
    not claim always-blocked status; the caller's ordinary fail-closed path
    (``is_safe_url``) handles those.
    """
    try:
        if not isinstance(url, str) or not url.strip():
            return False
        _scheme, hostname = _parse_target(url)
        if not hostname:
            return False

        if hostname in _BLOCKED_HOSTNAMES:
            logger.warning("Blocked request to cloud metadata hostname: %s", hostname)
            return True

        literal = _parse_resolved_ip(hostname)
        if literal is not None:
            if _is_always_blocked_ip(literal):
                logger.warning("Blocked request to cloud metadata IP: %s", hostname)
                return True
            return False

        try:
            addr_info = _resolve(hostname)
        except (socket.gaierror, OSError, UnicodeError):
            return False

        for _family, _type, _proto, _canon, sockaddr in addr_info:
            ip = _parse_resolved_ip(sockaddr[0] if sockaddr else None)
            if ip is not None and _is_always_blocked_ip(ip):
                logger.warning(
                    "Blocked request to %s: resolves to cloud metadata IP %s",
                    hostname,
                    ip,
                )
                return True
        return False
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Always-blocked URL check error for %s: %s", url, exc)
        return False


def _allows_private_ip_resolution(hostname: str, scheme: str) -> bool:
    """Return True when a trusted HTTPS hostname may bypass IP-class blocking."""
    return scheme == "https" and hostname in _TRUSTED_PRIVATE_IP_HOSTS


def _precheck(url: str) -> tuple[Optional[bool], str, str]:
    """Run the resolution-independent part of the SSRF check.

    Returns ``(verdict, scheme, hostname)``.  ``verdict`` is ``False`` when
    the URL is rejected outright, ``None`` when DNS resolution is still
    needed to decide.
    """
    if not isinstance(url, str) or not url.strip():
        return False, "", ""
    scheme, hostname = _parse_target(url)
    if scheme not in {"http", "https"}:
        logger.warning("Blocked request with disallowed scheme: %r", scheme)
        return False, scheme, hostname
    if not hostname:
        return False, scheme, hostname
    # Cloud metadata hostnames are blocked regardless of any toggle.
    if hostname in _BLOCKED_HOSTNAMES:
        logger.warning("Blocked request to internal hostname: %s", hostname)
        return False, scheme, hostname
    return None, scheme, hostname


def _evaluate_addresses(hostname: str, scheme: str, addr_info: Iterable) -> bool:
    """Decide whether every resolved address is acceptable.

    Fails closed: an empty result or an unparseable address blocks.
    """
    allow_all_private = _global_allow_private_urls()
    allow_private_ip = _allows_private_ip_resolution(hostname, scheme)

    saw_address = False
    for entry in addr_info:
        try:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
        except (IndexError, TypeError):
            logger.warning("Blocked request to %s: malformed resolver result", hostname)
            return False
        ip = _parse_resolved_ip(ip_str)
        if ip is None:
            logger.warning(
                "Blocked request to %s: unparseable resolved address %r",
                hostname,
                ip_str,
            )
            return False
        saw_address = True

        # Cloud metadata / link-local is always blocked, toggle or not.
        if _is_always_blocked_ip(ip):
            logger.warning(
                "Blocked request to cloud metadata address: %s -> %s", hostname, ip
            )
            return False

        if allow_all_private or allow_private_ip:
            continue

        if _is_blocked_ip(ip):
            logger.warning(
                "Blocked request to private/internal address: %s -> %s",
                hostname,
                ip,
            )
            return False

    if not saw_address:
        logger.warning("Blocked request to %s: DNS returned no addresses", hostname)
        return False
    return True


def is_safe_url(url: str) -> bool:
    """Return True only when ``url`` is safe to fetch (SSRF pre-flight check).

    - Only ``http``/``https`` with a hostname are accepted.
    - Cloud metadata hostnames are always rejected.
    - The hostname is resolved and the request is refused if ANY resolved
      address is private, loopback, link-local, CGNAT, multicast, reserved or
      unspecified — unless ``allow_private_urls`` is enabled globally or the
      host is an exact trusted HTTPS host in ``_TRUSTED_PRIVATE_IP_HOSTS``.
    - Cloud metadata IPs and the link-local range are rejected even then.
    - DNS failures and any unexpected error fail closed.
    """
    try:
        verdict, scheme, hostname = _precheck(url)
        if verdict is not None:
            return verdict
        try:
            addr_info = _resolve(hostname)
        except (socket.gaierror, OSError, UnicodeError) as exc:
            logger.warning("Blocked request to %s: DNS resolution failed (%s)", hostname, exc)
            return False
        return _evaluate_addresses(hostname, scheme, addr_info)
    except Exception as exc:
        logger.warning("SSRF check error for %s (failing closed): %s", url, exc)
        return False


async def async_is_safe_url(url: str) -> bool:
    """Async variant of :func:`is_safe_url`.

    Runs the blocking DNS resolution in a worker thread so the event loop is
    never stalled; the decision logic is identical to the sync check.
    """
    import asyncio

    try:
        verdict, scheme, hostname = _precheck(url)
        if verdict is not None:
            return verdict
        try:
            addr_info = await asyncio.to_thread(_resolve, hostname)
        except (socket.gaierror, OSError, UnicodeError) as exc:
            logger.warning("Blocked request to %s: DNS resolution failed (%s)", hostname, exc)
            return False
        return _evaluate_addresses(hostname, scheme, addr_info)
    except Exception as exc:
        logger.warning("SSRF check error for %s (failing closed): %s", url, exc)
        return False


def redirect_target_from_response(response: Any) -> Optional[str]:
    """Return the redirect target visible from inside an httpx response hook.

    In ``httpx.AsyncClient`` response event hooks, ``response.next_request`` is
    frequently ``None`` even for a genuine redirect (it is populated later by
    the redirect-following machinery). Relying on ``next_request`` alone means
    an SSRF redirect guard silently never fires: a public URL that 302s to
    ``http://169.254.169.254/`` gets followed anyway. The ``Location`` header,
    however, is already present on the response, so resolve the target from it
    first (handling relative Locations via ``urljoin``) and only fall back to
    ``next_request`` when no ``Location`` header is set.
    """
    if not getattr(response, "is_redirect", False):
        return None

    headers = getattr(response, "headers", {}) or {}
    location = headers.get("location")
    if location:
        return urljoin(str(getattr(response, "url", "")), str(location))

    next_request = getattr(response, "next_request", None)
    if next_request:
        return str(next_request.url)

    return None
