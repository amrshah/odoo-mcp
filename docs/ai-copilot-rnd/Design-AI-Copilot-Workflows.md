

# User

did a quick odoo setup on local docker; working on creating  AI Copilot for Odoo using the MCP server as detailed below; goal is to create our ClinicFlow/Zelix Vet's own AI Copilot along with AI features e.g. notes taker as the doctor consults a patient; need to see high value, regular use pain point workflows which should be automated with AI:

# System Architecture



## 1. Executive Summary & Goal

The primary goal of this project is to build an **AI Copilot** for an Odoo-based Veterinary Clinic / Hospital Management System (**VetCairn**). The system connects AI assistants (Claude, Cursor, web copilots, custom agents) to Odoo via the **Model Context Protocol (MCP)**, allowing natural language queries and execution of clinical workflows (e.g., patient lookup, appointment scheduling, treatment tracking, diagnostic orders, prescription generation).



---



## 2. High-Level Architecture



```mermaid

graph TD

    subgraph AI Layer

        Copilot["AI Copilot / Client (Claude, Antigravity, Custom Agent)"]

    end



    subgraph MCP Layer

        InAppMCP["In-Odoo MCP Addon (/mcp)<br/>OAuth 2.1 & REST/JSON-RPC"]

        FastMCP["FastMCP Server (:8008)<br/>Stdio & SSE Transport"]

    end



    subgraph Odoo 19 Core & Business Modules

        OdooWeb["Odoo 19.0 Community (:8069)"]

        VetCairn["VetCairn Veterinary Suite (22 Modules)<br/>Patients, Appointments, Encounters, Rx"]

    end



    subgraph Storage Layer

        PostgreSQL[("PostgreSQL 16 DB (odoo_hospital)")]

        Filestore[("Odoo Web Data Volume")]

    end



    Copilot <-->|HTTP /mcp / OAuth 2.1| InAppMCP

    Copilot <-->|SSE / Stdio MCP Protocol| FastMCP

    FastMCP <-->|XML-RPC API (2/common, 2/object)| OdooWeb

    InAppMCP <--> OdooWeb

    OdooWeb <--> VetCairn

    OdooWeb <--> PostgreSQL

    OdooWeb <--> Filestore

```



---



## 3. Core Components



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



## 4. Invariants & Guiding Principles



1. **Permission Parity:** All MCP operations execute strictly under the permissions of the authenticated Odoo user (UID). Elevated permissions are never bypassed.

2. **Schema Introspection First:** AI Copilots must inspect model schemas (`odoo_get_model_fields`) before generating write/create payloads to ensure required fields and relation types are satisfied.

3. **Module Isolation:** Custom clinical code resides inside `addons/` and does not modify Odoo core code.

4. **Odoo.sh Compatibility:** All addons follow Odoo 19 module standards, with dependencies maintained in `requirements.txt` for direct deployment to Odoo.sh Git repositories.



---



## 5. Failure Modes & Mitigations



| Failure Mode | Cause | Mitigation |

|---|---|---|

| `Port Allocation Conflict` | Host port 8000 occupied by another container | MCP server container mapped to host port `8008:8008` |

| `Missing Journal for Invoicing` | Creating `account.move` before Chart of Accounts exists | Install accounting localization (`l10n_*`) before initializing demo invoices |

| `External Pip in Docker` | Debian PEP 668 externally managed environment | Pass `--break-system-packages` when installing pip packages into container |

| `Registry Stale After Addon Install` | In-memory ORM registry not reloaded in running workers | Restart `odoo_web` container after installing new addons via CLI |

---

# Consultant

Yes. The MCP architecture is useful, but **MCP itself is not the product**. The product is the set of AI workflows sitting on top of Odoo that save vets and clinic staff time every day.

For ClinicFlow/Zelix Vet, I would prioritize workflows where the AI can **observe → reason/summarize → propose → execute**, rather than simply “chat with Odoo.”

### Highest-value workflows I'd investigate first

| Priority | Workflow | Frequency | AI value |
|---|---|---:|---|
| 🔥 1 | **Consultation → SOAP note** | Every consult | Extremely high |
| 🔥 2 | **Consultation → structured clinical record** | Every consult | Extremely high |
| 🔥 3 | **Follow-up / care-plan automation** | Daily | Very high |
| 🔥 4 | **Discharge summary + owner instructions** | Daily | Very high |
| 🔥 5 | **Appointment prep / patient briefing** | Every appointment | High |
| 🔥 6 | **Medical record summarization** | Every complex case | High |
| 🔥 7 | **Missed-follow-up / reminder intelligence** | Daily | High |
| 🔥 8 | **Prescription assistance** | Daily | High |
| 🔥 9 | **Lab/diagnostic result summarization** | Daily | High |
| 🔥 10 | **Daily clinic operations copilot** | Daily | High |

