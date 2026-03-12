---
phase: 2
slug: prd-decomposition-and-erp-init
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node.js built-in test runner (node:test) |
| **Config file** | package.json `"scripts": { "test": "node --test tests/" }` |
| **Quick run command** | `node --test tests/tiered-registry.test.cjs` |
| **Full suite command** | `npm test` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** `node --test tests/tiered-registry.test.cjs tests/config.test.cjs`
- **After every plan wave:** `npm test`
- **Before `/amil:verify-work`:** Full suite must be green
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| CONF-03 | New odoo config keys validated and written | unit | `node --test tests/config.test.cjs` | Yes (extend) |
| REG-08 | Tiered injection returns correct model detail levels | unit | `node --test tests/tiered-registry.test.cjs` | No - Wave 0 |
| NWRP-01 | new-erp command file exists and references workflow | unit | `node --test tests/new-erp.test.cjs` | No - Wave 0 |
| NWRP-02 | Config questions collect all 7 answers | integration | Manual - workflow test | N/A |
| NWRP-03 | 4 parallel agents spawn and produce output files | integration | Manual - workflow test | N/A |
| NWRP-04 | Merge produces correct decomposition from 4 agent outputs | unit | `node --test tests/new-erp.test.cjs` | No - Wave 0 |
| NWRP-05 | Human presented with decomposition for approval | integration | Manual - workflow test | N/A |
| NWRP-06 | Generated ROADMAP.md parseable by roadmap.cjs | integration | `node --test tests/roadmap.test.cjs` | Yes (extend) |
| NWRP-07 | Agent files exist with correct frontmatter | unit | `node --test tests/agent-frontmatter.test.cjs` | Yes (extend) |

*Status: pending*

---

## Wave 0 Requirements

- [ ] `tests/tiered-registry.test.cjs` — covers REG-08 tiered injection (direct/transitive/rest filtering)
- [ ] `tests/new-erp.test.cjs` — covers merge logic, decomposition.json schema validation, ROADMAP.md generation
- [ ] Extend `tests/config.test.cjs` — add cases for odoo.multi_company, odoo.localization, odoo.canvas_integration, odoo.deployment_target validation

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Config questions interactive flow | NWRP-02 | Depends on AskUserQuestion tool in Claude Code runtime | Run `/amil:new-erp` and verify 7 questions asked in order |
| 4 parallel agent spawn | NWRP-03 | Depends on Task() subagent execution in Claude Code runtime | Run new-erp with a test PRD and verify 4 JSON output files created |
| Human approval checkpoint | NWRP-05 | Depends on interactive presentation in Claude Code | Verify decomposition table shown and approval prompt works |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 8s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
