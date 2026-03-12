/**
 * Coherence — Structural validation checks for spec.json consistency
 *
 * Ensures spec.json references (Many2one targets, computed depends, security
 * groups) are consistent with the model registry before any module is approved
 * for generation.
 *
 * 4 checks: many2one_targets, duplicate_models, computed_depends, security_groups
 * Each returns: { check, status, violations }
 * runAllChecks aggregates: { status, checks }
 */

const fs = require('fs');
const path = require('path');
const { output, error } = require('./core.cjs');

// ─── Constants ──────────────────────────────────────────────────────────────

const BASE_ODOO_MODELS = new Set([
  'res.partner',
  'res.users',
  'res.company',
  'res.currency',
  'product.product',
  'product.template',
  'account.move',
  'account.account',
  'account.journal',
  'mail.thread',
  'mail.activity.mixin',
  'uom.uom',
  'ir.attachment',
  'ir.sequence',
  'ir.cron',
  'hr.employee',
  'hr.department',
  'base',
  'res.config.settings',
  'res.country',
]);

// Built-in Odoo security group prefixes that are always valid
const BASE_GROUP_PREFIXES = ['base.'];

// ─── Check Functions ────────────────────────────────────────────────────────

/**
 * Check that all relational field targets (Many2one, Many2many, One2many)
 * reference models that exist in spec, registry, or BASE_ODOO_MODELS.
 */
function checkMany2oneTargets(spec, registry) {
  const violations = [];
  const specModelNames = new Set((spec.models || []).map(m => m.name));
  const registryModelNames = new Set(Object.keys(registry.models || {}));

  for (const model of (spec.models || [])) {
    for (const field of (model.fields || [])) {
      if (!field.comodel_name) continue;
      if (field.type !== 'Many2one' && field.type !== 'Many2many' && field.type !== 'One2many') continue;

      const target = field.comodel_name;
      if (specModelNames.has(target)) continue;
      if (registryModelNames.has(target)) continue;
      if (BASE_ODOO_MODELS.has(target)) continue;

      violations.push({
        model: model.name,
        field: field.name,
        target,
        reason: 'target model not in registry or spec',
      });
    }
  }

  return {
    check: 'many2one_targets',
    status: violations.length === 0 ? 'pass' : 'fail',
    violations,
  };
}

/**
 * Check for duplicate model names between spec and registry.
 * Flags when a spec model name already exists in the registry AND
 * the registry model's module differs from the spec model's module.
 */
function checkDuplicateModels(spec, registry) {
  const violations = [];
  const registryModels = registry.models || {};

  for (const model of (spec.models || [])) {
    const regModel = registryModels[model.name];
    if (!regModel) continue;

    // Same module = owner updating their own model (OK)
    if (regModel.module === model.module) continue;

    violations.push({
      model: model.name,
      spec_module: model.module || null,
      registry_module: regModel.module,
      reason: 'model already exists in registry under different module',
    });
  }

  return {
    check: 'duplicate_models',
    status: violations.length === 0 ? 'pass' : 'fail',
    violations,
  };
}

/**
 * Check that computed field depends paths resolve to existing fields.
 * For dot-notation paths (e.g., "partner_id.name"), validates only
 * the first segment exists as a field on the model.
 */
function checkComputedDepends(spec, registry) {
  const violations = [];
  const registryModels = registry.models || {};

  for (const model of (spec.models || [])) {
    // Build field name set from spec model fields + registry model fields
    const specFieldNames = new Set((model.fields || []).map(f => f.name));
    const regModel = registryModels[model.name];
    const regFieldNames = new Set(Object.keys((regModel && regModel.fields) || {}));

    for (const field of (model.fields || [])) {
      if (!field.compute || !field.depends) continue;

      for (const depPath of field.depends) {
        // For dot-notation, validate first segment only
        const firstSegment = depPath.split('.')[0];
        if (specFieldNames.has(firstSegment)) continue;
        if (regFieldNames.has(firstSegment)) continue;

        violations.push({
          model: model.name,
          field: field.name,
          depends_path: depPath,
          reason: `field "${firstSegment}" not found on model`,
        });
      }
    }
  }

  return {
    check: 'computed_depends',
    status: violations.length === 0 ? 'pass' : 'fail',
    violations,
  };
}

