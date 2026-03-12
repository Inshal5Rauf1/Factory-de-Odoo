---
phase: 1
slug: fork-foundation-and-state-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node.js built-in test runner (v25.5.0) |
| **Config file** | `scripts/run-tests.cjs` (custom test runner that globs `tests/*.test.cjs`) |
| **Quick run command** | `node --test tests/{changed-module}.test.cjs` |
| **Full suite command** | `npm test` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `node --test tests/{changed-module}.test.cjs`
- **After every plan wave:** Run `npm test`
- **Before `/amil:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| REG-01 | Registry CRUD (read, read-model, update, validate, stats) | unit+integration | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-02 | Atomic writes (tmp + rename) | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-03 | Registry versioning (_meta.version increment) | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-04 | Registry rollback from .bak | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-05 | Validation (Many2one targets, duplicates, required fields) | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-06 | Stats (model count, field count, cross-refs) | unit | `node --test tests/registry.test.cjs` | No - Wave 0 |
| REG-07 | CLI subcommand dispatch | integration | `node --test tests/registry.test.cjs` | No - Wave 0 |
| STAT-01 | module_status.json creation | unit | `node --test tests/module-status.test.cjs` | No - Wave 0 |
| STAT-02 | Status transitions enforced | unit | `node --test tests/module-status.test.cjs` | No - Wave 0 |
| STAT-03 | Tier status computation | unit | `node --test tests/module-status.test.cjs` | No - Wave 0 |
| STAT-04 | Per-module artifact directory creation | unit | `node --test tests/module-status.test.cjs` | No - Wave 0 |
| DEPG-01 | Dependency graph construction | unit | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| DEPG-02 | Topological sort | unit | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| DEPG-03 | Circular dependency detection | unit | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| DEPG-04 | Tier grouping | unit | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| DEPG-05 | Generation blocking on dependency status | integration | `node --test tests/dependency-graph.test.cjs` | No - Wave 0 |
| FORK-10 | Zero remaining old references | smoke | `grep -r "get-shit-done\|/amil:" --include="*.cjs" --include="*.md" --include="*.js" \| grep -v node_modules` | No - Wave 0 |
| CONF-01 | Odoo config block schema | unit | `node --test tests/config.test.cjs` | Yes (extend) |
| CONF-02 | Odoo config validation | unit | `node --test tests/config.test.cjs` | Yes (extend) |
| TEST-05 | Existing tests pass with renamed prefix | smoke | `npm test` | Yes (update) |

*Status: pending*

---

## Wave 0 Requirements

- [ ] `tests/registry.test.cjs` — covers REG-01 through REG-07
- [ ] `tests/module-status.test.cjs` — covers STAT-01 through STAT-04
- [ ] `tests/dependency-graph.test.cjs` — covers DEPG-01 through DEPG-05
- [ ] Update `tests/helpers.cjs` — TOOLS_PATH must point to renamed `amil/bin/amil-tools.cjs`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fork rename completeness | FORK-01..FORK-09 | Involves file renames across 98 files; verified by FORK-10 grep | Run FORK-10 verification script; visually confirm command routing |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
