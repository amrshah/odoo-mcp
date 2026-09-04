# Stratos HMS — Architectural Deep Dive & System Specification

**Module Technical Name:** `stratos_hms`  
**Odoo Compatibility:** Odoo 19.0 Community  
**Author:** Stratos Hub  
**Status:** Integrated & Exposed via FastMCP (39 Clinical Models)

---

## 1. Executive Summary & Design Intent

**Stratos HMS** is a comprehensive, enterprise-grade Hospital Management System (HMS) and Electronic Medical Record (EMR) designed for human inpatient/outpatient healthcare facilities with acute localization for Pakistan (PKR currency, JazzCash/EasyPaisa journals, PMDC provider registration, Urdu/English Web Speech STT, XDR-typhoid and dengue protocol awareness, and Pakistani pharmaceutical brand names).

### Core Philosophy: "Propose While the Doctor Decides"
Unlike naive AI chatbots that hallucinate uncontrolled writes into clinical databases, Stratos HMS enforces a strict **Proposal-Approval Architecture**:
1. All AI suggestions (diagnoses, prescriptions, investigation orders) are staged in a transient state (`state="proposed"`).
2. Hard deterministic safety checks (allergen cross-reactivity, toxic maximum daily dosing, and drug-drug interactions) run *before* presentation.
3. Nothing commits to the patient's legal medical record until explicitly signed by a licensed practitioner (`state="approved"` / `state="signed"`).
4. Every clinical decision feeds into a closed-loop **Hospital Memory** and **Learned Rules Engine** that enables the system to continuously learn institutional prescribing patterns.

---

## 2. Complete Domain Breakdown & 39 Database Models

| Domain Area | Key Models (`ir.model`) | Core Responsibility & Architectural Invariants |
|---|---|---|
| **Master & Demographics** | `hms.patient`<br/>`hms.department`<br/>`hms.practitioner`<br/>`hms.allergy`<br/>`hms.icd10` | Universal Patient Master Index with MRN sequence (`PAT/YYYY/NNNNN`), CNIC, blood group, emergency contact, active allergy tags with red-banner propagation across all screens, and WHO ICD-10 codification. |
| **Visit & Triage Orchestration** | `hms.visit`<br/>`hms.vitals`<br/>`hms.consent`<br/>`hms.discount.request` | 7-stage Patient Journey Bar (`registered` ➔ `triaged` ➔ `in_consult` ➔ `orders_placed` ➔ `treatment` ➔ `results` ➔ `discharged`). Implements NEWS2 Early Warning Score (EWS) that automatically reorders doctor waiting queues (sickest first, ER ahead). |
| **Consultation & Scribe** | `hms.consult`<br/>`hms.consult.diagnosis`<br/>`hms.prescription.line` | Multi-tab consultation room with Web Speech API ambient speech-to-text (Urdu/English), AI Scribe extraction into HPI/ROS/Plan, safety checking, and legal signing ceremony. |
| **Institutional Intelligence** | `hms.ai.rule`<br/>`hms.case.memory`<br/>`hms.protocol`<br/>`hms.protocol.line`<br/>`hms.ai.service` | Dual-engine memory: **Learned Rules** ("teach once, it practises your way" with doctor/department/hospital scope) + **Hospital Case Memory** (de-identified case bank with TF-IDF keyword similarity matching) + Pluggable LLM reasoning (Offline, Claude 3.5, OpenAI GPT-4o, FastMCP/BitNet). |
| **Laboratory & Imaging** | `hms.order`<br/>`hms.test`<br/>`hms.critical.call` | 4-step diagnostic continuum: Order ➔ Dual-Gate Barcode Collection (Wristband MRN + Specimen Tube) ➔ Result Entry ➔ Doctor Acknowledgment. Auto-triggers `hms.critical.call` phone escalation whenever results exceed critical limits. |
| **Pharmacy & Formulary** | `hms.drug`<br/>`hms.dispense`<br/>`hms.dispense.line` | 70+ item Pakistani drug formulary (Panadol, Augmentin, Rocephin, etc.) with strict allergen classes, route/frequency validators, maximum daily dose guards, and double-checked dispensing queue. |
| **Inpatient Wards (IPD)** | `hms.admission`<br/>`hms.ward`<br/>`hms.bed`<br/>`hms.ward.order`<br/>`hms.mar`<br/>`hms.handoff`<br/>`hms.progress.note` | Live Bed Board with occupancy tracking, Medication Administration Record (MAR) that strictly blocks dose recording until both wristband MRN and drug barcode are scanned, and structured SBAR nursing shift handoffs. |
| **Surgical Theatre (OT)** | `hms.surgery`<br/>`hms.theatre` | Operation theatre management enforcing the **WHO Surgical Safety Checklist** as 3 hard gates: *Sign In* (pre-induction, blocked without signed surgical consent), *Time Out* (pre-incision), and *Sign Out* (pre-closure). |
| **Blood Bank** | `hms.blood.unit`<br/>`hms.blood.request` | Inventory of screened, crossmatched, ABO/Rh-compatible blood products (Whole Blood, PRBC, FFP, Platelets) enforcing dual-clinician physical verification before release. |
| **Billing & Financials** | `hms.charge`<br/>`account.move` (extended) | Event-driven charge capture (every consultation, dose, lab test, and bed night posts an `hms.charge`). Invoicing integrates directly into native Odoo `account.move` with JazzCash, EasyPaisa, and Cash Counter journals. |
| **Command Centre** | `hms.dashboard` | Real-time executive cockpit displaying live hospital census, critical lab call alerts, bed occupancy by ward, average TAT, EWS ≥ 5 patients, clinician load, and 14-day revenue mix. |

