# Current Sprint & System State

**Date:** 2026-09-03
**Status:** Operational / Multi-Model Tiered SLM Evaluated & ADR 001 Recorded

---

## 1. Running Services Status

| Service | Container Name | Port / Protocol | Health / Status | Notes |
|---|---|---|---|---|
| **PostgreSQL 16** | `odoo_db` | `5432/tcp` | **Healthy** | Database `odoo_hospital` initialized |
| **Odoo 19.0 Community** | `odoo_web` | `8069`, `8072` | **Running** | Werkzeug HTTP server & XML-RPC active |
| **In-Odoo MCP Addon** | `addons/mcp_server` | `/mcp` | **Active (HTTP 200)** | Master switch enabled, OAuth 2.1 ready |
| **FastMCP Standalone Server** | `odoo_mcp` | `8008/tcp` | **Active (HTTP 200)** | FastMCP 4.0.2 serving SSE on `/sse` |
| **Zelix Copilot Backend** | `zelix_copilot` | `8010/tcp` | **Active (HTTP 200)** | Multi-model SLM orchestration backend |
| **ZelixVet Copilot PWA** | `zelix-copilot-app` | `5173/tcp` | **Active (HTTP 200)** | Vite PWA with 11 Stitch clinical screens |
| **Ollama Local Engine** | `localhost:11434` | `11434/tcp` | **Active (HTTP 200)** | Gemma 3 1B, Qwen 3.5 4B, Qwen 2.5 7B, DeepSeek R1 14B |

---

## 2. Active Addons & Installed Modules
- **`mcp_server` (v19.0.2.1.0):** Model Context Protocol endpoint and permission layer.
- **`vet_installer` (v19.0.1.0.0):** Complete VetCairn veterinary practice management suite (22 modules active).
- **`stratos_hms` (v19.0.1.0.0):** Complete Human Hospital Management & EMR suite with AI Scribe, Hospital Case Memory, Learned Rules, and Command Centre (39 models active).
- **`zelix_ai` (v19.0.1.0.0):** Native Odoo 19 OWL 2 Copilot UI, In-Odoo Provider Settings (`res.config.settings`), Learned Prescribing Rules (`zelix.ai.rule`), Institutional Case Memory (`zelix.case.memory`), Systray launcher, Slide-out Drawer, Action Cards, Audit Ledger.
- **`stratos_vet_case_memory` (v19.0.1.0.0):** Veterinary Clinical Suggestions & Case Memory suite with similarity-based case matching, self-learning patterns (`vet.cm.pattern`), voice dictation (`vet.cm.voice.note`), and automated approval queues.
- **`stratos_vet_exam` & `stratos_vet_exam_vetcairn` (v19.0.1.0.0):** Structured Veterinary Exam Template builder (SOAP), vitals capture, and direct two-way sync with VetCairn encounters (`vet.encounter`) and patients (`vet.patient`). Connector modules `stratos_vet_case_memory_soap` and `stratos_vet_case_memory_vetcairn` bridge exam findings into case memory.
- **`stratos_crm_rfp` (v20.0.1.1.0, Odoo 19 compatible):** International RFP lifecycle tracking on CRM leads (`crm.lead`) with questionnaire and proposal deadlines, attachment management, automated reminder activities, and dedicated OWL 2 RFP Dashboard.
- **`stratos_social` (v20.0.1.2.0, Odoo 19 compatible):** Stratos Social Marketing suite for scheduling and publishing posts across Facebook Pages, Instagram Business, YouTube channels, and TikTok with multi-company isolation and token authentication wizards.
- **Alamia AI Gateway & Edge Workers:** Native serverless edge inference layer leveraging Cloudflare Workers AI free tier (10,000 neurons/day) with `@cf/meta/llama-3.1-8b-instruct-fp8`, `@cf/meta/llama-3.2-3b-instruct`, and `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b`.
- **100+ Total Models Exposed:** VetCairn + HMS + Zelix + Stratos Social (`stratos.social.*`) + CRM (`crm.lead`) + Core models registered in `mcp.enabled.model` with full CRUD access.

---

