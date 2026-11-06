"""
HTTP Authentication & Caller Context Middleware for Alamia OdooBridge.
Pure ASGI middleware enforcing BRIDGE_API_KEY on remote endpoints,
binding verified principal tokens, and preserving streaming SSE session compatibility.
"""

import logging
from typing import Optional
from starlette.requests import Request
from starlette.responses import JSONResponse

from .context import PrincipalVerifier, PrincipalClaims, current_principal
from .exceptions import AuthenticationError

logger = logging.getLogger("alamia_odoobridge.auth")


class BridgeAuthMiddleware:
    """
    Pure ASGI middleware enforcing API Key authentication on all MCP HTTP routes
    and propagating verified caller principal claims across SSE and HTTP sessions.
    Avoids BaseHTTPMiddleware response streaming buffering issues with SSE transports.
    """

    def __init__(
        self,
        app,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        enforce_api_key: bool = True,
    ):
        self.app = app
        self.api_key = api_key
        self.enforce_api_key = enforce_api_key
        self.verifier = PrincipalVerifier(secret_key=secret_key) if secret_key else None

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)

        # 1. Enforce Gateway API Key on all incoming requests
        if self.enforce_api_key and self.api_key:
            auth_header = request.headers.get("Authorization", "")
            x_api_key = request.headers.get("X-Bridge-API-Key", "")

            presented_key = ""
            if auth_header.startswith("Bearer "):
                presented_key = auth_header[7:].strip()
            elif x_api_key:
                presented_key = x_api_key.strip()

            if not presented_key or presented_key != self.api_key:
                logger.warning(
                    "Remote request rejected from %s: missing or invalid BRIDGE_API_KEY",
                    request.client.host if request.client else "unknown",
                )
                response = JSONResponse(
                    {
                        "error": "Unauthorized: Missing or invalid BRIDGE_API_KEY",
                        "status": 401,
                    },
                    status_code=401,
                    headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
                )
                await response(scope, receive, send)
                return

        # 2. Extract and verify Caller Principal Token (if provided)
        principal_token = request.headers.get("X-Bridge-Principal-Token")
        raw_principal_header = request.headers.get("X-Bridge-Principal")

        # Explicitly forbid trusting raw unverified headers
        if raw_principal_header and not principal_token:
            logger.warning("Rejected unverified X-Bridge-Principal header without cryptographic token")
            response = JSONResponse(
                {
                    "error": "Forbidden: Raw X-Bridge-Principal header is not trusted. Provide a signed X-Bridge-Principal-Token.",
                    "status": 403,
                },
                status_code=403,
            )
            await response(scope, receive, send)
            return

        token_to_reset = None
        if principal_token:
            if not self.verifier:
                logger.error("Principal token received but BRIDGE_SECRET_KEY is not configured")
                response = JSONResponse(
                    {
                        "error": "Server Configuration Error: BRIDGE_SECRET_KEY is not configured to verify caller tokens",
                        "status": 500,
                    },
                    status_code=500,
                )
                await response(scope, receive, send)
                return
            try:
                session_id = request.query_params.get("session_id") or request.headers.get("mcp-session-id")
                is_handshake = request.method == "GET" and (
                    request.url.path.endswith("/sse") or "text/event-stream" in request.headers.get("accept", "")
                )
                verified_claims = self.verifier.verify_token(
                    principal_token,
                    session_id=session_id,
                    is_handshake=is_handshake,
                )
                token_to_reset = current_principal.set(verified_claims)
                logger.debug("Bound verified principal: %s (session: %s)", verified_claims, session_id)
            except AuthenticationError as e:
                logger.warning("Caller principal token verification failed: %s", e)
                response = JSONResponse(
                    {"error": f"Forbidden: Principal verification failed: {e}", "status": 403},
                    status_code=403,
                )
                await response(scope, receive, send)
                return
        else:
            # Set explicit service-account-only principal context
            service_claims = PrincipalClaims(
                sub="service_account",
                username="service_account",
                is_service_only=True,
            )
            token_to_reset = current_principal.set(service_claims)

        try:
            await self.app(scope, receive, send)
        finally:
            if token_to_reset:
                current_principal.reset(token_to_reset)
