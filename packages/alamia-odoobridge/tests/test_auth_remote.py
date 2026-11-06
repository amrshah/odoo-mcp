"""
Integration tests for the complete remote HTTP authentication and authorization path.
Tests FastMCP HTTP app with BridgeAuthMiddleware over simulated ASGI requests.
"""

import pytest
import httpx
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from alamia_odoobridge.config import BridgeSettings
from alamia_odoobridge.core.auth import BridgeAuthMiddleware
from alamia_odoobridge.core.context import PrincipalVerifier, current_principal
from alamia_odoobridge.mcp.server import create_bridge_server


@pytest.fixture
def test_settings():
    return BridgeSettings(
        _env_file=None,
        ODOO_URL="http://localhost:8069",
        ODOO_DB="test_db",
        ODOO_USERNAME="test_user",
        ODOO_PASSWORD="test_password",
        BRIDGE_API_KEY="super_secret_bridge_token_2026",
        BRIDGE_SECRET_KEY="hmac_signing_secret_key_123",
        BRIDGE_ENFORCE_REMOTE_AUTH=True,
    )


@pytest.fixture
def auth_app(test_settings):
    server = create_bridge_server(test_settings)
    middleware = [
        Middleware(
            BridgeAuthMiddleware,
            api_key=test_settings.bridge_api_key,
            secret_key=test_settings.bridge_secret_key,
            enforce_api_key=test_settings.enforce_remote_auth,
        )
    ]
    # Create Starlette app using FastMCP's http_app
    app = server.http_app(transport="sse", middleware=middleware)
    return app


@pytest.mark.asyncio
async def test_remote_missing_api_key_rejected(auth_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth_app), base_url="http://testserver") as client:
        res = await client.get("/sse")
        assert res.status_code == 401
        data = res.json()
        assert "Unauthorized" in data["error"]


@pytest.mark.asyncio
async def test_remote_invalid_api_key_rejected(auth_app):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth_app), base_url="http://testserver") as client:
        res = await client.get("/sse", headers={"Authorization": "Bearer wrong_token"})
        assert res.status_code == 401
        data = res.json()
        assert "Unauthorized" in data["error"]


@pytest.mark.asyncio
async def test_remote_raw_unverified_principal_rejected(auth_app, test_settings):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth_app), base_url="http://testserver") as client:
        # Provide valid API key but spoof raw unverified human principal
        res = await client.get(
            "/sse",
            headers={
                "Authorization": f"Bearer {test_settings.bridge_api_key}",
                "X-Bridge-Principal": "spoofed_admin@hospital.com",
            },
        )
        assert res.status_code == 403
        data = res.json()
        assert "Raw X-Bridge-Principal header is not trusted" in data["error"]


@pytest.mark.asyncio
async def test_remote_tampered_principal_token_rejected(auth_app, test_settings):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth_app), base_url="http://testserver") as client:
        res = await client.get(
            "/sse",
            headers={
                "Authorization": f"Bearer {test_settings.bridge_api_key}",
                "X-Bridge-Principal-Token": "tampered.invalid.base64",
            },
        )
        assert res.status_code == 403
        data = res.json()
        assert "Principal verification failed" in data["error"]


@pytest.mark.asyncio
async def test_remote_valid_auth_with_verified_principal(auth_app, test_settings):
    verifier = PrincipalVerifier(test_settings.bridge_secret_key)
    valid_token = verifier.sign_claims({"sub": "dr_sarah", "role": "doctor", "user_id": 15})

    captured_principal = []

    async def probe(request: Request):
        principal = current_principal.get()
        captured_principal.append(principal)
        return JSONResponse({"sub": principal.sub if principal else None})

    auth_app.add_route("/probe_principal", probe)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth_app), base_url="http://testserver") as client:
        res = await client.get(
            "/probe_principal",
            headers={
                "Authorization": f"Bearer {test_settings.bridge_api_key}",
                "X-Bridge-Principal-Token": valid_token,
            },
        )
        assert res.status_code == 200
        assert res.json() == {"sub": "dr_sarah"}
        assert len(captured_principal) == 1
        assert captured_principal[0].sub == "dr_sarah"
        assert captured_principal[0].role == "doctor"