## 3. Verified Sample Clinical & Inventory Case
- **Clinic:** `VetCairn Downtown Animal Hospital` (ID: 3)
- **Patient:** `Max` (ID: 3, Canine, Identifier: `PAT-000004`, Status: `active`)
- **Appointment:** `Annual Wellness Check & Vaccination` (ID: 6, Status: `confirmed`)
- **Physical Pharmacy Inventory:** 4 pharmaceutical products stocked with verified quantities on hand, shelf locations, and reorder levels in `product.product` / `stock.quant`.

---

## 4. Work Accomplished vs. Pending Matrix

### ✅ COMPLETED & VERIFIED (Phases 1 to 5 + Model Evaluation)

1. **Phase 1: Infrastructure & Odoo 19 Setup**:
   - Deployed Odoo 19 Community + PostgreSQL 16 on Docker with live hot-reloading mounts.
   - Installed complete VetCairn suite (22 veterinary modules).
   - Configured XML-RPC & FastMCP bridges with 38 clinical models.

2. **Phase 2: Zelix Copilot Backend Architecture**:
   - Multi-Model SLM Provider Adapter & Router.
   - Role Security Policy Matrix (`roles/policy.py`) for Practice Manager, Doctor, Technician, Receptionist.
   - Dynamic Clinical Context Engine (`context/context_engine.py`) extracting longitudinal EHR context.
   - Clinical Action Card Protocol (`workflows/base_workflow.py`).

3. **Phase 3: P0 Hardening & Zero-Hallucination Pipeline**:
   - Deterministic Intent Router (`router/intent_router.py`) preventing workflow hijacking.
   - Deterministic Contradiction Validator (`validators/clinical_validator.py`).
   - Ambient Scribe SOAP Workflow (`w04_scribe_soap`), Pre-Consult (`w02`), Summary (`w01`), Rx Assistant (`w09`).
   - Strict Odoo Read-Back Persistence Verification (`CREATE -> READ -> ASSERT -> VERIFY`).
   - Audit Ledger (`audit/audit_ledger.py`) and in-Odoo `zelix.copilot.audit` model.

4. **Phase 4: Native Odoo 19 OWL 2 Web Client (`addons/zelix_ai`)**:
   - Top navbar Systray launcher (`copilot_systray.js` & `.xml`).
   - Slide-out Copilot Drawer (`copilot_sidebar.js` & `.xml`) with `markup()` rich HTML rendering.
   - Human-in-the-Loop Action Approval Cards (`action_card.js` & `.xml`).
   - Practice Operations & Physical Inventory Tracking (`w00_practice_query`).

5. **Phase 5: Multi-Model SLM Clinical Evaluation & ADR 001**:
   - Benchmarked `gemma3:1b-it-qat`, `qwen3.5:4b`, `qwen2.5:7b-instruct`, `deepseek-r1:14b`, and `BitNet 1.58b`.
   - Identified `qwen3.5:4b` thinking token mechanics and requirements for production JSON extraction.
   - Approved and recorded **[`ADR 001`](file:///e:/myapps/odoo-mcp/.ai/permanent/adr/001-multi-model-tiered-routing-and-safety.md)** for Tiered VPS Routing (`gemma3:1b` + `qwen3.5:4b` + `qwen2.5:7b` + `bge-m3`).

6. **Phase 6: Serverless Edge AI Gateway & Zero-Touch Deployment Automation**:
   - Deployed Alamia AI Gateway & Edge Workers integration with Cloudflare Workers AI free tier (10,000 daily neurons).
   - Installed `stratos_vet_case_memory_suite` without manual VPS SSH/bash commands.
   - Portainer Stack environment variables (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_GATEWAY_ID`, `CLOUDFLARE_MODEL`) auto-provision both Zelix AI and Vet Case Memory on container start via `setup_odoo_mcp_orm.py` and direct `os.getenv` fallback in `VetCmAiClient`.

---

### ⏳ PENDING & NEXT PRIORITIES (Phase 6)

1. **Production VPS Deployment Automation**:
   - Configure Ollama / vLLM runtime configurations for the tiered models with optimized context limits and thread allocations.
2. **Dense Semantic Retrieval (BGE-M3 RAG)**:
   - Vectorize historical encounters and lab documents to ground clinical prompts automatically.
3. **Proactive Background Clinical Task Queue**:
   - Background job scanning for overdue vaccine boosters, post-op recall checks, and low-inventory reorders.
