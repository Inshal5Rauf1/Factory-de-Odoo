# Pitfalls Research

**Domain:** Odoo ERP module orchestration (fork of Amil CLI for AI-driven module generation at scale)
**Researched:** 2026-03-05
**Confidence:** HIGH (domain-specific analysis based on actual codebase inspection + ecosystem research)

## Critical Pitfalls

### Pitfall 1: Fork Drift — 233 Hardcoded Path References Create a Rename Minefield

**What goes wrong:**
The Amil codebase contains 203 hardcoded `get-shit-done` / `gsd-tools` / `gsd/` references in workflows alone, plus 23 in templates and 7 in bin files. A naive find-and-replace from `gsd` to `amil` will produce false positives (e.g., `gsd-planner` becomes `amil-planner` but the agent file might still be named `gsd-planner`), miss references embedded in string interpolation, and break the 12 agent role names hardcoded in `core.cjs`'s model profile map. Partial renames result in a CLI that appears to work until a specific workflow triggers an unrenamed path, causing silent failures deep in a multi-agent pipeline.

**Why it happens:**
Amil was never designed for forking. Path references are scattered across markdown workflow files (which are essentially code — they contain `bash` blocks with `$HOME/.claude/get-shit-done/` paths), JavaScript libraries, and template files. Developers underestimate how many distinct reference patterns exist: install paths, tool invocation paths, branch template prefixes, agent role names, config key prefixes, and npm package names.

**How to avoid:**
1. Create a canonical rename manifest: enumerate every reference pattern (`~/.claude/get-shit-done/`, `gsd-tools.cjs`, `gsd/phase-`, `gsd-planner`, `gsd_state_version`, etc.) before touching any files.
2. Build a rename verification script that greps for ALL old patterns after renaming — zero matches required.
3. Rename in layers: paths first, then prefixes, then internal identifiers. Test each layer independently.
4. Keep a `FORK_DIFF.md` documenting every structural change from upstream Amil, so future upstream cherry-picks are feasible.

**Warning signs:**
- `command not found` or `file not found` errors during workflow execution
- Agent spawned with wrong role name (check `Task()` invocations)
- Branch names still using `gsd/` prefix instead of `amil/`

**Phase to address:**
Phase 1 (Foundation) — this must be the very first task, before any new functionality is built.

---

### Pitfall 2: Registry JSON Grows Beyond Context Window Budget

**What goes wrong:**
The `model_registry.json` starts small but grows combinatorially. Each Odoo model has ~10-30 fields, each field has type/relation/string/required/compute metadata. At 20+ modules with 3-5 models each (60-100 models), the full registry reaches 50-150KB of JSON. JSON is notoriously token-inefficient — roughly 40% of tokens are structural syntax (braces, quotes, colons). Injecting the full registry into an AI agent's 200K context window consumes 25-50K tokens on registry alone, leaving less room for the actual generation task and pushing important instructions into the model's low-attention middle zone.

**Why it happens:**
Registry design starts with "just store everything" because it's easy and complete. No one notices the size problem until module 15+ when generation quality degrades because the model can't attend to both the registry AND the generation instructions effectively. By then, the schema is entrenched and changing it requires migrating all existing state.

**How to avoid:**
1. Implement tiered injection from day one (already planned — full for direct depends, field-list for transitive, names for rest). Do not defer this.
2. Design the registry with a compact serialization format alongside the full JSON — e.g., a `registry_compact.json` that strips descriptions, defaults, and non-essential metadata.
3. Set a hard token budget per tier: direct depends gets max 20K tokens, transitive gets max 5K, rest gets max 1K. Measure and enforce.
4. Add a `registry stats` command that reports total size in bytes and estimated tokens from the start. Make size growth visible.

**Warning signs:**
- `model_registry.json` exceeds 50KB
- Generated modules start missing cross-module references that exist in the registry
- AI agents produce responses that ignore or contradict registry data (attention degradation)

**Phase to address:**
Phase 1 (Foundation) for schema design with tiered injection built in. Phase 2 (Core Workflow) for the token budget enforcement.

---

### Pitfall 3: Cross-Module Coherence Breaks Silently

**What goes wrong:**
Module B declares `Many2one('module_a.student')` but module A's model is actually `module_a.student_record`. Or Module C adds a computed field that depends on `module_b.enrollment_ids` but uses `One2many` instead of the correct `Many2many`. These referential integrity errors are invisible at generation time because each module is generated in isolation with only registry context. They only surface when all modules are installed together in Odoo, causing `KeyError`, `ValueError`, or worse — silent data corruption where related fields resolve to `None` instead of failing.

