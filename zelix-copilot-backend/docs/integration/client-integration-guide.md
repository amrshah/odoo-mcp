# Client Integration Guide: Connecting External Applications to Alamia Copilot

Alamia AI Copilot exposes an open, framework-agnostic HTTP/JSON and AG-UI Server-Sent Events (SSE) contract. Any client platform capable of executing HTTP POST requests and parsing JSON or SSE streams can integrate with Alamia Copilot without proprietary SDKs or cloud vendor lock-in. External channel messaging platforms (such as WhatsApp, Slack, and Telegram) integrate via a dedicated Channel Adapter bridge.

---

## 1. Architectural Scope & Core Invariants

```text
                                  ┌───────────────────────────────┐
                                  │      Client Applications      │
                                  └───────────────┬───────────────┘
                                                  │
                ┌─────────────────────────────────┴─────────────────────────────────┐
                │                                                                   │
                ▼                                                                   ▼
      [Path A: Simple REST]                                               [Path B: Streaming AG-UI]
  POST /api/copilot/chat (JSON)                                           POST /api/ag-ui (SSE Stream)
  • Synchronous turn execution                                            • Real-time token streaming
  • Simple widgets & webhook bots                                         • Live state sync & HITL interrupts
                │                                                                   │
                └─────────────────────────────────┬─────────────────────────────────┘
                                                  │
                                                  ▼
                                 ┌─────────────────────────────────┐
                                 │   API Gateway / Auth Handler    │
                                 │ • Resolves Bearer Token / JWT   │
                                 │ • Derives EmployeeContext       │
                                 │   (user_id, tenant_id, perms)   │
                                 └────────────────┬────────────────┘
                                                  │
                                                  ▼
                                 ┌─────────────────────────────────┐
                                 │       Alamia Copilot Core       │
                                 │ • PolicyEngine (Authorization)  │
                                 │ • Skills & Tool Registry        │
                                 │ • Append-Only Audit Trail       │
                                 └────────────────┬────────────────┘
                                                  │
                                 ┌────────────────┴────────────────┐
                                 ▼                                 ▼
                      POST /api/action/confirm          POST /api/action/reject
                      (HITL Action Approval)            (HITL Action Rejection)
```

### Core Invariants
1. **Core Platform Independence**: `core/` contains 0 imports or references to UI frameworks (React, Vue, Angular, Flutter) or client libraries (CopilotKit, Axios).
2. **Backend Authorization Authority**: Client requests never assert authoritative roles or permissions. The server-side `PolicyEngine` derives user permissions and tenant isolation strictly from the validated authentication token/session.
3. **Single Source of Truth**: All execution paths (REST and AG-UI SSE) share the same underlying skill registry, policy engine, application adapters, and audit log.

---

## 2. Integration Paths: REST vs. Streaming AG-UI

Alamia Copilot supports two distinct integration paths. Select the path suited to your client's UX requirements:

| Integration Path | Transport | Request / Response Format | Primary Use Case |
|---|---|---|---|
| **Path A: Simple REST** | HTTP POST | `application/json` → `application/json` | Request-response chat widgets, mobile apps without streaming, CLI tools, backend automation, webhook bots (WhatsApp/Slack). |
| **Path B: Streaming AG-UI** | HTTP POST + SSE | `application/json` → `text/event-stream` | Rich conversational web/desktop UIs, real-time token/text streaming, live state synchronization, inline Human-in-the-Loop (HITL) interrupt modals. |

---

## 3. Protocol & Wire Contract Specifications