The killer feature, IMO, is **not** an Odoo chatbot.

It's:

> **The vet talks to the patient/owner. AI listens. The clinical record practically writes itself.**

### 1. Ambient AI Consultation

Doctor starts consultation:

> “Milo, 4-year-old Labrador, vomiting for two days, decreased appetite…”

AI captures the conversation and produces:

**SOAP**
- Subjective
- Objective
- Assessment
- Plan

Then extracts structured entities:

- symptoms
- duration
- weight
- temperature
- diagnosis candidates
- medications
- tests ordered
- follow-up date

But critically:

**AI should NOT silently write everything into Odoo.**

Instead:

> **“I prepared the clinical note and detected 7 structured updates. Review & Save.”**

Vet approves.

MCP then executes the corresponding Odoo operations.

That gives you a very compelling product demo.

---

### 2. “Prepare My Next Patient”

Five minutes before an appointment, the copilot generates:

> **Milo — 10:30 AM**
>
> 4-year-old Labrador  
> Last visit: 14 days ago  
> Previous issue: gastroenteritis  
> Medications: Metronidazole  
> Outstanding diagnostic: fecal test  
> Previous weight: 28.4 kg  
> Today's appointment reason: vomiting
>
> **Things to check**
> - Has vomiting resolved?
> - Did owner complete medication?
> - Was fecal test performed?
> - Weight trend

That's much more useful than:

> “Ask me anything about Milo.”

---

### 3. One-click Follow-up Automation

After consultation:

> “Follow up with Milo in 7 days.”

AI creates:

- follow-up activity
- appointment/reminder
- owner communication task
- relevant clinical checklist

Potentially:

> “Remind owner tomorrow to administer medication.”

And later:

> **“Milo's follow-up is due today. No appointment exists.”**

That's where MCP becomes powerful: **AI isn't merely reading Odoo; it's maintaining workflows inside Odoo.**

---

### 4. Discharge → Owner-Friendly Instructions

Vet finishes treatment.

AI generates:

**For the owner**

- Medication: X — twice daily
- Food instructions
- Exercise restriction
- Warning signs
- Follow-up date

Then optionally sends through WhatsApp/SMS/email.

The clinical record remains technical; the owner gets plain language.

---

### 5. “Give Me the Case in 30 Seconds”

This could become one of the most-used buttons.

For a patient with 20 previous encounters:

> **“Summarize this patient.”**

AI produces:

**Patient history**
- chronic conditions
- previous surgeries
- allergies
- recurring problems
- vaccination status
- medications
- recent diagnostics
- recent weight trend
- unresolved issues

Then:

> **“What's changed since the last visit?”**

That's extremely valuable in a busy clinic.

---

### 6. Diagnostic Intelligence

Suppose the vet orders CBC + chemistry + imaging.

When results arrive:

> **“Explain these results in context of the patient's history.”**

AI combines:

`diagnostic results + current encounter + previous records + medications`

and produces a clinician-facing summary.

Important distinction:

**Don't market this initially as autonomous diagnosis.**

Market it as:

> **Clinical information synthesis and decision support.**

The vet remains responsible for interpretation.

---

### 7. Prescription Copilot

Instead of manually navigating:

Patient → prescription → medication → dosage → frequency → duration...

Vet says:

> “Give Max amoxicillin for seven days.”

AI resolves the patient and proposes the structured prescription.

Then:

> **Amoxicillin — [dose] — [frequency] — 7 days**
>
> ⚠️ Please verify dosage before saving.

Vet confirms.

MCP creates the prescription.

This is exactly where your **schema-introspection-first invariant** becomes valuable.

---

# The bigger opportunity: AI Workflow Engine

I wouldn't architect this as:

```text
Copilot
   ↓
MCP
   ↓
Odoo
```

I'd evolve it toward:

```text
                    ┌─────────────────────┐
                    │   AI Copilot        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Clinical AI Layer   │
                    │                     │
                    │ • Extraction        │
                    │ • Summarization     │
                    │ • Reasoning         │
                    │ • Planning          │
                    │ • Validation        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Workflow Engine     │
                    │                     │
                    │ Observe             │
                    │ → Propose           │
                    │ → Approve           │
                    │ → Execute           │
                    │ → Verify            │
                    └──────────┬──────────┘
                               │
                         MCP / Tools
                               │
                    ┌──────────▼──────────┐
                    │       Odoo          │
                    └─────────────────────┘
```

That distinction matters.

**MCP should be your tool/access layer, not your business intelligence layer.**

---

# And I'd add proactive AI

This is where ClinicFlow could become substantially more interesting than a normal Odoo implementation.

Instead of waiting for:

> “What needs attention?”

the system continuously watches Odoo events.

For example:

```text
Appointment completed
        ↓
AI detects medication prescribed
        ↓
Follow-up required in 7 days
        ↓
Create follow-up task
        ↓
Monitor appointment
        ↓
No appointment booked
        ↓
Alert staff
```

