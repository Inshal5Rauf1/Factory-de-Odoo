# Phase 3: Module Discussion - Research

**Researched:** 2026-03-05
**Domain:** CLI command, workflow, agent, JSON question templates, interactive Q&A
**Confidence:** HIGH

## Summary

Phase 3 creates the `/amil:discuss-module` command and workflow that runs an interactive, module-type-aware Q&A session to produce a structured CONTEXT.md for each Odoo module. The phase also enhances the existing `amil-module-researcher` agent with per-module Odoo knowledge (used in Phase 4, not Phase 3).

The implementation follows well-established patterns from Phases 1-2: a slash command file (`commands/amil/discuss-module.md`) that references a workflow file (`amil/workflows/discuss-module.md`), which spawns a new agent (`agents/amil-module-questioner.md`). A new JSON reference file (`amil/references/module-questions.json`) stores the 10 question templates (9 types + 1 generic). No new CJS library modules are needed -- the workflow reads `module_status.json` and `decomposition.json` directly using existing CLI subcommands.

**Primary recommendation:** Follow the exact command/workflow/agent pattern from `new-erp` (Phase 2). The questioner agent uses `AskUserQuestion` for interactive Q&A, receives the question template + module metadata as prompt context, and writes CONTEXT.md using the `Write` tool.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Module Type Detection (DISC-02):** Hybrid auto-detect from name + user confirmation. Pattern match `uni_fee` -> "fee", `uni_student` -> "student", etc. using a lookup table. If no match, user selects from type list. Quick confirmation: "Detected module type: **fee**. Correct? (yes / change)"
- **Question Templates (DISC-03):** 9 typed templates + 1 generic fallback, stored as single JSON file `amil/references/module-questions.json`. Format: `{ "fee": { "questions": [...], "context_hints": [...] } }`. 8-12 questions per type.
- **Discussion Flow Architecture (DISC-01, DISC-04):** Single `amil-module-questioner` agent handles full Q&A session. Agent receives: module type, question template, decomposition.json entry (models/depends/complexity), config.json odoo block. Adaptive: agent uses template as guide but can skip irrelevant questions or ask follow-ups. Session is interactive via AskUserQuestion -- present 1-2 questions at a time.
- **Researcher Agent Scope (AGNT-01):** Enhance existing `amil-module-researcher.md`, used in Phase 4 not Phase 3. Add: field type recommendations, security pattern lookup, view inheritance patterns, Odoo pitfalls per domain. Training knowledge only (no web search).

### Claude's Discretion
- Exact question wording in module-questions.json
- Generic fallback question selection
- How the questioner agent formats follow-up questions
- Internal structure of the discuss-module workflow file
- CONTEXT.md template structure for module discussion output
- How decomposition.json metadata influences question selection

### Deferred Ideas (OUT OF SCOPE)
- Multi-agent discussion (questioner + researcher pair)
- Question template versioning
- Discussion history/replay
- Auto-generated questions from model list
- Web-based OCA research during discussion
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DISC-01 | `/amil:discuss-module` command and workflow created | Command/workflow pattern from `new-erp` (Phase 2); command references workflow via `@~/.claude/amil/workflows/discuss-module.md` |
| DISC-02 | Module type detected from name/description | Lookup table in workflow with 9 known type prefixes; fallback to user selection via `AskUserQuestion` |
| DISC-03 | Module-type-specific question templates loaded | `module-questions.json` reference file with 10 entries (9 types + generic); 8-12 questions each with id, question, options, default, context fields |
| DISC-04 | `odoo-module-questioner` agent created with per-type expertise | Agent file `agents/amil-module-questioner.md` with frontmatter matching existing agent pattern; receives template + metadata in prompt |
| DISC-05 | Q&A output written to `.planning/modules/{module}/CONTEXT.md` | Questioner agent uses Write tool to produce structured CONTEXT.md at the artifact path from `module_status.json` |
| AGNT-01 | `researcher.md` agent specialized for Odoo research | Enhance existing `agents/amil-module-researcher.md` with per-domain field type knowledge, security patterns, view inheritance, and pitfall awareness |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Node.js built-ins (fs, path) | N/A | File I/O for JSON templates and CONTEXT.md | Zero npm runtime deps rule (CLAUDE.md) |
| `amil-tools.cjs` CLI | Current | `module-status get`, `config-get` subcommands | Established CLI tool; never edit state files directly |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `AskUserQuestion` (Claude Code tool) | N/A | Interactive Q&A with the user | Every question in the questioner agent |
| `Task()` (Claude Code tool) | N/A | Spawn questioner agent as subagent | Workflow spawns agent with full prompt context |
| `Write` (Claude Code tool) | N/A | Write CONTEXT.md output | Agent writes final output file |
| `Read` (Claude Code tool) | N/A | Read decomposition.json, config.json, module_status.json | Workflow reads metadata to build agent prompt |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Single JSON file for templates | Separate JSON per type | Single file is simpler, easier to maintain; separate files only needed at 20+ types |
| AskUserQuestion | Plain text prompting | AskUserQuestion provides structured options; locked decision |
| Task() for agent | Inline workflow logic | Agent isolation provides clean context; consistent with Phase 2 pattern |

