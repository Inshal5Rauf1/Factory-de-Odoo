const assert = require('assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const provRegistry = require('../amil/bin/lib/provisional-registry.cjs');
const circularBreaker = require('../amil/bin/lib/circular-dep-breaker.cjs');

function makeTmpDir() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'prov-reg-test-'));
  fs.mkdirSync(path.join(tmp, '.planning'), { recursive: true });
  return tmp;
}

function cleanup(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
}

const sampleDecomposition = {
  modules: [
    {
      name: 'uni_core',
      depends: [],
      models: [
        {
          name: 'uni.student',
          fields: [
            { name: 'name', type: 'Char' },
            { name: 'student_id', type: 'Char' },
            { name: 'department_id', type: 'Many2one', comodel_name: 'uni.department' },
          ],
        },
      ],
    },
    {
      name: 'uni_department',
      depends: ['uni_core'],
      models: [
        {
          name: 'uni.department',
          fields: [
            { name: 'name', type: 'Char' },
            { name: 'head_id', type: 'Many2one', comodel_name: 'res.partner' },
          ],
        },
      ],
    },
    {
      name: 'uni_hr',
      depends: ['uni_core'],
      models: [
        {
          name: 'uni.employee',
          fields: [
            { name: 'name', type: 'Char' },
            { name: 'payslip_ids', type: 'One2many', comodel_name: 'uni.payslip' },
          ],
        },
      ],
    },
    {
      name: 'uni_payroll',
      depends: ['uni_hr'],
      models: [
        {
          name: 'uni.payslip',
          fields: [
            { name: 'name', type: 'Char' },
            { name: 'employee_id', type: 'Many2one', comodel_name: 'uni.employee' },
          ],
        },
      ],
    },
  ],
};

// Test: buildFromDecomposition creates registry
{
  const reg = provRegistry.buildFromDecomposition(sampleDecomposition);
  assert.strictEqual(reg.version, 1);
  assert.ok(reg.modules['uni_core']);
  assert.strictEqual(reg.modules['uni_core'].status, 'provisional');
  assert.ok(reg.models['uni.student']);
  assert.strictEqual(reg.models['uni.student'].module, 'uni_core');
  assert.strictEqual(reg.models['uni.student'].confidence, 'high'); // >2 fields
  assert.ok(reg.references.length > 0);
  console.log('PASS: buildFromDecomposition creates registry');
}

// Test: updateFromSpec overwrites with spec data
{
  const reg = provRegistry.buildFromDecomposition(sampleDecomposition);
  const spec = {
    module_name: 'uni_core',
    depends: ['base'],
    models: [
      {
        name: 'uni.student',
        fields: [
          { name: 'name', type: 'Char' },
          { name: 'student_id', type: 'Char' },
          { name: 'email', type: 'Char' },
          { name: 'department_id', type: 'Many2one', comodel_name: 'uni.department' },
        ],
      },
    ],
  };
  const updated = provRegistry.updateFromSpec(reg, spec);
  assert.strictEqual(updated.modules['uni_core'].status, 'spec_approved');
  assert.strictEqual(updated.models['uni.student'].source, 'spec');
  assert.strictEqual(updated.models['uni.student'].confidence, 'high');
  assert.strictEqual(updated.models['uni.student'].fields.length, 4);
  // Original should be unchanged (immutable)
  assert.strictEqual(reg.modules['uni_core'].status, 'provisional');
  console.log('PASS: updateFromSpec overwrites with spec data');
}

// Test: markBuilt transitions module
{
  const reg = provRegistry.buildFromDecomposition(sampleDecomposition);
  const updated = provRegistry.markBuilt(reg, 'uni_core');
  assert.strictEqual(updated.modules['uni_core'].status, 'built');
  assert.strictEqual(updated.models['uni.student'].source, 'built');
  // Other modules unchanged
  assert.strictEqual(updated.modules['uni_department'].status, 'provisional');
  console.log('PASS: markBuilt transitions module');
}

// Test: resolveReference checks real → provisional → not found
{
  const reg = provRegistry.buildFromDecomposition(sampleDecomposition);

  // Standard model → always found
  const resPartner = provRegistry.resolveReference('res.partner', null, reg);
  assert.ok(resPartner.found);
  assert.strictEqual(resPartner.source, 'odoo_base');

  // Provisional model → found in provisional
  const uniStudent = provRegistry.resolveReference('uni.student', null, reg);
  assert.ok(uniStudent.found);
  assert.strictEqual(uniStudent.source, 'decomposition');

  // Real registry model → found in real
  const realReg = { models: { 'custom.model': { module: 'custom_mod' } } };
  const customModel = provRegistry.resolveReference('custom.model', realReg, reg);
  assert.ok(customModel.found);
  assert.strictEqual(customModel.source, 'built');

  // Unknown model → not found
  const unknown = provRegistry.resolveReference('nonexistent.model', null, reg);
  assert.ok(!unknown.found);

  console.log('PASS: resolveReference checks real → provisional → not found');
}

