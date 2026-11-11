---
id: FEAT-XXX
title: <title>
status: draft            # draft | approved | implemented | deprecated
owner: <human>
requirements: [REQ-xxx, NFR-xxx]
adrs: [ADR-nnnn]
modules: [<backend modules / frontend features touched>]
revision: 1
---

# FEAT-XXX: <title>

> Copy this file to `specs/FEAT-XXX-<slug>.md`. Keep every section; write "None" or "No change" instead of deleting one.
> Planned things are described as planned. Do not present anything as implemented.
> If the feature specifies driver schedules, include the notice: "The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance."

## 1. Goal

One paragraph: what exists when this feature is done.

## 2. Business context

Why it matters for the dispatcher or for the project. Link the requirements and the report sections.

## 3. Scope / Out of scope

**In scope:** …

**Out of scope:** …

## 4. Functional requirements

Numbered, testable statements (FR-1, FR-2, …).

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-xxx | … | … |

## 6. Contracts (API, data/migrations, ports, agent tools)

- **API:** method, path, role, request schema, response schema, every status code and problem `code`.
- **Data / migrations:** tables, columns, constraints, indexes; or "No change".
- **Ports:** protocol signatures; or "No change".
- **Configuration:** environment variables and defaults.
- **Agent tools:** one "Agent Tool Spec" block per tool (below); or "No change".

### Tool: <name>
- Agent(s): <allowlist>
- Kind: read | write (write ⇒ interrupt required)
- Input schema: <Pydantic model / fields>
- Output schema: <model>, max size: <N items>
- Backing service: <module.service.method>
- Facts exported for grounding: <fields>
- Untrusted fields: <fields with external content>
- Errors: <codes> → agent behaviour
- Tests: AC-…

## 7. Acceptance criteria

- **AC-FEAT-XXX-01** [unit|property|golden|contract|db|integration|agent|e2e|eval] Given … When … Then …

## 8. Edge cases

- …

## 9. Dependencies

Specifications, ADRs, libraries (name, version, licence) and shared files this feature needs.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| AC-FEAT-XXX-01 | `apps/api/tests/…` | … |

## 11. Open questions

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-XXX-01 | … | … | AC-… / nothing |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | YYYY-MM-DD | Initial draft |