**Installation:**
```bash
# No installation needed -- zero npm runtime deps
```

## Architecture Patterns

### Recommended Project Structure
```
commands/amil/
  discuss-module.md              # Slash command definition (NEW)

amil/workflows/
  discuss-module.md              # Workflow definition (NEW)

amil/references/
  module-questions.json          # 10 question templates (NEW)

agents/
  amil-module-questioner.md  # Questioner agent (NEW)
  amil-module-researcher.md  # Enhanced researcher (MODIFY)
```

### Pattern 1: Slash Command -> Workflow -> Agent

**What:** Three-layer pattern established in Phase 2. Command is a thin wrapper that references a workflow file. Workflow orchestrates multi-step logic and spawns agents via `Task()`.

**When to use:** Every new `/amil:*` command.

**Example (from new-erp.md command):**
```markdown
---
name: amil:discuss-module
description: Run interactive module discussion to capture design decisions
argument-hint: "{module_name}"
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<context>
Runs a module-type-aware Q&A session producing structured CONTEXT.md.

**Requires:** Module initialized in module_status.json (status: planned)
**Produces:** `.planning/modules/{module}/CONTEXT.md`
</context>

<objective>
Capture module design decisions through interactive discussion.
</objective>

<execution_context>
@~/.claude/amil/workflows/discuss-module.md
</execution_context>

<process>
Execute the discuss-module workflow end-to-end.
</process>
```

### Pattern 2: Agent Frontmatter Convention

**What:** Agent files use YAML frontmatter with specific fields: name, description, tools, color, model_tier, input, output, skills.

**When to use:** Every new agent.

**Example (from existing agents):**
```yaml
---
name: amil-module-questioner
description: Run per-type Q&A session for Odoo module design decisions
tools: Read, Write, Bash, AskUserQuestion
color: yellow
model_tier: quality
input: Module type + question template + decomposition entry + config odoo block
output: .planning/modules/{module}/CONTEXT.md
---
```

### Pattern 3: Module Status Gate

**What:** Before operating on a module, validate it exists in `module_status.json` and is at the correct lifecycle state.

**When to use:** Every module-level command (`discuss-module`, `plan-module`, `generate-module`).

**Example:**
```bash
# Check module exists and is at "planned" status
STATUS=$(node amil/bin/amil-tools.cjs module-status get ${MODULE} --raw --cwd "$(pwd)")
# Parse STATUS JSON to check .status === "planned"
```

### Pattern 4: Question Template JSON Structure

**What:** Each module type has a questions array and context_hints array. Questions have id, question text, options (optional), default (optional), and context (explanation).

**When to use:** Loading question bank for questioner agent.

