# Alamia AI Copilot Architecture

## Overview
Alamia AI Copilot is a modular, platform-agnostic boilerplate for embedding AI Copilots and autonomous AI Employees into arbitrary business applications without coupling the core runtime to any specific web framework, ORM, database, or LLM provider.

---

## Canonical Architecture

```text
          ┌────────────────────────────────────────────────────────┐
          │      CopilotKit Reference UI (React / Next.js)         │
          │  (Streaming, Generative UI, HITL Confirmation Modals)   │
          └──────────────────────────┬─────────────────────────────┘
                                     │ AG-UI Protocol (SSE/HTTP)
                                     ▼
                      ┌─────────────────────────────┐
                      │      AG-UI Edge Adapter     │
                      └──────────────┬──────────────┘
                                     │
                             ALAMIA AI COPILOT
                                     │
                            AI EMPLOYEE RUNTIME
                                     │
                  ┌──────────────────┼──────────────────┐
                  │                  │                  │
                Role              Session            Memory
              Manifest            Context         Typed Context
                  └──────────────────┼──────────────────┘
                                     ↓
                              Skill Registry
                                     ↓
                              Selected Skill
                                     ↓
                       ┌─────────────┼─────────────┐
                       ↓             ↓             ↓
                  Business       Knowledge      Events
                    Tools           Tools       /Triggers
                       └─────────────┼─────────────┘
                                     ↓
                                AI Router
                                     ↓
                         AI Model Provider Interface
                                     ↓
                     Local / Private / Cloud Models
                                     ↓
                              ActionProposal
                                     ↓
                   Authorization / Confirmation Policy
                                     ↓
                              Idempotency
                                     ↓
                           Application Adapter
                                     ↓
                  ┌──────────────────┼──────────────────┐
                  ↓                  ↓                  ↓
                 MCP                REST               SDK
                  ↓                  ↓                  ↓
               Odoo              Laravel             FastAPI
                                     ...
                                     ↓
                                   Audit
```

---

## Sacred Architectural Boundaries

1. **Deterministic Business Tools**: Return structured facts directly from application adapters. Business tools must never perform hidden LLM reasoning.
2. **Business Skills**: High-level workflows orchestrating tools, context, and reasoning. Skills must never import host application ORMs or framework-specific APIs.
3. **Structured Action Proposals**: All mutations begin as an `ActionProposal`. The backend evaluates intent, calculates risk, verifies permissions, checks idempotency, and enforces human confirmation.
4. **Application Adapter**: The core runtime accesses external domain entities purely through `ApplicationAdapter`. Host frameworks (Odoo, Laravel, FastAPI, etc.) are isolated at the edge.
5. **Agent UX & Transports**: CopilotKit is adopted at the edge as the reference Agent UX connected via the standardized `AG-UI` protocol.
