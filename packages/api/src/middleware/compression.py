"""
Response Compression Middleware.

Adds gzip/brotli compression for API responses.
"""

import gzip
import io
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse


class CompressionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to compress responses using gzip.
    
    Compresses responses when:
    - Client accepts gzip encoding
    - Response content type is compressible
    - Response size is above threshold
    
    Configuration:
    - minimum_size: Only compress responses larger than this (default: 500 bytes)
    """
    
    COMPRESSIBLE_TYPES = {
        "application/json",
        "text/plain",
        "text/html",
        "text/css",
        "application/javascript",
        "application/xml",
        "text/xml",
    }
    
    def __init__(self, app, minimum_size: int = 500):
        super().__init__(app)
        self.minimum_size = minimum_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)
        
        response = await call_next(request)
        
        # Don't compress streaming responses
        if isinstance(response, StreamingResponse):
            return response
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        base_content_type = content_type.split(";")[0].strip()
        
        if base_content_type not in self.COMPRESSIBLE_TYPES:
            return response
        
        # Get response body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        
        # Check size threshold
        if len(body) < self.minimum_size:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        
        # Compress the body
        buffer = io.BytesIO()
        with gzip.GzipFile(mode="wb", fileobj=buffer, compresslevel=6) as gz:
            gz.write(body)
        
        compressed_body = buffer.getvalue()
        
        # Only use compressed version if it's smaller
        if len(compressed_body) >= len(body):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        
        # Return compressed response
        headers = dict(response.headers)
        headers["content-encoding"] = "gzip"
        headers["content-length"] = str(len(compressed_body))
        
        # Remove content-length vary header if present (gzip changes the length)
        if "vary" in headers:
            vary = headers["vary"]
            if "accept-encoding" not in vary.lower():
                headers["vary"] = f"{vary}, Accept-Encoding"
        else:
            headers["vary"] = "Accept-Encoding"
        
        return Response(
            content=compressed_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