**Example:**
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
      },
      {
        "id": "fee_penalty_method",
        "question": "How should late payment penalties be calculated?",
        "options": ["fixed_amount", "percentage", "tiered"],
        "default": "percentage",
        "context": "Tiered allows different rates for different overdue periods"
      }
    ],
    "context_hints": [
      "Check config.json for localization (pk/sa/ae affects currency)",
      "Check if multi_company affects fee structure separation"
    ]
  }
}
```

### Anti-Patterns to Avoid
- **Hardcoding questions in the agent file:** Questions must live in `module-questions.json` for maintainability. The agent receives them as prompt context.
- **Multiple agent spawns per discussion:** Locked decision is single questioner agent. Do not spawn researcher during discussion.
- **Reading state files directly with fs:** Always use `amil-tools.cjs` CLI subcommands for state reads/writes (CLAUDE.md rule 2).
- **Writing CONTEXT.md from the workflow:** The agent writes CONTEXT.md, not the workflow. Workflow only orchestrates.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Module status lookup | Custom JSON parser | `amil-tools.cjs module-status get {name}` | Atomic reads, consistent error handling |
| Config reading | `fs.readFileSync` on config.json | `amil-tools.cjs config-get odoo` | Validated schema, proper defaults |
| Module type detection | Complex regex | Simple prefix lookup table (object literal) | 9 known prefixes, deterministic |
| Interactive Q&A | Custom prompt system | `AskUserQuestion` Claude Code tool | Built-in structured options, "Other" handling |

**Key insight:** This phase is primarily markdown files (command, workflow, agent) and one JSON file (templates). The only "code" is the lookup table logic embedded in the workflow markdown. No new CJS modules needed.

## Common Pitfalls

### Pitfall 1: Module Not Initialized
**What goes wrong:** `discuss-module` called before `new-erp` has run -- module doesn't exist in `module_status.json`.
**Why it happens:** User skips the init flow or types wrong module name.
**How to avoid:** Workflow Step 1 MUST validate module exists via `module-status get`. If not found, show clear error with available modules.
**Warning signs:** Empty or missing module_status.json.

### Pitfall 2: CONTEXT.md Already Exists
**What goes wrong:** User runs discuss-module twice -- overwrites previous decisions.
**Why it happens:** Re-running for refinement without realizing file exists.
**How to avoid:** Check if `.planning/modules/{module}/CONTEXT.md` has real content (not just placeholder). Offer update/skip/overwrite.
**Warning signs:** CONTEXT.md file size > placeholder size.

### Pitfall 3: Agent Context Overflow
**What goes wrong:** Passing ALL question templates to the agent wastes context window.
**Why it happens:** Loading full module-questions.json instead of just the relevant type.
**How to avoid:** Workflow extracts ONLY the relevant type's questions before injecting into agent prompt.
**Warning signs:** Agent responses become truncated or low quality.

### Pitfall 4: config.json Odoo Block Missing
**What goes wrong:** Questioner tries to read odoo config (multi_company, localization) but block doesn't exist.
**Why it happens:** Project initialized without `new-erp` running config collection.
**How to avoid:** Workflow checks for odoo block existence before spawning agent. Warn if missing but continue with defaults.
**Warning signs:** config.json has no `odoo` key.

### Pitfall 5: decomposition.json Not Found
**What goes wrong:** Module exists in module_status.json but decomposition.json is missing/corrupted.
**Why it happens:** module_status.json was created but research artifacts were deleted.
**How to avoid:** Workflow checks for decomposition.json; if missing, fall back to module_status.json entry data only.
**Warning signs:** `.planning/research/decomposition.json` not readable.

## Code Examples

Verified patterns from existing codebase:

### Module Type Detection Lookup Table
```javascript
// Embedded in workflow as inline logic description
const MODULE_TYPES = {
  'uni_core': 'core',
  'uni_student': 'student',
  'uni_fee': 'fee',
  'uni_exam': 'exam',
  'uni_faculty': 'faculty',
  'uni_hr': 'hr',
  'uni_timetable': 'timetable',
  'uni_notification': 'notification',
  'uni_portal': 'portal',
};

// Detection: exact match first, then prefix match
function detectModuleType(moduleName) {
  if (MODULE_TYPES[moduleName]) return MODULE_TYPES[moduleName];
  for (const [prefix, type] of Object.entries(MODULE_TYPES)) {
    if (moduleName.startsWith(prefix.replace('uni_', '') + '_') || moduleName.includes(type)) {
      return type;
    }
  }
  return null; // fallback to user selection
}
```

### Reading Module Metadata in Workflow
```bash
# Get module status and artifact path
MODULE_STATUS=$(node amil/bin/amil-tools.cjs module-status get "${MODULE}" --raw --cwd "$(pwd)")

# Get decomposition entry for the module (models, depends, complexity)
DECOMP=$(cat .planning/research/decomposition.json)

# Get odoo config block
ODOO_CONFIG=$(node amil/bin/amil-tools.cjs config-get odoo --raw --cwd "$(pwd)" 2>/dev/null || echo '{}')
```

### Agent Prompt Structure (Task() call)
```
Task(
  prompt="You are discussing module design for ${MODULE_NAME} (type: ${MODULE_TYPE}).

MODULE METADATA:
---
Name: ${MODULE_NAME}
Type: ${MODULE_TYPE}
Models: ${MODELS_LIST}
Dependencies: ${DEPENDS_LIST}
Complexity: ${COMPLEXITY}
---

ODOO CONFIG:
---
${ODOO_CONFIG_JSON}
---

QUESTION TEMPLATE:
---
${QUESTIONS_JSON_FOR_TYPE}
---

CONTEXT HINTS:
---
${CONTEXT_HINTS}
---

Follow your agent instructions to run the Q&A session and write CONTEXT.md to:
.planning/modules/${MODULE_NAME}/CONTEXT.md",
  subagent_type="amil-module-questioner",
  description="Module discussion: ${MODULE_NAME}"
)
```

### Module CONTEXT.md Output Structure
```markdown
# {Module Name} - Discussion Context

**Module:** uni_fee
**Type:** fee
**Discussed:** {date}
**Status:** Ready for spec generation

