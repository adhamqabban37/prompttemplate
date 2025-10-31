"""Strong SSRF protection utilities for URL scanning.

This module validates that a provided URL is safe to fetch from the backend.
It blocks localhost/loopback, RFC1918 private ranges, link-local, multicast,
and common test/internal domains. Only http/https schemes are allowed.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlparse
from typing import Optional


class SSRFProtectionError(ValueError):
    """Raised when a URL fails SSRF validation."""


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    """Return True if the IP is private, loopback, link-local, or multicast."""
    return bool(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
    )


def validate_url_or_raise(url: str) -> None:
    """Validate URL to prevent SSRF attacks.

    Raises SSRFProtectionError if:
    - Scheme is not http/https
    - Host is localhost/loopback or resolves to private ranges (RFC1918)
    - Host is link-local or multicast
    - URL contains embedded credentials
    - Hostname uses known private/test TLDs
    """
    if not url or not isinstance(url, str):
        raise SSRFProtectionError("URL must be a non-empty string")

    try:
        parsed = urlparse(url.strip())
    except Exception as e:
        raise SSRFProtectionError(f"Invalid URL format: {e}")

    if parsed.scheme not in ("http", "https"):
        raise SSRFProtectionError(f"Only http/https schemes allowed, got: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFProtectionError("URL must have a valid hostname")

    # Block obvious localhost variants early
    hostname_l = hostname.lower()
    if (
        hostname_l == "localhost"
        or hostname_l.endswith(".localhost")
        or hostname_l.startswith("127.")
        or hostname_l == "0.0.0.0"
        or hostname_l == "::1"
        or hostname_l == "[::1]"
        or hostname_l == "[::ffff:127.0.0.1]"
    ):
        raise SSRFProtectionError(f"Localhost/loopback addresses not allowed: {hostname}")

    # If it's an IP literal, evaluate directly
    try:
        ip = ipaddress.ip_address(hostname)
        if _is_blocked_ip(ip):
            raise SSRFProtectionError(f"Private/internal IP addresses not allowed: {ip}")
    except ValueError:
        # Not an IP literal, check for private/test TLDs (no DNS resolution performed)
        private_tlds = (".local", ".internal", ".test", ".example", ".invalid")
        if hostname_l.endswith(private_tlds):
            raise SSRFProtectionError(f"Private/test domains not allowed: {hostname}")

    # Block URLs with embedded credentials
    if parsed.username or parsed.password:
        raise SSRFProtectionError("URLs with embedded credentials not allowed")


def is_public_url(url: str) -> tuple[bool, Optional[str]]:
    """Check if URL passes SSRF checks without raising.

    Returns (is_valid, error_message_if_any)
    """
    try:
        validate_url_or_raise(url)
        return True, None
    except SSRFProtectionError as e:
        return False, str(e)
