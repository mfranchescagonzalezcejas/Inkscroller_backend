"""Shared security response headers."""

CSP_REPORT_ONLY = (
    "default-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'none'; "
    "object-src 'none'; "
    "report-uri /csp-report"
)


def get_security_headers(is_production: bool) -> dict[str, str]:
    """Return the baseline security headers for every API response."""
    headers: dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "0",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy-Report-Only": CSP_REPORT_ONLY,
    }

    if is_production:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    headers["Permissions-Policy"] = (
        "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
        "document-domain=(), encrypted-media=(), fullscreen=(), "
        "geolocation=(), gyroscope=(), magnetometer=(), microphone=(), "
        "midi=(), payment=(), picture-in-picture=(), publickey-credentials-get=(), "
        "screen-wake-lock=(), sync-xhr=(), usb=(), web-share=(), "
        "xr-spatial-tracking=()"
    )

    return headers
