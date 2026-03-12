const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const {
  LOG_FILENAME,
  getLogPath,
  initLog,
  appendEntry,
  appendBlockedModule,
  appendCoherenceEvent,
  updateCompactSummary,
  finalizeLog,
} = require('../amil/bin/lib/cycle-log.cjs');

function makeTmpDir() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'cycle-log-test-'));
  fs.mkdirSync(path.join(tmp, '.planning'), { recursive: true });
  return tmp;
}

function cleanup(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
}

// Test: initLog creates file with correct header
{
  const tmp = makeTmpDir();
  try {
    const logPath = initLog(tmp, 'Test ERP');
    assert.ok(fs.existsSync(logPath), 'Log file should exist');
    const content = fs.readFileSync(logPath, 'utf8');
    assert.ok(content.includes('# ERP Cycle Log: Test ERP'), 'Should contain project name');
    assert.ok(content.includes('COMPACT-SUMMARY-START'), 'Should contain compact summary start');
    assert.ok(content.includes('COMPACT-SUMMARY-END'), 'Should contain compact summary end');
    assert.ok(content.includes('**Last Iteration:** 0'), 'Should show iteration 0');
    assert.ok(content.includes('## Iterations'), 'Should have iterations section');
    console.log('PASS: initLog creates file with correct header');
  } finally {
    cleanup(tmp);
  }
}

// Test: appendEntry appends formatted markdown
{
  const tmp = makeTmpDir();
  try {
    initLog(tmp, 'Test ERP');
    appendEntry(tmp, {
      iteration: 1,
      module: 'uni_core',
      action: 'generate-module',
      result: 'success',
      wave: 1,
      stats: { shipped: 1, total: 90, in_progress: 0, remaining: 89 },
      next_action: 'verify-work for uni_core',
    });
    const content = fs.readFileSync(getLogPath(tmp), 'utf8');
    assert.ok(content.includes('### Iteration 1'), 'Should contain iteration header');
    assert.ok(content.includes('**Module:** uni_core'), 'Should contain module name');
    assert.ok(content.includes('**Action:** generate-module'), 'Should contain action');
    assert.ok(content.includes('**Result:** success'), 'Should contain result');
    assert.ok(content.includes('**Wave:** 1'), 'Should contain wave');
    assert.ok(content.includes('1/90 shipped'), 'Should contain progress');
    console.log('PASS: appendEntry appends formatted markdown');
  } finally {
    cleanup(tmp);
  }
}

// Test: appendEntry updates compact summary
{
  const tmp = makeTmpDir();
  try {
    initLog(tmp, 'Test ERP');
    appendEntry(tmp, {
      iteration: 5,
      module: 'uni_fee',
      action: 'generate-module',
      result: 'success',
      wave: 2,
      stats: { shipped: 5, total: 90, in_progress: 1, blocked: 0 },
      next_action: 'verify-work for uni_fee',
    });
    const content = fs.readFileSync(getLogPath(tmp), 'utf8');
    assert.ok(content.includes('**Last Iteration:** 5'), 'Summary should show iteration 5');
    assert.ok(content.includes('**Shipped:** 5/90'), 'Summary should show 5/90');
    assert.ok(content.includes('**Current Wave:** 2'), 'Summary should show wave 2');
    console.log('PASS: appendEntry updates compact summary');
  } finally {
    cleanup(tmp);
  }
}

// Test: updateCompactSummary replaces without corrupting body
{
  const tmp = makeTmpDir();
  try {
    initLog(tmp, 'Test ERP');
    appendEntry(tmp, {
      iteration: 1, module: 'mod1', action: 'gen', result: 'ok',
      stats: { shipped: 1, total: 10 }, next_action: 'verify',
    });
    updateCompactSummary(tmp, {
      iteration: 99, shipped: 50, total: 100,
      in_progress: 2, blocked: 1, next_action: 'finalize',
      wave: 6, coherence_warnings: 3,
    });
    const content = fs.readFileSync(getLogPath(tmp), 'utf8');
    assert.ok(content.includes('**Last Iteration:** 99'), 'Should update to 99');
    assert.ok(content.includes('### Iteration 1'), 'Should preserve iteration entry');
    assert.ok(content.includes('**Coherence Warnings:** 3'), 'Should include coherence warnings');
    // Ensure only one compact summary block exists
    const matches = content.match(/COMPACT-SUMMARY-START/g);
    assert.strictEqual(matches.length, 1, 'Should have exactly one summary block');
    console.log('PASS: updateCompactSummary replaces without corrupting body');
  } finally {
    cleanup(tmp);
  }
}

