'use strict';

/**
 * Decomposition — Merge 4 agent outputs into a unified module decomposition.
 *
 * Provides:
 * - mergeDecomposition: 5-step merge of agent JSON files
 * - formatDecompositionTable: Structured text presentation
 * - generateRoadmapMarkdown: Flat ROADMAP.md content
 */

const fs = require('fs');
const path = require('path');
const { topoSort, computeTiers } = require('./dependency-graph.cjs');

// ─── Helpers ─────────────────────────────────────────────────────────────────

function readJSON(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

const TIER_LABELS = ['foundation', 'core', 'operations', 'communication'];

function tierLabel(depth) {
  return TIER_LABELS[Math.min(depth, TIER_LABELS.length - 1)];
}

// ─── mergeDecomposition ──────────────────────────────────────────────────────

/**
 * 5-step merge of 4 agent JSON outputs into decomposition.json.
 *
 * @param {string} researchDir - Path to .planning/research/ containing agent outputs
 * @param {string} cwd - Project root (unused but passed for consistency)
 * @returns {Object} The decomposition object
 */
function mergeDecomposition(researchDir, cwd) {
  // Step 1: Read module-boundaries.json as base module list
  const boundaries = readJSON(path.join(researchDir, 'module-boundaries.json'));
  const modules = boundaries.modules.map(m => ({
    name: m.name,
    description: m.description,
    models: [...m.models],
    base_depends: [...m.base_depends],
    custom_depends: [],
    estimated_complexity: m.estimated_complexity,
    build_recommendation: 'build_new',
    oca_module: null,
    tier: 'foundation',
    tier_index: 0,
    computation_chains: [],
  }));

  const moduleMap = new Map(modules.map(m => [m.name, m]));

  // Step 2: Cross-reference OCA analysis — annotate build_recommendation
  const oca = readJSON(path.join(researchDir, 'oca-analysis.json'));
  for (const finding of oca.findings) {
    const mod = moduleMap.get(finding.odoo_module);
    if (mod) {
      mod.build_recommendation = finding.recommendation;
      mod.oca_module = finding.oca_module || null;
    }
  }

  // Step 3: Extract custom depends, run topoSort + computeTiers
  const depMap = readJSON(path.join(researchDir, 'dependency-map.json'));
  const customModuleNames = new Set(modules.map(m => m.name));

  for (const dep of depMap.dependencies) {
    const mod = moduleMap.get(dep.module);
    if (mod) {
      // Only include custom module deps (not base Odoo deps)
      mod.custom_depends = dep.depends_on.filter(d => customModuleNames.has(d));
    }
  }

  // Build adjacency for topoSort (custom deps only)
  const adjacency = {};
  for (const mod of modules) {
    adjacency[mod.name] = { depends: mod.custom_depends };
  }

  const tierResult = computeTiers(adjacency);

  for (const mod of modules) {
    const depth = tierResult.depths[mod.name] || 0;
    mod.tier = tierLabel(depth);
    mod.tier_index = depth;
  }

  // Step 4: Attach computation chains by step prefix matching
  const chains = readJSON(path.join(researchDir, 'computation-chains.json'));
  for (const chain of chains.chains) {
    for (const mod of modules) {
      const hasMatch = chain.steps.some(step => step.startsWith(mod.name + '.'));
      if (hasMatch) {
        mod.computation_chains.push({
          name: chain.name,
          description: chain.description,
          steps: [...chain.steps],
          cross_module: chain.cross_module,
        });
      }
    }
  }

  // Step 5: Generate warnings
  const warnings = [];

  // Modules with unknown complexity
  for (const mod of modules) {
    if (mod.estimated_complexity === 'unknown') {
      warnings.push(`Module "${mod.name}" has unknown complexity — review manually`);
    }
  }

  // Modules with 3+ same-tier custom depends
  for (const mod of modules) {
    const sameTierDeps = mod.custom_depends.filter(d => {
      const dep = moduleMap.get(d);
      return dep && dep.tier === mod.tier;
    });
    if (sameTierDeps.length >= 3) {
      warnings.push(`Module "${mod.name}" has ${sameTierDeps.length} same-tier dependencies — consider splitting`);
    }
  }

  // Build tiers object
  const tiers = {};
  for (const mod of modules) {
    if (!tiers[mod.tier]) tiers[mod.tier] = [];
    tiers[mod.tier].push(mod.name);
  }

  const decomposition = {
    modules,
    tiers,
    generation_order: tierResult.order,
    computation_chains: chains.chains,
    warnings,
  };

  // Write decomposition.json
  fs.writeFileSync(
    path.join(researchDir, 'decomposition.json'),
    JSON.stringify(decomposition, null, 2)
  );

  return decomposition;
}

// ─── formatDecompositionTable ────────────────────────────────────────────────

/**
 * Format decomposition as structured text for human review.
 *
 * @param {Object} decomposition - The decomposition object
 * @returns {string} Formatted text
 */
function formatDecompositionTable(decomposition) {
  const { modules, tiers, computation_chains, warnings } = decomposition;
  const tierCount = Object.keys(tiers).length;
  const lines = [];

  lines.push(`ERP MODULE DECOMPOSITION -- ${modules.length} modules across ${tierCount} tiers`);
  lines.push('');

  // Group by tier in TIER_LABELS order
  let tierNum = 0;
  for (const label of TIER_LABELS) {
    const tierModules = tiers[label];
    if (!tierModules || tierModules.length === 0) continue;
    tierNum++;
    const capitalLabel = label.charAt(0).toUpperCase() + label.slice(1);
    lines.push(`TIER ${tierNum}: ${capitalLabel} (${tierNum === 1 ? 'generate first' : 'depends on previous'})`);
    lines.push(`  | Module | Models | Build | Depends |`);
    lines.push(`  |--------|--------|-------|---------|`);
    for (const modName of tierModules) {
      const mod = modules.find(m => m.name === modName);
      if (!mod) continue;
      const allDeps = [...mod.base_depends, ...mod.custom_depends].join(', ');
      const buildLabel = mod.build_recommendation === 'build_new' ? 'NEW'
        : mod.build_recommendation.toUpperCase();
      lines.push(`  | ${mod.name} | ${mod.models.length} | ${buildLabel} | ${allDeps} |`);
    }
    lines.push('');
  }

  // Computation chains
  if (computation_chains && computation_chains.length > 0) {
    lines.push('COMPUTATION CHAINS (cross-module):');
    for (let i = 0; i < computation_chains.length; i++) {
      const chain = computation_chains[i];
      lines.push(`  ${i + 1}. ${chain.name}: ${chain.steps.join(' -> ')}`);
    }
    lines.push('');
  }

  // Warnings
  if (warnings && warnings.length > 0) {
    lines.push('WARNINGS:');
    for (const w of warnings) {
      lines.push(`  - ${w}`);
    }
    lines.push('');
  }

  lines.push('Approve this decomposition? (yes / modify / regenerate)');

  return lines.join('\n');
}

// ─── generateRoadmapMarkdown ─────────────────────────────────────────────────

/**
 * Generate flat ROADMAP.md content from decomposition.
 *
 * @param {Object} decomposition - The decomposition object
 * @returns {string} Markdown string
 */
function generateRoadmapMarkdown(decomposition) {
  const { modules, generation_order } = decomposition;
  const moduleMap = new Map(modules.map(m => [m.name, m]));
  const lines = [];

  for (let i = 0; i < generation_order.length; i++) {
    const name = generation_order[i];
    const mod = moduleMap.get(name);
    if (!mod) continue;

    const allDeps = [...mod.base_depends, ...mod.custom_depends].join(', ');
    const buildLabel = mod.build_recommendation === 'build_new' ? 'NEW'
      : mod.build_recommendation.toUpperCase();
    const tierIndex = mod.tier_index + 1;
    const tierName = mod.tier.charAt(0).toUpperCase() + mod.tier.slice(1);

    lines.push(`### Phase ${i + 1}: ${name}`);
    lines.push(`- Tier: ${tierIndex} (${tierName})`);
    lines.push(`- Models: ${mod.models.join(', ')}`);
    lines.push(`- Depends: ${allDeps}`);
    lines.push(`- Build: ${buildLabel}`);
    lines.push(`- Status: not_started`);
    lines.push('');
  }

  return lines.join('\n');
}

module.exports = {
  mergeDecomposition,
  formatDecompositionTable,
  generateRoadmapMarkdown,
};
