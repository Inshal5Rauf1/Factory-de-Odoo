# Phase 3: Module Discussion - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning
**Source:** User-approved recommendations

<domain>
## Phase Boundary

Phase 3 creates the `/amil:discuss-module` command and workflow that:
1. Detects module type from name (with user confirmation)
2. Loads type-specific question templates
3. Runs an interactive Q&A session via a questioner agent
4. Writes structured answers to `.planning/modules/{module}/CONTEXT.md`
5. Enhances the existing researcher agent for deeper Odoo knowledge (used in Phase 4)

</domain>

<decisions>
## Implementation Decisions

### Module Type Detection (DISC-02)

**Locked: Hybrid auto-detect from name + user confirmation**

- Pattern match `uni_fee` -> "fee", `uni_student` -> "student", etc. using a lookup table
- Lookup table stored in the workflow or a constants section of the questioner logic
- If no match (custom module name), user selects from the type list
- Quick confirmation: "Detected module type: **fee**. Correct? (yes / change)"
- Known types: core, student, fee, exam, faculty, hr, timetable, notification, portal

### Question Templates (DISC-03)

**Locked: 9 typed templates + 1 generic fallback, stored as JSON**

- 9 module types: core, student, fee, exam, faculty, hr, timetable, notification, portal
- 1 generic fallback for unrecognized types (asks about models, workflows, security, integrations)
- 8-12 questions per type
- Stored as: Single JSON file `amil/references/module-questions.json`
- Format: `{ "fee": { "questions": [...], "context_hints": [...] } }`
- Questions are domain-specific with Odoo knowledge baked in:
  - fee: monetary vs float, penalty method, payment channels, account.payment integration
  - exam: grading scales, makeup policy, grade computation, result publishing
  - student: enrollment states, academic holds, document management
  - core: institution hierarchy, multi-campus, academic year/term structure
  - faculty: workload tracking, leave integration, performance evaluation
  - hr: payroll integration, contract types, attendance method
  - timetable: conflict resolution, room allocation, recurring patterns
  - notification: channel selection, template engine, event triggers
  - portal: role-based access, self-service scope, document upload

### Discussion Flow Architecture (DISC-01, DISC-04)

**Locked: Single questioner agent, adaptive ordering, no researcher during discussion**

- One `amil-module-questioner` agent handles the full Q&A session
- Agent receives: module type, question template, decomposition.json entry (models/depends/complexity), config.json odoo block
- Adaptive: agent uses template as guide but can skip irrelevant questions or ask follow-ups
- Example: if config.json has multi_company=false, skip campus partitioning questions
- Session is interactive via AskUserQuestion — present 1-2 questions at a time
- Template provides the question bank, agent has discretion on ordering and depth

### Researcher Agent Scope (AGNT-01)

**Locked: Enhance existing amil-module-researcher.md, used in Phase 4 not Phase 3**

- The Phase 2 OCA checker agent already exists — extend it with per-module research capabilities
- Add: field type recommendations, security pattern lookup, view inheritance patterns, Odoo pitfalls per domain
- NOT invoked during discuss-module — runs during plan-module (Phase 4)
- Training knowledge only (no web search) — consistent with Phase 2 decision
- Phase 3 deliverable: update the agent file with enhanced prompts and Odoo-specific instructions

### Claude's Discretion

- Exact question wording in module-questions.json
- Generic fallback question selection
- How the questioner agent formats follow-up questions
- Internal structure of the discuss-module workflow file
- CONTEXT.md template structure for module discussion output
- How decomposition.json metadata influences question selection

</decisions>

<specifics>
## Specific Ideas

### Question Template JSON Structure

```json
{
  "fee": {
    "questions": [
      {
        "id": "fee_field_type",
        "question": "Will fee amounts use Odoo's monetary field (currency-aware) or plain float?",
        "options": ["monetary", "float"],
        "default": "monetary",
        "context": "Monetary fields auto-handle currency conversion and rounding"
      }
    ],
    "context_hints": [
      "Check config.json for localization (pk/sa/ae affects currency)",
      "Check if multi_company affects fee structure separation"
    ]
  }
}
```

### Module CONTEXT.md Output Format

The questioner agent writes to `.planning/modules/{module}/CONTEXT.md`:

```markdown
# {Module Name} - Discussion Context

**Module:** uni_fee
**Type:** fee
**Discussed:** {date}
**Status:** Ready for spec generation

## Design Decisions

### Fee Structure
- Field type: monetary (currency-aware)
- ...

### Payment Integration
- ...

## Odoo-Specific Choices
- ...

## Open Questions
- Items deferred to spec generation phase
```

### discuss-module Command Flow

1. Validate module exists in module_status.json (must be at "planned" status)
2. Check if CONTEXT.md already exists (offer update/skip)
3. Load module entry from decomposition.json
4. Detect module type from name
5. Confirm type with user
6. Load question template for type
7. Spawn questioner agent with template + module context
8. Agent runs interactive Q&A
9. Agent writes CONTEXT.md to `.planning/modules/{module}/CONTEXT.md`

</specifics>

<deferred>
## Deferred Ideas

- Multi-agent discussion (questioner + researcher pair) — keep simple for v1
- Question template versioning — not needed until templates stabilize
- Discussion history/replay — not needed for MVP
- Auto-generated questions from model list — too complex, manual templates sufficient
- Web-based OCA research during discussion — deferred to v2

</deferred>

---

*Phase: 03-module-discussion*
*Context gathered: 2026-03-05 via user-approved recommendations*
