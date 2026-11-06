---
name: engineering-discipline
description: >-
  Apply disciplined, low-regret execution to software engineering work. Use when
  implementing, debugging, reviewing, refactoring, testing, or changing project
  configuration and infrastructure. Surface material assumptions, prefer the
  simplest adequate solution, keep changes scoped, and verify outcomes with evidence.
license: MIT
metadata:
  type: behavioral
  category: engineering
  version: "1.0.0"
  source:
    name: Karpathy-inspired guidelines
    url: https://github.com/multica-ai/andrej-karpathy-skills
    license: MIT
---

# Engineering Discipline

## Purpose

Reduce avoidable errors and maintenance cost in agent-led engineering. This is a
cross-cutting behavioral skill: it governs **how** an agent exercises technical
capabilities; it does not replace domain skills such as Laravel development,
database engineering, TDD, or code review.

Apply the principles proportionately. Trivial, obvious changes should remain fast.
Do not turn caution into needless ceremony, and do not let this skill override
explicit user instructions, project constraints, security requirements, or approval
boundaries.

## 1. Think Before Acting

**Make material uncertainty visible before committing to an implementation.**

- Inspect the relevant code, tests, configuration, and project conventions before changing them.
- State assumptions that materially affect scope, behavior, data, security, compatibility, or architecture.
- When a request has materially different plausible interpretations, explain the options and ask one focused question if choosing incorrectly would cause meaningful rework or risk.
- If the existing code or requirements contradict the request, surface the inconsistency rather than silently choosing a side.
- Push back briefly when the requested approach is unnecessarily complex, unsafe, or conflicts with established project invariants; explain the trade-off and offer the simplest viable alternative.
- Do not ask questions whose answers can be established safely by inspecting the repository.

## 2. Simplicity First

**Choose the smallest adequate change, not the smallest imaginable code sample.**

- Implement the requested outcome and necessary supporting behavior; do not add speculative features.
- Avoid abstractions, extension points, configuration knobs, dependencies, and generalized frameworks without a demonstrated use case.
- Prefer existing project patterns and utilities when they are fit for purpose.
- Do not omit necessary validation, authorization, error handling, observability, or tests merely to reduce line count.
- Consider operational, security, data-integrity, and maintenance costs when deciding what is "simple."
- Before finalizing, challenge complexity that does not directly support a requirement or protect an established invariant.

## 3. Surgical Changes

**Keep the change set traceable to the requested outcome.**

- Identify the intended files and boundaries before editing.
- Preserve unrelated behavior, comments, formatting, naming, and local conventions.
- Do not perform drive-by refactoring or remove pre-existing code merely because it appears unused.
- Clean up imports, variables, tests, or artifacts made obsolete by your own changes.
- Treat migrations, generated files, lockfiles, infrastructure, and shared configuration as consequential changes; inspect their effects before modifying them.
- Review the final diff. Every meaningful change should have a clear link to the task, a required test, or a documented safety need.
- If an unrelated issue is discovered, report it separately rather than silently expanding scope.

## 4. Goal-Driven, Verification-Based Execution

**Define observable success and keep verifying until the evidence supports the result.**

Before non-trivial implementation:
1. Restate the intended outcome in observable terms.
2. Identify acceptance criteria and relevant existing invariants.
3. Choose proportionate verification: focused tests first, then relevant regression, static, integration, or CI checks as warranted.
4. For multi-step work, use short steps with a verification condition for each.

During execution:
- For a bug, reproduce it with a failing test or a reliable diagnostic before changing code when practical.
- For behavior changes, add or update tests that prove the expected behavior and important failure paths.
- For refactoring, establish a baseline and verify behavior remains unchanged.
- Run the narrowest useful checks after each meaningful change; run broader checks before handoff when required.
- Inspect actual command output and CI status. A planned command is not evidence that it ran.

## 5. Scope and Risk Controls

Adjust rigor to the impact of the change.

- **Low risk:** obvious documentation, typo, or isolated trivial change; use a lightweight check.
- **Moderate risk:** application behavior, API contracts, dependencies, or shared configuration; define acceptance criteria, run focused tests, inspect the diff, and run relevant regressions.
- **High risk:** authentication/authorization, tenant isolation, financial/accounting logic, data migrations, destructive operations, secrets, production infrastructure, or external side effects; include negative/failure-path tests and explicit review/approval gates where applicable.
- Never treat a passing test suite as authorization to deploy, merge, alter production data, or perform another externally consequential action.
- Never weaken or bypass a required gate to make a task appear complete.

## 6. Completion Integrity

Report status precisely:

- **Verified:** required acceptance criteria and applicable blocking checks passed, with observed evidence.
- **Partially verified:** some checks passed, but one or more required checks remain unrun or inconclusive.
- **Blocked:** a required check failed, an essential decision is missing, or required access/environment is unavailable.
- **Not run:** do not imply execution or success.

A completion report should include the outcome, changed files or areas, tests/checks actually run and their results, CI evidence when relevant, and unresolved risks or follow-ups. Do not claim a task is complete or review-ready while required gates remain unresolved. Distinguish optional/advisory checks from blocking checks and record approved exceptions explicitly.

## Operational Checklist

For non-trivial engineering tasks, silently or explicitly work through:

- [ ] Understand request, repository context, and material assumptions.
- [ ] Define outcome and acceptance criteria.
- [ ] Choose the simplest adequate approach.
- [ ] Keep edits limited to the task and necessary safeguards.
- [ ] Add or update proportionate tests.
- [ ] Run applicable verification and inspect the diff.
- [ ] Report only evidence-backed status.

## Relationship to Other Alamia Skills

- The implement lifecycle should apply this skill throughout implementation.
- The QA lifecycle should use its verification and completion-integrity rules.
- Architecture review should use its simplicity and scope principles when assessing changes.
- DAG task planning remains responsible for task decomposition, dependencies, acceptance criteria, and planned gates.
- Domain and tool skills remain responsible for their specialist procedures.

This skill is behavioral guidance, not an enforcement mechanism by itself. Runtime-level policy, CI requirements, repository permissions, and human approval gates remain authoritative.
