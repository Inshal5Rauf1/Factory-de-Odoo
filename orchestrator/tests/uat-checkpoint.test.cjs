const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const {
  isCheckpointDue,
  generateChecklist,
  recordResult,
  getUATSummary,
} = require('../amil/bin/lib/uat-checkpoint.cjs');

function makeTmpDir() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'uat-test-'));
  fs.mkdirSync(path.join(tmp, '.planning', 'modules'), { recursive: true });
  return tmp;
}

function cleanup(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
}

// Test: isCheckpointDue
{
  assert.ok(isCheckpointDue(['a','b','c','d','e','f','g','h','i','j'], 0, 10));
  assert.ok(!isCheckpointDue(['a','b','c'], 0, 10));
  assert.ok(isCheckpointDue(['a','b','c','d','e','f','g','h','i','j','k','l'], 2, 10));
  console.log('PASS: isCheckpointDue returns correct boolean');
}

// Test: generateChecklist produces per-module flows
{
  const modules = [
    {
      name: 'uni_exam',
      module_name: 'uni_exam',
      models: [
        {
          name: 'uni.exam',
          fields: [
            { name: 'name', type: 'Char' },
            { name: 'total_score', type: 'Float', compute: '_compute_total' },
          ],
        },
      ],
      workflow: [{ model: 'uni.exam', states: ['draft', 'scheduled', 'done'] }],
      reports: [{ name: 'Exam Report' }],
    },
  ];
  const checklist = generateChecklist(modules, {});
  assert.strictEqual(checklist.perModule.length, 1);
  assert.ok(checklist.perModule[0].flows.length >= 1);
  console.log('PASS: generateChecklist produces per-module flows');
}

// Test: generateChecklist detects cross-module flows
{
  const modules = [
    {
      name: 'mod_a',
      module_name: 'mod_a',
      models: [
        {
          name: 'a.model',
          fields: [{ name: 'b_id', type: 'Many2one', comodel_name: 'b.model' }],
        },
      ],
    },
    {
      name: 'mod_b',
      module_name: 'mod_b',
      models: [
        { name: 'b.model', fields: [{ name: 'name', type: 'Char' }] },
      ],
    },
  ];
  const checklist = generateChecklist(modules, {});
  assert.ok(checklist.crossModule.length > 0, 'Should detect cross-module flow');
  console.log('PASS: generateChecklist detects cross-module flows');
}

// Test: recordResult writes files
{
  const tmp = makeTmpDir();
  try {
    const data = recordResult(tmp, 'uni_test', 'pass', null);
    assert.strictEqual(data.result, 'pass');
    const resultFile = path.join(tmp, '.planning', 'modules', 'uni_test', 'uat-result.json');
    assert.ok(fs.existsSync(resultFile));
    console.log('PASS: recordResult writes pass result');
  } finally {
    cleanup(tmp);
  }
}

// Test: recordResult creates feedback file for failures
{
  const tmp = makeTmpDir();
  try {
    recordResult(tmp, 'uni_broken', 'fail', 'Button does not trigger workflow transition');
    const feedbackFile = path.join(tmp, '.planning', 'modules', 'uni_broken', 'uat-feedback.md');
    assert.ok(fs.existsSync(feedbackFile), 'Feedback file should exist for fail');
    const content = fs.readFileSync(feedbackFile, 'utf8');
    assert.ok(content.includes('Button does not trigger'));
    console.log('PASS: recordResult creates feedback file for failures');
  } finally {
    cleanup(tmp);
  }
}

// Test: getUATSummary aggregates results
{
  const tmp = makeTmpDir();
  try {
    recordResult(tmp, 'mod_a', 'pass', null);
    recordResult(tmp, 'mod_b', 'fail', 'broken');
    recordResult(tmp, 'mod_c', 'minor', 'cosmetic issue');
    const summary = getUATSummary(tmp, ['mod_a', 'mod_b', 'mod_c', 'mod_d']);
    assert.strictEqual(summary.summary.pass, 1);
    assert.strictEqual(summary.summary.fail, 1);
    assert.strictEqual(summary.summary.minor, 1);
    assert.strictEqual(summary.summary.untested, 1);
    console.log('PASS: getUATSummary aggregates results correctly');
  } finally {
    cleanup(tmp);
  }
}

console.log('\nAll uat-checkpoint tests passed!');
