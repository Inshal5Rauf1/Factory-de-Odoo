---
phase: 4
slug: spec-generation-and-coherence
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-05
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node.js built-in test runner (node:test) |
| **Config file** | package.json `"scripts": { "test": "node --test tests/" }` |
| **Quick run command** | `node --test tests/coherence.test.cjs` |
| **Full suite command** | `npm test` |
| **Estimated runtime** | ~12 seconds |

---

## Sampling Rate

- **After every task commit:** `node --test tests/coherence.test.cjs tests/plan-module.test.cjs`
- **After every plan wave:** `npm test`
- **Before `/amil:verify-work`:** Full suite must be green
- **Max feedback latency:** 12 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| SPEC-05 | Coherence checker CJS with 4 structural checks | unit | `node --test tests/coherence.test.cjs` | No - Wave 0 (Plan 01 Task 1) |
| SPEC-06 | Many2one, duplicates, computed depends, security groups validation | unit | `node --test tests/coherence.test.cjs` | No - Wave 0 (Plan 01 Task 1) |
| TEST-03 | Coherence tests covering Many2one, chains, spec diffing | unit | `node --test tests/coherence.test.cjs` | No - Wave 0 (Plan 01 Task 1) |
| SPEC-01 | plan-module command file exists and references workflow | unit | `node --test tests/plan-module.test.cjs` | No - Wave 0 (Plan 03 Task 2) |
| SPEC-03 | spec.json schema has all 12 sections + _available_models | unit | `node --test tests/plan-module.test.cjs` | No - Wave 0 (Plan 03 Task 2) |
| SPEC-04 | Tiered registry injected as _available_models | unit | `node --test tests/plan-module.test.cjs` | No - Wave 0 (Plan 03 Task 2) |
| SPEC-02 | Spec generator agent exists with correct frontmatter | unit | `node --test tests/agent-frontmatter.test.cjs` | Yes (extend) |
| AGNT-02 | Spec generator agent Odoo-specialized | unit | `node --test tests/agent-frontmatter.test.cjs` | Yes (extend) |
| AGNT-04 | Spec reviewer agent exists with correct frontmatter | unit | `node --test tests/agent-frontmatter.test.cjs` | Yes (extend) |
| SPEC-07 | Human presented with coherence report + spec summary | integration | Manual - workflow test | N/A |
| SPEC-08 | Module status transitions to spec_approved on approval | integration | Manual - workflow test | N/A |

*Status: pending*

---

## Wave 0 Requirements

- [ ] `tests/coherence.test.cjs` — covers SPEC-05, SPEC-06, TEST-03 (4 check types, violation detection, pass/fail reporting) — **Created by Plan 01 Task 1**
- [ ] `tests/plan-module.test.cjs` — covers SPEC-01, SPEC-03, SPEC-04 (command exists, spec schema validation, registry injection) — **Created by Plan 03 Task 2**
- [ ] Extend `tests/agent-frontmatter.test.cjs` — add cases for spec-generator and spec-reviewer agents — **Extended by Plan 02 Task 2**

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Human approval flow | SPEC-07, SPEC-08 | Depends on AskUserQuestion + module_status transition in runtime | Run `/amil:plan-module uni_core` with test data and verify coherence report shown, approval works |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 12s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