/**
 * Check that security ACL dict keys match the roles array,
 * and defaults keys match the roles array.
 */
function checkSecurityGroups(spec, registry) {
  const violations = [];
  const security = spec.security;

  if (!security) {
    return { check: 'security_groups', status: 'pass', violations: [] };
  }

  // Build set of defined roles
  const definedRoles = new Set(security.roles || []);

  // Check that every ACL key exists in roles
  for (const aclRole of Object.keys(security.acl || {})) {
    if (!definedRoles.has(aclRole)) {
      violations.push({
        role: aclRole,
        location: 'acl',
        reason: 'ACL entry references role not defined in security.roles',
      });
    }
  }

  // Check that every defaults key exists in roles
  for (const defaultRole of Object.keys(security.defaults || {})) {
    if (!definedRoles.has(defaultRole)) {
      violations.push({
        role: defaultRole,
        location: 'defaults',
        reason: 'defaults entry references role not defined in security.roles',
      });
    }
  }

  // Check that every role has an ACL entry
  for (const role of definedRoles) {
    if (!security.acl || !(role in security.acl)) {
      violations.push({
        role,
        location: 'roles',
        reason: 'role defined but has no ACL entry',
      });
    }
  }

  return {
    check: 'security_groups',
    status: violations.length === 0 ? 'pass' : 'fail',
    violations,
  };
}

// ─── Aggregation ────────────────────────────────────────────────────────────

/**
 * Run all 4 checks and aggregate results.
 * status is "pass" only when all 4 checks pass.
 */
function runAllChecks(spec, registry) {
  const checks = [
    checkMany2oneTargets(spec, registry),
    checkDuplicateModels(spec, registry),
    checkComputedDepends(spec, registry),
    checkSecurityGroups(spec, registry),
  ];

  const allPass = checks.every(c => c.status === 'pass');

  return {
    status: allPass ? 'pass' : 'fail',
    checks,
  };
}

// ─── CLI Command ────────────────────────────────────────────────────────────

/**
 * CLI handler for `coherence check --spec <path> --registry <path>`.
 * Loads files from disk, runs all checks, outputs JSON report.
 */
function cmdCoherenceCheck(cwd, specPath, registryPath, raw) {
  if (!specPath) {
    error('Usage: coherence check --spec <path> --registry <path>');
  }

  const resolvedSpec = path.isAbsolute(specPath) ? specPath : path.join(cwd, specPath);
  if (!fs.existsSync(resolvedSpec)) {
    error(`Spec file not found: ${specPath}`);
  }

  let spec;
  try {
    spec = JSON.parse(fs.readFileSync(resolvedSpec, 'utf-8'));
  } catch (e) {
    error(`Failed to parse spec file: ${e.message}`);
  }

  let registry;
  if (registryPath) {
    const resolvedReg = path.isAbsolute(registryPath) ? registryPath : path.join(cwd, registryPath);
    if (!fs.existsSync(resolvedReg)) {
      error(`Registry file not found: ${registryPath}`);
    }
    try {
      registry = JSON.parse(fs.readFileSync(resolvedReg, 'utf-8'));
    } catch (e) {
      error(`Failed to parse registry file: ${e.message}`);
    }
  } else {
    // Try default registry location
    const defaultReg = path.join(cwd, '.planning', 'model_registry.json');
    if (fs.existsSync(defaultReg)) {
      registry = JSON.parse(fs.readFileSync(defaultReg, 'utf-8'));
    } else {
      registry = { _meta: {}, models: {} };
    }
  }

  const result = runAllChecks(spec, registry);
  output(result, raw);
}

// ─── Exports ────────────────────────────────────────────────────────────────

module.exports = {
  checkMany2oneTargets,
  checkDuplicateModels,
  checkComputedDepends,
  checkSecurityGroups,
  runAllChecks,
  cmdCoherenceCheck,
  BASE_ODOO_MODELS,
};