Or:

```text
Patient admitted
      ↓
Treatment plan exists
      ↓
Medication due
      ↓
Nurse hasn't recorded administration
      ↓
AI flags exception
```

Or:

```text
Vaccination due
      ↓
No appointment
      ↓
Generate reminder candidate
      ↓
Staff approves
      ↓
WhatsApp message
```

Now you're building an **AI operating layer for veterinary clinics**, rather than another ERP chatbot.

---

## I would structure the product into 4 AI surfaces

### 🩺 1. During Consultation

**Ambient Scribe**

- transcription
- SOAP generation
- structured extraction
- diagnosis extraction
- prescription extraction
- treatment-plan extraction
- follow-up extraction

### 🧠 2. Inside the Patient Record

**Patient Copilot**

Questions like:

> “Summarize Max.”

> “What happened during his last three visits?”

> “What medications has he received?”

> “What's still unresolved?”

> “Compare today's weight with the last six visits.”

### ⚙️ 3. Clinic Operations

**Operations Copilot**

> “Which appointments need attention today?”

> “Who hasn't completed their follow-up?”

> “Which patients have overdue vaccinations?”

> “Show today's cancellations.”

> “Which hospitalized patients have pending tasks?”

### 🤖 4. Proactive AI

**AI watches Odoo**

and generates actionable exceptions:

> 🔴 3 follow-ups overdue  
> 🟠 7 vaccination reminders due  
> 🟠 2 patients have pending diagnostic results  
> 🔴 1 inpatient treatment task overdue

This fourth surface is potentially the **biggest differentiator**.

---

## Your MCP server should therefore expose primitives, not 100 AI-specific tools

Something like:

```text
odoo.search_read
odoo.create
odoo.update
odoo.call_method
odoo.get_fields
odoo.get_record
```

Then the AI layer builds capabilities on top:

```text
Clinical
 ├── prepare_patient
 ├── summarize_patient
 ├── generate_soap
 ├── create_prescription
 ├── create_treatment_plan
 └── prepare_discharge

Operations
 ├── find_overdue_followups
 ├── find_pending_tasks
 ├── prepare_daily_brief
 └── identify_exceptions

Communication
 ├── draft_owner_message
 ├── draft_followup
 └── draft_discharge_instructions
```

That gives you a very clean separation:

**Odoo = system of record**  
**MCP = controlled access/execution**  
**AI layer = intelligence**  
**Workflow engine = automation**  
**Copilot = user experience**

And importantly, this architecture can eventually be reused for **human medicine, dentistry, salons, service businesses, etc.** without contaminating the MCP layer with vertical-specific intelligence.

If you're serious about making this a product rather than a demo, the next thing I'd do is **map the actual VetCairn 22 modules into ~30–50 concrete AI workflows and score each by frequency × time saved × clinical value × implementation difficulty × safety risk**. That will tell us exactly what ClinicFlow/Zelix Vet's first AI release should contain.

---

# User

a few points need attention:

1. UI/UX of the AI Copilot: how should it be in UI/UX + should be implemented as Odoo module? or we can setup on a separate URL?
2. Their are various roles in a vet care/general human hospital; my vision is for the ai to be "role aware"
3. My relevant recent research on 1-bit LLM (MS Bitnet), Phi models: I'm eagerly looking to use them for inference instead of using cloud apis (paid); possible/capabale enough?

Keep your responses concise and oriented towards ai dev agent

---

# Consultant

Yes. These three points should materially change the architecture.

### 1. Copilot UI/UX — Odoo module vs separate app

**Recommendation: hybrid.**

Make the **AI Copilot UI a dedicated Odoo module**, but architect the AI backend independently.

```text
Odoo
 └── ClinicFlow AI module
      ├── Copilot sidebar/panel
      ├── contextual actions
      ├── patient-aware chat
      ├── ambient scribe UI
      └── approval dialogs
              │
              ▼
       Alamia AI / AI Gateway
              │
       ┌──────┴──────┐
       │             │
   Local Models   Cloud fallback
       │
       ▼
      MCP
       │
      Odoo
```

**Why Odoo-native first?**

The AI needs context. If I'm viewing:

> Patient → Max → Encounter #182

the Copilot should automatically know the relevant record/context.

UX should therefore feel like:

```text
┌───────────────────────────────┬──────────────────┐
│ Odoo clinical workspace       │  AI Copilot      │
│                               │                  │
│ Patient: Max                  │ "I found 3       │
│ Encounter                     │  relevant things" │
│ SOAP                          │                  │
│ Diagnosis                     │ • Previous Rx    │
│                               │ • Lab pending    │
│                               │ • Follow-up due  │
│                               │                  │
│                               │ [Prepare note]   │
│                               │ [Summarize case] │
└───────────────────────────────┴──────────────────┘
```