## Design Decisions

### Fee Structure
- Field type: monetary (currency-aware)
- Supports multiple fee structures per program: yes
- Fee components: tuition, lab fees, activity fees

### Payment Integration
- Payment gateway: none (manual for v1)
- Installment plans: yes, configurable per fee structure
- Late penalties: percentage-based, single rate

## Odoo-Specific Choices

- Use monetary fields for all amounts (currency-aware with localization)
- Fee structures as separate model linked to uni.program via Many2one
- Invoice generation via account.move integration

## Open Questions

- Items deferred to spec generation phase
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Generic phase discussion | Module-type-specific templates | Phase 3 (new) | Domain-specific questions produce richer context |
| OCA checker only | Enhanced researcher with field/security/view knowledge | Phase 3 (new) | Better recommendations in Phase 4 |

**Deprecated/outdated:**
- None -- this is a new capability being built for the first time.

## Open Questions

1. **Module name prefix flexibility**
   - What we know: Current lookup assumes `uni_` prefix for all modules
   - What's unclear: Will the project ever have modules without `uni_` prefix?
   - Recommendation: Support `uni_` prefix as default but allow the lookup table to be extended. The fallback to user selection handles edge cases.

2. **Question template evolution**
   - What we know: 8-12 questions per type is the locked decision
   - What's unclear: How questions will evolve after first use
   - Recommendation: Keep the JSON flat and simple. Template versioning was explicitly deferred.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Node.js built-in `node:test` |
| Config file | `scripts/run-tests.cjs` (test runner) |
| Quick run command | `node --test tests/discuss-module.test.cjs` |
| Full suite command | `npm test` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DISC-02 | Module type detection from name | unit | `node --test tests/discuss-module.test.cjs --test-name-pattern "type detection"` | No -- Wave 0 |
| DISC-03 | Question template loading and validation | unit | `node --test tests/discuss-module.test.cjs --test-name-pattern "question template"` | No -- Wave 0 |
| DISC-05 | CONTEXT.md output structure validation | unit | `node --test tests/discuss-module.test.cjs --test-name-pattern "context output"` | No -- Wave 0 |
| DISC-01 | Command file exists with correct frontmatter | unit | `node --test tests/discuss-module.test.cjs --test-name-pattern "command"` | No -- Wave 0 |
| DISC-04 | Agent file exists with correct frontmatter | unit | `node --test tests/discuss-module.test.cjs --test-name-pattern "agent"` | No -- Wave 0 |
| AGNT-01 | Researcher agent has enhanced Odoo sections | unit | `node --test tests/discuss-module.test.cjs --test-name-pattern "researcher"` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `node --test tests/discuss-module.test.cjs`
- **Per wave merge:** `npm test`
- **Phase gate:** Full suite green before `/amil:verify-work`

### Wave 0 Gaps
- [ ] `tests/discuss-module.test.cjs` -- covers DISC-01 through DISC-05, AGNT-01
- [ ] Test should validate: module-questions.json is valid JSON with all 10 types, each type has 8-12 questions, question objects have required fields (id, question, context)
- [ ] Test should validate: command file frontmatter has correct name, allowed-tools
- [ ] Test should validate: agent file frontmatter has correct name, tools include AskUserQuestion
- [ ] Test should validate: type detection returns correct type for all 9 known prefixes and null for unknown
- [ ] No framework install needed -- `node:test` already in use (633 tests passing)

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `commands/amil/new-erp.md` -- command pattern
- Codebase inspection: `amil/workflows/new-erp.md` -- workflow pattern with Task() spawning
- Codebase inspection: `agents/amil-module-researcher.md` -- agent frontmatter and structure
- Codebase inspection: `agents/amil-erp-decomposer.md` -- agent with structured JSON output
- Codebase inspection: `amil/bin/lib/module-status.cjs` -- module lifecycle API
- Codebase inspection: `amil/workflows/discuss-phase.md` -- AskUserQuestion patterns and questioning flow
- Codebase inspection: `amil/references/questioning.md` -- question design philosophy
- Codebase inspection: `tests/new-erp.test.cjs` -- test pattern with fixtures and node:test
- Codebase inspection: `CLAUDE.md` -- project rules (CJS, zero deps, atomic writes)

### Secondary (MEDIUM confidence)
- Phase 3 CONTEXT.md -- locked decisions from user discussion

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all patterns directly observed in codebase
- Architecture: HIGH -- follows established Phase 2 patterns exactly
- Pitfalls: HIGH -- derived from observed error handling in existing code
- Test approach: HIGH -- uses same node:test framework with 633 existing tests

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable -- internal tooling, no external dependency changes)
