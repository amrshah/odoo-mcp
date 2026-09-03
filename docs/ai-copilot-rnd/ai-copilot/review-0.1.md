Proceed with the remediation and hardening now.

Treat this as a **P0 stabilization sprint**. Do not implement additional clinical workflows until all P0 issues below are resolved and the regression suite passes.

### Required implementation order

1. Intent/workflow router
2. Typed workflow schemas
3. Schema parsing + retry/rejection
4. Deterministic data/instruction validation
5. W02 evidence/fact separation
6. Odoo read-back verification
7. Full safety-pipeline orchestration
8. Automated regression/E2E tests
9. Re-run the original E2E suite unchanged

### Important architectural constraints

#### 1. Intent routing

Do NOT replace keyword matching with another keyword matcher.

Implement intent classification using explicit workflow definitions and intent examples.

The router must distinguish:

* consultation documentation → W04
* SOAP generation → W04
* prescription request → W09
* patient preparation → W02

A consultation transcript containing words such as "medicine", "prescribe", or "medication" must NOT automatically become W09.

When confidence is insufficient or intents conflict:

`ASK_CLARIFICATION`

Do not guess when a write-capable clinical workflow could be triggered.

---

#### 2. Typed outputs

Every workflow must have a strict Pydantic contract.

At minimum:

```text
W02 → PreConsultBriefSchema
W04 → SOAPNoteSchema
W09 → PrescriptionProposalSchema
```

The workflow must never treat arbitrary LLM markdown as a successful result.

Pipeline:

```text
LLM
 ↓
parse
 ↓
Pydantic validation
 ↓
retry if recoverable
 ↓
reject if invalid
```

Keep raw model output available in debug/audit logs, but never pass unvalidated output into execution.

---

#### 3. Deterministic validation

Create a narrow deterministic validator.

It must detect contradictions such as:

`BID + once daily`

and other obvious structured inconsistencies.

For prescriptions validate, where applicable:

* medication present
* dose present
* unit present
* route present when required
* frequency valid
* duration valid
* frequency/instruction consistency
* quantity consistency where derivable
* no contradictory fields

Do NOT attempt to build a comprehensive autonomous clinical safety/diagnostic engine in this sprint.

The validator is a **data-integrity and consistency barrier**, not a replacement for veterinary judgment.

---

#### 4. W02 evidence grounding

Separate:

```text
odoo_facts
suggested_checks
```

`odoo_facts` must originate from retrieved Odoo data.

AI must not silently turn generated recommendations into patient facts.

W02 V1 should primarily provide:

* patient snapshot
* relevant history
* active medications
* allergies
* pending diagnostics
* active treatments
* recent encounters
* outstanding follow-ups
* things the veterinarian should verify

Avoid autonomous treatment recommendations in W02.

---

#### 5. Temporal integrity

Dates must be grounded in Odoo/context data.

Never allow the model to invent:

* encounter dates
* symptom onset dates
* follow-up dates
* medication dates
* future/past dates

If the source date is unavailable:

`date = unknown`

Add regression coverage for the September 4th vs September 3rd failure observed in the original E2E test.

---

#### 6. Odoo write verification

`success=True` is forbidden unless read-back verification succeeds.

Required:

```text
CREATE
 ↓
record_id
 ↓
READ(record_id)
 ↓
record exists?
 ↓
critical fields match?
 ↓
VERIFIED
```

If the read returns `[]`, `None`, or an unexpected record:

`success=False`

The test must fail.

Do not weaken the assertion merely to make the existing test pass.

---

#### 7. Full orchestration barrier

Enforce:

```text
Role Resolution
 ↓
Context Resolution
 ↓
Intent Classification
 ↓
Workflow Selection
 ↓
Model Selection
 ↓
Inference
 ↓
Schema Validation
 ↓
Data/Clinical Consistency Validation
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
Audit
```

Each stage must have explicit success/failure states.

A failed stage must stop downstream execution.

---

#### 8. Human approval

All V1 clinical writes remain approval-required.

Examples:

* prescription creation
* diagnosis creation
* treatment modification
* clinical note commit

The AI may prepare/propose.

The veterinarian/user approves.

MCP executes under the authenticated Odoo user's permissions.

---

#### 9. Auditability

For every AI action capture at minimum:

```text
request_id
user_id
role
workflow_id
model_used
input/context identifiers
raw/model response reference
validated output
validation results
proposed action
approval status
MCP operation
Odoo record IDs
read-back verification
final status
timestamp
```

Never store secrets or unnecessary sensitive data in logs.

---

### Required regression tests

Add automated tests for:

```text
W02 → W02
W04 → W04
W09 → W09

consultation containing "prescribe" → W04
consultation containing medication discussion → W04
explicit prescription request → W09

invalid SOAP output → rejected/retried
invalid prescription output → rejected/retried

BID + once daily → rejected
missing dose → rejected
missing medication → rejected
contradictory frequency → rejected

missing source date → unknown
future fabricated date → rejected

Odoo create + successful read-back → success
Odoo create + empty read-back → failure
Odoo create + mismatched fields → failure

unauthorized write → rejected
unapproved clinical action → not executed
MCP failure → workflow failure
```

### Final acceptance criterion

Re-run the **original E2E test without modifying its expected behavior merely to make it pass**.

The suite should demonstrate:

1. Correct workflow routing.
2. Correct typed output.
3. No unsupported clinical recommendations presented as facts.
4. No temporal hallucination.
5. Contradictory prescription data rejected.
6. Human approval required.
7. Odoo write actually occurs.
8. Odoo read-back actually verifies the write.
9. Audit trail exists.
10. BitNet remains usable where its output passes the required quality/validation gates.

Only after this P0 stabilization sprint is green should implementation proceed to additional AI workflows.
