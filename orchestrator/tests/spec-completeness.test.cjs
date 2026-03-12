const assert = require('assert');
const { scoreModule, scoreAllModules, getDiscussionBatches, getDiscussionSummary } = require('../amil/bin/lib/spec-completeness.cjs');

// Test: well-specified module scores >= 70
{
  const mod = {
    name: 'uni_core',
    description: 'Core university management module with student records',
    depends: ['base', 'mail'],
    models: [
      {
        name: 'uni.student',
        fields: [
          { name: 'name', type: 'Char' },
          { name: 'student_id', type: 'Char' },
          { name: 'email', type: 'Char' },
        ],
      },
    ],
    security: { roles: ['manager', 'user'] },
    workflow: [{ model: 'uni.student', states: ['draft', 'active'] }],
  };
  const result = scoreModule(mod, []);
  assert.ok(result.score >= 70, `Well-specified module should score >= 70, got ${result.score}`);
  assert.ok(result.ready);
  assert.strictEqual(result.discussionDepth, 'none');
  console.log('PASS: well-specified module scores >= 70');
}

// Test: underspecified module scores < 40
{
  const mod = {
    name: 'uni_unknown',
    description: 'TBD',
    models: [],
  };
  const result = scoreModule(mod, []);
  assert.ok(result.score < 40, `Empty module should score < 40, got ${result.score}`);
  assert.ok(!result.ready);
  assert.strictEqual(result.discussionDepth, 'full');
  assert.ok(result.gaps.length > 0);
  console.log('PASS: underspecified module scores < 40');
}

// Test: brief discussion for mid-range score
{
  const mod = {
    name: 'uni_mid',
    description: 'Module with some detail but incomplete',
    models: [
      {
        name: 'uni.thing',
        fields: [
          { name: 'name', type: 'Char' },
          { name: 'desc', type: 'Text' },
          { name: 'ref', type: 'Char' },
        ],
      },
    ],
    security: { roles: ['user'] },
  };
  const result = scoreModule(mod, []);
  assert.ok(result.score >= 40 && result.score < 70, `Mid module should score 40-69, got ${result.score}`);
  assert.strictEqual(result.discussionDepth, 'brief');
  console.log('PASS: brief discussion for mid-range score');
}

// Test: scoreAllModules processes all modules
{
  const decomposition = {
    modules: [
      { name: 'mod_a', models: [], description: 'short' },
      { name: 'mod_b', description: 'A detailed description of module B functionality', depends: ['base'], models: [
        { name: 'b.model', fields: [{ name: 'x', type: 'Char' }, { name: 'y', type: 'Char' }, { name: 'z', type: 'Char' }] },
      ], security: { roles: ['admin'] }, workflow: [{ model: 'b.model', states: ['draft', 'done'] }] },
    ],
  };
  const scores = scoreAllModules(decomposition);
  assert.ok(scores['mod_a']);
  assert.ok(scores['mod_b']);
  assert.ok(scores['mod_b'].score > scores['mod_a'].score);
  console.log('PASS: scoreAllModules processes all modules');
}

// Test: getDiscussionSummary
{
  const scores = {
    a: { score: 20, ready: false, discussionDepth: 'full' },
    b: { score: 50, ready: false, discussionDepth: 'brief' },
    c: { score: 80, ready: true, discussionDepth: 'none' },
  };
  const summary = getDiscussionSummary(scores);
  assert.strictEqual(summary.total, 3);
  assert.strictEqual(summary.ready, 1);
  assert.strictEqual(summary.full, 1);
  assert.strictEqual(summary.brief, 1);
  console.log('PASS: getDiscussionSummary counts correctly');
}

// Test: getDiscussionBatches groups by tier
{
  const scores = {
    a: { score: 20, discussionDepth: 'full', gaps: ['no models'] },
    b: { score: 20, discussionDepth: 'full', gaps: ['no models'] },
    c: { score: 50, discussionDepth: 'brief', gaps: ['few fields'] },
  };
  const moduleData = {
    modules: [
      { name: 'a', tier: 'foundation' },
      { name: 'b', tier: 'foundation' },
      { name: 'c', tier: 'operations' },
    ],
  };
  const batches = getDiscussionBatches(scores, moduleData);
  assert.ok(batches.length > 0);
  // Full discussion batches should come first
  assert.strictEqual(batches[0].depth, 'full');
  console.log('PASS: getDiscussionBatches groups by tier');
}

console.log('\nAll spec-completeness tests passed!');
