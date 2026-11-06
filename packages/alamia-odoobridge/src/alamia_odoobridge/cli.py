"""
CLI Entrypoint for Alamia OdooBridge.
Supports local execution (stdio) for IDEs and remote execution (SSE / Streamable HTTP)
with mandatory API Key enforcement and caller principal propagation.
"""

import argparse
import logging
import sys
from starlette.middleware import Middleware

from .config import BridgeSettings, ExecutionPolicy, TransportType, get_settings
from .core.auth import BridgeAuthMiddleware
from .mcp.server import create_bridge_server

logger = logging.getLogger("alamia_odoobridge.cli")


def parse_args():
    parser = argparse.ArgumentParser(
        prog="alamia-odoobridge",
        description="Alamia OdooBridge - The Independent Integration Gateway for Odoo & AI Agents",
    )
    parser.add_argument("--url", dest="odoo_url", help="Odoo server URL (e.g. http://localhost:8069)")
    parser.add_argument("--db", dest="odoo_db", help="Odoo database name")
    parser.add_argument("--user", dest="odoo_username", help="Odoo service username")
    parser.add_argument("--password", dest="odoo_password", help="Odoo service password or API key")
    parser.add_argument(
        "--transport",
        dest="mcp_transport",
        choices=["stdio", "sse", "streamable-http"],
        default=None,
        help="MCP Transport mode (default: from env or sse)",
    )
    parser.add_argument("--host", dest="mcp_server_host", help="MCP server bind host (default: 0.0.0.0)")
    parser.add_argument("--port", dest="mcp_server_port", type=int, help="MCP server port (default: 8008)")
    parser.add_argument(
        "--policy",
        dest="execution_policy",
        choices=["read_only", "controlled_writes", "workflow_execution"],
        help="Operation security policy",
    )
    parser.add_argument(
        "--allow-unlink",
        dest="allow_unlink",
        action="store_true",
        help="Explicitly enable record deletion (disabled by default)",
    )
    parser.add_argument("--api-key", dest="bridge_api_key", help="Gateway access token (required for remote endpoints)")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = get_settings()

    # Apply CLI argument overrides
    if args.odoo_url:
        cfg.odoo_url = args.odoo_url
    if args.odoo_db:
        cfg.odoo_db = args.odoo_db
    if args.odoo_username:
        cfg.odoo_username = args.odoo_username
    if args.odoo_password:
        cfg.odoo_password = args.odoo_password
    if args.mcp_transport:
        cfg.mcp_transport = TransportType(args.mcp_transport.replace("-", "_"))
    if args.mcp_server_host:
        cfg.mcp_server_host = args.mcp_server_host
    if args.mcp_server_port:
        cfg.mcp_server_port = args.mcp_server_port
    if args.execution_policy:
        cfg.execution_policy = ExecutionPolicy(args.execution_policy)
    if args.allow_unlink:
        cfg.allow_unlink = True
    if args.bridge_api_key:
        cfg.bridge_api_key = args.bridge_api_key

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info(
        "Initializing Alamia OdooBridge (Transport: %s, Policy: %s)",
        cfg.mcp_transport.value,
        cfg.execution_policy.value,
    )

    server = create_bridge_server(cfg)

    if cfg.mcp_transport == TransportType.STDIO:
        server.run(transport="stdio")
    else:
        # Remote network transports (SSE or Streamable HTTP)
        if cfg.enforce_remote_auth and not cfg.bridge_api_key:
            logger.error(
                "Security Policy Error: Remote transport '%s' requires BRIDGE_API_KEY. "
                "Set BRIDGE_API_KEY in environment or pass --api-key.",
                cfg.mcp_transport.value,
            )
            sys.exit(1)

        middleware = [
            Middleware(
                BridgeAuthMiddleware,
                api_key=cfg.bridge_api_key,
                secret_key=cfg.bridge_secret_key,
                enforce_api_key=cfg.enforce_remote_auth,
            )
        ]

        if cfg.mcp_transport == TransportType.SSE:
            logger.info("Serving SSE on http://%s:%s/sse", cfg.mcp_server_host, cfg.mcp_server_port)
            server.run(
                transport="sse",
                host=cfg.mcp_server_host,
                port=cfg.mcp_server_port,
                middleware=middleware,
            )
        elif cfg.mcp_transport == TransportType.STREAMABLE_HTTP:
            logger.info("Serving Streamable HTTP on http://%s:%s/mcp", cfg.mcp_server_host, cfg.mcp_server_port)
            server.run(
                transport="streamable-http",
                host=cfg.mcp_server_host,
                port=cfg.mcp_server_port,
                middleware=middleware,
            )


if __name__ == "__main__":
    main()
