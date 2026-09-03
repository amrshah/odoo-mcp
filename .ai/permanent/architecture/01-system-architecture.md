# System Architecture

## 1. Executive Summary & Goal
The primary goal of this project is to build an **AI Copilot** for an Odoo-based Veterinary Clinic / Hospital Management System (**VetCairn**). The system connects AI assistants (Claude, Cursor, web copilots, custom agents) to Odoo via the **Model Context Protocol (MCP)**, allowing natural language queries and execution of clinical workflows (e.g., patient lookup, appointment scheduling, treatment tracking, diagnostic orders, prescription generation).

---

## 2. High-Level Architecture

```mermaid
graph TD
    subgraph UI & Web Client Layer
        WebClient["Odoo 19 OWL 2 Web Client (:8069)"]
        Systray["Zelix AI Systray Launcher"]
        Drawer["Copilot Sidebar Drawer"]
        Cards["Human Approval Action Cards"]
        Systray --> Drawer
        Drawer --> Cards
    end

    subgraph Zelix AI Copilot Backend (:8010)
        Router["Deterministic Intent Router"]
        ContextEng["Clinical Context Engine (EHR)"]
        Validator["Clinical Contradiction Validator"]
        AuditLedger["Audit Ledger (zelix.copilot.audit)"]
        
        subgraph Multi-Model Tiered SLM Layer
            Gemma["Gemma 3 1B (Fast Worker)"]
            Qwen4B["Qwen 3.5 4B (Primary Clinical)"]
            Qwen7B["Qwen 2.5 7B Instruct (Clinical Authority)"]
            BGEM3["BGE-M3 (Embedding / RAG)"]
        end
    end

    subgraph MCP & Integration Layer
        FastMCP["FastMCP Server (:8008)<br/>Stdio & SSE Transport"]
        InAppMCP["In-Odoo MCP Addon (/mcp)<br/>OAuth 2.1 & REST/JSON-RPC"]
    end

    subgraph Odoo 19 Core & Business Modules
        OdooWeb["Odoo 19.0 Community (:8069)"]
        VetCairn["VetCairn Veterinary Suite (22 Modules)<br/>Patients, Appointments, Encounters, Rx, Inventory"]
    end

    subgraph Storage Layer
        PostgreSQL[("PostgreSQL 16 DB (odoo_hospital)")]
        Filestore[("Odoo Web Data Volume")]
    end

    Drawer <-->|JSON-RPC /zelix_ai/chat| Router
    Cards <-->|JSON-RPC /zelix_ai/action/approve| FastMCP
    Router --> ContextEng
    ContextEng --> Gemma
    ContextEng --> Qwen4B
    ContextEng --> Qwen7B
    ContextEng --> BGEM3
    Qwen4B --> Validator
    Qwen7B --> Validator
    Validator --> Cards
    FastMCP <-->|XML-RPC API| OdooWeb
    OdooWeb <--> VetCairn
    OdooWeb <--> PostgreSQL
    OdooWeb <--> Filestore
```

---

## 3. Multi-Model Tiered SLM Topology

| Tier | Model Identifier | Memory Footprint | Role & Workflows Assigned |
|---|---|---|---|
| **Tier 0 (RAG & Retrieval)** | `bge-m3` | ~1.2 GB | Dense vector search across patient medical histories, prior encounters, and SOAP notes. |
| **Tier 1 (Fast Worker)** | `gemma3:1b-it-qat` | ~1.0 GB | Intent classification, query normalization, fast census lookups, and greetings (< 2s). |
| **Tier 2 (Primary Clinical)** | `qwen3.5:4b` | ~3.4 GB | Consultation transcription scribe (W04), Pre-consult brief (W02), Rx extraction (W09). |
| **Tier 3 (Clinical Authority)** | `qwen2.5:7b-instruct` | ~4.7 GB | Non-coder general instruct authority for difficult multi-turn cases and complex differentials. |
| **Deterministic Layer** | Python Regex & Schema | 0 MB | Authoritative safety validation (`validators/clinical_validator.py`) and Odoo read-back verification. |

---

## 4. Core Components

### A. Odoo 19 Community & PostgreSQL 16
- **Container Environment:** Multi-container Docker Compose with PostgreSQL 16 Alpine and `odoo:19.0`.
- **Database:** `odoo_hospital` initialized with core Odoo modules and complete VetCairn practice suite.
- **Port Mapping:** Port `8069` (HTTP web interface & XML-RPC), Port `8072` (Longpolling).

### B. In-Odoo MCP Server Addon (`addons/mcp_server`)
- Native Odoo module exposing HTTP `/mcp` (JSON-RPC 2.0 / Streamable HTTP).
- Implements RFC 9728 & RFC 8414 OAuth 2.1 discovery (`/.well-known/oauth-authorization-server`).
- Model-level access gating via `mcp.enabled.model` records and security groups (`MCP User`, `MCP Administrator`).

### C. Standalone FastMCP Server (`mcp-server/`)
- Python-based microservice implementing FastMCP 4.x.
- Exposes 10 core tools covering schema introspection, `search_read`, CRUD operations, and generic business method calls (`execute_kw`).
- Dual transport: **SSE** (port `8008`) for network copilots and **stdio** for local desktop agents.

### D. VetCairn Veterinary Clinic Suite (`addons/VetCairn/`)
- Comprehensive clinical management system comprising 22 specialized modules:
  - `vet_base`: Patients (`vet.patient`), Species (`vet.species`), Breeds (`vet.breed`), Clinics (`vet.clinic`).
  - `vet_appointment`: Scheduling, appointment types, provider assignments.
  - `vet_clinical`: Clinical encounters (`vet.encounter`), SOAP notes, diagnoses (`vet.diagnosis`).
  - `vet_prescription`: Medication orders (`vet.prescription`, `vet.medication`).
  - `vet_vaccination`: Vaccine protocols (`vet.vaccination`, `vet.vaccine.protocol`).
  - `vet_treatment`: Treatment plans (`vet.treatment.plan`) and activities.
  - `vet_diagnostic`: Lab and imaging orders (`vet.diagnostic.order`, `vet.diagnostic.type`).
  - `vet_admission`: Wards (`vet.ward`), beds/cages (`vet.bed`), inpatient admissions.
  - `vet_billing`, `vet_inventory`, `vet_documents`, `vet_reminder`, `vet_communication`, `vet_dashboard`.

---

## 5. Invariants & Guiding Principles

1. **Deterministic Safety Enforcement:** Never rely on an LLM to validate another LLM. All medical prescriptions and dosages must be validated deterministically by code before being presented for human approval.
2. **Permission Parity:** All MCP operations execute strictly under the permissions of the authenticated Odoo user (UID). Elevated permissions are never bypassed.
3. **Strict Read-Back Persistence Verification:** Every write operation executes a `CREATE -> READ -> ASSERT` cycle to ensure database persistence before marking an Action Card executed.
4. **Physical Inventory vs. Formulary Separation:** Physical stock levels (`product.product`, `qty_available`, `vet_storage_location`) are tracked separately from static drug catalog entries (`vet.medication`).
5. **Human-in-the-Loop Approval:** No clinical prescription or diagnostic order is written to Odoo without explicit clinician review and approval.
