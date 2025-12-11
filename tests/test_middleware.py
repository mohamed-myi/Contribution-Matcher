"""
Tests for API Middleware.

Tests:
- Compression middleware
- Security headers middleware
- Rate limiting middleware
"""

import pytest


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""
    
    def test_adds_security_headers(self):
        """Test that security headers are added to response."""
        from packages.api.src.middleware.security import SecurityHeadersMiddleware
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.testclient import TestClient
        
        app = Starlette()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.route("/test")
        async def test_route(request):
            return JSONResponse({"status": "ok"})
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert "Referrer-Policy" in response.headers
    
    def test_hsts_configuration(self):
        """Test HSTS header is properly configured."""
        from packages.api.src.middleware.security import SecurityHeadersMiddleware
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.testclient import TestClient
        
        app = Starlette()
        app.add_middleware(
            SecurityHeadersMiddleware,
            hsts_max_age=86400,
            include_subdomains=False,
        )
        
        @app.route("/test")
        async def test_route(request):
            return JSONResponse({"status": "ok"})
        
        client = TestClient(app)
        response = client.get("/test")
        
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=86400" in hsts
        assert "includeSubDomains" not in hsts


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""
    
    def test_get_limit_for_path_default(self):
        """Test default rate limit is returned."""
        from packages.api.src.middleware.rate_limit import RateLimitMiddleware
        
        middleware = RateLimitMiddleware(None)
        
        limit = middleware._get_limit_for_path("/api/unknown")
        
        assert limit == middleware.DEFAULT_LIMIT
    
    def test_get_limit_for_path_scoring(self):
        """Test scoring endpoint has lower limit."""
        from packages.api.src.middleware.rate_limit import RateLimitMiddleware
        
        middleware = RateLimitMiddleware(None)
        
        limit = middleware._get_limit_for_path("/scoring/user/1")
        
        assert limit == 20  # Lower limit for scoring
    
    def test_get_limit_for_path_ml(self):
        """Test ML train endpoint has lowest limit."""
        from packages.api.src.middleware.rate_limit import RateLimitMiddleware
        
        middleware = RateLimitMiddleware(None)
        
        limit = middleware._get_limit_for_path("/ml/train")
        
        assert limit == 5


class TestCompressionMiddleware:
    """Tests for CompressionMiddleware."""
    
    def test_compressible_types(self):
        """Test that JSON is in compressible types."""
        from packages.api.src.middleware.compression import CompressionMiddleware
        
        assert "application/json" in CompressionMiddleware.COMPRESSIBLE_TYPES
        assert "text/html" in CompressionMiddleware.COMPRESSIBLE_TYPES
    
    def test_no_compression_without_accept_header(self):
        """Test no compression when client doesn't accept gzip."""
        from packages.api.src.middleware.compression import CompressionMiddleware
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.testclient import TestClient
        
        app = Starlette()
        app.add_middleware(CompressionMiddleware)
        
        @app.route("/test")
        async def test_route(request):
            return JSONResponse({"data": "x" * 1000})
        
        client = TestClient(app)
        response = client.get("/test", headers={"Accept-Encoding": ""})
        
        assert "content-encoding" not in response.headers
