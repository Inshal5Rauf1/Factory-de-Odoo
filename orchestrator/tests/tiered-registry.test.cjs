/**
 * Tiered Registry Injection Tests (REG-08)
 *
 * Tests that tieredRegistryInjection() returns three distinct detail levels:
 * - Direct depends: full model data (all fields with metadata)
 * - Transitive depends: field-list-only (model name + field names, no metadata)
 * - Everything else: names-only (model name and module)
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');

const { tieredRegistryInjection, readRegistryFile } = require('../amil/bin/lib/registry.cjs');

// ─── helpers ──────────────────────────────────────────────────────────────────

function createTempProject() {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'tiered-reg-test-'));
  fs.mkdirSync(path.join(tmpDir, '.planning'), { recursive: true });
  return tmpDir;
}

function cleanup(tmpDir) {
  fs.rmSync(tmpDir, { recursive: true, force: true });
}

function writeRegistry(tmpDir, registry) {
  fs.writeFileSync(
    path.join(tmpDir, '.planning', 'model_registry.json'),
    JSON.stringify(registry, null, 2),
    'utf-8'
  );
}

function writeModuleStatus(tmpDir, statusData) {
  fs.writeFileSync(
    path.join(tmpDir, '.planning', 'module_status.json'),
    JSON.stringify(statusData, null, 2),
    'utf-8'
  );
}

// ─── fixtures ─────────────────────────────────────────────────────────────────

function buildFixtures(tmpDir) {
  // Module dependency chain:
  // uni_enrollment depends on [uni_student]
  // uni_student depends on [uni_core]
  // uni_core depends on []
  // uni_fee depends on [uni_student]
  // uni_notification depends on []

  writeModuleStatus(tmpDir, {
    _meta: { version: 1, last_updated: '2026-01-01' },
    modules: {
      uni_core: { status: 'planned', tier: 'foundation', depends: [], updated: '2026-01-01' },
      uni_student: { status: 'planned', tier: 'core', depends: ['uni_core'], updated: '2026-01-01' },
      uni_enrollment: { status: 'planned', tier: 'operations', depends: ['uni_student'], updated: '2026-01-01' },
      uni_fee: { status: 'planned', tier: 'operations', depends: ['uni_student'], updated: '2026-01-01' },
      uni_notification: { status: 'planned', tier: 'communication', depends: [], updated: '2026-01-01' },
    },
    tiers: {},
  });

  writeRegistry(tmpDir, {
    _meta: { version: 1, last_updated: '2026-01-01', modules_contributing: ['uni_core', 'uni_student', 'uni_enrollment', 'uni_fee', 'uni_notification'], odoo_version: '17.0' },
    models: {
      'uni.core.setting': {
        name: 'uni.core.setting',
        module: 'uni_core',
        fields: {
          name: { type: 'Char', required: true },
          value: { type: 'Text', required: false },
        },
      },
      'uni.student': {
        name: 'uni.student',
        module: 'uni_student',
        fields: {
          name: { type: 'Char', required: true },
          student_id: { type: 'Char', required: true },
          setting_id: { type: 'Many2one', comodel_name: 'uni.core.setting', required: false },
        },
      },
      'uni.enrollment': {
        name: 'uni.enrollment',
        module: 'uni_enrollment',
        fields: {
          student_id: { type: 'Many2one', comodel_name: 'uni.student', required: true },
          date: { type: 'Date', required: true },
        },
      },
      'uni.fee': {
        name: 'uni.fee',
        module: 'uni_fee',
        fields: {
          amount: { type: 'Float', required: true },
          student_id: { type: 'Many2one', comodel_name: 'uni.student', required: true },
        },
      },
      'uni.notification': {
        name: 'uni.notification',
        module: 'uni_notification',
        fields: {
          message: { type: 'Text', required: true },
          channel: { type: 'Selection', required: true },
        },
      },
    },
  });
}

// ─── tests ────────────────────────────────────────────────────────────────────

describe('tieredRegistryInjection', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
    buildFixtures(tmpDir);
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('direct dep gets full model data (all fields with metadata)', () => {
    // uni_enrollment depends on [uni_student] (direct)
    // uni_student's model should have full field metadata
    const result = tieredRegistryInjection(tmpDir, 'uni_enrollment');
    const studentModel = result.models['uni.student'];

    assert.ok(studentModel, 'Direct dep model should be present');
    assert.strictEqual(studentModel.name, 'uni.student');
    assert.strictEqual(studentModel.module, 'uni_student');
    // Full metadata: type, required, comodel_name preserved
    assert.strictEqual(studentModel.fields.name.type, 'Char');
    assert.strictEqual(studentModel.fields.name.required, true);
    assert.strictEqual(studentModel.fields.student_id.type, 'Char');
    assert.strictEqual(studentModel.fields.setting_id.type, 'Many2one');
    assert.strictEqual(studentModel.fields.setting_id.comodel_name, 'uni.core.setting');
  });

  test('transitive dep (dep of dep) gets field-list-only (no field metadata)', () => {
    // uni_enrollment -> uni_student -> uni_core (transitive)
    // uni_core's model should have field names but no metadata
    const result = tieredRegistryInjection(tmpDir, 'uni_enrollment');
    const coreModel = result.models['uni.core.setting'];

    assert.ok(coreModel, 'Transitive dep model should be present');
    assert.strictEqual(coreModel.name, 'uni.core.setting');
    assert.strictEqual(coreModel.module, 'uni_core');
    // Field names present but no metadata (no type, no required, no comodel_name)
    assert.ok(coreModel.fields.name, 'Field name should exist');
    assert.ok(coreModel.fields.value, 'Field value should exist');
    assert.strictEqual(coreModel.fields.name.name, 'name');
    assert.strictEqual(coreModel.fields.name.type, undefined, 'No type metadata for transitive');
    assert.strictEqual(coreModel.fields.name.required, undefined, 'No required metadata for transitive');
  });

  test('unrelated module gets names-only (just model name and module)', () => {
    // uni_enrollment has no relation to uni_notification
    const result = tieredRegistryInjection(tmpDir, 'uni_enrollment');
    const notifModel = result.models['uni.notification'];

    assert.ok(notifModel, 'Unrelated model should be present');
    assert.strictEqual(notifModel.name, 'uni.notification');
    assert.strictEqual(notifModel.module, 'uni_notification');
    assert.strictEqual(notifModel.fields, undefined, 'Names-only should have no fields');
  });

  test('module with no depends returns empty models object', () => {
    // uni_core has no depends, so nothing is direct/transitive
    // All models become names-only, and the target module's own models are also names-only
    const result = tieredRegistryInjection(tmpDir, 'uni_core');
    assert.ok(result.models, 'Should have models object');

    // No direct deps, so all models should be names-only
    for (const [, model] of Object.entries(result.models)) {
      assert.strictEqual(model.fields, undefined,
        `Model ${model.name} should be names-only (no fields) since uni_core has no depends`);
    }
  });

  test('non-existent module name returns empty models object', () => {
    const result = tieredRegistryInjection(tmpDir, 'uni_nonexistent');
    assert.deepStrictEqual(result, { models: {} });
  });

  test('all transitive deps computed recursively (not just depth 2)', () => {
    // Create a deeper chain: A -> B -> C -> D
    // For module A: B is direct, C and D are transitive
    writeModuleStatus(tmpDir, {
      _meta: { version: 1, last_updated: '2026-01-01' },
      modules: {
        mod_d: { status: 'planned', tier: 'foundation', depends: [], updated: '2026-01-01' },
        mod_c: { status: 'planned', tier: 'core', depends: ['mod_d'], updated: '2026-01-01' },
        mod_b: { status: 'planned', tier: 'operations', depends: ['mod_c'], updated: '2026-01-01' },
        mod_a: { status: 'planned', tier: 'operations', depends: ['mod_b'], updated: '2026-01-01' },
      },
      tiers: {},
    });

    writeRegistry(tmpDir, {
      _meta: { version: 1, last_updated: '2026-01-01', modules_contributing: ['mod_a', 'mod_b', 'mod_c', 'mod_d'], odoo_version: '17.0' },
      models: {
        'model.b': { name: 'model.b', module: 'mod_b', fields: { x: { type: 'Char', required: true } } },
        'model.c': { name: 'model.c', module: 'mod_c', fields: { y: { type: 'Integer', required: false } } },
        'model.d': { name: 'model.d', module: 'mod_d', fields: { z: { type: 'Text', required: true } } },
      },
    });

    const result = tieredRegistryInjection(tmpDir, 'mod_a');

    // mod_b is direct dep -> full model
    assert.strictEqual(result.models['model.b'].fields.x.type, 'Char', 'Direct dep should have full metadata');

    // mod_c is transitive (dep of mod_b) -> field-list-only
    assert.ok(result.models['model.c'].fields.y, 'Transitive dep should have field name');
    assert.strictEqual(result.models['model.c'].fields.y.type, undefined, 'Transitive dep should NOT have type metadata');

    // mod_d is also transitive (dep of mod_c, depth 3) -> field-list-only
    assert.ok(result.models['model.d'].fields.z, 'Deep transitive dep should have field name');
    assert.strictEqual(result.models['model.d'].fields.z.type, undefined, 'Deep transitive dep should NOT have type metadata');
  });

  test('direct dep models include full field metadata (type, comodel_name, required)', () => {
    const result = tieredRegistryInjection(tmpDir, 'uni_enrollment');
    const studentModel = result.models['uni.student'];

    // Verify all metadata keys are preserved for direct deps
    const settingField = studentModel.fields.setting_id;
    assert.strictEqual(settingField.type, 'Many2one');
    assert.strictEqual(settingField.comodel_name, 'uni.core.setting');
    assert.strictEqual(settingField.required, false);
  });

  test('own module models appear as names-only (not included in any tier)', () => {
    // uni_enrollment's own model should appear as names-only
    const result = tieredRegistryInjection(tmpDir, 'uni_enrollment');
    const enrollModel = result.models['uni.enrollment'];

    assert.ok(enrollModel, 'Own module model should be present');
    assert.strictEqual(enrollModel.name, 'uni.enrollment');
    assert.strictEqual(enrollModel.module, 'uni_enrollment');
    assert.strictEqual(enrollModel.fields, undefined, 'Own module should be names-only');
  });

  test('sibling modules (same parent dep) are names-only when not in dep chain', () => {
    // For uni_enrollment: uni_fee depends on uni_student too, but is NOT a dep of uni_enrollment
    const result = tieredRegistryInjection(tmpDir, 'uni_enrollment');
    const feeModel = result.models['uni.fee'];

    assert.ok(feeModel, 'Sibling module model should be present');
    assert.strictEqual(feeModel.name, 'uni.fee');
    assert.strictEqual(feeModel.fields, undefined, 'Sibling should be names-only');
  });
});
