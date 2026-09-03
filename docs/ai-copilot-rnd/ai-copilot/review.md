## CRITICAL E2E FINDINGS — FIX BEFORE PROCEEDING

The Phase 0/1 E2E test has successfully demonstrated:

* Alamia AI connectivity works.
* BitNet inference works.
* Odoo patient/appointment lookup works.
* MCP/action execution works sufficiently to create records.
* Human approval → Odoo write flow exists.

However, the test exposed several blocking correctness issues. Fix these before implementing additional clinical workflows.

### P0-1 — Workflow Routing Failure

W04 Ambient Consultation Scribe was routed to:

`w09_prescription_assistant`

This is incorrect.

Implement deterministic workflow classification tests and ensure workflow selection is based on user intent, not merely entities found in context.

Examples:

* "Document today's consultation" → W04
* "Generate SOAP note" → W04
* "Prepare prescription" → W09
* "Prescribe amoxicillin" → W09
* "Prepare me for today's patient" → W02

Add regression tests proving W04 cannot accidentally route to W09.

For ambiguous intent, require clarification rather than executing a potentially dangerous workflow.

---

### P0-2 — Strict Workflow Output Schemas

Every workflow must have an explicit typed output contract.

W04 must return:

```python
class SOAPNote(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str
```

W09 must return a separate PrescriptionProposal schema.

W02 must return a PreConsultBrief schema.

Reject/retry model responses that do not conform to the workflow schema.

Do not rely on prompts alone.

---

### P0-3 — Clinical Data Integrity Validation

Implement deterministic validation after model generation and BEFORE any approval/write operation.

At minimum detect:

* BID + once daily contradiction
* missing medication
* missing dosage
* invalid frequency
* invalid duration
* contradictory fields
* impossible dates
* unsupported Odoo relation values

A contradiction such as:

`BID (once daily)`

must produce a hard validation failure and must never become an executable prescription.

---

### P0-4 — Separate Odoo Facts From AI Suggestions

W02 currently generated:

"Maropitant Cerenia 16mg once daily for 3 days is recommended..."

Unless this recommendation exists in authoritative Odoo data, it must NOT be presented as a patient fact.

W02 V1 should be strictly evidence-grounded.

Separate output into:

1. Patient Facts — sourced from Odoo
2. Recent History — sourced from Odoo
3. Active Medications — sourced from Odoo
4. Pending Items — sourced from Odoo
5. Things To Verify — generated from available facts

Do not generate autonomous treatment recommendations in W02.

If recommendations are introduced later, they must be explicitly labelled as AI-generated clinical decision support and require clinician review.

---

### P0-5 — No Fabricated Dates

Dates must be grounded in Odoo records.

The E2E output contained:

"vomiting ... since September 4th"

while the current test date is September 3rd.

Determine whether this is bad fixture data or model hallucination.

Add temporal consistency validation.

AI must never invent dates when source data is unavailable.

---

### P0-6 — Fix Odoo Write Verification

Current behavior:

```text
Successfully created vet.prescription #5
[VERIFIED] Record #5: []
```

This is not valid verification.

After every successful write:

1. Capture returned record ID.
2. Read the exact record back from Odoo.
3. Assert the record exists.
4. Assert expected fields match the approved action payload.
5. Fail the E2E test if read-back fails.

Expected pattern:

```text
CREATE
 ↓
record_id
 ↓
READ(record_id)
 ↓
FIELD ASSERTIONS
 ↓
VERIFIED
```

Never report a successful workflow when persistence verification returns an empty result.

---

### P0-7 — Establish the AI Workflow Safety Pipeline

All clinical write workflows must follow:

```text
User Request
 ↓
Role Resolution
 ↓
Context Resolution
 ↓
Workflow Classification
 ↓
Model Inference
 ↓
Structured Schema Validation
 ↓
Clinical/Data Integrity Validation
 ↓
Action Proposal
 ↓
Human Approval
 ↓
MCP Execution
 ↓
Odoo ACL Enforcement
 ↓
Read-back Verification
 ↓
Audit Log
```

No shortcut should bypass this pipeline.

---

### P1 — Model Evaluation Separation

Do not conclude that BitNet is unsuitable based on these failures.

Separate evaluation into:

A. Model capability
B. Workflow routing correctness
C. Structured-output reliability
D. Clinical/data validation
E. Tool selection
F. Odoo execution
G. Persistence verification

Create benchmark cases specifically for BitNet, Phi and the other available SLMs.

The goal is to determine which models are reliable for which tasks, rather than selecting one model globally.

---

### P1 — Evidence Provenance

For patient-facing/clinical factual outputs, retain source metadata where practical.

Example:

```json
{
  "claim": "Previous weight was 28.4 kg",
  "source": {
    "model": "vet.patient",
    "record_id": 3,
    "field": "weight"
  }
}
```

The UI should eventually allow the clinician to inspect the originating Odoo record.

---

### P1 — Expand E2E Regression Coverage

Before proceeding to additional workflows, establish passing tests for:

* W02 correct routing
* W04 correct routing
* W09 correct routing
* W04 valid SOAP schema
* W09 valid prescription schema
* contradictory prescription detection
* missing data handling
* fabricated date detection
* permission denial
* human approval
* Odoo create
* Odoo read-back verification
* failed MCP execution
* failed Odoo persistence
* model timeout/failure
* model fallback

The test suite must fail on any P0 condition.

### Definition of Ready for Next Sprint

Do not proceed to broad workflow implementation until:

* W02/W04/W09 routing is deterministic and regression-tested.
* W04 actually produces a SOAP structure.
* W09 produces a validated prescription structure.
* Contradictory medication instructions are rejected.
* W02 does not fabricate clinical recommendations.
* Odoo writes are verified by read-back.
* All P0 E2E tests pass.
