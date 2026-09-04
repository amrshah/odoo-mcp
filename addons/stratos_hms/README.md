# Stratos HMS — Hospital Management & EMR with AI (Odoo 19 Community)

One live patient record for the whole hospital. Front desk, triage, consults with a speech-to-text
scribe and an AI assistant that *proposes while the doctor decides*, laboratory, pharmacy, wards,
operation theatre, blood bank, billing and a live command centre — built and tested on Odoo 19.0
Community Edition, for hospitals in Pakistan (PKR, JazzCash/EasyPaisa, Urdu speech, XDR-typhoid-aware
protocols, Pakistani brand names in the formulary).

Every feature shown in the Medica explainer and demo videos is here, plus the two things discussed
on top: **learned rules** ("teach once, it practises your way") and **hospital memory** (every signed
consult becomes a de-identified case; a new patient with a similar presentation gets "in this
hospital, for this, your doctors usually give…" next to the guideline).

---

## 1. Installation

### Requirements
* Odoo **19.0 Community** (tested on the 19.0 branch, September 2026), Python 3.10+, PostgreSQL 13+.
* `wkhtmltopdf` for PDF prescriptions / bills / reports (standard Odoo requirement).
* Google Chrome or Microsoft Edge on the doctors' workstations for the microphone (Web Speech API).
* Python package `requests` (ships with Odoo).

### Steps
1. Unzip `stratos_hms.zip` so that you have a folder `stratos_hms/` inside one of your addons paths, e.g.

       /opt/odoo/custom-addons/stratos_hms/

2. Make sure that path is in `odoo.conf`:

       addons_path = /opt/odoo/odoo/addons,/opt/odoo/custom-addons

3. Restart Odoo and update the apps list (Settings → Apps → *Update Apps List*), or from the shell:

       ./odoo-bin -c odoo.conf -d <yourdb> -i stratos_hms --stop-after-init

   For a **demo database with the sample morning** (patients, queues, a STEMI, a critical troponin,
   an inpatient with a MAR, memory cases):

       ./odoo-bin -c odoo.conf -d hms_demo -i stratos_hms --with-demo --stop-after-init

   (`--with-demo` only applies to a *new* database.)

4. Log in as the administrator. The **Hospital** app appears in the menu. On install the module:
   * switches the company currency to **PKR** (only if no journal entries exist yet) and sets the country to Pakistan,
   * creates payment journals **Cash Counter, Card Terminal, JazzCash, EasyPaisa**,
   * loads 27 departments, 60+ ICD-10 codes, a 70-item formulary with Pakistani brands, allergy classes and
     interactions, 60 lab/imaging/procedure tests with reference and critical ranges, 15 protocols, wards, beds, theatres.

### Demo logins (demo database only — password = login + `123`)
| Login | Role | Sees |
|---|---|---|
| `nasreen` | Front desk | Queue, register, consents, collections, discount requests, held files, bed board |
| `hina` | Nurse | Triage queue, vitals/EWS, treatment board (MAR), ward board, handoffs |
| `dr.ayesha` | Doctor, General Medicine | My queue, consult room, results to acknowledge, inpatients, learned rules |
| `dr.bilal` | Doctor, Cardiology | same |
| `dr.farhan` | Doctor, Paediatrics | same |
| `dr.sana` | Head of Medicine | + discount approvals, command centre, management |
| `usman` | Pharmacist | Verification queue, formulary |
| `tariq` | Lab technologist | Worklist, imaging, critical calls, test catalogue |
| `kamran` | Blood bank | Requests, inventory |
| `rubina` | OT coordinator | Surgeries with WHO checklist |
| `director` | Director | Everything, incl. configuration |

---

## 2. Configuring the AI (Hospital → Configuration → Settings)

The AI layer is **pluggable**:

| Provider | What you need | Notes |
|---|---|---|
| **Offline** (default) | nothing | Proposals come from hospital memory + learned rules + protocol table. The full workflow works without any external API. |
| **Anthropic Claude** | API key from console.anthropic.com | Model default `claude-sonnet-4-5`. |
| **OpenAI** | API key from platform.openai.com | Model default `gpt-4o`, JSON mode. |

Press **Test connection** after entering a key. The server needs outbound HTTPS to the provider.
What the model receives: the patient's chart context, vitals/EWS, the transcript, the department's
*specialty pack*, the hospital-memory summary, the doctor's learned rules, matching guidelines, the
formulary (with IDs, dose guards and allergen classes) and the test catalogue. It must return JSON;
every proposal lands as a line in state *Proposed* and nothing is written to the chart until the doctor
approves and signs. The raw proposal is kept on the consult (tab *AI Trace*, HOD only) for audit.

**Scribe / speech-to-text**: the microphone button on the transcript, HPI, plan, SBAR, nurse note and
operative note fields uses the browser's speech recognition (Chrome/Edge). Language is per consult
(English / Urdu `ur-PK`); default in Settings. No audio goes to the Odoo server — only text.
A *"Consent to consultation recording"* consent type exists for the front desk to capture.

---

## 3. The workflow, screen by screen (maps 1:1 to the Medica features)

**Front desk** — Register Visit → the consultation fee posts as a charge, three consents are created,
the file is *Held – payment pending* until the desk collects (policy switch in Settings). Discounts are a
**request, not a favour**: the desk submits % + reason, the file shows *Held – approval pending*, an HOD
approves or rejects by name, the bill applies the approved % to every line and *Collect* is pre-filled
with the discounted total. Bills are real Odoo invoices (`account.move`) linked to the visit; *WhatsApp
Bill* opens a pre-filled wa.me message; *Print hospital bill* gives the PDF.

**Patient Journey Bar** — Registered → Triaged → In Consult → Orders Placed → Treatment → Results →
Discharged, on top of every visit and consult, moving by itself as departments act.

**Nurse station** — vitals once; abnormal values flag themselves; a NEWS2-style **Early Warning Score**
computes and re-orders every doctor's queue (sickest first, then longest wait; ER always ahead).
Allergies travel as a red banner on every screen.

**Consult room** — *Patient Summary* (five bullets, from every department, allergy in caps) → record or
type the conversation → **✦ Analyse** → Diagnosis / Medication / Investigations tabs fill with proposals,
each carrying its reasoning and its source (`ai` / `memory` / `protocol`, learned rules wear a *Learned*
badge). Safety check runs on top: allergy conflicts block approval, interacting pairs are listed.
Approve/reject one by one, or all. **AI Assist off** turns the form into a plain, fast consult form.
**End & sign** files the note (HTML, with the patient's own words), creates the pharmacy queue entry,
posts investigation charges, creates the referral visit (with an AI brief for the specialist) and writes
the case into **Hospital Memory**. **✦ Teach** records a rule for next time.

**Laboratory** — worklist with STAT on top and a turnaround timer; **collection is a gate**: wristband
(MRN) and specimen barcode must both match or the system will not proceed; result entered once,
auto-flagged against reference/critical ranges; **critical values open a call-log entry** that stays red
until the doctor is phoned, the value read back and the call logged; released results stay in the
doctor's *Results to Acknowledge* inbox until he acknowledges them (blocked while a call is pending).

**Pharmacy** — signed prescriptions arrive in the verification queue; allergy conflicts are **blocked**
unless a documented override is recorded; dispensing posts the charges.

**Wards** — admission takes a bed on the live bed board; ward orders are priced when picked and appear on
the nurse's treatment board immediately; the **MAR will not record a dose until the band and the medicine
are scanned**; each given dose posts its charge; **SBAR handoff** is drafted from the chart (medicines this
shift, flagged results, escalation thresholds), sent to the incoming nurse and acknowledged; discharge
posts bed charges and drafts the discharge summary.

**Operation theatre** — WHO Surgical Safety Checklist as three hard gates (Sign In / Time Out / Sign
Out); Sign In is blocked without signed surgical consent; completion posts the procedure charge.

**Blood bank** — ABO/Rh-compatible, screened, in-date units are reserved automatically; **two different
people** must verify (crossmatch + consent) before issue.

**Command centre** — live tiles (patients today, in building, EWS ≥ 5, bed occupancy, held files,
approvals, lab worklist/TAT, critical calls, unacknowledged results, pharmacy queue, theatre, handoffs),
billed/collected/outstanding, 14-day revenue, revenue mix, patient flow, bed occupancy by ward,
sickest in the building, clinician load, top diagnoses. Every tile is clickable. Refreshes every minute.

**Reports (PDF)** — Prescription, Hospital Bill, Lab/Imaging Report, Discharge Summary.

---

## 4. Security model
One login per person, one workspace per role (menus are filtered by group). Groups: Hospital Staff (read
chart), Front Desk, Nurse, Doctor, Pharmacist, Laboratory & Imaging, Blood Bank, Operation Theatre,
Head of Department (approvals), Director / Administrator. A doctor sees and edits his own learned rules;
HOD sees all. Every discount, order, result, dose, handoff and signature carries a name and a time in the
chatter of the record.

Link people to logins under Hospital → Configuration → Staff & Logins (`hms.practitioner`): the role
there drives the queues ("my queue", "my inpatients"), the fee, and the PMDC number on prescriptions.

---

## 5. Data model (for your implementation team)
`hms.patient` · `hms.visit` (journey, EWS, holds, money) · `hms.vitals` · `hms.consent` ·
`hms.discount.request` · `hms.consult` + `hms.consult.diagnosis` + `hms.prescription.line` ·
`hms.order` (lab/imaging/procedure) + `hms.critical.call` · `hms.dispense` + lines ·
`hms.admission` · `hms.ward` · `hms.bed` · `hms.ward.order` · `hms.mar` · `hms.handoff` ·
`hms.progress.note` · `hms.surgery` · `hms.theatre` · `hms.blood.unit` · `hms.blood.request` ·
`hms.charge` (every billable event; invoices are built from it) · `hms.drug` (formulary) ·
`hms.test` · `hms.protocol` (+ lines) · `hms.icd10` · `hms.allergy` · `hms.department` ·
`hms.practitioner` · `hms.ai.rule` (learned rules) · `hms.case.memory` (hospital memory) ·
`hms.ai.service` (provider adapters + prompts) · `hms.dashboard` (command-centre data).
`account.move` gains `hms_visit_id` / `hms_patient_id`.

---

## 6. Going live — things to decide with the hospital
* **Formulary and prices** are seed data: review Hospital → Pharmacy → Formulary and Laboratory → Test Catalogue.
* **Protocols** (Management → Protocols & Guidelines) are the "second voice" next to hospital memory. Add the hospital's own.
* **Consent texts** are in `hms.consent` (editable per record); adapt to your legal wording and Urdu.
* **Recording consent**: keep the *Consent to consultation recording* on the front-desk checklist where the scribe is used.
* **AI**: decision support only. The doctor signs. Keep *AI Trace* for audit and review learned rules periodically.
* **WhatsApp**: uses wa.me deep links (no API needed). Swap `hms.whatsapp.link_action` for a Business API call when you have one.
* **Stock**: pharmacy charges use products (`product.product`) but do not move stock; add Odoo Inventory integration if you want on-hand quantities.

---

Built by Stratos Hub. LGPL-3.