Later, a **separate URL** can provide a full-screen/mobile Copilot for cross-Odoo workflows.

So tell the agent:

> **Do not couple AI business logic to Odoo frontend. Build an Odoo-native Copilot shell over a separately deployable AI service.**

---

# 2. Role-aware AI is absolutely the right direction

Don't build:

> **One AI for everyone.**

Build:

> **One AI platform + role-specific intelligence.**

For example:

```text
Role
 │
 ├── Veterinarian
 │    ├── Clinical summary
 │    ├── SOAP
 │    ├── diagnostics
 │    ├── treatment
 │    └── prescription
 │
 ├── Vet Technician / Nurse
 │    ├── treatment tasks
 │    ├── medication administration
 │    ├── vitals
 │    └── inpatient monitoring
 │
 ├── Receptionist
 │    ├── appointments
 │    ├── reminders
 │    ├── check-in/out
 │    └── client communication
 │
 ├── Practice Manager
 │    ├── operations
 │    ├── staffing
 │    ├── revenue
 │    └── exceptions
 │
 └── Owner / Admin
      ├── KPIs
      ├── financials
      ├── utilization
      └── business intelligence
```

And **role awareness must affect both what AI can see and what it can do**.

Not merely:

```text
system prompt = "You are a veterinarian"
```

Instead:

```text
User
 ↓
Odoo identity / roles
 ↓
Role Policy
 ↓
Allowed context
 ↓
Allowed tools
 ↓
Allowed actions
 ↓
AI
```

Your existing **permission parity invariant is therefore critical**.

I'd add:

> **AI must never gain capabilities merely because the user asks for them in natural language. Odoo authorization remains the ultimate enforcement layer.**

---

# 3. BitNet / Phi instead of paid APIs

**Yes — but don't make the mistake of assuming one small model can do everything.**

Your Alamia Model Garden approach is actually ideal here.

For ClinicFlow:

```text
                    AI Router
                       │
       ┌───────────────┼────────────────┐
       ▼               ▼                ▼
   BitNet 2B        Phi small       Larger local
 classification     extraction       reasoning
 summarization      structured       complex cases
 simple dialogue    tasks
       │               │                │
       └───────────────┴────────────────┘
                       │
                 Optional fallback
                       │
                  Cloud model
```

### Where small local models are very realistic

**Excellent candidates:**

- intent classification
- entity extraction
- structured data extraction
- appointment classification
- note cleanup
- summarization
- document classification
- reminder generation
- routing
- simple dialogue
- transforming dictated text → structured SOAP

### Where I'd be more cautious

- complex clinical reasoning
- difficult diagnostic interpretation
- long longitudinal patient reasoning
- complicated multi-step tool orchestration
- safety-critical recommendations

And importantly:

**You don't need a frontier model to do most of the boring work.**

That's exactly where BitNet/Phi become commercially interesting.

---

## The architecture I'd give your AI dev agent

```text
                 ┌──────────────────────┐
                 │ ClinicFlow Copilot   │
                 │ Odoo UI / Mobile UI  │
                 └──────────┬───────────┘
                            │
                   User + Role Context
                            │
                 ┌──────────▼───────────┐
                 │ AI Orchestrator      │
                 │                      │
                 │ Role Policy          │
                 │ Context Builder      │
                 │ Task Classifier      │
                 │ Model Router         │
                 │ Workflow Engine      │
                 └──────────┬───────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          BitNet/Phi    Larger Local   Cloud*
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                       Tool/MCP Layer
                            │
                            ▼
                           Odoo
```

`*` Cloud should be an **optional fallback**, not an architectural dependency.

### My strongest recommendation

Don't call this merely **“Odoo AI Copilot.”**

Build the reusable underlying product as:

> **Alamia AI Clinical/Business Copilot Engine**

Then ClinicFlow/Zelix Vet is the **first vertical implementation**.

That lets you eventually have:

```text
Alamia AI Copilot Engine
       │
       ├── ClinicFlow / Vet
       ├── Human Hospital
       ├── Dental
       ├── Travel
       └── General Odoo
```

And your BitNet/Phi work becomes infrastructure that powers all of them rather than something hardwired into VetCairn.

---

# User

perfect create a detailed PRD/sprints DAG tasks based on what was discussed above; my bitnet, phi and a couple slms are available at: https://ai.alamiaconnect.com with header bearer token auth already setup so copilot can call the endpoint for inference

---

# Consultant

Yes. I’d turn this into a **real implementation PRD + DAG**, with the first milestone deliberately focused on proving the architecture and the local-model strategy before the agent builds dozens of workflows.

One important architectural constraint: MCP's current tool guidance explicitly favors human confirmation for tool invocations, and authorization should remain tied to the caller's permissions. ([GitHub](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx?utm_source=chatgpt.com)) Your existing permission-parity principle is therefore the correct foundation.

