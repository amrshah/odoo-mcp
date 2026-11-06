"""
Real MCP Client Integration Tests for both SSE and Streamable HTTP transports.
Verifies signed principal propagation, repeated tool calls, token expiration,
session-binding replay rejection, service-only fallback, and concurrent sessions.
"""

import time
import socket
import asyncio
import threading
import pytest
import uvicorn
import httpx2
from fastmcp import FastMCP
from starlette.middleware import Middleware
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

from alamia_odoobridge.core.auth import BridgeAuthMiddleware
from alamia_odoobridge.core.context import PrincipalVerifier, current_principal


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def sse_test_server():
    port = get_free_port()
    api_key = "test-gateway-api-key-999"
    secret_key = "test-secret-hmac-key-888"
    verifier = PrincipalVerifier(secret_key=secret_key)

    mcp = FastMCP("alamia-mcp-sse-server")

    @mcp.tool()
    def inspect_caller() -> dict:
        p = current_principal.get()
        return {
            "sub": p.sub if p else None,
            "role": p.role if p else None,
            "is_service_only": p.is_service_only if p else True,
            "company_id": p.company_id if p else None,
        }

    middleware = [
        Middleware(
            BridgeAuthMiddleware,
            api_key=api_key,
            secret_key=secret_key,
            enforce_api_key=True,
        )
    ]

    app = mcp.http_app(transport="sse", middleware=middleware)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.0)

    yield {
        "port": port,
        "url": f"http://127.0.0.1:{port}/sse",
        "api_key": api_key,
        "secret_key": secret_key,
        "verifier": verifier,
    }

    server.should_exit = True


@pytest.fixture(scope="module")
def streamable_http_test_server():
    port = get_free_port()
    api_key = "test-streamable-api-key-777"
    secret_key = "test-streamable-hmac-key-666"
    verifier = PrincipalVerifier(secret_key=secret_key)

    mcp = FastMCP("alamia-mcp-streamable-server")

    @mcp.tool()
    def inspect_caller() -> dict:
        p = current_principal.get()
        return {
            "sub": p.sub if p else None,
            "role": p.role if p else None,
            "is_service_only": p.is_service_only if p else True,
            "company_id": p.company_id if p else None,
        }

    middleware = [
        Middleware(
            BridgeAuthMiddleware,
            api_key=api_key,
            secret_key=secret_key,
            enforce_api_key=True,
        )
    ]

    app = mcp.http_app(transport="streamable-http", middleware=middleware)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1.0)

    yield {
        "port": port,
        "url": f"http://127.0.0.1:{port}/mcp",
        "api_key": api_key,
        "secret_key": secret_key,
        "verifier": verifier,
    }

    server.should_exit = True


# --- SSE Client Tests ---

@pytest.mark.asyncio
async def test_mcp_real_client_signed_principal_and_repeated_calls(sse_test_server):
    """Verifies that a signed human principal propagates over SSE and survives repeated tool calls."""
    verifier: PrincipalVerifier = sse_test_server["verifier"]
    token = verifier.sign_claims({
        "sub": "dr_smith",
        "role": "doctor",
        "company_id": 1,
    })

    headers = {
        "Authorization": f"Bearer {sse_test_server['api_key']}",
        "X-Bridge-Principal-Token": token,
    }

    async with sse_client(sse_test_server["url"], headers=headers) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            res1 = await session.call_tool("inspect_caller", {})
            assert "dr_smith" in res1.content[0].text
            assert "doctor" in res1.content[0].text
            assert '"is_service_only":false' in res1.content[0].text

            # Repeated call in same session
            res2 = await session.call_tool("inspect_caller", {})
            assert "dr_smith" in res2.content[0].text


@pytest.mark.asyncio
async def test_mcp_real_client_service_only_fallback(sse_test_server):
    """Verifies that requests without a principal token receive service-only identity."""
    headers = {
        "Authorization": f"Bearer {sse_test_server['api_key']}",
    }

    async with sse_client(sse_test_server["url"], headers=headers) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            res = await session.call_tool("inspect_caller", {})
            assert '"is_service_only":true' in res.content[0].text
            assert "service_account" in res.content[0].text


