/**
 * Amil Tools Tests - registry.cjs
 *
 * CLI integration tests for registry subcommands: read, read-model, update,
 * rollback, validate, stats.
 *
 * Requirements: REG-01 through REG-07, TEST-01
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { createTempProject, cleanup } = require('./helpers.cjs');

// Direct-require the registry module for unit tests
const registryPath = path.join(__dirname, '..', 'amil', 'bin', 'lib', 'registry.cjs');

// ─── helpers ──────────────────────────────────────────────────────────────────

function registryFilePath(tmpDir) {
  return path.join(tmpDir, '.planning', 'model_registry.json');
}

function bakFilePath(tmpDir) {
  return path.join(tmpDir, '.planning', 'model_registry.json.bak');
}

function writeRegistry(tmpDir, data) {
  fs.writeFileSync(registryFilePath(tmpDir), JSON.stringify(data, null, 2), 'utf-8');
}

function readRegistry(tmpDir) {
  return JSON.parse(fs.readFileSync(registryFilePath(tmpDir), 'utf-8'));
}

function writeManifest(tmpDir, name, data) {
  const manifestPath = path.join(tmpDir, name);
  fs.writeFileSync(manifestPath, JSON.stringify(data, null, 2), 'utf-8');
  return manifestPath;
}

/**
 * Build a sample populated registry for testing.
 */
function sampleRegistry() {
  return {
    _meta: {
      version: 3,
      last_updated: '2026-03-05T10:00:00Z',
      modules_contributing: ['university_core'],
      odoo_version: '17.0',
    },
    models: {
      'university.student': {
        name: 'university.student',
        module: 'university_core',
        description: 'Student record',
        fields: {
          name: { type: 'Char', string: 'Name', required: true },
          partner_id: { type: 'Many2one', string: 'Partner', comodel_name: 'res.partner' },
          course_ids: { type: 'Many2many', string: 'Courses', comodel_name: 'university.course' },
        },
        _inherit: [],
      },
      'university.course': {
        name: 'university.course',
        module: 'university_core',
        description: 'Course offering',
        fields: {
          name: { type: 'Char', string: 'Name', required: true },
          student_ids: {
            type: 'One2many',
            string: 'Students',
            comodel_name: 'university.student',
            inverse_name: 'course_id',
          },
        },
        _inherit: [],
      },
    },
  };
}

// ─── Registry Read Tests (REG-01) ──────────────────────────────────────────

describe('registry read', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('returns empty registry when no file exists', () => {
    const registry = require(registryPath);
    // Call internal readRegistry (not CLI) to avoid process.exit
    const result = registry.readRegistryFile(tmpDir);
    assert.deepStrictEqual(result.models, {});
    assert.strictEqual(result._meta.version, 0);
    assert.strictEqual(result._meta.last_updated, null);
  });

  test('returns populated data when model_registry.json exists', () => {
    const sample = sampleRegistry();
    writeRegistry(tmpDir, sample);

    const registry = require(registryPath);
    const result = registry.readRegistryFile(tmpDir);
    assert.strictEqual(result._meta.version, 3);
    assert.ok(result.models['university.student']);
    assert.strictEqual(result.models['university.student'].fields.name.type, 'Char');
  });

  test('recovers from .bak when main file is corrupted', () => {
    const sample = sampleRegistry();
    // Write valid backup
    fs.writeFileSync(bakFilePath(tmpDir), JSON.stringify(sample, null, 2), 'utf-8');
    // Write corrupted main file
    fs.writeFileSync(registryFilePath(tmpDir), '{invalid json!!!', 'utf-8');

    const registry = require(registryPath);
    const result = registry.readRegistryFile(tmpDir);
    assert.strictEqual(result._meta.version, 3);
    assert.ok(result.models['university.student']);
  });
});

// ─── Registry Read Model Tests (REG-02) ─────────────────────────────────────

describe('registry read-model', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
    writeRegistry(tmpDir, sampleRegistry());
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('returns single model object by name', () => {
    const registry = require(registryPath);
    const result = registry.readModelFromRegistry(tmpDir, 'university.student');
    assert.strictEqual(result.name, 'university.student');
    assert.strictEqual(result.module, 'university_core');
    assert.ok(result.fields.name);
  });

  test('returns error for nonexistent model', () => {
    const registry = require(registryPath);
    const result = registry.readModelFromRegistry(tmpDir, 'nonexistent.model');
    assert.strictEqual(result, null);
  });
});

// ─── Registry Update Tests (REG-03) ─────────────────────────────────────────

