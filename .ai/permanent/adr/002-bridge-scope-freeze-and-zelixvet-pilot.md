# ADR 002: Alamia OdooBridge Feature Freeze & ZelixVet Controlled Integration Pilot

**Date:** 2026-11-06  
**Status:** Approved / Active  
**Deciders:** Lead Systems Architect & AI Engineering Team  
**Context:** Alamia OdooBridge v0.1.2 Hardening, FastMCP Compatibility, and ZelixVet Clinical Integration.

---

## 1. Context & Problem Statement

Alamia OdooBridge has completed its focused security and protocol hardening pass (v0.1.2):
- Implemented Odoo 19 JSON-2 named-parameter adapter alongside the standard XML-RPC adapter.
- Distinguished credential invalidity (HTTP 401 `AuthenticationError`) from model access restrictions (HTTP 403 `PermissionDeniedError`).
- Implemented role-aware model discovery (`check_model_discovery`) with cache isolation.
- Enforced strict multi-company boundary constraints (`allowed_company_ids`).
- Converted FastMCP authentication middleware to pure ASGI supporting SSE and Streamable HTTP.
- Set default `READ_ONLY` execution policy with explicit service write scopes.

Rather than continuously expanding feature scope (which introduces stability risks), the bridge must be frozen at v0.1.2 and tested against a real clinical consumer (ZelixVet Copilot Backend). ZelixVet currently relies on a direct XML-RPC adapter (`ZelixOdooAdapter`). A naive immediate cutover could risk regressions in live clinical workflows (SOAP notes, prescriptions, census queries).

---

## 2. Decision

1. **Freeze Bridge Feature Scope at v0.1.2**:
   - The 10 canonical FastMCP tools, `OdooClient` API, security policies, and adapter interfaces are locked.
   - No experimental toolpacks, licensing gates, or domain-specific workflows will be added to `alamia-odoobridge`.
   - The standalone repository (`https://github.com/AlamiaSoft/alamia-odoo-bridge`) and monorepo package (`packages/alamia-odoobridge`) serve as the canonical connectivity foundation.

2. **Implement Dual-Mode Shadow Pilot in ZelixVet**:
   - Refactor `ZelixOdooAdapter` to support configurable backends via `ZELIX_ODOO_PILOT_MODE`:
     - `direct`: Legacy direct XML-RPC connection (zero risk, rollback baseline).
     - `dual`: Executes the primary call via the direct adapter, concurrently/shadow executes via `alamia_odoobridge.OdooClient`, compares results for exact schema and data parity, logs discrepancies and latency deltas to the audit log, and returns the direct output.
     - `bridge`: Fully routes all traffic through `alamia_odoobridge.OdooClient`.
   - The pilot defaults to `dual` mode in development/staging environments and `direct` mode in unverified production paths.

3. **Parity Verification Matrix**:
   - Parity must be verified across 5 distinct dimensions:
     - Read Operations (patients, appointments, encounters, inventory, census).
     - Write Operations (encounters, appointments, prescription issuance, updates).
     - Allowlisted business methods.
     - Role-based authorization boundaries.
     - Multi-company context isolation.

4. **Rollback & Cutover Gate**:
   - The legacy direct path will remain available in the codebase until the dual-mode shadow pilot records zero parity violations across the full test suite and clinical benchmark scenarios.

---

## 3. Consequences

### Positive
- Zero disruption to existing clinical operations during pilot integration.
- Quantitative parity evidence and latency profiling before full cutover.
- Strict architectural decoupling: Alamia OdooBridge owns protocol and security; ZelixVet owns clinical workflows.

### Tradeoffs
- Temporary duplicate execution overhead while operating in `dual` mode.
- Requires maintaining parity comparison assertions for any changes to domain entity schemas.