Also, I could not inspect `ai.alamiaconnect.com` because it correctly returned `401 Unauthorized`; the PRD below treats its API contract as an existing dependency and tells the agent to discover/validate the actual endpoint contract rather than inventing one.

# VetCairn / ClinicFlow AI Copilot
## Product Requirements Document + Engineering Sprint DAG

**Document status:** Implementation specification  
**Target:** Odoo 19 + VetCairn  
**AI Runtime:** Alamia AI endpoint (`https://ai.alamiaconnect.com`)  
**Primary integration:** Odoo MCP  
**Deployment:** Local-first / self-hostable  
**Cloud AI:** Optional fallback only

---

# 1. Product Vision

Build an **AI-native operating layer for veterinary clinics running Odoo/VetCairn**.

The Copilot must not merely answer questions about Odoo.

It must:

> **Understand the user's role, understand the current clinical/business context, reason over Odoo data, propose actions, execute approved actions, and proactively identify work requiring attention.**

Core loop:

```text
OBSERVE
   ↓
UNDERSTAND
   ↓
REASON
   ↓
PROPOSE
   ↓
HUMAN APPROVAL
   ↓
EXECUTE
   ↓
VERIFY
   ↓
MONITOR
```

The product should eventually support:

- Veterinarians
- Veterinary technicians/nurses
- Receptionists
- Practice managers
- Hospital administrators
- Owners/executives

The architecture must remain reusable for a future **human hospital / general healthcare vertical**.

---

# 2. Non-Goals for V1

Do NOT initially build:

- autonomous diagnosis
- autonomous prescription approval
- autonomous clinical decision-making
- unrestricted database access
- generic "ChatGPT inside Odoo"
- dependence on OpenAI/Anthropic/etc.
- AI that bypasses Odoo permissions
- dozens of AI-specific MCP tools
- an independent replacement for Odoo

---

# 3. Target Architecture

```text
                         ┌────────────────────────┐
                         │      Odoo 19           │
                         │                        │
                         │ VetCairn + AI Module   │
                         └───────────┬────────────┘
                                     │
                           Context / User / Role
                                     │
                                     ▼
                         ┌────────────────────────┐
                         │   AI Copilot Backend   │
                         │                        │
                         │ Role Engine             │
                         │ Context Engine          │
                         │ Task Classifier         │
                         │ Workflow Engine         │
                         │ Model Router            │
                         │ Guardrails              │
                         └───────────┬────────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
                 BitNet/Phi      Other SLMs     Optional
                 local AI        local AI        cloud AI
                      │              │              │
                      └──────────────┼──────────────┘
                                     ▼
                              MCP Tool Layer
                                     │
                                     ▼
                                    Odoo
```

### Architectural rule

**Odoo module = UX/context integration.**

**AI backend = intelligence.**

**MCP = controlled Odoo tool/access layer.**

Do not put orchestration/business intelligence inside the MCP server.

---

# 4. Odoo AI Module

Create:

```text
addons/vetcairn_ai/
```

Responsibilities:

### UI

- Copilot sidebar
- contextual Copilot button
- patient-aware chat
- action proposal cards
- approval UI
- tool execution indicators
- AI-generated content review
- ambient consultation interface
- AI activity/history

### Context provider

When the user is looking at:

```text
Patient → Max → Encounter #182
```

the module sends contextual information to the AI backend.

Example:

```json
{
  "user": {
    "odoo_uid": 42,
    "roles": ["veterinarian"]
  },
  "context": {
    "model": "vet.encounter",
    "record_id": 182,
    "patient_id": 51
  }
}
```

Never expose unnecessary Odoo data.

---

# 5. Role-Aware AI

Implement a formal `RolePolicy`.

Example:

```text
Veterinarian
    read:
      patient
      encounter
      diagnosis
      prescription
      diagnostics
      treatment
      vaccination

    write:
      encounter
      diagnosis
      prescription
      treatment
      diagnostics

Technician
    read:
      patient
      treatment
      diagnostics
      admission

    write:
      vitals
      treatment_activity
      medication_administration

Receptionist
    read:
      patient
      appointment

    write:
      appointment
      communication
```

But this must **never replace Odoo ACLs/record rules**.

The policy is an AI safety layer.

Odoo remains the final authorization boundary.

---

# 6. Copilot UX

## Persistent Copilot

Desktop:

```text
┌─────────────────────────────────────┬───────────────┐
│                                     │ AI COPILOT    │
│ Odoo screen                         │               │
│                                     │ Context       │
│ Patient: Max                        │ Max / #182    │
│                                     │               │
│                                     │ Ask anything  │
│                                     │ about Max...  │
│                                     │               │
│                                     │ Suggestions   │
│                                     │ • Summarize   │
│                                     │ • Prepare note│
│                                     │ • Follow-up   │
└─────────────────────────────────────┴───────────────┘
```

