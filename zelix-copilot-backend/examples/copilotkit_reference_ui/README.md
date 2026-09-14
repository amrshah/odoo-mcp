# CopilotKit Reference UI for Alamia AI Copilot

This reference UI demonstrates how to integrate **CopilotKit React components** with the **Alamia AI Copilot Core** using the **AG-UI protocol**.

## Architecture

```text
React / Next.js UI (CopilotKit)
          │  AG-UI Protocol (SSE / HTTP)
          ▼
AGUIHandler (`adapters/ag_ui/server.py`)
          │
    CopilotEngine (`core/runtime/engine.py`)
          │
    ApplicationAdapter (`adapters/application/`)
```

## Features Demonstrated
1. **Streaming Chat**: Real-time token streaming with `@copilotkit/react-ui`.
2. **Generative UI**: Contextual cards like `Customer360Widget` embedded in the UI.
3. **Human-in-the-Loop (HITL) Interrupts**: High-risk actions proposed by Skills trigger `HITLApprovalModal` before backend execution.
4. **100% Self-Hostable**: Does NOT require CopilotKit Intelligence cloud subscription.
