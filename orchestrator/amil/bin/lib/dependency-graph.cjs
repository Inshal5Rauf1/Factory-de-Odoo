'use strict';

/**
 * Dependency Graph — Topological sort, cycle detection, tier grouping, generation blocking
 *
 * Reads module dependency data from module_status.json and provides:
 * - Topological ordering for generation sequence
 * - Circular dependency detection with cycle path reporting
 * - Tier grouping based on dependency depth
 * - Generation readiness checking (all deps must be >= "generated")
 */

const fs = require('fs');
const path = require('path');
const { output, error } = require('./core.cjs');
const { readStatusFile } = require('./module-status.cjs');

// ─── Constants ──────────────────────────────────────────────────────────────

const TIER_LABELS = ['foundation', 'core', 'operations', 'communication'];

// Statuses that indicate a module has been generated (or beyond)
const GENERATED_OR_BEYOND = new Set(['generated', 'checked', 'shipped']);

// ─── Internal functions ─────────────────────────────────────────────────────

/**
 * DFS-based topological sort with cycle detection.
 *
 * @param {Object} modules - { name: { depends: [dep1, dep2] } }
 * @returns {string[]} Module names in dependency order (deps before dependents)
 */
function topoSort(modules) {
  const visited = new Set();
  const visiting = new Set();
  const result = [];

  function visit(name, ancestors) {
    if (visited.has(name)) return;

    if (visiting.has(name)) {
      const cycleStart = ancestors.indexOf(name);
      const cyclePath = [...ancestors.slice(cycleStart), name];
      throw new Error(
        `Circular dependency detected: ${cyclePath.join(' -> ')}`
      );
    }

    visiting.add(name);

    const mod = modules[name];
    if (mod && mod.depends) {
      for (const dep of mod.depends) {
        visit(dep, [...ancestors, name]);
      }
    }

    visiting.delete(name);
    visited.add(name);
    result.push(name);
  }

  for (const name of Object.keys(modules)) {
    visit(name, []);
  }

  return result;
}

/**
 * Compute tier labels based on max dependency depth.
 *
 * @param {Object} modules - { name: { depends: [dep1, dep2] } }
 * @returns {{ tiers: Object, depths: Object, order: string[] }}
 */
function computeTiers(modules) {
  const order = topoSort(modules);
  const depths = {};

  // Process in topological order so deps are computed first
  for (const name of order) {
    const mod = modules[name];
    const deps = (mod && mod.depends) ? mod.depends : [];
    if (deps.length === 0) {
      depths[name] = 0;
    } else {
      depths[name] = Math.max(...deps.map(d => (depths[d] || 0))) + 1;
    }
  }

  // Group by tier label
  const tiers = {};
  for (const name of order) {
    const depth = depths[name];
    const tierIndex = Math.min(depth, TIER_LABELS.length - 1);
    const tierLabel = TIER_LABELS[tierIndex];
    if (!tiers[tierLabel]) {
      tiers[tierLabel] = [];
    }
    tiers[tierLabel].push(name);
  }

  return { tiers, depths, order };
}

// ─── CLI command functions ──────────────────────────────────────────────────

/**
 * Build adjacency list from module_status.json.
 */
function cmdDepGraphBuild(cwd, raw) {
  const data = readStatusFile(cwd);
  const modules = {};

  for (const [name, mod] of Object.entries(data.modules)) {
    modules[name] = { depends: mod.depends || [] };
  }

  output({ modules }, raw, JSON.stringify({ modules }, null, 2));
}

/**
 * Return modules in topological (generation) order.
 */
function cmdDepGraphOrder(cwd, raw) {
  const data = readStatusFile(cwd);
  const modules = {};

  for (const [name, mod] of Object.entries(data.modules)) {
    modules[name] = { depends: mod.depends || [] };
  }

  try {
    const order = topoSort(modules);
    output(order, raw, JSON.stringify(order, null, 2));
  } catch (err) {
    error(err.message);
  }
}

/**
 * Return tier groupings based on dependency depth.
 */
function cmdDepGraphTiers(cwd, raw) {
  const data = readStatusFile(cwd);
  const modules = {};

  for (const [name, mod] of Object.entries(data.modules)) {
    modules[name] = { depends: mod.depends || [] };
  }

  try {
    const result = computeTiers(modules);
    output(result, raw, JSON.stringify(result, null, 2));
  } catch (err) {
    error(err.message);
  }
}

/**
 * Check if a module's dependencies have all reached "generated" status or beyond.
 */
function cmdDepGraphCanGenerate(cwd, moduleName, raw) {
  if (!moduleName) {
    error('Usage: dep-graph can-generate <module_name>');
  }

  const data = readStatusFile(cwd);
  const mod = data.modules[moduleName];

  if (!mod) {
    error(`Module "${moduleName}" not found in module_status.json`);
  }

  const depends = mod.depends || [];
  const blockedBy = [];

  for (const dep of depends) {
    const depMod = data.modules[dep];
    const depStatus = depMod ? depMod.status : 'planned';
    if (!GENERATED_OR_BEYOND.has(depStatus)) {
      blockedBy.push({ module: dep, status: depStatus });
    }
  }

  const result = {
    can_generate: blockedBy.length === 0,
    blocked_by: blockedBy,
  };

  output(result, raw, JSON.stringify(result, null, 2));
}

module.exports = {
  cmdDepGraphBuild,
  cmdDepGraphOrder,
  cmdDepGraphTiers,
  cmdDepGraphCanGenerate,
  topoSort,
  computeTiers,
};