The panel should be:

- collapsible
- keyboard accessible
- streaming
- contextual
- conversation-aware
- capable of showing tool activity

---

# 7. Action Cards

Never dump raw tool calls into the UI.

Instead:

```text
AI proposes:

Create follow-up appointment

Patient: Max
Date: 10 Sep
Reason: Gastroenteritis follow-up

[Approve] [Edit] [Reject]
```

For writes, default to **approval required**.

This aligns with MCP's current guidance that applications should provide clear tool-use indicators and human confirmation for tool invocations. ([GitHub](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx?utm_source=chatgpt.com))

---

# 8. AI Model Architecture

The AI backend must integrate with:

```text
https://ai.alamiaconnect.com
```

Use an adapter:

```text
AlamiaAIProvider
```

Do **not** hardcode model names into clinical workflows.

Instead:

```text
Task
 ↓
Model Router
 ↓
Capability requirements
 ↓
Best available model
```

Example:

```text
SOAP extraction
→ structured extraction
→ BitNet/Phi/SLM

Patient summarization
→ summarization
→ Phi/SLM

Intent classification
→ classification
→ smallest capable SLM

Complex reasoning
→ larger local model

Unavailable / insufficient confidence
→ optional cloud fallback
```

---

# 9. Local AI Requirement

V1 must explicitly benchmark the available:

- Microsoft BitNet
- Phi
- other available SLMs

against representative VetCairn tasks.

Create:

```text
ai-benchmarks/
```

Tests:

```text
T01 intent classification
T02 patient entity extraction
T03 SOAP extraction
T04 SOAP cleanup
T05 medical-history summarization
T06 appointment classification
T07 follow-up extraction
T08 prescription structure extraction
T09 owner-message generation
T10 tool-selection accuracy
T11 multi-step workflow reasoning
```

Measure:

- accuracy
- structured-output validity
- latency
- tokens/sec
- memory
- CPU utilization
- hallucination/error rate
- JSON failure rate
- retry rate

### Acceptance principle

Do not ask:

> "Is BitNet smart enough?"

Ask:

> **"Which percentage of our actual Copilot workload can be reliably handled by each local model?"**

That is the commercially useful measurement.

---

# 10. MCP Layer

Retain generic primitives:

```text
odoo_get_model_fields
odoo_search_read
odoo_create
odoo_write
odoo_unlink
odoo_execute_kw
```

Potentially add:

```text
odoo_get_record
odoo_search_count
odoo_get_related_records
```

But resist creating:

```text
create_patient_summary
create_vet_appointment
generate_prescription
...
```

inside MCP.

Those belong to the **AI workflow layer**.

MCP should remain a general controlled interface to Odoo.

Authorization should continue using bearer credentials appropriately; current MCP authorization guidance requires authorization on protected requests and prohibits putting access tokens in URLs. ([Model Context Protocol](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization?utm_source=chatgpt.com))

---

# 11. Core AI Workflow Framework

Create:

```text
ai/
├── roles/
├── context/
├── policies/
├── workflows/
├── models/
├── providers/
├── orchestration/
├── guardrails/
├── audit/
└── evaluation/
```

Workflow abstraction:

```python
Workflow
    id
    name
    role
    required_context
    allowed_tools
    model_requirements
    approval_policy
    execute()
    verify()
```

---

# 12. V1 High-Value Workflows

## W01 — Patient Summary

Input:

> "Summarize Max."

Output:

- demographics
- relevant history
- active problems
- medications
- recent encounters
- diagnostics
- vaccinations
- treatment
- unresolved issues

---

## W02 — Pre-Consult Brief

Automatically prepare:

```text
Patient
Last visit
Reason
Recent changes
Active medication
Pending diagnostics
Previous weight
Relevant history
Questions to ask
```

---

## W03 — Ambient Consultation Scribe

Flow:

```text
Audio
 ↓
transcription
 ↓
clinical extraction
 ↓
SOAP draft
 ↓
structured fields
 ↓
vet review
 ↓
Odoo write
```

Important:

**Never silently commit clinical content.**

---

## W04 — SOAP Generator

Input:

```text
consultation transcript
```

Output:

```text
Subjective
Objective
Assessment
Plan
```

---

## W05 — Follow-up Planner

AI detects:

- follow-up interval
- required appointment
- reminder
- pending task

Then proposes:

```text
Create follow-up
Create reminder
Draft owner communication
```

---

## W06 — Discharge Assistant

Generate:

- discharge summary
- medication instructions
- diet
- activity restrictions
- warning signs
- follow-up instructions

---

## W07 — Patient History Q&A

Examples:

> "What medications has Max received in the last six months?"

> "When did his weight start increasing?"

> "What happened at his previous visit?"

Must retrieve evidence from Odoo rather than hallucinating.