describe('registry update', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('increments _meta.version, updates last_updated, adds to modules_contributing', () => {
    writeRegistry(tmpDir, {
      _meta: { version: 1, last_updated: null, modules_contributing: [], odoo_version: '17.0' },
      models: {},
    });

    const manifest = writeManifest(tmpDir, 'manifest.json', {
      module: 'university_core',
      models: {
        'university.student': {
          name: 'university.student',
          module: 'university_core',
          description: 'Student',
          fields: { name: { type: 'Char', string: 'Name', required: true } },
          _inherit: [],
        },
      },
    });

    const registry = require(registryPath);
    const result = registry.updateRegistry(tmpDir, manifest);
    assert.strictEqual(result._meta.version, 2);
    assert.ok(result._meta.last_updated);
    assert.ok(result._meta.modules_contributing.includes('university_core'));
    assert.ok(result.models['university.student']);
  });

  test('creates .bak backup before writing', () => {
    const existing = {
      _meta: { version: 1, last_updated: null, modules_contributing: [], odoo_version: '17.0' },
      models: {},
    };
    writeRegistry(tmpDir, existing);

    const manifest = writeManifest(tmpDir, 'manifest.json', {
      module: 'test_mod',
      models: {},
    });

    const registry = require(registryPath);
    registry.updateRegistry(tmpDir, manifest);

    assert.ok(fs.existsSync(bakFilePath(tmpDir)), '.bak file should exist');
    const bak = JSON.parse(fs.readFileSync(bakFilePath(tmpDir), 'utf-8'));
    assert.strictEqual(bak._meta.version, 1);
  });

  test('uses atomic write (tmp + rename pattern)', () => {
    writeRegistry(tmpDir, {
      _meta: { version: 0, last_updated: null, modules_contributing: [], odoo_version: '17.0' },
      models: {},
    });

    const manifest = writeManifest(tmpDir, 'manifest.json', {
      module: 'test_mod',
      models: {},
    });

    const registry = require(registryPath);
    registry.updateRegistry(tmpDir, manifest);

    // After write, no .tmp file should remain (it was renamed)
    const tmpFile = registryFilePath(tmpDir) + '.tmp';
    assert.ok(!fs.existsSync(tmpFile), '.tmp file should not remain');

    // Main file should be valid JSON
    const data = readRegistry(tmpDir);
    assert.strictEqual(data._meta.version, 1);
  });
});

// ─── Registry Rollback Tests (REG-04) ───────────────────────────────────────

describe('registry rollback', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('restores from .bak file', () => {
    const original = {
      _meta: { version: 1, last_updated: null, modules_contributing: [], odoo_version: '17.0' },
      models: { 'old.model': { name: 'old.model', module: 'm', fields: {}, _inherit: [], description: '' } },
    };
    const updated = {
      _meta: { version: 2, last_updated: '2026-03-05', modules_contributing: ['m'], odoo_version: '17.0' },
      models: {},
    };

    fs.writeFileSync(bakFilePath(tmpDir), JSON.stringify(original, null, 2), 'utf-8');
    writeRegistry(tmpDir, updated);

    const registry = require(registryPath);
    const result = registry.rollbackRegistry(tmpDir);
    assert.strictEqual(result._meta.version, 1);
    assert.ok(result.models['old.model']);
  });

  test('fails gracefully when no .bak exists', () => {
    const registry = require(registryPath);
    const result = registry.rollbackRegistry(tmpDir);
    assert.strictEqual(result, null);
  });
});

// ─── Registry Validate Tests (REG-05) ───────────────────────────────────────

