# Open Source Software (OSS) Evaluation

## Overview
This document evaluates candidate open-source frameworks and libraries for potential integration with the Alamia AI Copilot Boilerplate.

Evaluation Criteria:
1. Problem solved
2. License & IP compliance
3. Production maturity & activity
4. Self-hosting capability (zero proprietary cloud dependencies)
5. Provider neutrality (no lock-in to OpenAI, Anthropic, etc.)
6. Backend & framework neutrality (no required coupling to FastAPI, Node, LangChain, etc.)
7. Architectural decision: **Adopt directly**, **Wrap behind Alamia interface**, **Optionally integrate as adapter**, or **Reject**.

---

## Candidate Evaluations

| Candidate | License | Maturity | Self-Hostable | Role in Alamia | Architectural Decision |
|-----------|---------|----------|---------------|----------------|------------------------|
| **CopilotKit** | MIT | High | Yes (OSS core) | Reference Agent UX | **Wrap / Edge Reference UX** (Adopt OSS React UI + AG-UI adapter; Reject CopilotKit Intelligence cloud) |
| **AG-UI Protocol** | Open / MIT | Medium-High | Yes | Agent ↔ App Protocol | **Adopt as Adapter Protocol** (`adapters/ag_ui/` for standardized agent streaming) |
| **Model Context Protocol (MCP)** | MIT | High | Yes | External Tool Transport | **Optional Adapter** (`adapters/application/mcp/`; never a core dependency) |
| **Pydantic / PydanticAI** | MIT | High | Yes | Typing / Contracts | **Adopt Pydantic for Core Typing**; wrap agent mechanics behind Alamia interfaces |
| **LangGraph** | MIT | High | Yes | Agent Orchestration | **Wrap / Reject for Core**; Alamia maintains its own state machine and policy engine |
| **LiteLLM** | MIT | High | Yes | Multi-provider LLM proxy | **Optional Adapter** (`adapters/ai/providers/litellm_provider.py`) |
| **Langfuse / OpenTelemetry**| MIT / Apache 2.0 | High | Yes | Observability & Audit | **Wrap behind Audit Interface** (`core/audit/` can export to OTel / Langfuse) |
| **Guardrails AI** | Apache 2.0 | Medium-High | Yes | Guardrails / Safety | **Wrap behind Policy Engine** (Alamia backend policies remain sovereign) |

---

## Detailed Findings

### 1. CopilotKit & AG-UI
- **Fit**: Excellent for Agent UX (React components, streaming, generative UI widgets, HITL approval dialogs).
- **Strategy**: Use AG-UI as a transport adapter (`adapters/ag_ui/`). Keep `core/` 100% agnostic. Use the open-source CopilotKit React SDK on the frontend without relying on paid/cloud CopilotKit Intelligence.

### 2. Model Context Protocol (MCP)
- **Fit**: Industry-standard protocol for exposing application capabilities and data sources as deterministic tools over stdio/SSE.
- **Strategy**: Implement as an optional application adapter (`adapters/application/mcp/`). Core runtime operates purely on abstract `ApplicationAdapter` and `ToolDefinition`.

### 3. Pydantic
- **Fit**: Essential for robust data contracts, strict schema validation, type safety, and JSON serialization.
- **Strategy**: Adopt Pydantic for all core models (`ActionProposal`, `SkillDefinition`, `RoleManifest`, `EmployeeContext`, `MemoryRecord`, `EmployeeEvent`).

### 4. AI Providers (LiteLLM / Direct / Local)
- **Fit**: Multiple model providers (local Ollama, vLLM, OpenAI-compatible APIs, cloud endpoints).
- **Strategy**: Standardize on `AIModelProvider` and `AIModelRouter` interfaces in `core/ai/`. Specific SDKs live in `adapters/ai/providers/`.

### 5. Audit & Observability (OpenTelemetry / Langfuse)
- **Fit**: Structured audit trails and traces for agent invocations, tool executions, and security decisions.
- **Strategy**: Core provides `AuditLogger` interface; adapters stream events to OpenTelemetry, local logs, or persistence stores.
