/**
 * Provisional Registry — Tracks "promised" models from modules that
 * haven't been generated yet. Populated from decomposition data and
 * spec.json files. Models move to the real registry when generated.
 *
 * This solves the forward reference problem at 90+ modules:
 * Module 15 can reference module 60's model because the provisional
 * registry knows module 60 WILL provide that model.
 */

const fs = require('fs');
const path = require('path');

const PROV_REGISTRY_FILE = 'provisional_registry.json';

function getProvRegistryPath(cwd) {
  return path.join(cwd, '.planning', PROV_REGISTRY_FILE);
}

/**
 * Build provisional registry from decomposition data.
 * Called once after PRD decomposition, updated after each spec.
 *
 * @param {Object} decomposition - The full decomposition.json
 * @returns {Object} provisionalRegistry
 */
function buildFromDecomposition(decomposition) {
  const registry = {
    version: 1,
    built_at: new Date().toISOString(),
    source: 'decomposition',
    modules: {},
    models: {},       // model_name -> { module, fields[], confidence }
    references: [],   // { from_module, from_model, to_model, type }
  };

  for (const mod of (decomposition.modules || [])) {
    const moduleName = mod.name;
    registry.modules[moduleName] = {
      status: 'provisional',
      model_count: (mod.models || []).length,
      depends: mod.depends || mod.base_depends || [],
    };

    for (const model of (mod.models || [])) {
      const modelName = model.name;
      const fields = (model.fields || []).map(f => ({
        name: f.name,
        type: f.type,
        comodel_name: f.comodel_name || null,
      }));

      registry.models[modelName] = {
        module: moduleName,
        fields,
        confidence: model.fields?.length > 2 ? 'high' : 'low',
        source: 'decomposition',
      };

      // Track cross-module references
      for (const field of (model.fields || [])) {
        if (field.comodel_name) {
          registry.references.push({
            from_module: moduleName,
            from_model: modelName,
            to_model: field.comodel_name,
            field_name: field.name,
            type: field.type, // Many2one, One2many, Many2many
          });
        }
      }
    }
  }

  return registry;
}

/**
 * Update provisional registry when a spec.json is approved.
 * Spec data is more detailed than decomposition, so it overwrites.
 *
 * @param {Object} registry - Current provisional registry
 * @param {Object} spec - The approved spec.json
 * @returns {Object} Updated registry
 */
function updateFromSpec(registry, spec) {
  const moduleName = spec.module_name;
  const newRegistry = JSON.parse(JSON.stringify(registry)); // immutable

  newRegistry.modules[moduleName] = {
    ...newRegistry.modules[moduleName],
    status: 'spec_approved',
    model_count: (spec.models || []).length,
    depends: spec.depends || [],
  };

  for (const model of (spec.models || [])) {
    const modelName = model.name;
    const fields = (model.fields || []).map(f => ({
      name: f.name,
      type: f.type,
      comodel_name: f.comodel_name || null,
    }));

    newRegistry.models[modelName] = {
      module: moduleName,
      fields,
      confidence: 'high', // spec-level detail
      source: 'spec',
    };

    // Update references
    newRegistry.references = newRegistry.references.filter(
      r => r.from_module !== moduleName || r.from_model !== modelName
    );
    for (const field of (model.fields || [])) {
      if (field.comodel_name) {
        newRegistry.references.push({
          from_module: moduleName,
          from_model: modelName,
          to_model: field.comodel_name,
          field_name: field.name,
          type: field.type,
        });
      }
    }
  }

  return newRegistry;
}

/**
 * Mark a module as "built" — its models graduate from provisional
 * to the real registry. Called after successful generation.
 *
 * @param {Object} registry - Current provisional registry
 * @param {string} moduleName - The module that was just generated
 * @returns {Object} Updated registry with module marked as built
 */
function markBuilt(registry, moduleName) {
  const newRegistry = JSON.parse(JSON.stringify(registry));

  if (newRegistry.modules[moduleName]) {
    newRegistry.modules[moduleName].status = 'built';
  }

  // Models for this module are now in the real registry
  // Keep them in provisional for reference resolution, but mark as built
  for (const [modelName, modelData] of Object.entries(newRegistry.models)) {
    if (modelData.module === moduleName) {
      newRegistry.models[modelName] = {
        ...modelData,
        source: 'built',
      };
    }
  }

  return newRegistry;
}

/**
 * Resolve a model reference — check both real and provisional registries.
 *
 * @param {string} modelName - The model being referenced (e.g., 'hr.payroll.slip')
 * @param {Object} realRegistry - The real model_registry.json
 * @param {Object} provRegistry - The provisional registry
 * @returns {Object} { found, source, module, confidence }
 */
