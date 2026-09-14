# Application Adapter Guide

The `ApplicationAdapter` is the foundational contract isolating host application stacks from Alamia Core.

---

## 1. Adapter Responsibilities

Host applications implement the `ApplicationAdapter` interface (`adapters/application/base/adapter.py`):

| Method | Purpose |
|--------|---------|
| `identity(user_id)` | Fetches user profile / actor context |
| `permissions(user_id)` | Fetches authorized permission strings |
| `search(entity_type, query, limit)` | Query records of a given entity type |
| `get(entity_type, entity_id)` | Fetch single record by ID |
| `create(entity_type, data)` | Insert record |
| `update(entity_type, entity_id, data)` | Update existing record |
| `delete(entity_type, entity_id)` | Delete record |
| `execute(action_type, target, changes, meta)` | Execute domain action / transaction |
| `relationships(entity_type, entity_id, relation)` | Traverse relationships |
| `audit(entry)` | Send audit record to application store |

---

## 2. Supported Transport Modes

1. **In-Memory**: `InMemoryApplicationAdapter` for tests and local development.
2. **Model Context Protocol (MCP)**: `MCPApplicationAdapter` communicating with any MCP server over JSON-RPC.
3. **HTTP REST**: `RESTApplicationAdapter` connecting to web APIs.
4. **Native SDK**: `SDKApplicationAdapter` wrapping Python SDK clients.
