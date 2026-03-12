/**
 * Registry — Model registry CRUD with atomic writes, versioning, rollback,
 * validation, and stats for Odoo module cross-reference tracking.
 *
 * The model registry is the central source of truth for all Odoo models
 * across modules. Every subsequent phase (spec generation, coherence
 * checking, belt integration) reads and writes through it.
 */

const fs = require('fs');
const path = require('path');
const { output, error } = require('./core.cjs');

// ─── Constants ───────────────────────────────────────────────────────────────

const REGISTRY_FILENAME = 'model_registry.json';
const REGISTRY_BAK_FILENAME = 'model_registry.json.bak';

const EMPTY_REGISTRY = {
  _meta: {
    version: 0,
    last_updated: null,
    modules_contributing: [],
    odoo_version: '19.0',
  },
  models: {},
};

const MODEL_NAME_PATTERN = /^[a-z][a-z0-9_.]+$/;

const RELATIONAL_TYPES = new Set(['Many2one', 'One2many', 'Many2many']);

// ─── Internal Helpers ────────────────────────────────────────────────────────

function registryPath(cwd) {
  return path.join(cwd, '.planning', REGISTRY_FILENAME);
}

function bakPath(cwd) {
  return path.join(cwd, '.planning', REGISTRY_BAK_FILENAME);
}

/**
 * Atomic write: backup existing file to .bak, write to .tmp, rename .tmp to target.
 * Never mutates input data.
 */
function atomicWriteJSON(filePath, data) {
  const bakFile = filePath + '.bak';
  const tmpFile = filePath + '.tmp';

  // Create backup of existing file if it exists
  if (fs.existsSync(filePath)) {
    fs.copyFileSync(filePath, bakFile);
  }

  // Write to tmp file first
  const content = JSON.stringify(data, null, 2);
  fs.writeFileSync(tmpFile, content, 'utf-8');

  // Atomic rename
  fs.renameSync(tmpFile, filePath);
}

/**
 * Read registry from disk. Returns EMPTY_REGISTRY if file does not exist.
 * On parse error, attempts recovery from .bak file.
 */
