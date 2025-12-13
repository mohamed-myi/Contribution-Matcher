from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Headers added:
    - X-Frame-Options: DENY (Prevents clickjacking)
    - X-Content-Type-Options: nosniff (Prevents MIME sniffing)
    - X-XSS-Protection: 1; mode=block (Legacy XSS protection)
    - Referrer-Policy: strict-origin-when-cross-origin
    - Strict-Transport-Security: (In production only)
    - Content-Security-Policy: (Basic protection)
    """

    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.is_production = self.settings.env.lower() in ("production", "prod")

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Add security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # CSP: Allow self and data images (common), and unsafe-inline styles/scripts for now
        # Verification phase should tighten this
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline';"
        )

        # HSTS (Production only)
        if self.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
