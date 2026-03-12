/**
 * Amil Tools Tests - coherence.cjs
 *
 * Unit tests for the coherence checker: 4 structural validation checks,
 * runAllChecks aggregation, cmdCoherenceCheck CLI integration, and edge cases.
 *
 * Requirements: SPEC-05, SPEC-06, TEST-03
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { createTempProject, cleanup, runGsdTools } = require('./helpers.cjs');

const coherencePath = path.join(__dirname, '..', 'amil', 'bin', 'lib', 'coherence.cjs');
const {
  checkMany2oneTargets,
  checkDuplicateModels,
  checkComputedDepends,
  checkSecurityGroups,
  runAllChecks,
  BASE_ODOO_MODELS,
} = require(coherencePath);

// ─── Test Fixtures ──────────────────────────────────────────────────────────

function makeSpec(models, security) {
  const spec = { models: models || [] };
  if (security) spec.security = security;
  return spec;
}

function makeRegistry(models) {
  return {
    _meta: { version: 1, last_updated: null, modules_contributing: [], odoo_version: '17.0' },
    models: models || {},
  };
}

// ─── BASE_ODOO_MODELS ───────────────────────────────────────────────────────

describe('BASE_ODOO_MODELS', () => {
  test('is a Set with common Odoo models', () => {
    assert.ok(BASE_ODOO_MODELS instanceof Set);
    assert.ok(BASE_ODOO_MODELS.size >= 15, `Expected >= 15 models, got ${BASE_ODOO_MODELS.size}`);
    assert.ok(BASE_ODOO_MODELS.has('res.partner'));
    assert.ok(BASE_ODOO_MODELS.has('res.users'));
    assert.ok(BASE_ODOO_MODELS.has('res.company'));
    assert.ok(BASE_ODOO_MODELS.has('product.product'));
    assert.ok(BASE_ODOO_MODELS.has('account.move'));
    assert.ok(BASE_ODOO_MODELS.has('mail.thread'));
    assert.ok(BASE_ODOO_MODELS.has('ir.attachment'));
    assert.ok(BASE_ODOO_MODELS.has('base'));
  });
});

// ─── checkMany2oneTargets ───────────────────────────────────────────────────

describe('checkMany2oneTargets', () => {
  test('passes when comodel_name exists in spec models', () => {
    const spec = makeSpec([
      { name: 'uni.program', fields: [] },
      { name: 'uni.fee', fields: [{ name: 'program_id', type: 'Many2one', comodel_name: 'uni.program' }] },
    ]);
    const result = checkMany2oneTargets(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
    assert.strictEqual(result.violations.length, 0);
  });

  test('passes when comodel_name exists in registry', () => {
    const spec = makeSpec([
      { name: 'uni.fee', fields: [{ name: 'program_id', type: 'Many2one', comodel_name: 'uni.program' }] },
    ]);
    const registry = makeRegistry({ 'uni.program': { name: 'uni.program', module: 'core', fields: {} } });
    const result = checkMany2oneTargets(spec, registry);
    assert.strictEqual(result.status, 'pass');
  });

  test('passes for BASE_ODOO_MODELS even if not in registry', () => {
    const spec = makeSpec([
      { name: 'uni.student', fields: [
        { name: 'partner_id', type: 'Many2one', comodel_name: 'res.partner' },
        { name: 'user_id', type: 'Many2one', comodel_name: 'res.users' },
      ]},
    ]);
    const result = checkMany2oneTargets(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
  });

  test('fails when target model missing from spec and registry', () => {
    const spec = makeSpec([
      { name: 'uni.fee.line', fields: [
        { name: 'enrollment_id', type: 'Many2one', comodel_name: 'uni.enrollment' },
      ]},
    ]);
    const result = checkMany2oneTargets(spec, makeRegistry());
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.violations.length, 1);
    assert.strictEqual(result.violations[0].model, 'uni.fee.line');
    assert.strictEqual(result.violations[0].field, 'enrollment_id');
    assert.strictEqual(result.violations[0].target, 'uni.enrollment');
  });

  test('handles Many2many comodel_name', () => {
    const spec = makeSpec([
      { name: 'uni.course', fields: [
        { name: 'tag_ids', type: 'Many2many', comodel_name: 'uni.tag' },
      ]},
    ]);
    const result = checkMany2oneTargets(spec, makeRegistry());
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.violations[0].target, 'uni.tag');
  });

  test('handles One2many comodel_name', () => {
    const spec = makeSpec([
      { name: 'uni.course', fields: [
        { name: 'line_ids', type: 'One2many', comodel_name: 'uni.course.line' },
      ]},
    ]);
    const result = checkMany2oneTargets(spec, makeRegistry());
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.violations[0].target, 'uni.course.line');
  });

  test('passes with empty spec models array', () => {
    const result = checkMany2oneTargets(makeSpec([]), makeRegistry());
    assert.strictEqual(result.status, 'pass');
    assert.strictEqual(result.violations.length, 0);
  });

  test('check name is many2one_targets', () => {
    const result = checkMany2oneTargets(makeSpec([]), makeRegistry());
    assert.strictEqual(result.check, 'many2one_targets');
  });
});

// ─── checkDuplicateModels ───────────────────────────────────────────────────

describe('checkDuplicateModels', () => {
  test('passes when spec model names are unique and not in registry', () => {
    const spec = makeSpec([
      { name: 'uni.fee', module: 'fees', fields: [] },
      { name: 'uni.payment', module: 'fees', fields: [] },
    ]);
    const result = checkDuplicateModels(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
    assert.strictEqual(result.violations.length, 0);
  });

  test('fails when spec model name exists in registry with different module', () => {
    const spec = makeSpec([
      { name: 'uni.student', module: 'fees', fields: [] },
    ]);
    const registry = makeRegistry({
      'uni.student': { name: 'uni.student', module: 'core', fields: {} },
    });
    const result = checkDuplicateModels(spec, registry);
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.violations.length, 1);
    assert.strictEqual(result.violations[0].model, 'uni.student');
  });

  test('passes when spec model exists in registry with same module (owner)', () => {
    const spec = makeSpec([
      { name: 'uni.student', module: 'core', fields: [] },
    ]);
    const registry = makeRegistry({
      'uni.student': { name: 'uni.student', module: 'core', fields: {} },
    });
    const result = checkDuplicateModels(spec, registry);
    assert.strictEqual(result.status, 'pass');
  });

  test('passes with empty spec models', () => {
    const result = checkDuplicateModels(makeSpec([]), makeRegistry());
    assert.strictEqual(result.status, 'pass');
  });

  test('check name is duplicate_models', () => {
    const result = checkDuplicateModels(makeSpec([]), makeRegistry());
    assert.strictEqual(result.check, 'duplicate_models');
  });
});

// ─── checkComputedDepends ───────────────────────────────────────────────────

describe('checkComputedDepends', () => {
  test('passes when depends fields exist on the model', () => {
    const spec = makeSpec([
      { name: 'uni.fee', fields: [
        { name: 'amount', type: 'Float' },
        { name: 'total', type: 'Float', compute: '_compute_total', depends: ['amount'] },
      ]},
    ]);
    const result = checkComputedDepends(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
  });

  test('fails when depends field not found on model', () => {
    const spec = makeSpec([
      { name: 'uni.fee', fields: [
        { name: 'total', type: 'Float', compute: '_compute_total', depends: ['missing_field'] },
      ]},
    ]);
    const result = checkComputedDepends(spec, makeRegistry());
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.violations.length, 1);
    assert.strictEqual(result.violations[0].model, 'uni.fee');
    assert.strictEqual(result.violations[0].field, 'total');
    assert.strictEqual(result.violations[0].depends_path, 'missing_field');
  });

  test('handles dot-notation paths (validates first segment)', () => {
    const spec = makeSpec([
      { name: 'uni.fee', fields: [
        { name: 'partner_id', type: 'Many2one', comodel_name: 'res.partner' },
        { name: 'total', type: 'Float', compute: '_compute_total', depends: ['partner_id.name'] },
      ]},
    ]);
    const result = checkComputedDepends(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
  });

  test('fails on dot-notation when first segment not found', () => {
    const spec = makeSpec([
      { name: 'uni.fee', fields: [
        { name: 'total', type: 'Float', compute: '_compute_total', depends: ['missing_rel.name'] },
      ]},
    ]);
    const result = checkComputedDepends(spec, makeRegistry());
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.violations[0].depends_path, 'missing_rel.name');
  });

  test('passes when model has no computed fields', () => {
    const spec = makeSpec([
      { name: 'uni.fee', fields: [
        { name: 'amount', type: 'Float' },
      ]},
    ]);
    const result = checkComputedDepends(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
  });

  test('resolves depends fields from registry model', () => {
    const spec = makeSpec([
      { name: 'uni.fee', fields: [
        { name: 'total', type: 'Float', compute: '_compute_total', depends: ['reg_field'] },
      ]},
    ]);
    const registry = makeRegistry({
      'uni.fee': { name: 'uni.fee', module: 'fees', fields: { reg_field: { type: 'Float' } } },
    });
    const result = checkComputedDepends(spec, registry);
    assert.strictEqual(result.status, 'pass');
  });

  test('check name is computed_depends', () => {
    const result = checkComputedDepends(makeSpec([]), makeRegistry());
    assert.strictEqual(result.check, 'computed_depends');
  });
});

// ─── checkSecurityGroups ────────────────────────────────────────────────────

describe('checkSecurityGroups', () => {
  test('passes when acl and defaults keys match defined roles', () => {
    const spec = makeSpec(
      [{ name: 'uni.fee', fields: [] }],
      {
        roles: ['manager', 'user'],
        acl: {
          manager: { create: true, read: true, write: true, unlink: true },
          user: { create: false, read: true, write: false, unlink: false },
        },
        defaults: { manager: 'full', user: 'read' },
      }
    );
    const result = checkSecurityGroups(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
  });

  test('fails when acl key references undefined role', () => {
    const spec = makeSpec(
      [{ name: 'uni.fee', fields: [] }],
      {
        roles: ['manager'],
        acl: {
          manager: { create: true, read: true, write: true, unlink: true },
          unknown_role: { create: false, read: true, write: false, unlink: false },
        },
      }
    );
    const result = checkSecurityGroups(spec, makeRegistry());
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.violations.length, 1);
    assert.strictEqual(result.violations[0].role, 'unknown_role');
    assert.strictEqual(result.violations[0].location, 'acl');
  });

  test('fails when defaults key references undefined role', () => {
    const spec = makeSpec(
      [{ name: 'uni.fee', fields: [] }],
      {
        roles: ['manager'],
        acl: { manager: { create: true, read: true, write: true, unlink: true } },
        defaults: { manager: 'full', unknown_role: 'read' },
      }
    );
    const result = checkSecurityGroups(spec, makeRegistry());
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.violations[0].role, 'unknown_role');
    assert.strictEqual(result.violations[0].location, 'defaults');
  });

  test('fails when role has no acl entry', () => {
    const spec = makeSpec(
      [{ name: 'uni.fee', fields: [] }],
      {
        roles: ['manager', 'orphan_role'],
        acl: { manager: { create: true, read: true, write: true, unlink: true } },
      }
    );
    const result = checkSecurityGroups(spec, makeRegistry());
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.violations[0].role, 'orphan_role');
    assert.strictEqual(result.violations[0].location, 'roles');
  });

  test('passes when no security section in spec', () => {
    const spec = makeSpec([{ name: 'uni.fee', fields: [] }]);
    const result = checkSecurityGroups(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
  });

  test('passes with empty roles and empty acl', () => {
    const spec = makeSpec(
      [{ name: 'uni.fee', fields: [] }],
      { roles: [], acl: {}, defaults: {} }
    );
    const result = checkSecurityGroups(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
  });

  test('check name is security_groups', () => {
    const result = checkSecurityGroups(makeSpec([]), makeRegistry());
    assert.strictEqual(result.check, 'security_groups');
  });
});

// ─── runAllChecks ───────────────────────────────────────────────────────────

describe('runAllChecks', () => {
  test('returns pass when all 4 checks pass', () => {
    const spec = makeSpec([
      { name: 'uni.fee', fields: [{ name: 'amount', type: 'Float' }] },
    ]);
    const result = runAllChecks(spec, makeRegistry());
    assert.strictEqual(result.status, 'pass');
    assert.strictEqual(result.checks.length, 4);
    for (const check of result.checks) {
      assert.strictEqual(check.status, 'pass');
    }
  });

  test('returns fail if any check fails', () => {
    const spec = makeSpec([
      { name: 'uni.fee', fields: [
        { name: 'missing_ref', type: 'Many2one', comodel_name: 'uni.nonexistent' },
      ]},
    ]);
    const result = runAllChecks(spec, makeRegistry());
    assert.strictEqual(result.status, 'fail');
    assert.strictEqual(result.checks.length, 4);
    // At least one should fail
    const failedChecks = result.checks.filter(c => c.status === 'fail');
    assert.ok(failedChecks.length >= 1);
  });

  test('includes all 4 check names', () => {
    const result = runAllChecks(makeSpec([]), makeRegistry());
    const names = result.checks.map(c => c.check);
    assert.deepStrictEqual(names, [
      'many2one_targets',
      'duplicate_models',
      'computed_depends',
      'security_groups',
    ]);
  });

  test('handles empty spec and empty registry', () => {
    const result = runAllChecks(makeSpec([]), makeRegistry());
    assert.strictEqual(result.status, 'pass');
  });
});

// ─── CLI integration (cmdCoherenceCheck) ────────────────────────────────────

describe('CLI coherence check', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('outputs valid JSON coherence report via CLI', () => {
    const specData = {
      models: [
        { name: 'uni.program', fields: [] },
        { name: 'uni.fee', fields: [
          { name: 'program_id', type: 'Many2one', comodel_name: 'uni.program' },
        ]},
      ],
    };
    const registryData = {
      _meta: { version: 1, last_updated: null, modules_contributing: [], odoo_version: '17.0' },
      models: {},
    };

    const specPath = path.join(tmpDir, 'spec.json');
    const regPath = path.join(tmpDir, 'registry.json');
    fs.writeFileSync(specPath, JSON.stringify(specData), 'utf-8');
    fs.writeFileSync(regPath, JSON.stringify(registryData), 'utf-8');

    const result = runGsdTools(
      ['coherence', 'check', '--spec', specPath, '--registry', regPath, '--raw'],
      tmpDir
    );
    assert.ok(result.success, `CLI failed: ${result.error}`);
    const parsed = JSON.parse(result.output);
    assert.strictEqual(parsed.status, 'pass');
    assert.strictEqual(parsed.checks.length, 4);
  });

  test('reports failures via CLI', () => {
    const specData = {
      models: [
        { name: 'uni.fee', fields: [
          { name: 'enrollment_id', type: 'Many2one', comodel_name: 'uni.enrollment' },
        ]},
      ],
    };
    const registryData = {
      _meta: { version: 1, last_updated: null, modules_contributing: [], odoo_version: '17.0' },
      models: {},
    };

    const specPath = path.join(tmpDir, 'spec.json');
    const regPath = path.join(tmpDir, 'registry.json');
    fs.writeFileSync(specPath, JSON.stringify(specData), 'utf-8');
    fs.writeFileSync(regPath, JSON.stringify(registryData), 'utf-8');

    const result = runGsdTools(
      ['coherence', 'check', '--spec', specPath, '--registry', regPath, '--raw'],
      tmpDir
    );
    assert.ok(result.success, `CLI failed: ${result.error}`);
    const parsed = JSON.parse(result.output);
    assert.strictEqual(parsed.status, 'fail');
    const m2oCheck = parsed.checks.find(c => c.check === 'many2one_targets');
    assert.strictEqual(m2oCheck.status, 'fail');
    assert.ok(m2oCheck.violations.length > 0);
  });
});