**Why it happens:**
The AI agent generating Module B receives the registry snapshot, but it may hallucinate model names, field names, or relation types despite having correct data in context. There is no automated validation between generation and the next module's generation. The registry records what was planned (spec), not what was actually generated (code). Drift between spec and generated code accumulates silently.

**How to avoid:**
1. After each module generation, parse the actual generated Python code (AST analysis via amil-utils) and update the registry with what was ACTUALLY produced, not what was specified.
2. Implement a coherence check that runs after registry update: for every Many2one/One2many/Many2many field, verify the target model and inverse field exist in the registry.
3. Block tier progression if coherence check fails — do not generate Module C until Module A and B are verified coherent.
4. Store both `spec_fields` and `actual_fields` in registry entries. Diff them to detect spec-vs-reality drift.

**Warning signs:**
- Registry has model names that don't match the generated `_name` attribute in Python files
- `_inherit` references in generated code point to models not yet in the registry
- Odoo installation fails with "field X does not exist on model Y"

**Phase to address:**
Phase 2 (Core Workflow) — the generate-module command must include post-generation registry reconciliation.

---

### Pitfall 4: Belt Integration Assumes a Stable Contract That Does Not Exist Yet

**What goes wrong:**
amil is being built before amil is installed or its output format is finalized. The orchestrator builds assumptions about what the belt produces (manifest structure, file layout, exit codes, error formats) that turn out to be wrong when integration actually happens. Rebuilding the integration layer after 20+ modules of workflow has been designed around incorrect assumptions wastes enormous effort.

**Why it happens:**
The project explicitly defers belt manifest schema to amil ("Schema defined by amil, not amil — adapt to whatever the belt produces"). This is architecturally correct but operationally dangerous: without even a draft contract, every `Task()` invocation, every manifest parser, and every registry update routine is built on guesswork. The PROJECT.md even notes "amil is not yet installed."

**How to avoid:**
1. Create a `belt_contract_draft.json` with the minimum expected interface: input format (what amil passes to belt), output format (what belt returns), exit codes, and error envelope. Even if it changes, having a strawman prevents designing in a vacuum.
2. Build a mock belt for testing — a script that accepts spec.json and produces a dummy module with manifest and model stubs. Test the entire orchestration pipeline against this mock.
3. Define the integration boundary as a single adapter module (`belt_adapter.js`) that translates between amil's internal format and the belt's format. When the real belt arrives, only this adapter needs to change.
4. Ship a canary integration test early: generate one real module through the actual belt and validate every assumption.

**Warning signs:**
- Multiple places in the codebase parse belt output with different assumptions
- No tests can run end-to-end because the belt doesn't exist
- Belt integration is "Phase 3" or later — it should be validated in Phase 2

**Phase to address:**
Phase 1 (Foundation) for the adapter pattern and mock belt. Phase 2 (Core Workflow) for canary integration test.

---

### Pitfall 5: State File Corruption From Non-Atomic Writes

**What goes wrong:**
Amil's `state.cjs` uses raw `fs.writeFileSync` wrapped in a `writeStateMd` function. The new project adds three additional JSON state files (`model_registry.json`, `module_status.json`, `computation_chains.json`, `security_scope.json`). If a `Task()` subagent crashes mid-write (context window exhaustion, timeout, network issue), the JSON file is left in a truncated/corrupted state. The next operation reads corrupted JSON, `JSON.parse` throws, and the entire pipeline halts. Recovery requires manual file restoration because there's no backup.

**Why it happens:**
Developers assume `writeFileSync` is atomic — it is not. On Linux, `writeFileSync` can leave partial writes if the process is killed (SIGKILL, OOM). With multiple state files being updated in sequence (registry, then status, then computation chains), a crash between writes leaves the system in an inconsistent state where some files reflect the new module and others don't.

**How to avoid:**
1. Implement write-then-rename pattern: write to `model_registry.json.tmp`, then `fs.renameSync` to `model_registry.json`. Rename is atomic on Linux.
2. Keep the previous version as `model_registry.json.bak` before each write. One-step rollback.
3. Add a `registry rollback` command that restores from `.bak` files.
4. Validate JSON integrity after every read — if parse fails, auto-restore from `.bak` and log a warning.

