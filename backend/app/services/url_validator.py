"""SSRF protection for URL scanning."""
import ipaddress
import re
from urllib.parse import urlparse
from typing import Optional


class SSRFProtectionError(ValueError):
    """Raised when a URL fails SSRF validation."""
    pass


def validate_scan_url(url: str) -> None:
    """
    Validate URL to prevent SSRF attacks.
    
    Raises SSRFProtectionError if:
    - Scheme is not http/https
    - Host resolves to private IP (RFC1918, loopback, link-local)
    - URL contains suspicious patterns
    """
    if not url or not isinstance(url, str):
        raise SSRFProtectionError("URL must be a non-empty string")
    
    # Parse URL
    try:
        parsed = urlparse(url.strip())
    except Exception as e:
        raise SSRFProtectionError(f"Invalid URL format: {e}")
    
    # Check scheme
    if parsed.scheme not in ("http", "https"):
        raise SSRFProtectionError(f"Only http/https schemes allowed, got: {parsed.scheme}")
    
    # Check hostname exists
    hostname = parsed.hostname
    if not hostname:
        raise SSRFProtectionError("URL must have a valid hostname")
    
    # Block localhost variants
    localhost_patterns = [
        "localhost", "127.", "::1", "0.0.0.0",
        "[::1]", "[::ffff:127.0.0.1]"
    ]
    hostname_lower = hostname.lower()
    for pattern in localhost_patterns:
        if pattern in hostname_lower:
            raise SSRFProtectionError(f"Localhost/loopback addresses not allowed: {hostname}")
    
    # Try to parse as IP address
    try:
        ip = ipaddress.ip_address(hostname)
        # Block private, loopback, link-local, multicast
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
            raise SSRFProtectionError(f"Private/internal IP addresses not allowed: {ip}")
    except ValueError:
        # Not an IP address, check for common private domain patterns
        private_tlds = [".local", ".internal", ".localhost", ".test", ".example", ".invalid"]
        for tld in private_tlds:
            if hostname_lower.endswith(tld):
                raise SSRFProtectionError(f"Private/test domains not allowed: {hostname}")
    
    # Block URLs with credentials (rare in legitimate use)
    if parsed.username or parsed.password:
        raise SSRFProtectionError("URLs with embedded credentials not allowed")
    
    # Additional checks for suspicious patterns
    suspicious = ["file://", "ftp://", "gopher://", "dict://", "jar://"]
    url_lower = url.lower()
    for sus in suspicious:
        if sus in url_lower:
            raise SSRFProtectionError(f"Suspicious URL scheme detected: {sus}")


def is_valid_public_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Check if URL is valid and public (for non-exception use).
    
    Returns:
        (is_valid, error_message)
    """
    try:
        validate_scan_url(url)
        return (True, None)
    except SSRFProtectionError as e:
        return (False, str(e))