// Test: analyzeForwardReferences detects forward refs and circular risks
{
  const reg = provRegistry.buildFromDecomposition(sampleDecomposition);
  const analysis = provRegistry.analyzeForwardReferences(reg);

  // uni_core → uni.department (forward ref to uni_department module)
  assert.ok(analysis.forwardRefs.length > 0, 'Should detect forward refs');

  // uni_hr → uni_payroll and uni_payroll → uni_hr (circular)
  assert.ok(analysis.circularRisks.length > 0, 'Should detect circular risks');
  const circPair = analysis.circularRisks[0];
  assert.ok(circPair.modules.includes('uni_hr'));
  assert.ok(circPair.modules.includes('uni_payroll'));

  console.log('PASS: analyzeForwardReferences detects forward refs and circular risks');
}

// Test: findCriticalChains finds chains
{
  const decomposition = {
    modules: [
      { name: 'a', depends: [], models: [] },
      { name: 'b', depends: ['a'], models: [] },
      { name: 'c', depends: ['b'], models: [] },
      { name: 'd', depends: ['c'], models: [] },
      { name: 'e', depends: ['d'], models: [] },
    ],
  };
  const reg = provRegistry.buildFromDecomposition(decomposition);
  const chains = provRegistry.findCriticalChains(reg);
  assert.ok(chains.length > 0, 'Should find at least one chain');
  assert.ok(chains[0].length >= 4, 'Chain should be 4+ modules');
  console.log('PASS: findCriticalChains finds chains of 4+');
}

// Test: save and load
{
  const tmp = makeTmpDir();
  try {
    const reg = provRegistry.buildFromDecomposition(sampleDecomposition);
    provRegistry.save(tmp, reg);
    const loaded = provRegistry.load(tmp);
    assert.deepStrictEqual(loaded.modules, reg.modules);
    assert.deepStrictEqual(loaded.models, reg.models);
    console.log('PASS: save and load round-trips correctly');
  } finally {
    cleanup(tmp);
  }
}

// --- Circular Dep Breaker Tests ---

// Test: analyzeCircularPair identifies primary/secondary
{
  const reg = provRegistry.buildFromDecomposition(sampleDecomposition);
  const analysis = provRegistry.analyzeForwardReferences(reg);
  if (analysis.circularRisks.length > 0) {
    const result = circularBreaker.analyzeCircularPair(analysis.circularRisks[0], reg);
    assert.ok(result.primary, 'Should identify primary module');
    assert.ok(result.secondary, 'Should identify secondary module');
    assert.strictEqual(result.buildOrder.length, 2, 'Build order should have 2 entries');
    assert.strictEqual(result.buildOrder[0], result.primary, 'Primary should be first');
    console.log('PASS: analyzeCircularPair identifies primary/secondary');
  } else {
    console.log('SKIP: no circular risks to test analyzeCircularPair');
  }
}

// Test: planBuildOrder with no circular risks
{
  const topoOrder = ['a', 'b', 'c', 'd'];
  const result = circularBreaker.planBuildOrder(topoOrder, [], null);
  assert.deepStrictEqual(result.order, topoOrder);
  assert.strictEqual(result.patchRounds.length, 0);
  console.log('PASS: planBuildOrder with no circular risks');
}

// Test: planBuildOrder adjusts for circular deps
{
  const circularRisk = {
    pair: 'modA:modB',
    modules: ['modA', 'modB'],
    refs_a_to_b: [
      { from_module: 'modA', to_module: 'modB', from_model: 'a.model', to_model: 'b.model', field: 'b_id', type: 'Many2one' },
    ],
    refs_b_to_a: [
      { from_module: 'modB', to_module: 'modA', from_model: 'b.model', to_model: 'a.model', field: 'a_ids', type: 'One2many' },
    ],
  };
  const topoOrder = ['modB', 'modA', 'modC'];
  const result = circularBreaker.planBuildOrder(topoOrder, [circularRisk], null);
  // modA has more M2O → primary → should come first
  const idxA = result.order.indexOf('modA');
  const idxB = result.order.indexOf('modB');
  assert.ok(idxA < idxB, 'Primary (modA) should come before secondary (modB)');
  assert.ok(result.patchRounds.length > 0, 'Should have patch rounds');
  console.log('PASS: planBuildOrder adjusts for circular deps');
}

// Test: generatePatchSpec
{
  const resolution = {
    primary: 'modA',
    secondary: 'modB',
    buildOrder: ['modA', 'modB'],
    deferredRefs: [
      { from_module: 'modB', to_module: 'modA', from_model: 'b.model', to_model: 'a.model', field: 'a_ids', type: 'One2many' },
    ],
    patchRequired: true,
  };
  const patch = circularBreaker.generatePatchSpec(resolution);
  assert.ok(patch, 'Should produce patch spec');
  assert.strictEqual(patch.module, 'modA');
  assert.strictEqual(patch.patches.length, 1);
  assert.strictEqual(patch.patches[0].field.name, 'a_ids');
  console.log('PASS: generatePatchSpec produces valid field additions');
}

console.log('\nAll provisional-registry and circular-dep-breaker tests passed!');