**Warning signs:**
- `SyntaxError: Unexpected end of JSON input` in any state file read
- State files with 0 bytes
- Module status says "generated" but registry doesn't contain the module's models

**Phase to address:**
Phase 1 (Foundation) — the `registry.js` CRUD module must use atomic writes from the start.

---

### Pitfall 6: Odoo Security Scope Explosion Creates Combinatorial Complexity

**What goes wrong:**
The university ERP has 5 scope levels (institution, campus, faculty, department, program) with multi-company support and dynamic RBAC. Each module needs security rules (`ir.rule`) that respect all applicable scope levels. With 20+ modules, each needing 3-8 record rules across 5 scope levels, you get 300-800 security rules that must be coherent. AI agents routinely generate security rules that are either too permissive (missing scope filters) or too restrictive (blocking legitimate cross-scope access), and the errors only manifest as "Access Denied" in production.

**Why it happens:**
Security scope is the hardest part of multi-tenant Odoo to get right. Each scope level adds a `domain` filter to record rules, and these filters must compose correctly across inherited models. AI models struggle with the combinatorial nature — they generate plausible-looking rules that fail edge cases (e.g., a department head who is also a faculty member).

**How to avoid:**
1. Define security scope templates in `security_scope.json` that modules reference rather than generating from scratch. The AI fills in model-specific fields but the scope logic comes from templates.
2. Create a security scope validator that checks: every model has rules for every applicable scope level, no two rules create contradictory access, and multi-company filters are present where needed.
3. Generate security rules as a separate pass after all module models are registered — security needs the full picture.
4. Include security rule testing in the coherence check: simulate access for each role at each scope level.

**Warning signs:**
- Modules generating their own scope filtering logic instead of using shared utilities
- `ir.rule` records with empty or trivially-true domains
- Missing `company_id` filters on models that should be multi-company

**Phase to address:**
Phase 2 (Core Workflow) — security scope templates should be established before any module generation begins.

---

### Pitfall 7: Third-Party Model Scanning Is Incomplete or Stale

**What goes wrong:**
When a custom module declares `depends: ['account']`, the registry needs account module's models (account.move, account.move.line, etc.) to validate cross-module references. On-demand scanning sounds efficient but breaks in practice: the scanner may not have access to the Odoo source (no local installation), may scan the wrong version (Odoo 16 models vs Odoo 17), or may produce an incomplete scan (missing computed fields, missing related fields). Downstream modules then generate references to fields that don't exist in the actual Odoo 17 base modules.

**Why it happens:**
Odoo's base modules are massive (account alone has 50+ models). Scanning them requires either a running Odoo instance (heavy) or static AST analysis of the source code (fragile — misses dynamic field additions via `_inherit`). The project plans on-demand scanning but the scanner (amil-utils) is a separate repo that may not be ready.

**How to avoid:**
1. Pre-build registry snapshots for common Odoo 17 base modules (base, account, hr, purchase, sale, stock, mail). These are static for a given Odoo version — scan once, ship as data files.
2. Version-tag all third-party registry entries with the Odoo version they were scanned from.
3. For OCA modules, require explicit field-list declarations in the module spec rather than relying on scanning — the spec author knows what fields they need.
4. Add a `registry verify-externals` command that checks all third-party references against the pre-built snapshots.

**Warning signs:**
- Registry entries for base models missing key fields (e.g., `account.move` without `state` field)
- Module specs reference fields that exist in Odoo 16 but were renamed/removed in Odoo 17
- Scanner produces different results on different runs for the same module

**Phase to address:**
Phase 1 (Foundation) for pre-built base module snapshots. Phase 2 for on-demand scanning of non-standard modules.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Storing full model definitions in a single JSON file | Simple reads, no database needed | File grows to 100KB+, slow reads, merge conflicts | MVP only — split by module within first milestone |
| Skipping AST validation after generation | Faster pipeline, no dependency on amil-utils | Spec-vs-reality drift accumulates silently | Never — at minimum validate model names and field names |
| Hardcoding Odoo 17 assumptions in registry schema | Simpler schema, no version abstraction | Cannot reuse for Odoo 18+ projects | Acceptable for this milestone, add version field for future |
| Using markdown regex parsing (inherited from Amil state.cjs) | Works, already built | Fragile — breaks on unexpected formatting, 194-line function for field extraction | Acceptable for STATE.md, but use JSON for all new state files |
| Sequential module generation without parallelism | Simpler pipeline, no race conditions | 20 modules at 5-10 min each = 2-3 hours per full generation run | Acceptable for first milestone per PROJECT.md constraint |

