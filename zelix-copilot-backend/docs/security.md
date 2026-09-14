# Security Architecture & Policies

Security in Alamia AI Copilot is built on the fundamental principle of **Backend Authority**.

---

## 1. Zero Trust for LLM Claims

The core runtime NEVER trusts LLM-generated output for:
- Permissions or Roles
- Risk Level ratings
- Confirmation bypasses (`"requires_confirmation": false`)
- Action executability

The LLM proposes intent; the backend **PolicyEngine** authoritatively evaluates intent.

---

## 2. Policy Enforcement Pipeline

```text
LLM Proposes Action
        ↓
PolicyEngine.evaluate_proposal()
        ├─ 1. PermissionPolicy: Check context.has_permission(required_permission)
        ├─ 2. RiskPolicy: Classify authoritative backend risk (LOW, MEDIUM, HIGH, CRITICAL)
        └─ 3. ConfirmationPolicy: Force AWAITING_CONFIRMATION if risk >= HIGH or action in always-confirm list
        ↓
ActionExecutor (Requires CONFIRMED status before dispatching mutation to ApplicationAdapter)
```