---

## 3. The 10 Clinical Safety Invariants & Hard Gates

1. **Deterministic Allergen Blocking**: If a patient has a documented allergy class (e.g. `penicillin`), any prescription proposal containing that class is hard-blocked from sign-off.
2. **Dual-Gate Specimen Collection**: Laboratory staff cannot mark a specimen collected without matching both the patient's wristband MRN and the specimen tube barcode.
3. **Critical Lab Escalation Gate**: When a diagnostic result falls into the critical panic range (e.g. Troponin I > 0.04 ng/mL or Potassium < 2.5 mEq/L), the system locks result release until a verbal telephone read-back is logged with the attending physician (`hms.critical.call`).
4. **Dual-Scan Medication Administration (MAR)**: Inpatient nurses cannot chart a medication as "given" without scanning both the patient's physical wristband and the medication blister pack barcode.
5. **WHO Surgical Safety Checklist Gates**: Surgery cannot transition to "in_progress" without completing *Sign In* (verified consent, site marked, anesthesia check) and *Time Out* (team introductions, anticipated critical events).
6. **Dual-Verifier Blood Issue**: Blood units cannot be released from the blood bank without two distinct staff members validating crossmatch compatibility and signed transfusion consent.
7. **Role-Governed Financial Holds**: Front-desk discounts exceeding threshold policies require named approval from the Head of Department (`hms.discount.request`), placing the visit file into *Held - Approval Pending*.
8. **EWS Dynamic Queue Prioritization**: NEWS2 vitals trigger automatic calculation of the Early Warning Score (0–20); any score ≥ 5 elevates the patient to the top of all consultation and nursing queues with emergency visual flags.
9. **Consent Gating**: Invasive procedures, blood transfusions, and ambient consultation audio recordings require verified `hms.consent` records.
10. **De-Identified Institutional Memory**: When a consultation is signed, it is stripped of direct patient identifiers and ingested into `hms.case.memory` to inform future similar clinical encounters.

---

## 4. Architectural Comparison: Stratos HMS vs. VetCairn Clinical Suite

| Architectural Dimension | Stratos HMS (`addons/stratos_hms`) | VetCairn Veterinary Suite (`addons/VetCairn`) |
|---|---|---|
| **Target Domain** | Human Acute & Tertiary Hospital Management | Multi-Branch Veterinary Clinics & Animal Hospitals |
| **Patient Identification** | Medical Record Number (`MRN`) + National CNIC | Patient Microchip Number + Pet Name + Species/Breed |
| **Clinical Encounter Model** | `hms.visit` + `hms.consult` + `hms.admission` | `vet.appointment` + `vet.encounter` + `vet.admission` |
| **Triage & Acuity** | NEWS2 Early Warning Score (`EWS`) | Triage Level (1-Immediate to 5-Non-urgent) |
| **Diagnostic Layer** | `hms.order` + `hms.test` + `hms.critical.call` | `vet.diagnostic.order` + `vet.diagnostic.type` |
| **Medication Layer** | `hms.drug` (Pakistani Brands + Allergen Classes) | `vet.prescription` + `vet.medication` (Veterinary Formulary) |
| **Surgical Safety** | WHO Surgical Safety Checklist (3 Gates) | `vet.treatment.plan` + Inpatient Bed Allotment |
| **AI Integration** | Native OWL 2 Scribe Field + SBAR + Hospital Memory | Zelix Copilot Backend (:8010) + FastMCP Server (:8008) |
| **Payment Protocols** | Cash, Card, JazzCash, EasyPaisa, Corporate Handoffs | Vet Insurance, Cash, Card, Client Invoicing |

---

## 5. Integration with FastMCP & Zelix Copilot

All 39 models of `stratos_hms` are registered in Odoo's `mcp.enabled.model` table with full CRUD permissions:
- External AI agents and the Zelix Copilot backend interact with Stratos HMS via standard FastMCP tools (`odoo_search_read`, `odoo_create_record`, `odoo_execute_method`).
- FastMCP bridges both human hospital workflows (`hms.*`) and veterinary workflows (`vet.*`) concurrently under unified role-based access control.
