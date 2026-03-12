---
phase: 3
slug: module-discussion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Node.js built-in test runner (node:test) |
| **Config file** | package.json `"scripts": { "test": "node --test tests/" }` |
| **Quick run command** | `node --test tests/discuss-module.test.cjs` |
| **Full suite command** | `npm test` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** `node --test tests/discuss-module.test.cjs tests/agent-frontmatter.test.cjs`
- **After every plan wave:** `npm test`
- **Before `/amil:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| DISC-01 | discuss-module command file exists and references workflow | unit | `node --test tests/discuss-module.test.cjs` | No - Wave 0 |
| DISC-02 | Module type detected from name with fallback | unit | `node --test tests/discuss-module.test.cjs` | No - Wave 0 |
| DISC-03 | Question templates loaded for all 10 types (9 + generic) | unit | `node --test tests/discuss-module.test.cjs` | No - Wave 0 |
| DISC-04 | Questioner agent file exists with correct frontmatter | unit | `node --test tests/agent-frontmatter.test.cjs` | Yes (extend) |
| DISC-05 | Q&A output written to correct CONTEXT.md path | integration | Manual - workflow test | N/A |
| AGNT-01 | Researcher agent enhanced with Odoo-specific instructions | unit | `node --test tests/agent-frontmatter.test.cjs` | Yes (extend) |

*Status: pending*

---

## Wave 0 Requirements

- [ ] `tests/discuss-module.test.cjs` — covers DISC-01 (command exists), DISC-02 (type detection), DISC-03 (template loading/schema)
- [ ] Extend `tests/agent-frontmatter.test.cjs` — add cases for new questioner agent and enhanced researcher agent

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Interactive Q&A session | DISC-05 | Depends on AskUserQuestion tool in Claude Code runtime | Run `/amil:discuss-module uni_fee` and verify questions asked and CONTEXT.md written |
| Adaptive question ordering | DISC-04 | Agent discretion during live session | Verify agent skips irrelevant questions based on config |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