## Integration Gotchas

Common mistakes when connecting to external services/tools.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| amil belt via Task() | Passing the entire registry as a string argument, blowing the Task() context | Pass only tiered registry subset; use file references for large payloads |
| amil-utils AST scanner | Assuming scanner output matches registry schema directly | Build an adapter that normalizes scanner output to registry format |
| Claude Code Task() subagents | Assuming Task() inherits parent's file system state | Task() gets fresh 200K context — explicitly pass all needed file paths and content |
| Docker validation (via belt) | Assuming Docker is available and Odoo instance is running | Check Docker availability before belt invocation; provide clear error when unavailable |
| Amil upstream updates | Cherry-picking Amil commits directly into amil fork | Maintain a FORK_DIFF.md; evaluate each upstream change for compatibility before merging |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Reading full registry JSON on every command | Noticeable CLI lag | Lazy-load registry; cache parsed JSON in memory within a session | >50 models (~80KB JSON) |
| Injecting full security_scope.json into every agent | Token waste, attention dilution | Only inject scope rules relevant to current module's depends | >10 modules with security rules |
| Storing computation chains as a flat list | O(n) lookup for chain validation | Index by source model and target model | >50 computation chains |
| Re-scanning third-party modules on every generation | 5-10 second delay per module | Cache scans with version+hash key; invalidate only on explicit request | Any module depending on base Odoo modules |
| Full git diff in every workflow step (inherited from Amil) | Slow on large generated codebases | Scope git operations to current module's directory only | >10 generated modules in addons dir |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| AI generates `ir.rule` with `[(1,'=',1)]` (allow-all domain) | Complete bypass of multi-tenant isolation; any user sees all records | Coherence checker must flag trivially-true domains; require explicit scope filters |
| Missing `company_id` field on models in multi-company setup | Data leaks between companies; users see other companies' records | Registry schema should flag models requiring `company_id`; validate at generation time |
| Generated `ir.model.access` gives full CRUD to base user group | Privilege escalation — regular users can delete critical records | Security templates should default to read-only for base groups; write access requires explicit justification |
| Hardcoded superuser bypass in computed fields | Computed fields running as `sudo()` skip all access rules | Belt should never generate `sudo()` calls without explicit spec instruction; coherence checker flags them |

## UX Pitfalls