---

## W08 — Diagnostic Summary

Combine:

```text
current results
+
previous diagnostics
+
encounter context
```

Produce clinician-facing summary.

No autonomous diagnosis.

---

## W09 — Prescription Assistant

Natural language:

> "Prescribe X for Max for seven days."

AI resolves and proposes structured prescription.

Vet confirms.

---

## W10 — Vaccination/Reminder Intelligence

Identify:

```text
vaccination due
follow-up overdue
medication follow-up
diagnostic pending
```

Generate actionable queue.

---

# 13. Proactive AI

This should be a **separate subsystem**, not merely chat.

```text
Odoo Events
     ↓
Event Processor
     ↓
AI Rules
     ↓
Candidate Action
     ↓
Human Approval
     ↓
Odoo
```

Examples:

```text
Appointment completed
→ follow-up required
→ no appointment
→ flag

Diagnostic ordered
→ result pending
→ flag

Vaccination due
→ no booking
→ reminder candidate

Inpatient treatment due
→ activity not recorded
→ exception
```

---

# 14. Daily Role Brief

This is likely one of the strongest features after the scribe.

### Veterinarian

> **Good morning, Dr. Ahmed**

```text
Today's appointments: 14

⚠ 2 patients have pending diagnostics
⚠ 3 follow-ups due
⚠ 1 chronic patient has not returned

Today's high-priority cases:
1. Max — recurring vomiting
2. Bella — post-op follow-up
```

### Receptionist

```text
Today's appointments
Cancellations
Unconfirmed bookings
Follow-ups requiring contact
```

### Manager

```text
Appointments
No-shows
Revenue
Utilization
Pending operational issues
```

Same Copilot platform.

Different intelligence.

---

# 15. Sprint DAG

The agent should execute these in dependency order.

```text
S0 Foundation
 │
 ├── S1 AI Provider Adapter
 │
 ├── S2 Odoo AI Module
 │
 ├── S3 Role/Policy Engine
 │
 └── S4 Context Engine
          │
          ▼
       S5 Copilot
          │
          ├──────────────┐
          ▼              ▼
       S6 MCP        S7 Model Router
          │              │
          └──────┬───────┘
                 ▼
              S8 Workflow Engine
                 │
       ┌─────────┼──────────┐
       ▼         ▼          ▼
     S9 Scribe  S10 Patient  S11 Operations
       │         │          │
       └─────────┼──────────┘
                 ▼
             S12 Proactive AI
                 │
                 ▼
             S13 Evaluation
                 │
                 ▼
             S14 Production Hardening
```

---

# S0 — Repository & Architecture Foundation

### Tasks

- establish repository structure
- environment configuration
- Docker development environment
- Odoo module skeleton
- AI backend skeleton
- shared schemas
- logging
- configuration
- correlation IDs

### Deliverable

System starts cleanly with:

```text
Odoo
AI backend
MCP
Alamia AI
PostgreSQL
```

---

# S1 — Alamia AI Provider

### Tasks

1. Inspect actual API contract of `ai.alamiaconnect.com`.
2. Create provider interface.
3. Implement authenticated HTTP client.
4. Bearer token via environment/secret.
5. Timeouts.
6. retries.
7. streaming if available.
8. structured JSON output support.
9. model discovery if endpoint supports it.
10. health check.
11. metrics.

Interface:

```python
class AIProvider:
    async def generate(...)
    async def structured(...)
    async def stream(...)
    async def health(...)
```

### Acceptance

Copilot can execute:

```text
prompt
→ Alamia AI
→ response
```

without any cloud provider.

---

# S2 — Odoo Copilot Module

Build:

```text
vetcairn_ai
```

### Tasks

- sidebar
- chat UI
- contextual record detection
- user identity
- loading state
- streaming
- error state
- action cards
- confirmation dialog
- tool activity display
- conversation history

---

# S3 — Role Engine

Implement:

```text
RoleResolver
RolePolicy
CapabilityPolicy
ActionPolicy
```

Tests:

```text
vet cannot access accounting data
receptionist cannot create prescriptions
technician cannot approve prescription
manager can access operational KPIs
```

Also test against actual Odoo ACL behavior.

---

# S4 — Context Engine

Implement:

```text
Current user
Current Odoo model
Current record
Related records
Relevant history
Current workflow
```

Context should be **minimal**, not "send the entire patient database to the LLM."

---

# S5 — Copilot Orchestrator

Pipeline:

```text
User request
 ↓
Role resolution
 ↓
Context resolution
 ↓
Intent classification
 ↓
Workflow selection
 ↓
Model selection
 ↓
Tool planning
 ↓
Execution
 ↓
Response
```

Add trace:

```text
request_id
user
role
workflow
model
tools
latency
result
approval
```

---

# S6 — MCP Hardening

Validate:

