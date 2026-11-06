import time
import pytest
from unittest.mock import MagicMock
from alamia_odoobridge.core.cache import SchemaCache
from alamia_odoobridge.config import BridgeSettings
from alamia_odoobridge.mcp.server import create_bridge_server


def test_cache_hit_and_miss():
    cache = SchemaCache(default_ttl=60.0)
    assert cache.get("missing_key") is None
    assert cache.stats["misses"] == 1
    assert cache.stats["hits"] == 0

    cache.set("key1", {"field": "val"})
    assert cache.get("key1") == {"field": "val"}
    assert cache.stats["hits"] == 1
    assert cache.stats["entries"] == 1


def test_cache_expiration():
    cache = SchemaCache(default_ttl=0.05)
    cache.set("short_lived", "data")
    assert cache.get("short_lived") == "data"
    
    time.sleep(0.06)
    assert cache.get("short_lived") is None
    assert cache.stats["misses"] == 1


def test_cache_invalidation_exact():
    cache = SchemaCache(default_ttl=60.0)
    cache.set("model:res.partner", "data1")
    cache.set("model:res.users", "data2")

    deleted = cache.invalidate("model:res.partner")
    assert deleted == 1
    assert cache.get("model:res.partner") is None
    assert cache.get("model:res.users") == "data2"


def test_cache_invalidation_prefix():
    cache = SchemaCache(default_ttl=60.0)
    cache.set("model:fields:res.partner:all", "fields1")
    cache.set("model:fields:res.partner:name,email", "fields2")
    cache.set("model:fields:res.users:all", "fields3")

    deleted = cache.invalidate("model:fields:res.partner")
    assert deleted == 2
    assert cache.get("model:fields:res.partner:all") is None
    assert cache.get("model:fields:res.partner:name,email") is None
    assert cache.get("model:fields:res.users:all") == "fields3"


def test_cache_disabled():
    cache = SchemaCache(enabled=False)
    cache.set("key", "val")
    assert cache.get("key") is None
    assert cache.stats["enabled"] is False


@pytest.mark.asyncio
async def test_server_uses_cache():
    settings = BridgeSettings(_env_file=None, enable_schema_cache=True)
    server = create_bridge_server(settings)

    mock_adapter = MagicMock()
    mock_adapter.list_models.return_value = [{"model": "res.partner", "name": "Contact"}]
    mock_adapter.get_model_fields.return_value = {"name": {"type": "char"}}

    # Replace adapter with mock
    import alamia_odoobridge.mcp.server as srv_mod
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("alamia_odoobridge.mcp.server.get_adapter", lambda s: mock_adapter)
        server = create_bridge_server(settings)

        tool_list = await server.get_tool("odoo_list_models")
        # First call: cache miss, adapter called
        res1 = tool_list.fn(filter_term="res.partner")
        assert res1 == [{"model": "res.partner", "name": "Contact"}]
        assert mock_adapter.list_models.call_count == 1

        # Second call: cache hit, adapter NOT called again
        res2 = tool_list.fn(filter_term="res.partner")
        assert res2 == [{"model": "res.partner", "name": "Contact"}]
        assert mock_adapter.list_models.call_count == 1

        # Fields tool test
        tool_fields = await server.get_tool("odoo_get_model_fields")
        f1 = tool_fields.fn(model="res.partner")
        assert f1 == {"name": {"type": "char"}}
        assert mock_adapter.get_model_fields.call_count == 1

        f2 = tool_fields.fn(model="res.partner")
        assert f2 == {"name": {"type": "char"}}
        assert mock_adapter.get_model_fields.call_count == 1
