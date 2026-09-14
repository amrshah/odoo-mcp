# Action System & State Machine

Every state mutation in Alamia AI Copilot is structured as an **ActionProposal** and governed by the **ActionStateMachine**.

---

## 1. Action Lifecycle States

```text
               ┌───────────────┐
               │   PROPOSED    │
               └───────┬───────┘
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
┌────────────────────────┐    ┌─────────────────┐
│ AWAITING_CONFIRMATION  │    │    CONFIRMED    │
└──────────────┬─────────┘    └────────┬────────┘
               │                       │
               ▼                       ▼
       ┌───────────────┐      ┌─────────────────┐
       │   REJECTED    │      │    EXECUTING    │
       └───────────────┘      └────────┬────────┘
                                       │
                               ┌───────┴───────┐
                               ▼               ▼
                       ┌───────────────┐ ┌───────────┐
                       │   COMPLETED   │ │  FAILED   │
                       └───────────────┘ └───────────┘
```

---

## 2. Idempotency Key Enforcement

Every executable action includes an `idempotency_key`. The `ActionExecutor` tracks all executed keys. If an action with an identical key is received:
- If already `COMPLETED`, the cached outcome is returned immediately without re-executing.
- If in `EXECUTING` or `FAILED`, an `IdempotencyViolationError` is raised.