function readRegistryFile(cwd) {
  const regPath = registryPath(cwd);
  const bakFile = bakPath(cwd);

  if (!fs.existsSync(regPath)) {
    // No file -- return fresh empty registry
    return { ...EMPTY_REGISTRY, _meta: { ...EMPTY_REGISTRY._meta, modules_contributing: [] }, models: {} };
  }

  try {
    const raw = fs.readFileSync(regPath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    // Main file corrupted -- try .bak recovery
    if (fs.existsSync(bakFile)) {
      try {
        const bakRaw = fs.readFileSync(bakFile, 'utf-8');
        return JSON.parse(bakRaw);
      } catch {
        // Both corrupted -- return empty
        return { ...EMPTY_REGISTRY, _meta: { ...EMPTY_REGISTRY._meta, modules_contributing: [] }, models: {} };
      }
    }
    return { ...EMPTY_REGISTRY, _meta: { ...EMPTY_REGISTRY._meta, modules_contributing: [] }, models: {} };
  }
}

/**
 * Read a single model from the registry by Odoo model name.
 * Returns the model object or null if not found.
 */
function readModelFromRegistry(cwd, modelName) {
  const registry = readRegistryFile(cwd);
  const model = registry.models[modelName];
  return model || null;
}

/**
 * Update registry from a manifest file. Merges models, increments version,
 * updates metadata. Uses atomic write. Returns the new registry state.
 */
function updateRegistry(cwd, manifestPath) {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
  const registry = readRegistryFile(cwd);

  const moduleName = manifest.module || 'unknown';
  const manifestModels = manifest.models || {};

  // Build new models map (immutable)
  const newModels = { ...registry.models };
  for (const [key, model] of Object.entries(manifestModels)) {
    newModels[key] = { ...model };
  }

  // Build new modules_contributing (immutable, deduplicated)
  const modules = registry._meta.modules_contributing.includes(moduleName)
    ? [...registry._meta.modules_contributing]
    : [...registry._meta.modules_contributing, moduleName];

  const newRegistry = {
    _meta: {
      ...registry._meta,
      version: registry._meta.version + 1,
      last_updated: new Date().toISOString(),
      modules_contributing: modules,
    },
    models: newModels,
  };

  atomicWriteJSON(registryPath(cwd), newRegistry);
  return newRegistry;
}

/**
 * Rollback registry to the previous version from .bak file.
 * Returns the restored registry or null if no backup exists.
 */
function rollbackRegistry(cwd) {
  const bakFile = bakPath(cwd);
  const regPath = registryPath(cwd);

  if (!fs.existsSync(bakFile)) {
    return null;
  }

  try {
    const bakData = JSON.parse(fs.readFileSync(bakFile, 'utf-8'));
    fs.copyFileSync(bakFile, regPath);
    return bakData;
  } catch {
    return null;
  }
}

/**
 * Validate the registry for referential integrity.
 * Checks: relational target existence, One2many inverse_name, model name format,
 * duplicate model names (name vs key mismatch).
 * Returns { valid, errors, model_count }.
 */
function validateRegistry(cwd) {
  const registry = readRegistryFile(cwd);
  const errors = [];
  const modelNames = Object.keys(registry.models);
  const modelNameSet = new Set(modelNames);

  // Track seen model names for duplicate detection
  const seenNames = new Map();

  for (const [key, model] of Object.entries(registry.models)) {
    // Check model name format
    if (!MODEL_NAME_PATTERN.test(key)) {
      errors.push(`Model "${key}": name format invalid (must match ${MODEL_NAME_PATTERN})`);
    }

    // Check for duplicate model names (model.name differs from key)
    if (model.name && model.name !== key) {
      errors.push(`Model "${key}": name mismatch/duplicate -- model.name is "${model.name}" but key is "${key}"`);
    }

    // Track model.name for cross-key duplicate detection
    if (model.name) {
      if (seenNames.has(model.name) && seenNames.get(model.name) !== key) {
        errors.push(`Duplicate model name "${model.name}" found in keys "${seenNames.get(model.name)}" and "${key}"`);
      }
      seenNames.set(model.name, key);
    }

    // Check relational field targets
    const fields = model.fields || {};
    for (const [fieldName, field] of Object.entries(fields)) {
      if (RELATIONAL_TYPES.has(field.type) && field.comodel_name) {
        if (!modelNameSet.has(field.comodel_name)) {
          errors.push(
            `Model "${key}", field "${fieldName}": ${field.type} target "${field.comodel_name}" not found in registry`
          );
        }
      }

      // One2many must have inverse_name
      if (field.type === 'One2many' && !field.inverse_name) {
        errors.push(
          `Model "${key}", field "${fieldName}": One2many missing inverse_name`
        );
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    model_count: modelNames.length,
  };
}

/**
 * Compute registry statistics.
 * Returns { model_count, field_count, cross_reference_count, version }.
 * cross_reference_count = relational fields pointing to models from different modules.
 */
function statsRegistry(cwd) {
  const registry = readRegistryFile(cwd);
  const models = registry.models;
  const modelEntries = Object.entries(models);

  let fieldCount = 0;
  let crossRefCount = 0;

  for (const [, model] of modelEntries) {
    const fields = model.fields || {};
    const fieldEntries = Object.entries(fields);
    fieldCount += fieldEntries.length;

    for (const [, field] of fieldEntries) {
      if (RELATIONAL_TYPES.has(field.type) && field.comodel_name) {
        const targetModel = models[field.comodel_name];
        if (targetModel && targetModel.module !== model.module) {
          crossRefCount += 1;
        }
      }
    }
  }

  return {
    model_count: modelEntries.length,
    field_count: fieldCount,
    cross_reference_count: crossRefCount,
    version: registry._meta.version,
  };
}

// ─── Tiered Registry Injection (REG-08) ─────────────────────────────────────

/**
 * Return a filtered view of the model registry with three detail tiers:
 * - Direct depends: full model data (all fields with metadata)
 * - Transitive depends: field-list-only (model name + field names, no metadata)
 * - Everything else: names-only (model name and module)
 *
 * Read-only: returns a new object, never writes to disk.
 */
function tieredRegistryInjection(cwd, moduleName) {
  const { readStatusFile } = require('./module-status.cjs');
  const registry = readRegistryFile(cwd);
  const statusData = readStatusFile(cwd);
  const mod = statusData.modules[moduleName];

  if (!mod) {
    return { models: {} };
  }

  const directDeps = new Set(mod.depends || []);

  // Compute ALL transitive deps recursively (BFS through dep chains)
  const transitiveDeps = new Set();
  const queue = [];
  for (const dep of directDeps) {
    const depMod = statusData.modules[dep];
    if (depMod && depMod.depends) {
      for (const td of depMod.depends) {
        if (!directDeps.has(td)) {
          queue.push(td);
        }
      }
    }
  }

  while (queue.length > 0) {
    const current = queue.shift();
    if (transitiveDeps.has(current) || directDeps.has(current)) {
      continue;
    }
    transitiveDeps.add(current);
    const currentMod = statusData.modules[current];
    if (currentMod && currentMod.depends) {
      for (const td of currentMod.depends) {
        if (!directDeps.has(td) && !transitiveDeps.has(td)) {
          queue.push(td);
        }
      }
    }
  }

  const result = { models: {} };
  for (const [modelName, model] of Object.entries(registry.models)) {
    const modelModule = model.module;
    if (directDeps.has(modelModule)) {
      // Full model: all fields with metadata
      result.models[modelName] = { ...model, fields: { ...model.fields } };
    } else if (transitiveDeps.has(modelModule)) {
      // Field-list-only: model name, module, field names (no metadata)
      result.models[modelName] = {
        name: model.name,
        module: model.module,
        fields: Object.fromEntries(
          Object.keys(model.fields || {}).map(f => [f, { name: f }])
        ),
      };
    } else {
      // Names-only: just model name and module
      result.models[modelName] = { name: model.name, module: model.module };
    }
  }

  return result;
}

// ─── Spec-to-Registry Conversion (BELT-04) ──────────────────────────────────

/**
 * Convert a spec.json object (models as array, fields as array) to the
 * registry manifest format (models as object, fields as object).
 *
 * Spec format:
 *   { module_name, models: [{ name, fields: [{ name, type, ... }] }] }
 *
 * Manifest format:
 *   { module, models: { "model.name": { name, module, fields: { field_name: {...} } } } }
 */
function specToManifest(spec) {
  const moduleName = spec.module_name || 'unknown';
  const models = {};

  for (const model of (spec.models || [])) {
    const modelName = model.name;
    if (!modelName) continue;

    const fields = {};
    for (const field of (model.fields || [])) {
      if (!field.name) continue;
      fields[field.name] = { ...field };
    }

    models[modelName] = {
      name: modelName,
      module: moduleName,
      description: model.description || '',
      fields,
      _inherit: model._inherit || [],
    };
  }

  return { module: moduleName, models };
}

/**
 * Update registry directly from a spec.json object.
 * Converts spec format to manifest format, then merges into registry.
 * Uses atomic write. Returns the new registry state.
 */
function updateFromSpec(cwd, spec) {
  const manifest = specToManifest(spec);
  const registry = readRegistryFile(cwd);
  const moduleName = manifest.module || 'unknown';
  const manifestModels = manifest.models || {};

  const newModels = { ...registry.models };
  for (const [key, model] of Object.entries(manifestModels)) {
    newModels[key] = { ...model };
  }

  const modules = registry._meta.modules_contributing.includes(moduleName)
    ? [...registry._meta.modules_contributing]
    : [...registry._meta.modules_contributing, moduleName];

  const newRegistry = {
    _meta: {
      ...registry._meta,
      version: registry._meta.version + 1,
      last_updated: new Date().toISOString(),
      modules_contributing: modules,
    },
    models: newModels,
  };

  atomicWriteJSON(registryPath(cwd), newRegistry);
  return newRegistry;
}

// ─── CLI Command Functions ───────────────────────────────────────────────────

function cmdRegistryRead(cwd, raw) {
  const registry = readRegistryFile(cwd);
  output(registry, raw);
}

function cmdRegistryReadModel(cwd, modelName, raw) {
  if (!modelName) {
    error('Usage: registry read-model <model.name>');
  }
  const model = readModelFromRegistry(cwd, modelName);
  if (!model) {
    error(`Model not found: ${modelName}`);
  }
  output(model, raw);
}

function cmdRegistryUpdate(cwd, manifestPath, raw) {
  if (!manifestPath) {
    error('Usage: registry update <manifest.json>');
  }
  const fullPath = path.isAbsolute(manifestPath) ? manifestPath : path.join(cwd, manifestPath);
  if (!fs.existsSync(fullPath)) {
    error(`Manifest file not found: ${manifestPath}`);
  }
  const result = updateRegistry(cwd, fullPath);
  output(result, raw);
}

function cmdRegistryRollback(cwd, raw) {
  const result = rollbackRegistry(cwd);
  if (!result) {
    error('No backup file found for rollback');
  }
  output(result, raw);
}

function cmdRegistryValidate(cwd, raw) {
  const result = validateRegistry(cwd);
  output(result, raw);
}

function cmdRegistryStats(cwd, raw) {
  const result = statsRegistry(cwd);
  output(result, raw);
}

// ─── Exports ─────────────────────────────────────────────────────────────────

module.exports = {
  // CLI commands
  cmdRegistryRead,
  cmdRegistryReadModel,
  cmdRegistryUpdate,
  cmdRegistryRollback,
  cmdRegistryValidate,
  cmdRegistryStats,
  // Internal functions (for direct unit testing)
  readRegistryFile,
  readModelFromRegistry,
  updateRegistry,
  rollbackRegistry,
  validateRegistry,
  statsRegistry,
  // Tiered injection (REG-08)
  tieredRegistryInjection,
  // Spec-to-Registry conversion (BELT-04)
  specToManifest,
  updateFromSpec,
  // Constants
  EMPTY_REGISTRY,
};
