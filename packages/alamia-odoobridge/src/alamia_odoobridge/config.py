"""
Configuration management for Alamia OdooBridge.
Loads environment variables and CLI overrides with Pydantic validation.
"""

from enum import Enum
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExecutionPolicy(str, Enum):
    READ_ONLY = "read_only"
    CONTROLLED_WRITES = "controlled_writes"
    WORKFLOW_EXECUTION = "workflow_execution"


class TransportType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


class OdooAdapterType(str, Enum):
    AUTO = "auto"
    XMLRPC = "xmlrpc"
    JSON2 = "json2"


class BridgeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Odoo Connection
    odoo_url: str = Field(default="http://localhost:8069", alias="ODOO_URL")
    odoo_db: str = Field(default="odoo_hospital", alias="ODOO_DB")
    odoo_username: str = Field(default="zelix_service", alias="ODOO_USERNAME")
    odoo_password: str = Field(default="", alias="ODOO_PASSWORD")
    odoo_adapter: OdooAdapterType = Field(default=OdooAdapterType.AUTO, alias="ODOO_ADAPTER")
    odoo_timeout_seconds: float = Field(default=30.0, alias="ODOO_TIMEOUT_SECONDS")

    # MCP Transport & Networking
    mcp_transport: TransportType = Field(default=TransportType.SSE, alias="MCP_TRANSPORT")
    mcp_server_host: str = Field(default="0.0.0.0", alias="MCP_SERVER_HOST")
    mcp_server_port: int = Field(default=8008, alias="MCP_SERVER_PORT")

    # Security & Guardrails
    bridge_api_key: Optional[str] = Field(default=None, alias="BRIDGE_API_KEY")
    bridge_secret_key: Optional[str] = Field(default=None, alias="BRIDGE_SECRET_KEY")
    enforce_remote_auth: bool = Field(default=True, alias="BRIDGE_ENFORCE_REMOTE_AUTH")
    service_scopes: List[str] = Field(default=["read"], alias="BRIDGE_SERVICE_SCOPES")
    execution_policy: ExecutionPolicy = Field(
        default=ExecutionPolicy.READ_ONLY, alias="BRIDGE_EXECUTION_POLICY"
    )
    allow_unlink: bool = Field(default=False, alias="BRIDGE_ALLOW_UNLINK")
    allowed_methods: List[str] = Field(
        default=[
            "account.move:action_post",
            "sale.order:action_confirm",
            "stock.picking:button_validate",
            "crm.lead:action_set_won",
            "crm.lead:action_set_lost",
            "vet.appointment:action_confirm",
            "vet.appointment:action_done",
            "vet.appointment:action_cancel",
            "vet.cm.case:get_dashboard_data",
            "vet.cm.case:get_rfp_dashboard_data",
        ],
        alias="BRIDGE_ALLOWED_METHODS",
    )
    disallowed_models: List[str] = Field(
        default=[
            "ir.model",
            "ir.model.fields",
            "ir.rule",
            "ir.model.access",
            "res.groups",
            "ir.cron",
            "ir.module.module",
        ],
        alias="BRIDGE_DISALLOWED_MODELS",
    )

    # Logging & Audit
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    enable_audit_log: bool = Field(default=True, alias="BRIDGE_ENABLE_AUDIT_LOG")

    # Schema Caching
    enable_schema_cache: bool = Field(default=True, alias="BRIDGE_ENABLE_SCHEMA_CACHE")
    schema_cache_ttl_seconds: float = Field(default=3600.0, alias="BRIDGE_SCHEMA_CACHE_TTL_SECONDS")


def get_settings() -> BridgeSettings:
    """Retrieve validated runtime settings."""
    return BridgeSettings()