- authentication
- authorization
- schema introspection
- CRUD
- execute_kw
- error normalization
- timeouts
- audit logging
- dangerous operation handling

Every write:

```text
AI
 ↓
MCP
 ↓
Odoo permission check
 ↓
operation
```

---

# S7 — Model Router

Create task capability matrix:

| Task | Preferred | Fallback |
|---|---|---|
| Classification | smallest SLM | Phi |
| Extraction | BitNet/Phi | larger local |
| SOAP | Phi/SLM | larger local |
| Summary | Phi | larger local |
| Tool selection | stronger SLM | larger model |
| Complex reasoning | larger local | cloud |
| Simple rewriting | smallest SLM | Phi |

But **benchmark must determine final routing**, not assumptions.

---

# S8 — Workflow Engine

Implement:

```text
WorkflowRegistry
WorkflowExecutor
ApprovalManager
ExecutionVerifier
AuditLogger
```

Workflow lifecycle:

```text
DRAFT
 ↓
PROPOSED
 ↓
APPROVAL_REQUIRED
 ↓
APPROVED
 ↓
EXECUTING
 ↓
COMPLETED
 ↓
VERIFIED
```

Failure:

```text
EXECUTION_FAILED
```

with rollback/compensation where possible.

---

# S9 — Ambient Scribe

This deserves its own sprint.

### Pipeline

```text
Audio
 ↓
Transcription
 ↓
Speaker segmentation
 ↓
Clinical extraction
 ↓
SOAP generation
 ↓
Structured extraction
 ↓
Validation
 ↓
Doctor review
 ↓
Odoo
```

V1 can initially support **text/pasted transcript** before implementing live audio.

That gives you a much faster vertical slice.

---

# S10 — Patient Intelligence

Implement:

- patient summary
- timeline
- last-visit summary
- medication history
- diagnostic history
- unresolved issues
- "what changed?"
- pre-consult briefing

Every generated factual claim should be traceable to Odoo records where practical.

---

# S11 — Operations Copilot

Implement:

- daily brief
- appointment intelligence
- overdue follow-ups
- pending diagnostics
- vaccination reminders
- inpatient exceptions
- no-show detection

---

# S12 — Proactive AI

Implement event-driven architecture.

Start with only:

```text
follow-up overdue
diagnostic pending
vaccination due
treatment task overdue
```

Don't build a giant autonomous agent.

---

# S13 — Evaluation Harness

Create real evaluation datasets.

```text
eval/
├── classification/
├── extraction/
├── summarization/
├── tool_selection/
├── workflow/
├── safety/
└── regression/
```

Every model must run against the same benchmark.

Track:

```text
accuracy
latency
JSON validity
hallucination
tool errors
Odoo errors
human correction rate
```

This becomes extremely important for your BitNet/Phi strategy.

---

# S14 — Production Hardening

### Security

- secrets never in frontend
- tenant isolation
- Odoo ACL enforcement
- audit logs
- prompt-injection defenses
- tool allowlists
- action confirmation
- request limits
- model/provider isolation

### Reliability

- retries
- timeout
- circuit breaker
- model fallback
- MCP failure handling
- partial workflow recovery

### Observability

```text
AI request
Model
Tokens
Latency
Tool calls
Odoo operations
Approval
Outcome
```

---

# 16. Definition of Done

The first serious release should allow this exact experience:

### Vet opens patient

```text
Max
```

Copilot automatically knows:

```text
Current patient = Max
Current encounter = #182
User = Veterinarian
```

Vet asks:

> "Prepare me for this patient."

Copilot retrieves the relevant Odoo history.

Local model generates the briefing.

Vet asks:

> "Create today's SOAP draft from these notes."

AI generates it.

Vet reviews.

> **Save to encounter**

AI asks confirmation.

MCP executes.

Odoo stores it.

Then AI detects:

> Follow-up recommended in 7 days.

It proposes:

```text
Create follow-up appointment
```

Vet approves.

MCP creates it.

That is the **first complete AI-native clinical workflow**.

---

# 17. Most Important Engineering Principle

Give the dev agent this rule:

> **Do not optimize for the number of AI features. Optimize for the number of real clinic workflows completed with fewer clicks, less typing, and less cognitive load.**

And another:

> **Local AI is the default execution path. Cloud AI is an optional capability fallback, never a hidden dependency.**

Your existing Alamia AI endpoint makes that architecture particularly clean: **ClinicFlow becomes a consumer of your own AI infrastructure rather than becoming financially dependent on third-party inference APIs.**

Finally, don't let the agent start by building the 10 workflows above. **S0 → S1 → S2 → S3 → S4 → S5 → S7 → S8 → S9** should be the first vertical slice. Once *ambient/text consultation → structured SOAP → human approval → Odoo write* works reliably with BitNet/Phi/your SLMs, you have proven the hardest and most commercially important part of the architecture.