### 3.1 Authentication & Context Derivation
Every request to Alamia Copilot must supply an authenticated bearer token or session identifier:
```http
Authorization: Bearer <session_or_jwt_token>
```
The server-side authentication layer validates the token and constructs an immutable [`EmployeeContext`](file:///e:/Alamia/AlamiaAICopilot-Starter/core/sessions/context.py):
* `tenant_id`: Authoritative tenant identifier for multi-tenant data isolation.
* `user_id`: Authenticated employee/user identifier.
* `role`: Assigned role manifest (e.g., `finance_assistant`, `executive_assistant`).
* `permissions`: Validated RBAC permission list (e.g., `["customers.read", "invoices.read", "tasks.create"]`).

Clients **cannot** escalate privileges or override permissions via request payloads.

---

### 3.2 Path A: Simple REST API (`POST /api/copilot/chat`)

#### Request Contract
- **Method**: `POST`
- **Path**: `/api/copilot/chat`
- **Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <token>`
- **Payload**:
```json
{
  "query": "Follow up on overdue payments"
}
```

#### Response Contract (`application/json`)
```json
{
  "query": "Follow up on overdue payments",
  "skill_id": "payment_followup",
  "success": true,
  "output": {
    "customer_name": "Acme Global Industries",
    "overdue_count": 1,
    "total_overdue": 5400.0
  },
  "proposed_actions": [
    {
      "action_id": "act_followup_cust_101",
      "action_type": "create_followup",
      "idempotency_key": "followup_cust_cust_101_overdue_1",
      "target": {
        "type": "customer",
        "id": "cust_101"
      },
      "reason": "Customer has 1 overdue invoice(s) totaling $5400.00.",
      "risk_level": "LOW",
      "status": "AWAITING_CONFIRMATION"
    }
  ],
  "error": null,
  "message": "Analyzed overdue accounts for cust_101. Proposed follow-up action awaiting your confirmation."
}
```

---

### 3.3 Path B: Streaming AG-UI Protocol (`POST /api/ag-ui`)

Alamia Copilot implements a vendor-neutral subset of the **AG-UI protocol** transmitted over **Server-Sent Events (SSE)**.

#### Request Contract
- **Method**: `POST`
- **Path**: `/api/ag-ui`
- **Headers**:
  - `Content-Type: application/json`
  - `Accept: text/event-stream`
  - `Authorization: Bearer <token>`
- **Payload**:
```json
{
  "skill_id": "payment_followup",
  "inputs": {
    "customer_id": "cust_101"
  },
  "run_id": "run_98234"
}
```

#### SSE Stream Frame Lifecycle
The server responds with `Content-Type: text/event-stream` and emits sequential frames formatted as `event: <type>\ndata: <json>\n\n`:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: close

event: RUN_STARTED
data: {"event_type": "RUN_STARTED", "run_id": "run_98234", "data": {"skill_id": "payment_followup", "user_id": "usr_finance", "role": "finance_assistant"}}

event: STATE_UPDATE
data: {"event_type": "STATE_UPDATE", "run_id": "run_98234", "data": {"employee_context": {"user_id": "usr_finance", "role": "finance_assistant", "tenant_id": "tenant_1", "permissions": ["customers.read", "invoices.read", "tasks.create"]}}}

event: TEXT_DELTA
data: {"event_type": "TEXT_DELTA", "run_id": "run_98234", "data": {"delta": "{\"customer_name\": \"Acme Global Industries\", \"overdue_count\": 1, \"total_overdue\": 5400.0}"}}

event: INTERRUPT
data: {"event_type": "INTERRUPT", "run_id": "run_98234", "data": {"interrupt_id": "int_act_followup_cust_101", "prompt": "Confirm action 'create_followup' for customer:cust_101", "options": ["Approve", "Reject"], "action_proposal": {"action_id": "act_followup_cust_101", "action_type": "create_followup", "target": {"type": "customer", "id": "cust_101"}, "reason": "Customer has 1 overdue invoice(s) totaling $5400.00.", "risk_level": "LOW", "status": "AWAITING_CONFIRMATION"}}}

event: RUN_FINISHED
data: {"event_type": "RUN_FINISHED", "run_id": "run_98234", "data": {"result": {"skill_id": "payment_followup", "success": true, "output": {"customer_name": "Acme Global Industries", "overdue_count": 1, "total_overdue": 5400.0}}}}
```

#### Implemented AG-UI Event Subset
| Event Type | Purpose | Payload Schema |
|---|---|---|
| `RUN_STARTED` | Signals the commencement of an agent skill run | `{"skill_id": str, "user_id": str, "role": str}` |
| `STATE_UPDATE` | Synchronizes active session context | `{"employee_context": dict}` |
| `TEXT_DELTA` | Incremental streaming text/JSON tokens | `{"delta": str}` |
| `TOOL_CALL_STARTED` | Emitted when a registered tool starts execution | `{"tool_name": str, "tool_inputs": dict}` |
| `TOOL_CALL_FINISHED` | Emitted when a tool finishes execution | `{"tool_name": str, "tool_output": dict}` |
| `INTERRUPT` | Signals a Human-in-the-Loop confirmation gate | `{"interrupt_id": str, "prompt": str, "options": list, "action_proposal": dict}` |
| `RUN_FINISHED` | Indicates normal run completion | `{"result": dict}` |
| `RUN_ERROR` | Indicates failure or unhandled exception | `{"error": str}` |

---

### 3.4 Human-in-the-Loop (HITL) Action Confirmation Endpoints

When a skill proposes an `ActionProposal` requiring human approval (or when policy forces confirmation), the client resolves it via:

#### 1. Action Approval: `POST /api/action/confirm`
```json
// Request
{
  "action_id": "act_followup_cust_101"
}

// Response (200 OK)
{
  "status": "SUCCESS",
  "action": {
    "action_id": "act_followup_cust_101",
    "status": "COMPLETED",
    "result": {
      "status": "success",
      "task": {
        "id": "task_2",
        "title": "Follow up with Acme Global Industries regarding overdue invoices",
        "status": "pending"
      }
    }
  }
}
```

#### 2. Action Rejection: `POST /api/action/reject`
```json
// Request
{
  "action_id": "act_followup_cust_101"
}

// Response (200 OK)
{
  "status": "REJECTED",
  "action_id": "act_followup_cust_101"
}
```

---

## 4. Protocol Compatibility Matrix

| Client Platform | Direct REST (Path A) | Direct AG-UI SSE (Path B) | Requires Adapter | Notes |
|---|:---:|:---:|:---:|---|
| **React (CopilotKit)** | ✅ | ✅ | ❌ | Consumes `/api/ag-ui` via `runtimeUrl`. Alamia Core remains independent. |
| **React (Custom / Native)** | ✅ | ✅ | ❌ | Uses standard `fetch` or `EventSource`. |
| **Vue.js (2 / 3 / Nuxt)** | ✅ | ✅ | ❌ | Uses native `fetch` or browser `EventSource`. |
| **Angular (14+ / RxJS)** | ✅ | ✅ | ❌ | Uses Angular `HttpClient` + SSE observable stream. |
| **Flutter / Dart** | ✅ | ✅ | ❌ | Uses `http` package and Dart `Stream` transformers. |
| **Native iOS (Swift)** | ✅ | ✅ | ❌ | Uses `URLSession` and `URLSessionDataDelegate` for SSE. |
| **Native Android (Kotlin)** | ✅ | ✅ | ❌ | Uses `OkHttp` `EventSourceListener`. |
| **WhatsApp Business API** | ❌ | ❌ | **YES** | Requires Channel Adapter to translate webhook callbacks to REST turns and interactive buttons. |
| **Slack / Telegram Bots** | ❌ | ❌ | **YES** | Requires Channel Adapter bridge to map bot events to Alamia turns. |
| **CLI / Backend Services** | ✅ | ✅ | ❌ | Uses standard `curl`, Python `urllib`/`requests`, or Node `fetch`. |

---

## 5. Client Implementation Examples

### 5.1 React with CopilotKit
CopilotKit frontends connect directly to the streaming AG-UI endpoint. CopilotKit acts strictly as an external consumer; Alamia does not require Copilot Cloud Intelligence:

```tsx
import React from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import "@copilotkit/react-ui/styles.css";

export function CopilotPanel({ sessionToken }: { sessionToken: string }) {
  return (
    <CopilotKit 
      runtimeUrl="http://localhost:8000/api/ag-ui"
      headers={{
        Authorization: `Bearer ${sessionToken}`
      }}
    >
      <div className="copilot-container">
        <CopilotChat 
          labels={{
            title: "Alamia Business Copilot",
            initial: "Welcome! Ask me to review customers, check invoices, or execute workflows."
          }}
        />
      </div>
    </CopilotKit>
  );
}
```

---

### 5.2 Vue.js (Direct REST + HITL Modal)
```vue
<template>
  <div class="copilot-widget">
    <div class="messages">
      <div v-for="(m, i) in messages" :key="i" :class="m.role">{{ m.text }}</div>
    </div>

    <!-- Human-in-the-Loop Confirmation Gate -->
    <div v-if="pendingAction" class="hitl-banner">
      <p><strong>Action Proposed:</strong> {{ pendingAction.reason }}</p>
      <button @click="confirmAction(pendingAction.action_id, true)">Confirm & Execute</button>
      <button @click="confirmAction(pendingAction.action_id, false)">Reject</button>
    </div>

    <input v-model="userInput" @keyup.enter="sendQuery" placeholder="Ask Alamia..." />
  </div>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({ authToken: String });
const messages = ref([]);
const userInput = ref('');
const pendingAction = ref(null);

async function sendQuery() {
  const query = userInput.value;
  messages.value.push({ role: 'user', text: query });
  userInput.value = '';

  const res = await fetch('http://localhost:8000/api/copilot/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${props.authToken}`
    },
    body: JSON.stringify({ query })
  });
  const data = await res.json();
  messages.value.push({ role: 'assistant', text: data.message });

  if (data.proposed_actions?.length > 0) {
    pendingAction.value = data.proposed_actions[0];
  }
}

