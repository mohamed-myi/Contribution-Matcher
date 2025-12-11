"""
Middleware that injects a request ID into every incoming request.
"""

import uuid

from fastapi import Request

from core.logging import bind_context


class RequestIDMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        scope.setdefault("state", {})["request_id"] = request_id

        # Bind request ID to logging context
        bind_context(request_id=request_id)

        async def send_wrapper(response):
            if response["type"] == "http.response.start":
                headers = response.setdefault("headers", [])
                headers.append((b"x-request-id", request_id.encode()))
            await send(response)

        await self.app(scope, receive, send_wrapper)
