# Session Handoff: Multi-Model SLM Benchmarking, Architecture ADR & Deterministic Invariants

**Date:** 2026-09-03  
**Status:** Ready for Continuation  
**Branch / Workspace:** `e:\myapps\odoo-mcp`

---

## 1. Summary of Accomplishments This Session

1. **Multi-Model Clinical Evaluation Suite (Stage A & Stage B)**:
   - Evaluated 5 model candidates across 4 clinical battery tests (W04 Ambient Scribe SOAP Extraction, W09 Prescription Extraction, Contradiction Detection, and Acute Abdomen Differential Reasoning).
   - Evaluated: `BitNet-1.58b-2B` (remote), `gemma3:1b-it-qat` (local Ollama), `qwen3.5:4b` (local Ollama), `qwen2.5:7b` (local Ollama), and `deepseek-r1:14b` (local Ollama).
   - Saved full comparative report and telemetry in [`clinical_model_comparison_report.json`](file:///e:/myapps/odoo-mcp/zelix-copilot-backend/clinical_model_comparison_report.json).

2. **Empirical Findings & Insights**:
   - **`gemma3:1b-it-qat` (1.0 GB)**: Ultra-fast worker (45–125 tok/s, ~660ms for Rx extraction). Ideal for intent routing, query normalization, and quick UI greetings.
   - **`qwen3.5:4b` (3.4 GB)**: Deep reasoning via `<think>` stream (spends ~540 thinking tokens). Requires `num_predict >= 2048` when generating structured JSON to avoid token truncation.
   - **`qwen2.5:7b-instruct` (4.7 GB)**: Excellent all-around instruct model (5.4s avg latency), passed 100% of clinical tests.
   - **`deepseek-r1:14b` (9.0 GB)**: Deep clinical reasoning, but CPU latency is high (84.4s avg), making it strictly an offline/escalation tier.
   - **`BitNet 1.58b`**: Deprecated as clinical extraction engine due to non-standard nested formatting and missing contradiction checks.

3. **Permanent Architecture & ADR Documentation**:
   - Created **[`ADR 001: Multi-Model Tiered SLM Routing & Clinical Safety Validation Architecture`](file:///e:/myapps/odoo-mcp/.ai/permanent/adr/001-multi-model-tiered-routing-and-safety.md)**.
   - Updated **[`01-system-architecture.md`](file:///e:/myapps/odoo-mcp/.ai/permanent/architecture/01-system-architecture.md)** reflecting the Multi-Model Tiered topology (`gemma3:1b` + `qwen3.5:4b` + `qwen2.5:7b` + `bge-m3`).
   - Reaffirmed the **Deterministic Safety Invariant**: no LLM validates another LLM; contradiction checks (e.g. `BID (once daily)`) and schema validation are enforced strictly in code before presenting Action Cards.
   - Grounded all practice census and inventory queries directly in live Odoo ORM records (`vet.patient`, `vet.appointment`, `product.product`, `stock.quant`).

4. **FastMCP & In-Odoo Integration**:
   - Verified active FastMCP standalone server (`:8008`) and Zelix Copilot Backend (`:8010`).
   - Verified strict `CREATE -> READ -> ASSERT` persistence pipeline for all Action Proposal Card executions.

---

## 2. Active Services & Ports

| Service | Port | Endpoint | Status |
|---|---|---|---|
| **Odoo 19 Community** | `8069` | `http://localhost:8069` | Running (Docker) |
| **PostgreSQL 16** | `5432` | `localhost:5432` (`odoo_hospital`) | Running (Docker) |
| **FastMCP Server** | `8008` | `http://localhost:8008/sse` | Running (Docker) |
| **Zelix Copilot Backend** | `8010` | `http://localhost:8010` | Running (`main.py`) |
| **Ollama Local SLM** | `11434` | `http://localhost:11434/api/chat` | Running (Local) |

---

## 3. Next Session Priorities

1. **VPS Multi-Model Deployment Preparation**:
   - Prepare deployment scripts/configs for the target VPS (e.g., Docker / Ollama / vLLM stack) hosting:
     - `gemma3:1b-it-qat` (Worker / Router)
     - `qwen3.5:4b` (Primary Clinical Engine with `num_predict >= 2048`)
     - `qwen2.5:7b-instruct` (Clinical Authority)
     - `bge-m3` (Dense Retrieval & RAG)
2. **Proactive Background Task Queue**:
   - Implement scheduled cron job scanning for overdue vaccine boosters, post-op recall checks, and low-inventory restock alerts.
3. **BGE-M3 Dense Retrieval Pipeline**:
   - Connect `bge-m3` to vectorize prior encounter notes and lab histories for semantic grounding before calling the clinical SLM.