async function confirmAction(actionId, approve) {
  const endpoint = approve ? '/api/action/confirm' : '/api/action/reject';
  await fetch(`http://localhost:8000${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${props.authToken}`
    },
    body: JSON.stringify({ action_id: actionId })
  });
  pendingAction.value = null;
  messages.value.push({ role: 'system', text: `Action ${approve ? 'approved and executed' : 'rejected'}.` });
}
</script>
```

---

### 5.3 Flutter / Mobile (Dart)
```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class AlamiaCopilotClient {
  final String baseUrl;
  final String authToken;

  AlamiaCopilotClient({required this.baseUrl, required this.authToken});

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer $authToken',
  };

  Future<Map<String, dynamic>> sendQuery(String query) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/copilot/chat'),
      headers: _headers,
      body: jsonEncode({'query': query}),
    );
    return jsonDecode(response.body);
  }

  Future<bool> resolveAction(String actionId, bool approve) async {
    final endpoint = approve ? '/api/action/confirm' : '/api/action/reject';
    final response = await http.post(
      Uri.parse('$baseUrl$endpoint'),
      headers: _headers,
      body: jsonEncode({'action_id': actionId}),
    );
    return response.statusCode == 200;
  }
}
```

---

### 5.4 WhatsApp / Messaging Channel Adapter
Channel platforms (WhatsApp, Slack, Telegram) do not support browser SSE connections. They integrate via an inbound Webhook listener that maps channel identities to server-authenticated context:

```python
"""WhatsApp Business Channel Adapter Bridge."""
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
ALAMIA_RUNTIME_URL = "http://localhost:8000"

