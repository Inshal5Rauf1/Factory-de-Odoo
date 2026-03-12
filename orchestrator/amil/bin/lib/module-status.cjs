'use strict';

/**
 * Module Status — Lifecycle state machine for Odoo module tracking
 *
 * Manages module lifecycle: planned -> spec_approved -> generated -> checked -> shipped
 * Provides tier computation, artifact directory creation, and atomic state persistence.
 */

const fs = require('fs');
const path = require('path');
const { output, error } = require('./core.cjs');

// ─── Constants ──────────────────────────────────────────────────────────────

const VALID_TRANSITIONS = {
  planned:       ['spec_approved'],
  spec_approved: ['generated', 'planned'],
  generated:     ['checked', 'spec_approved'],
  checked:       ['shipped'],
  shipped:       [],
};

const EMPTY_MODULE_STATUS = {
  _meta: { version: 0, last_updated: null },
  modules: {},
  tiers: {},
};

// ─── Internal helpers ───────────────────────────────────────────────────────

function statusFilePath(cwd) {
  return path.join(cwd, '.planning', 'module_status.json');
}

function readStatusFile(cwd) {
  const filePath = statusFilePath(cwd);
  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return { ...EMPTY_MODULE_STATUS, _meta: { ...EMPTY_MODULE_STATUS._meta }, modules: {}, tiers: {} };
  }
}

function atomicWriteJSON(filePath, data) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const backupPath = filePath + '.bak';
  if (fs.existsSync(filePath)) {
    fs.copyFileSync(filePath, backupPath);
  }
  const tmpPath = filePath + '.tmp';
  fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2) + '\n', 'utf-8');
  fs.renameSync(tmpPath, filePath);
}

function writeStatusFile(cwd, data) {
  const updated = {
    ...data,
    _meta: {
      ...data._meta,
      version: (data._meta.version || 0) + 1,
      last_updated: new Date().toISOString(),
    },
  };
  atomicWriteJSON(statusFilePath(cwd), updated);
  return updated;
}

// ─── CLI command functions ──────────────────────────────────────────────────

/**
 * Read full module_status.json or return empty structure if not exists.
 */
function cmdModuleStatusRead(cwd, raw) {
  const data = readStatusFile(cwd);
  output(data, raw, JSON.stringify(data, null, 2));
}

/**
 * Read single module status. Defaults to "planned" if module not found.
 */
function cmdModuleStatusGet(cwd, moduleName, raw) {
  if (!moduleName) {
    error('Usage: module-status get <module_name>');
  }
  const data = readStatusFile(cwd);
  const mod = data.modules[moduleName];
  const result = mod
    ? { name: moduleName, ...mod }
    : { name: moduleName, status: 'planned', tier: null, depends: [], updated: null };
  output(result, raw, JSON.stringify(result, null, 2));
}

/**
 * Initialize a new module with status "planned".
 * Creates artifact directory with CONTEXT.md placeholder.
 */
function cmdModuleStatusInit(cwd, moduleName, tier, dependsJson, raw) {
  if (!moduleName || !tier) {
    error('Usage: module-status init <module_name> <tier> <depends_json>');
  }

  const data = readStatusFile(cwd);

  if (data.modules[moduleName]) {
    error(`Module "${moduleName}" already exists`);
  }

  const depends = dependsJson ? JSON.parse(dependsJson) : [];
  const now = new Date().toISOString();

  const newModules = {
    ...data.modules,
    [moduleName]: {
      status: 'planned',
      tier,
      depends,
      updated: now,
      artifacts_dir: `.planning/modules/${moduleName}/`,
    },
  };

  const newData = { ...data, modules: newModules };
  const written = writeStatusFile(cwd, newData);

  // Create artifact directory with CONTEXT.md placeholder
  const artifactsDir = path.join(cwd, '.planning', 'modules', moduleName);
  fs.mkdirSync(artifactsDir, { recursive: true });
  const contextPath = path.join(artifactsDir, 'CONTEXT.md');
  fs.writeFileSync(contextPath, `# ${moduleName} Context\n`, 'utf-8');

  output(written, raw, JSON.stringify(written, null, 2));
}

/**
 * Transition module status with validation against VALID_TRANSITIONS.
 */
function cmdModuleStatusTransition(cwd, moduleName, newStatus, raw) {
  if (!moduleName || !newStatus) {
    error('Usage: module-status transition <module_name> <new_status>');
  }

  const data = readStatusFile(cwd);
  const mod = data.modules[moduleName];
  const currentStatus = mod ? mod.status : 'planned';

  const allowed = VALID_TRANSITIONS[currentStatus];
  if (!allowed || !allowed.includes(newStatus)) {
    const allowedStr = (allowed || []).join(', ') || 'none';
    error(
      `Invalid transition: ${moduleName} cannot go from "${currentStatus}" to "${newStatus}". Allowed: ${allowedStr}`
    );
  }

  const now = new Date().toISOString();
  const updatedModule = { ...(mod || { tier: null, depends: [] }), status: newStatus, updated: now };
  const newModules = { ...data.modules, [moduleName]: updatedModule };
  const newData = { ...data, modules: newModules };
  const written = writeStatusFile(cwd, newData);

  output(written, raw, JSON.stringify(written, null, 2));
}

/**
 * Compute tier summary: group modules by tier, count statuses, determine completion.
 */
function cmdTierStatus(cwd, raw) {
  const data = readStatusFile(cwd);
  const tierMap = {};

  for (const [name, mod] of Object.entries(data.modules)) {
    const tier = mod.tier || 'unknown';
    if (!tierMap[tier]) {
      tierMap[tier] = { modules: [], status: 'incomplete', counts: {} };
    }
    tierMap[tier].modules.push(name);
    const s = mod.status || 'planned';
    tierMap[tier].counts[s] = (tierMap[tier].counts[s] || 0) + 1;
  }

  // Determine tier completion
  for (const tier of Object.values(tierMap)) {
    const allShipped = tier.modules.length > 0 &&
      Object.keys(tier.counts).length === 1 &&
      tier.counts.shipped > 0;
    tier.status = allShipped ? 'complete' : 'incomplete';
  }

  const result = { tiers: tierMap };
  output(result, raw, JSON.stringify(result, null, 2));
}

module.exports = {
  cmdModuleStatusRead,
  cmdModuleStatusGet,
  cmdModuleStatusInit,
  cmdModuleStatusTransition,
  cmdTierStatus,
  VALID_TRANSITIONS,
  readStatusFile,
};