function resolveReference(modelName, realRegistry, provRegistry) {
  // Check base Odoo models (always valid)
  const STANDARD_MODELS = [
    'res.partner', 'res.users', 'res.company', 'res.currency',
    'res.country', 'res.country.state', 'res.config.settings',
    'ir.cron', 'ir.attachment', 'ir.sequence', 'ir.mail_server',
    'mail.thread', 'mail.activity.mixin', 'mail.message',
  ];
  if (STANDARD_MODELS.includes(modelName)) {
    return { found: true, source: 'odoo_base', module: 'base', confidence: 'certain' };
  }

  // Check real registry (built modules)
  if (realRegistry?.models?.[modelName]) {
    return {
      found: true,
      source: 'built',
      module: realRegistry.models[modelName].module,
      confidence: 'certain',
    };
  }

  // Check provisional registry (planned/spec'd modules)
  if (provRegistry?.models?.[modelName]) {
    const provModel = provRegistry.models[modelName];
    return {
      found: true,
      source: provModel.source, // 'decomposition', 'spec', or 'built'
      module: provModel.module,
      confidence: provModel.confidence,
    };
  }

  return { found: false, source: null, module: null, confidence: null };
}

/**
 * Analyze all forward references — find which planned modules
 * reference models in other planned modules. Returns a dependency
 * map that informs generation order.
 *
 * @param {Object} provRegistry - The provisional registry
 * @returns {Object} { forwardRefs, unresolvedRefs, circularRisks }
 */
function analyzeForwardReferences(provRegistry) {
  const forwardRefs = [];   // references from unbuilt → unbuilt
  const unresolvedRefs = []; // references to models that don't exist anywhere
  const circularRisks = [];  // pairs of modules that reference each other

  // Build module → referenced_modules map
  const moduleRefs = {}; // moduleName -> Set of referenced module names

  for (const ref of (provRegistry.references || [])) {
    const sourceModule = ref.from_module;
    const targetModel = ref.to_model;

    // Find which module provides the target model
    const targetModelData = provRegistry.models[targetModel];
    if (!targetModelData) {
      // Check if it's an Odoo base model
      const resolved = resolveReference(targetModel, null, provRegistry);
      if (!resolved.found) {
        unresolvedRefs.push({
          from_module: sourceModule,
          from_model: ref.from_model,
          to_model: targetModel,
          field: ref.field_name,
        });
      }
      continue;
    }

    const targetModule = targetModelData.module;
    if (targetModule === sourceModule) continue; // same module, not cross-module

    // Track forward reference
    if (targetModelData.source !== 'built') {
      forwardRefs.push({
        from_module: sourceModule,
        to_module: targetModule,
        from_model: ref.from_model,
        to_model: targetModel,
        field: ref.field_name,
      });
    }

    // Track module-level references for circular detection
    if (!moduleRefs[sourceModule]) moduleRefs[sourceModule] = new Set();
    moduleRefs[sourceModule].add(targetModule);
  }

  // Detect circular references (A→B and B→A)
  for (const [modA, refsA] of Object.entries(moduleRefs)) {
    for (const modB of refsA) {
      if (moduleRefs[modB]?.has(modA)) {
        // Only add each pair once
        const pair = [modA, modB].sort().join(':');
        if (!circularRisks.find(c => c.pair === pair)) {
          circularRisks.push({
            pair,
            modules: [modA, modB],
            refs_a_to_b: forwardRefs.filter(r => r.from_module === modA && r.to_module === modB),
            refs_b_to_a: forwardRefs.filter(r => r.from_module === modB && r.to_module === modA),
          });
        }
      }
    }
  }

  return { forwardRefs, unresolvedRefs, circularRisks };
}

/**
 * Find critical dependency chains — sequences of 4+ modules where
 * each depends on the previous. If any module in the chain fails,
 * everything downstream is blocked.
 *
 * @param {Object} provRegistry - The provisional registry
 * @returns {Array} chains sorted by length (longest = highest risk)
 */
function findCriticalChains(provRegistry) {
  // Build adjacency list from module dependencies
  const adj = {};
  for (const [modName, modData] of Object.entries(provRegistry.modules || {})) {
    adj[modName] = (modData.depends || []).filter(d =>
      provRegistry.modules[d] // Only count deps within our module set
    );
  }

  // DFS to find longest chain through each node
  const chains = [];
  const visited = new Set();

  function dfs(node, chain) {
    if (visited.has(node)) return;
    visited.add(node);
    chain.push(node);

    const deps = adj[node] || [];
    if (deps.length === 0 || deps.every(d => visited.has(d))) {
      if (chain.length >= 4) {
        chains.push([...chain]);
      }
    } else {
      for (const dep of deps) {
        if (!visited.has(dep)) {
          dfs(dep, chain);
        }
      }
    }

    chain.pop();
    visited.delete(node);
  }

  for (const mod of Object.keys(adj)) {
    dfs(mod, []);
  }

  // Sort by length descending
  chains.sort((a, b) => b.length - a.length);
  return chains.slice(0, 10); // Top 10 critical chains
}

/**
 * Save provisional registry to disk.
 */
function save(cwd, registry) {
  const registryPath = getProvRegistryPath(cwd);
  fs.writeFileSync(registryPath, JSON.stringify(registry, null, 2), 'utf8');
}

/**
 * Load provisional registry from disk.
 */
function load(cwd) {
  const registryPath = getProvRegistryPath(cwd);
  if (!fs.existsSync(registryPath)) return null;
  return JSON.parse(fs.readFileSync(registryPath, 'utf8'));
}

module.exports = {
  PROV_REGISTRY_FILE,
  getProvRegistryPath,
  buildFromDecomposition,
  updateFromSpec,
  markBuilt,
  resolveReference,
  analyzeForwardReferences,
  findCriticalChains,
  save,
  load,
};