@pytest.mark.asyncio
async def test_mcp_real_client_expired_token_rejected(sse_test_server):
    """Verifies that an expired principal token is rejected during SSE establishment."""
    verifier: PrincipalVerifier = sse_test_server["verifier"]
    expired_token = verifier.sign_claims({"sub": "dr_expired", "role": "doctor"}, ttl_seconds=-10.0)

    headers = {
        "Authorization": f"Bearer {sse_test_server['api_key']}",
        "X-Bridge-Principal-Token": expired_token,
    }

    with pytest.raises(Exception):
        async with sse_client(sse_test_server["url"], headers=headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()


@pytest.mark.asyncio
async def test_mcp_real_client_token_replay_rejection(sse_test_server):
    """Verifies that reusing the same token in a new independent SSE session is rejected."""
    verifier: PrincipalVerifier = sse_test_server["verifier"]
    token = verifier.sign_claims({"sub": "dr_alice", "role": "doctor"})

    headers = {
        "Authorization": f"Bearer {sse_test_server['api_key']}",
        "X-Bridge-Principal-Token": token,
    }

    async with sse_client(sse_test_server["url"], headers=headers) as (r1, w1):
        async with ClientSession(r1, w1) as s1:
            await s1.initialize()
            res = await s1.call_tool("inspect_caller", {})
            assert "dr_alice" in res.content[0].text

    # Replay in a second session fails
    with pytest.raises(Exception):
        async with sse_client(sse_test_server["url"], headers=headers) as (r2, w2):
            async with ClientSession(r2, w2) as s2:
                await s2.initialize()


@pytest.mark.asyncio
async def test_mcp_real_client_concurrent_sessions(sse_test_server):
    """Verifies concurrent SSE sessions maintain strict identity isolation without claim bleeding."""
    verifier: PrincipalVerifier = sse_test_server["verifier"]
    token_doctor = verifier.sign_claims({"sub": "dr_concurrent", "role": "doctor"})
    token_nurse = verifier.sign_claims({"sub": "nurse_concurrent", "role": "technician"})

    headers_doc = {
        "Authorization": f"Bearer {sse_test_server['api_key']}",
        "X-Bridge-Principal-Token": token_doctor,
    }
    headers_nurse = {
        "Authorization": f"Bearer {sse_test_server['api_key']}",
        "X-Bridge-Principal-Token": token_nurse,
    }

    async def client_worker(headers, expected_sub, expected_role):
        async with sse_client(sse_test_server["url"], headers=headers) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                for _ in range(3):
                    res = await s.call_tool("inspect_caller", {})
                    assert expected_sub in res.content[0].text
                    assert expected_role in res.content[0].text
                    await asyncio.sleep(0.05)

    await asyncio.gather(
        client_worker(headers_doc, "dr_concurrent", "doctor"),
        client_worker(headers_nurse, "nurse_concurrent", "technician"),
    )


# --- Streamable HTTP Client Tests ---

@pytest.mark.asyncio
async def test_mcp_streamable_http_signed_principal_and_repeated_calls(streamable_http_test_server):
    """Verifies Streamable HTTP session initialization, signed principal propagation, and repeated calls."""
    verifier: PrincipalVerifier = streamable_http_test_server["verifier"]
    token = verifier.sign_claims({
        "sub": "dr_watson",
        "role": "doctor",
        "company_id": 2,
    })

    headers = {
        "Authorization": f"Bearer {streamable_http_test_server['api_key']}",
        "X-Bridge-Principal-Token": token,
    }

    async with httpx2.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(streamable_http_test_server["url"], http_client=http_client) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                res1 = await session.call_tool("inspect_caller", {})
                assert "dr_watson" in res1.content[0].text
                assert "doctor" in res1.content[0].text
                assert '"is_service_only":false' in res1.content[0].text

                # Repeated call within same Streamable HTTP session
                res2 = await session.call_tool("inspect_caller", {})
                assert "dr_watson" in res2.content[0].text


@pytest.mark.asyncio
async def test_mcp_streamable_http_service_only_fallback(streamable_http_test_server):
    """Verifies Streamable HTTP requests without principal token receive service-only identity."""
    headers = {
        "Authorization": f"Bearer {streamable_http_test_server['api_key']}",
    }

    async with httpx2.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(streamable_http_test_server["url"], http_client=http_client) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                res = await session.call_tool("inspect_caller", {})
                assert '"is_service_only":true' in res.content[0].text
                assert "service_account" in res.content[0].text


@pytest.mark.asyncio
async def test_mcp_streamable_http_expired_token_rejected(streamable_http_test_server):
    """Verifies expired principal token is rejected during Streamable HTTP handshake."""
    verifier: PrincipalVerifier = streamable_http_test_server["verifier"]
    expired_token = verifier.sign_claims({"sub": "dr_expired_sh", "role": "doctor"}, ttl_seconds=-10.0)

    headers = {
        "Authorization": f"Bearer {streamable_http_test_server['api_key']}",
        "X-Bridge-Principal-Token": expired_token,
    }

    with pytest.raises(Exception):
        async with httpx2.AsyncClient(headers=headers) as http_client:
            async with streamable_http_client(streamable_http_test_server["url"], http_client=http_client) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()


@pytest.mark.asyncio
async def test_mcp_streamable_http_token_replay_rejection(streamable_http_test_server):
    """Verifies reusing a token in a second Streamable HTTP session is rejected."""
    verifier: PrincipalVerifier = streamable_http_test_server["verifier"]
    token = verifier.sign_claims({"sub": "dr_bob", "role": "doctor"})

    headers = {
        "Authorization": f"Bearer {streamable_http_test_server['api_key']}",
        "X-Bridge-Principal-Token": token,
    }

    # Session 1 succeeds
    async with httpx2.AsyncClient(headers=headers) as c1:
        async with streamable_http_client(streamable_http_test_server["url"], http_client=c1) as (r1, w1):
            async with ClientSession(r1, w1) as s1:
                await s1.initialize()
                res = await s1.call_tool("inspect_caller", {})
                assert "dr_bob" in res.content[0].text

    # Session 2 with the same token is rejected
    with pytest.raises(Exception):
        async with httpx2.AsyncClient(headers=headers) as c2:
            async with streamable_http_client(streamable_http_test_server["url"], http_client=c2) as (r2, w2):
                async with ClientSession(r2, w2) as s2:
                    await s2.initialize()


@pytest.mark.asyncio
async def test_mcp_streamable_http_concurrent_sessions(streamable_http_test_server):
    """Verifies concurrent Streamable HTTP sessions maintain strict identity isolation."""
    verifier: PrincipalVerifier = streamable_http_test_server["verifier"]
    token_user1 = verifier.sign_claims({"sub": "user_stream_1", "role": "doctor"})
    token_user2 = verifier.sign_claims({"sub": "user_stream_2", "role": "technician"})

    headers1 = {
        "Authorization": f"Bearer {streamable_http_test_server['api_key']}",
        "X-Bridge-Principal-Token": token_user1,
    }
    headers2 = {
        "Authorization": f"Bearer {streamable_http_test_server['api_key']}",
        "X-Bridge-Principal-Token": token_user2,
    }

    async def worker(headers, expected_sub, expected_role):
        async with httpx2.AsyncClient(headers=headers) as http_client:
            async with streamable_http_client(streamable_http_test_server["url"], http_client=http_client) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    for _ in range(3):
                        res = await s.call_tool("inspect_caller", {})
                        assert expected_sub in res.content[0].text
                        assert expected_role in res.content[0].text
                        await asyncio.sleep(0.05)

    await asyncio.gather(
        worker(headers1, "user_stream_1", "doctor"),
        worker(headers2, "user_stream_2", "technician"),
    )