describe('registry validate', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('passes on valid registry (all Many2one targets exist)', () => {
    const validRegistry = sampleRegistry();
    // Add res.partner as a model so the Many2one target exists
    validRegistry.models['res.partner'] = {
      name: 'res.partner',
      module: 'base',
      description: 'Partner',
      fields: {},
      _inherit: [],
    };
    writeRegistry(tmpDir, validRegistry);

    const registry = require(registryPath);
    const result = registry.validateRegistry(tmpDir);
    assert.strictEqual(result.valid, true);
    assert.strictEqual(result.errors.length, 0);
  });

  test('reports errors for Many2one pointing to non-existent model', () => {
    // university.student has Many2one to res.partner which is NOT in registry
    writeRegistry(tmpDir, sampleRegistry());

    const registry = require(registryPath);
    const result = registry.validateRegistry(tmpDir);
    assert.strictEqual(result.valid, false);
    assert.ok(result.errors.some(e => e.includes('res.partner')));
  });

  test('reports errors for duplicate model names', () => {
    // Create registry with duplicate (trick: write raw JSON with same key -- not possible via JSON.parse)
    // Instead, we test the validation logic by having model.name not match its key
    const reg = sampleRegistry();
    reg.models['university.student_dup'] = {
      ...reg.models['university.student'],
      name: 'university.student', // name collision
    };
    writeRegistry(tmpDir, reg);

    const registry = require(registryPath);
    const result = registry.validateRegistry(tmpDir);
    assert.strictEqual(result.valid, false);
    assert.ok(result.errors.some(e => e.toLowerCase().includes('duplicate') || e.toLowerCase().includes('mismatch')));
  });

  test('reports errors for One2many missing inverse_name', () => {
    const reg = {
      _meta: { version: 1, last_updated: null, modules_contributing: [], odoo_version: '17.0' },
      models: {
        'test.parent': {
          name: 'test.parent',
          module: 'test',
          description: 'Parent',
          fields: {
            child_ids: {
              type: 'One2many',
              string: 'Children',
              comodel_name: 'test.child',
              // Missing inverse_name!
            },
          },
          _inherit: [],
        },
        'test.child': {
          name: 'test.child',
          module: 'test',
          description: 'Child',
          fields: {},
          _inherit: [],
        },
      },
    };
    writeRegistry(tmpDir, reg);

    const registry = require(registryPath);
    const result = registry.validateRegistry(tmpDir);
    assert.strictEqual(result.valid, false);
    assert.ok(result.errors.some(e => e.toLowerCase().includes('inverse_name')));
  });

  test('reports errors for invalid model name format', () => {
    const reg = {
      _meta: { version: 1, last_updated: null, modules_contributing: [], odoo_version: '17.0' },
      models: {
        'InvalidModelName': {
          name: 'InvalidModelName',
          module: 'test',
          description: 'Bad name',
          fields: {},
          _inherit: [],
        },
      },
    };
    writeRegistry(tmpDir, reg);

    const registry = require(registryPath);
    const result = registry.validateRegistry(tmpDir);
    assert.strictEqual(result.valid, false);
    assert.ok(result.errors.some(e => e.toLowerCase().includes('name') && e.toLowerCase().includes('format')));
  });
});

// ─── Registry Stats Tests (REG-06) ──────────────────────────────────────────

describe('registry stats', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('returns model_count, field_count, cross_reference_count', () => {
    // Create a registry with cross-module references
    const reg = {
      _meta: { version: 2, last_updated: '2026-03-05', modules_contributing: ['mod_a', 'mod_b'], odoo_version: '17.0' },
      models: {
        'mod_a.model1': {
          name: 'mod_a.model1',
          module: 'mod_a',
          description: 'Model A1',
          fields: {
            name: { type: 'Char', string: 'Name' },
            ref_id: { type: 'Many2one', string: 'Ref', comodel_name: 'mod_b.model2' },
          },
          _inherit: [],
        },
        'mod_b.model2': {
          name: 'mod_b.model2',
          module: 'mod_b',
          description: 'Model B2',
          fields: {
            title: { type: 'Char', string: 'Title' },
          },
          _inherit: [],
        },
      },
    };
    writeRegistry(tmpDir, reg);

    const registry = require(registryPath);
    const result = registry.statsRegistry(tmpDir);
    assert.strictEqual(result.model_count, 2);
    assert.strictEqual(result.field_count, 3); // name, ref_id, title
    assert.strictEqual(result.cross_reference_count, 1); // ref_id points to mod_b from mod_a
    assert.strictEqual(result.version, 2);
  });

  test('returns zeros for empty registry', () => {
    const registry = require(registryPath);
    const result = registry.statsRegistry(tmpDir);
    assert.strictEqual(result.model_count, 0);
    assert.strictEqual(result.field_count, 0);
    assert.strictEqual(result.cross_reference_count, 0);
    assert.strictEqual(result.version, 0);
  });
});

// ─── Spec-to-Manifest Conversion Tests (BELT-04) ────────────────────────────

describe('registry specToManifest', () => {
  test('converts spec models array to manifest models object', () => {
    const registry = require(registryPath);
    const spec = {
      module_name: 'uni_fee',
      models: [
        {
          name: 'uni_fee.fee_structure',
          description: 'Fee structure',
          fields: [
            { name: 'name', type: 'Char', string: 'Name', required: true },
            { name: 'amount', type: 'Monetary', string: 'Amount' },
          ],
        },
        {
          name: 'uni_fee.fee_payment',
          description: 'Fee payment',
          fields: [
            { name: 'student_id', type: 'Many2one', string: 'Student', comodel_name: 'res.partner' },
          ],
        },
      ],
    };

    const manifest = registry.specToManifest(spec);
    assert.strictEqual(manifest.module, 'uni_fee');
    assert.ok(manifest.models['uni_fee.fee_structure']);
    assert.ok(manifest.models['uni_fee.fee_payment']);
    assert.strictEqual(manifest.models['uni_fee.fee_structure'].module, 'uni_fee');
    assert.strictEqual(manifest.models['uni_fee.fee_structure'].fields.name.type, 'Char');
    assert.strictEqual(manifest.models['uni_fee.fee_payment'].fields.student_id.comodel_name, 'res.partner');
  });

  test('handles empty models array', () => {
    const registry = require(registryPath);
    const manifest = registry.specToManifest({ module_name: 'empty', models: [] });
    assert.strictEqual(manifest.module, 'empty');
    assert.deepStrictEqual(manifest.models, {});
  });

  test('handles models with no fields', () => {
    const registry = require(registryPath);
    const manifest = registry.specToManifest({
      module_name: 'test',
      models: [{ name: 'test.model', fields: [] }],
    });
    assert.ok(manifest.models['test.model']);
    assert.deepStrictEqual(manifest.models['test.model'].fields, {});
  });

  test('skips models with no name', () => {
    const registry = require(registryPath);
    const manifest = registry.specToManifest({
      module_name: 'test',
      models: [{ fields: [{ name: 'x', type: 'Char' }] }],
    });
    assert.deepStrictEqual(manifest.models, {});
  });

  test('skips fields with no name', () => {
    const registry = require(registryPath);
    const manifest = registry.specToManifest({
      module_name: 'test',
      models: [{ name: 'test.m', fields: [{ type: 'Char' }, { name: 'valid', type: 'Char' }] }],
    });
    assert.strictEqual(Object.keys(manifest.models['test.m'].fields).length, 1);
    assert.ok(manifest.models['test.m'].fields.valid);
  });
});