// Test: appendBlockedModule adds blockquote
{
  const tmp = makeTmpDir();
  try {
    initLog(tmp, 'Test ERP');
    appendBlockedModule(tmp, 'uni_broken', 'Docker install failed: missing depends');
    const content = fs.readFileSync(getLogPath(tmp), 'utf8');
    assert.ok(content.includes('**BLOCKED:** `uni_broken`'), 'Should contain blocked module');
    assert.ok(content.includes('Docker install failed'), 'Should contain reason');
    console.log('PASS: appendBlockedModule adds blockquote');
  } finally {
    cleanup(tmp);
  }
}

// Test: appendCoherenceEvent logs coherence warnings
{
  const tmp = makeTmpDir();
  try {
    initLog(tmp, 'Test ERP');
    appendCoherenceEvent(tmp, {
      type: 'forward_ref',
      source_module: 'uni_hr',
      target_module: 'uni_payroll',
      details: 'Many2one to hr.payroll.slip not yet built',
      resolution: 'Deferred to provisional registry',
    });
    const content = fs.readFileSync(getLogPath(tmp), 'utf8');
    assert.ok(content.includes('COHERENCE [forward_ref]'), 'Should contain coherence type');
    assert.ok(content.includes('`uni_hr` → `uni_payroll`'), 'Should contain module pair');
    assert.ok(content.includes('Resolution'), 'Should contain resolution');
    console.log('PASS: appendCoherenceEvent logs coherence warnings');
  } finally {
    cleanup(tmp);
  }
}

// Test: finalizeLog adds summary footer
{
  const tmp = makeTmpDir();
  try {
    initLog(tmp, 'Test ERP');
    finalizeLog(tmp, {
      total: 90,
      shipped: 85,
      blocked: 5,
      iterations: 307,
      errors: 12,
      coherence_warnings: 3,
      context_resets: 8,
      shipped_list: ['mod_a', 'mod_b'],
      blocked_list: [{ name: 'mod_x', reason: 'circular dep' }],
    });
    const content = fs.readFileSync(getLogPath(tmp), 'utf8');
    assert.ok(content.includes('## Cycle Complete'), 'Should have completion header');
    assert.ok(content.includes('**Total Modules:** 90'), 'Should show total');
    assert.ok(content.includes('**Shipped:** 85'), 'Should show shipped');
    assert.ok(content.includes('**Coherence Warnings:** 3'), 'Should show coherence warnings');
    assert.ok(content.includes('**Context Resets:** 8'), 'Should show context resets');
    assert.ok(content.includes('- mod_a'), 'Should list shipped modules');
    assert.ok(content.includes('mod_x: circular dep'), 'Should list blocked with reasons');
    console.log('PASS: finalizeLog adds summary footer');
  } finally {
    cleanup(tmp);
  }
}

// Test: Multiple entries accumulate correctly
{
  const tmp = makeTmpDir();
  try {
    initLog(tmp, 'Test ERP');
    for (let i = 1; i <= 5; i++) {
      appendEntry(tmp, {
        iteration: i, module: `mod_${i}`, action: 'gen', result: 'ok',
        stats: { shipped: i, total: 10, in_progress: 0, remaining: 10 - i },
        next_action: 'continue',
      });
    }
    const content = fs.readFileSync(getLogPath(tmp), 'utf8');
    for (let i = 1; i <= 5; i++) {
      assert.ok(content.includes(`### Iteration ${i}`), `Should contain iteration ${i}`);
      assert.ok(content.includes(`mod_${i}`), `Should contain mod_${i}`);
    }
    assert.ok(content.includes('**Last Iteration:** 5'), 'Summary should reflect latest');
    assert.ok(content.includes('**Shipped:** 5/10'), 'Summary should show 5/10');
    console.log('PASS: Multiple entries accumulate correctly');
  } finally {
    cleanup(tmp);
  }
}

console.log('\nAll cycle-log tests passed!');