# Identity Directory: Map phone numbers to internal authenticated user tokens
PHONE_TO_TOKEN_MAP = {
    "+15551234567": "auth_token_usr_finance_001",
    "+15559876543": "auth_token_usr_exec_002",
}

@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    payload = request.json
    sender_phone = payload.get("from")
    incoming_text = payload.get("text", {}).get("body", "")

    auth_token = PHONE_TO_TOKEN_MAP.get(sender_phone)
    if not auth_token:
        send_whatsapp_text(sender_phone, "Unauthorized: Phone number not registered.")
        return jsonify({"status": "unauthorized"}), 403

    # 1. Forward query to Alamia Copilot via authenticated REST
    headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    copilot_res = requests.post(
        f"{ALAMIA_RUNTIME_URL}/api/copilot/chat",
        headers=headers,
        json={"query": incoming_text}
    ).json()

    # 2. Check for HITL Proposed Actions
    proposed_actions = copilot_res.get("proposed_actions", [])
    if proposed_actions:
        action = proposed_actions[0]
        # Emit Interactive WhatsApp Buttons for human confirmation
        send_whatsapp_buttons(
            to=sender_phone,
            body=f"⚠️ Action Required: {action['reason']}",
            buttons=[
                {"id": f"confirm_{action['action_id']}", "title": "Approve"},
                {"id": f"reject_{action['action_id']}", "title": "Reject"}
            ]
        )
    else:
        send_whatsapp_text(to=sender_phone, text=copilot_res.get("message", "Processed."))

    return jsonify({"status": "ok"}), 200

def send_whatsapp_text(to: str, text: str):
    # Call WhatsApp Cloud API endpoint
    pass