Common user experience mistakes for the CLI operator (developer using amil).

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress visibility during multi-module generation | Developer waits 2+ hours with no feedback | Show per-module status table with ETA; update after each module completes |
| Coherence errors reported as raw Python tracebacks | Developer must decode Odoo internals to understand the problem | Translate coherence failures to plain English: "Module B references model 'student' but Module A defines 'student_record'" |
| Failed module blocks entire tier with no suggested fix | Developer stuck; must manually debug and re-run | Suggest specific fixes: "Field 'enrollment_id' not found on 'uni.student'. Did you mean 'enrollment_ids'?" |
| Registry state invisible — no way to inspect what's registered | Developer can't verify if generation used correct registry context | Provide `amil registry show [module]` and `amil registry diff` commands |
| No dry-run mode for generation | Developer must commit to a full generation to see what would happen | Add `--dry-run` flag that shows spec + registry injection without invoking belt |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Fork rename:** Often missing internal agent role names in `core.cjs` model profile map — verify `grep -r "gsd-" bin/` returns zero matches
- [ ] **Registry CRUD:** Often missing rollback mechanism — verify `.bak` files are created on every write
- [ ] **Module generation:** Often missing post-generation registry reconciliation — verify registry matches actual generated code, not just spec
- [ ] **Coherence check:** Often missing Many2many inverse field validation — verify both sides of every M2M are registered
- [ ] **Security scope:** Often missing multi-company filters — verify every model with `company_id` has corresponding `ir.rule`
- [ ] **Status transitions:** Often missing error-state handling — verify a module can transition from "generated" back to "spec_approved" on failure
- [ ] **Belt invocation:** Often missing timeout handling — verify Task() has a timeout and the pipeline handles it gracefully
- [ ] **Third-party scanning:** Often missing `_inherit` resolution — verify inherited fields from parent models are included in scan results
- [ ] **Tier blocking:** Often missing manual override — verify developer can force-skip a failed module when appropriate
- [ ] **Progress command:** Often missing per-tier breakdown — verify `progress` shows tier-level completion, not just flat module count

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Fork rename incomplete | LOW | Run verification grep; fix remaining references; re-test all workflows |
| Registry JSON corrupted | LOW | Restore from `.bak` file; re-run last module's registry update |
| Cross-module incoherence detected after 10+ modules | HIGH | Identify divergence point; rollback registry to last coherent state; re-generate from that module forward |
| Belt contract mismatch discovered at integration | MEDIUM | Update `belt_adapter.js`; re-parse all existing belt outputs through new adapter; update registry |
| Security scope errors found in production | HIGH | Audit all `ir.rule` and `ir.model.access` records; regenerate security layer for affected modules; full regression test |
| State files inconsistent (some updated, some not) | MEDIUM | Use `.bak` files to identify last consistent state; replay operations from that point |
| Third-party model scan was wrong version | MEDIUM | Re-scan with correct Odoo version; diff against registry; regenerate affected modules |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Fork rename minefield | Phase 1 (Foundation) | Zero matches for `grep -r "get-shit-done\|gsd-tools\|gsd-planner\|gsd-executor"` in entire codebase |
| Registry JSON growth | Phase 1 (Foundation) | `registry stats` command shows size; tiered injection tested with synthetic 100-model registry |
| Cross-module incoherence | Phase 2 (Core Workflow) | Coherence check passes for 5+ interdependent test modules |
| Belt contract assumptions | Phase 1 (Foundation) + Phase 2 (Core Workflow) | Mock belt produces output that parses correctly; one real belt integration test passes |
| State file corruption | Phase 1 (Foundation) | Kill test: terminate mid-write, verify recovery from `.bak` |
| Security scope explosion | Phase 2 (Core Workflow) | Security templates cover all 5 scope levels; validator flags missing scopes |
| Third-party model staleness | Phase 1 (Foundation) | Pre-built snapshots for base, account, hr verified against Odoo 17.0 source |

## Sources

- [VS Code Fork Analysis — EclipseSource](https://eclipsesource.com/blogs/2024/12/17/is-it-a-good-idea-to-fork-vs-code/) — fork maintenance burden analysis
- [Cursor Fork Impact — DEV Community](https://dev.to/pullflow/forked-by-cursor-the-hidden-cost-of-vs-code-fragmentation-4p1) — real-world fork fragmentation costs
- [Context Window Management — Maxim](https://www.getmaxim.ai/articles/context-window-management-strategies-for-long-context-ai-agents-and-chatbots/) — context dumping anti-pattern, selective injection
- [Context Window Problem — Factory.ai](https://factory.ai/news/context-window-problem) — scaling agents beyond token limits
- [TOON vs JSON — jduncan.io](https://jduncan.io/blog/2025-11-11-toon-vs-json-agent-optimized-data/) — JSON token inefficiency (40% structural overhead)
- [JetBrains Research — Context Management](https://blog.jetbrains.com/research/2025/12/efficient-context-management/) — observation masking vs summarization
- [Odoo Forum — Module Dependencies](https://www.odoo.com/forum/help-1/when-is-it-required-to-add-a-module-as-a-dependency-to-another-module-125784) — when depends are required
- [Odoo Forum — Interdependency Problems](https://www.odoo.com/forum/help-1/interdependency-of-modules-and-valueerror-from-a-field-from-one-of-these-modules-163776) — circular dependency failures
- [Odoo Forum — Many2one Related Field v17 Bug](https://www.odoo.com/forum/help-1/v17-module-upgrade-fails-due-to-many2one-related-field-289123) — KeyError during module upgrades
- [Beyond Code Generation in Odoo — Oduist](https://oduist.com/blog/odoo-experience-2025-ai-summaries-2/305-beyond-code-generation-integrating-ai-into-odoo-s-development-lifecycle-lessons-learned-306) — version blindness, context vacuum, silent failure in AI-generated Odoo code
- [Google Developers — Multi-Agent Framework](https://developers.googleblog.com/architecting-efficient-context-aware-multi-agent-framework-for-production/) — state-based context isolation patterns
- Actual Amil codebase inspection: 96 files, 203 workflow path references, 721-line state.cjs, 169-line config.cjs

---
*Pitfalls research for: Odoo ERP module orchestration (amil fork)*
*Researched: 2026-03-05*