// ─── Update-from-Spec Tests (BELT-04) ───────────────────────────────────────

describe('registry updateFromSpec', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('creates registry from spec when no registry exists', () => {
    const registry = require(registryPath);
    const spec = {
      module_name: 'test_mod',
      models: [
        {
          name: 'test_mod.model_a',
          description: 'Model A',
          fields: [
            { name: 'name', type: 'Char', string: 'Name' },
          ],
        },
      ],
    };

    const result = registry.updateFromSpec(tmpDir, spec);
    assert.strictEqual(result._meta.version, 1);
    assert.ok(result._meta.modules_contributing.includes('test_mod'));
    assert.ok(result.models['test_mod.model_a']);
    assert.strictEqual(result.models['test_mod.model_a'].fields.name.type, 'Char');
  });

  test('merges into existing registry without overwriting other modules', () => {
    const registry = require(registryPath);
    writeRegistry(tmpDir, {
      _meta: { version: 2, last_updated: '2026-03-05', modules_contributing: ['existing_mod'], odoo_version: '17.0' },
      models: {
        'existing_mod.existing': {
          name: 'existing_mod.existing',
          module: 'existing_mod',
          description: 'Existing',
          fields: { name: { type: 'Char', string: 'Name' } },
          _inherit: [],
        },
      },
    });

    const spec = {
      module_name: 'new_mod',
      models: [
        {
          name: 'new_mod.new_model',
          description: 'New',
          fields: [{ name: 'title', type: 'Char' }],
        },
      ],
    };

    const result = registry.updateFromSpec(tmpDir, spec);
    assert.strictEqual(result._meta.version, 3);
    assert.ok(result._meta.modules_contributing.includes('existing_mod'));
    assert.ok(result._meta.modules_contributing.includes('new_mod'));
    assert.ok(result.models['existing_mod.existing'], 'existing model preserved');
    assert.ok(result.models['new_mod.new_model'], 'new model added');
  });

  test('overwrites existing models from same module', () => {
    const registry = require(registryPath);
    writeRegistry(tmpDir, {
      _meta: { version: 1, last_updated: null, modules_contributing: ['test_mod'], odoo_version: '17.0' },
      models: {
        'test_mod.model_a': {
          name: 'test_mod.model_a',
          module: 'test_mod',
          description: 'Old version',
          fields: { old_field: { type: 'Char' } },
          _inherit: [],
        },
      },
    });

    const spec = {
      module_name: 'test_mod',
      models: [
        {
          name: 'test_mod.model_a',
          description: 'New version',
          fields: [{ name: 'new_field', type: 'Integer' }],
        },
      ],
    };

    const result = registry.updateFromSpec(tmpDir, spec);
    assert.strictEqual(result.models['test_mod.model_a'].description, 'New version');
    assert.ok(result.models['test_mod.model_a'].fields.new_field);
    assert.ok(!result.models['test_mod.model_a'].fields.old_field, 'old field should be overwritten');
  });

  test('does not duplicate module in modules_contributing', () => {
    const registry = require(registryPath);
    writeRegistry(tmpDir, {
      _meta: { version: 1, last_updated: null, modules_contributing: ['test_mod'], odoo_version: '17.0' },
      models: {},
    });

    const result = registry.updateFromSpec(tmpDir, {
      module_name: 'test_mod',
      models: [{ name: 'test_mod.m', fields: [] }],
    });

    const count = result._meta.modules_contributing.filter(m => m === 'test_mod').length;
    assert.strictEqual(count, 1, 'should not duplicate module name');
  });
});