def send_whatsapp_buttons(to: str, body: str, buttons: list):
    # Call WhatsApp Cloud API interactive message endpoint
    pass
```

---

## 6. Concrete cURL Recipes

### 1. Authenticated REST Request (`POST /api/copilot/chat`)
```bash
curl -X POST http://localhost:8000/api/copilot/chat \
  -H "Authorization: Bearer mock_jwt_usr_finance" \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me customer 101"}'
```

### 2. Authenticated AG-UI SSE Stream (`POST /api/ag-ui`)
```bash
curl -N -X POST http://localhost:8000/api/ag-ui \
  -H "Authorization: Bearer mock_jwt_usr_finance" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"skill_id": "payment_followup", "inputs": {"customer_id": "cust_101"}}'
```

### 3. HITL Action Approval (`POST /api/action/confirm`)
```bash
curl -X POST http://localhost:8000/api/action/confirm \
  -H "Authorization: Bearer mock_jwt_usr_finance" \
  -H "Content-Type: application/json" \
  -d '{"action_id": "act_followup_cust_101"}'
```

### 4. HITL Action Rejection (`POST /api/action/reject`)
```bash
curl -X POST http://localhost:8000/api/action/reject \
  -H "Authorization: Bearer mock_jwt_usr_finance" \
  -H "Content-Type: application/json" \
  -d '{"action_id": "act_followup_cust_101"}'
```

---

## 7. Security, Invariants & State Integrity

1. **Deterministic Idempotency Guarantees**:
   - Every `ActionProposal` includes a unique, deterministic `idempotency_key` generated from its domain target and input parameters (e.g. `followup_cust_cust_101_overdue_1`).
   - If an action with the same key has already been executed, re-execution attempts are rejected, preventing duplicate mutations across network retries or repeated user clicks.
2. **Append-Only Immutable Audit Trail**:
   - All skill executions, tool calls, and HITL approvals/rejections append structured audit records into `core/audit/`.
   - Records capture timestamp, user ID, tenant ID, action payload, and status.
3. **Tenant Data Isolation**:
   - All tool lookups and application adapters enforce `tenant_id` filtering on every query and mutation to prevent cross-tenant data leakage.

---

## 8. Verified vs. Planned Capabilities

| Capability | Status | Verification Reference |
|---|:---:|---|
| **Natural Language REST Turns (`/api/copilot/chat`)** | **Verified** | [`tests/test_client_interoperability.py`](file:///e:/Alamia/AlamiaAICopilot-Starter/tests/test_client_interoperability.py) |
| **AG-UI SSE Event Streaming (`/api/ag-ui`)** | **Verified** | [`tests/test_ag_ui_server.py`](file:///e:/Alamia/AlamiaAICopilot-Starter/tests/test_ag_ui_server.py), [`tests/test_raw_wire_protocol.py`](file:///e:/Alamia/AlamiaAICopilot-Starter/tests/test_raw_wire_protocol.py) |
| **HITL Interrupt & Confirm/Reject Lifecycle** | **Verified** | [`examples/raw_wire_client.py`](file:///e:/Alamia/AlamiaAICopilot-Starter/examples/raw_wire_client.py), Standalone SPA (`http://localhost:8080`) |
| **Decoupled Standalone Frontend Client** | **Verified** | [`examples/standalone_external_spa/`](file:///e:/Alamia/AlamiaAICopilot-Starter/examples/standalone_external_spa/) |
| **Zero Core Framework Dependencies** | **Verified** | [`tests/test_architectural_negative.py`](file:///e:/Alamia/AlamiaAICopilot-Starter/tests/test_architectural_negative.py) |
| **Backend RBAC Policy Enforcement** | **Verified** | [`tests/test_platform_independence.py`](file:///e:/Alamia/AlamiaAICopilot-Starter/tests/test_platform_independence.py) |
| **Production JWT / OAuth2 Gateway Filter** | *Planned* | Reference runtime uses in-process token mapping; OAuth2/OIDC filter planned for Phase 6. |
| **Cryptographic Merkle Audit Proofs** | *Planned* | Current audit log is append-only structured storage; cryptographic signature trees planned for compliance add-on. |
| **Live WhatsApp Cloud API Webhook Service** | *Planned* | Architecture & adapter recipe documented; live production webhook connector is in roadmap. |
