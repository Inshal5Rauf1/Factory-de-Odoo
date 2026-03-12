/**
 * Config — Planning config CRUD operations
 */

const fs = require('fs');
const path = require('path');
const { output, error } = require('./core.cjs');

function cmdConfigEnsureSection(cwd, raw) {
  const configPath = path.join(cwd, '.planning', 'config.json');
  const planningDir = path.join(cwd, '.planning');

  // Ensure .planning directory exists
  try {
    if (!fs.existsSync(planningDir)) {
      fs.mkdirSync(planningDir, { recursive: true });
    }
  } catch (err) {
    error('Failed to create .planning directory: ' + err.message);
  }

  // Check if config already exists
  if (fs.existsSync(configPath)) {
    const result = { created: false, reason: 'already_exists' };
    output(result, raw, 'exists');
    return;
  }

  // Detect Brave Search API key availability
  const homedir = require('os').homedir();
  const braveKeyFile = path.join(homedir, '.odoo-gsd', 'brave_api_key');
  const hasBraveSearch = !!(process.env.BRAVE_API_KEY || fs.existsSync(braveKeyFile));

  // Load user-level defaults from ~/.odoo-gsd/defaults.json if available
  const globalDefaultsPath = path.join(homedir, '.odoo-gsd', 'defaults.json');
  let userDefaults = {};
  try {
    if (fs.existsSync(globalDefaultsPath)) {
      userDefaults = JSON.parse(fs.readFileSync(globalDefaultsPath, 'utf-8'));
      // Migrate deprecated "depth" key to "granularity"
      if ('depth' in userDefaults && !('granularity' in userDefaults)) {
        const depthToGranularity = { quick: 'coarse', standard: 'standard', comprehensive: 'fine' };
        userDefaults.granularity = depthToGranularity[userDefaults.depth] || userDefaults.depth;
        delete userDefaults.depth;
        try { fs.writeFileSync(globalDefaultsPath, JSON.stringify(userDefaults, null, 2), 'utf-8'); } catch { /* best-effort migration write */ }
      }
    }
  } catch (err) {
    // Ignore malformed global defaults, fall back to hardcoded
  }

  // Create default config (user-level defaults override hardcoded defaults)
  const hardcoded = {
    model_profile: 'balanced',
    commit_docs: true,
    search_gitignored: false,
    branching_strategy: 'none',
    phase_branch_template: 'odoo-gsd/phase-{phase}-{slug}',
    milestone_branch_template: 'odoo-gsd/{milestone}-{slug}',
    workflow: {
      research: true,
      plan_check: true,
      verifier: true,
      nyquist_validation: true,
    },
    parallelization: true,
    brave_search: hasBraveSearch,
  };
  const defaults = {
    ...hardcoded,
    ...userDefaults,
    workflow: { ...hardcoded.workflow, ...(userDefaults.workflow || {}) },
  };

  try {
    fs.writeFileSync(configPath, JSON.stringify(defaults, null, 2), 'utf-8');
    const result = { created: true, path: '.planning/config.json' };
    output(result, raw, 'created');
  } catch (err) {
    error('Failed to create config.json: ' + err.message);
  }
}

// ─── Odoo Config Validation ──────────────────────────────────────────────────

const VALID_ODOO_VERSIONS = ['17.0', '18.0', '19.0'];
const VALID_NOTIFICATION_CHANNELS = ['email', 'sms', 'push', 'in_app', 'whatsapp'];
const VALID_LOCALIZATIONS = ['pk', 'sa', 'ae', 'none'];
const VALID_LMS_INTEGRATIONS = ['canvas', 'moodle', 'none'];
const VALID_DEPLOYMENT_TARGETS = ['single', 'multi'];

/**
 * Validate odoo-specific config keys before setting.
 * Returns null if valid, or an error message string if invalid.
 */
function validateOdooConfigKey(keyPath, parsedValue, rawValue) {
  if (keyPath === 'odoo.version') {
    // Use the raw string value to preserve "17.0" vs "17" distinction
    const strVal = rawValue !== undefined ? String(rawValue) : String(parsedValue);
    if (!VALID_ODOO_VERSIONS.includes(strVal)) {
      return `Invalid odoo.version: "${strVal}". Must be one of: ${VALID_ODOO_VERSIONS.join(', ')}`;
    }
  }
  if (keyPath === 'odoo.scope_levels') {
    if (!Array.isArray(parsedValue) || parsedValue.length === 0) {
      return 'odoo.scope_levels must be a non-empty array';
    }
  }
  if (keyPath === 'odoo.multi_company') {
    if (typeof parsedValue !== 'boolean') {
      return 'odoo.multi_company must be a boolean';
    }
  }
  if (keyPath === 'odoo.localization') {
    if (!VALID_LOCALIZATIONS.includes(String(parsedValue))) {
      return `Invalid odoo.localization: "${parsedValue}". Must be one of: ${VALID_LOCALIZATIONS.join(', ')}`;
    }
  }
  if (keyPath === 'odoo.canvas_integration') {
    if (!VALID_LMS_INTEGRATIONS.includes(String(parsedValue))) {
      return `Invalid odoo.canvas_integration: "${parsedValue}". Must be one of: ${VALID_LMS_INTEGRATIONS.join(', ')}`;
    }
  }
  if (keyPath === 'odoo.deployment_target') {
    if (!VALID_DEPLOYMENT_TARGETS.includes(String(parsedValue))) {
      return `Invalid odoo.deployment_target: "${parsedValue}". Must be one of: ${VALID_DEPLOYMENT_TARGETS.join(', ')}`;
    }
  }
  if (keyPath === 'odoo.notification_channels') {
    if (!Array.isArray(parsedValue)) {
      return 'odoo.notification_channels must be an array';
    }
    for (const ch of parsedValue) {
      if (!VALID_NOTIFICATION_CHANNELS.includes(ch)) {
        return `Invalid notification channel: "${ch}". Allowed: ${VALID_NOTIFICATION_CHANNELS.join(', ')}`;
      }
    }
  }
  return null;
}

function cmdConfigSet(cwd, keyPath, value, raw) {
  const configPath = path.join(cwd, '.planning', 'config.json');

  if (!keyPath) {
    error('Usage: config-set <key.path> <value>');
  }

  // Parse value (handle booleans, numbers, and JSON arrays/objects)
  let parsedValue = value;
  if (value === 'true') parsedValue = true;
  else if (value === 'false') parsedValue = false;
  else if (typeof value === 'string' && (value.startsWith('[') || value.startsWith('{'))) {
    try {
      parsedValue = JSON.parse(value);
    } catch {
      // Keep as string if JSON parse fails
    }
  } else if (!isNaN(value) && value !== '') parsedValue = Number(value);

  // Validate odoo-specific keys (use original string value for version check)
  if (keyPath.startsWith('odoo.')) {
    const validationError = validateOdooConfigKey(keyPath, parsedValue, value);
    if (validationError) {
      error(validationError);
    }
    // Preserve odoo.version as string (e.g., "17.0" not 17)
    if (keyPath === 'odoo.version') {
      parsedValue = String(value);
    }
  }

  // Load existing config or start with empty object
  let config = {};
  try {
    if (fs.existsSync(configPath)) {
      config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    }
  } catch (err) {
    error('Failed to read config.json: ' + err.message);
  }

  // Set nested value using dot notation (e.g., "workflow.research")
  const keys = keyPath.split('.');
  function deepSet(obj, keyArr, value) {
    if (keyArr.length === 1) {
      return { ...obj, [keyArr[0]]: value };
    }
    const [head, ...rest] = keyArr;
    const child = (obj[head] !== undefined && typeof obj[head] === 'object') ? obj[head] : {};
    return { ...obj, [head]: deepSet(child, rest, value) };
  }
  config = deepSet(config, keys, parsedValue);

  // Write back
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');
    const result = { updated: true, key: keyPath, value: parsedValue };
    output(result, raw, `${keyPath}=${parsedValue}`);
  } catch (err) {
    error('Failed to write config.json: ' + err.message);
  }
}

function cmdConfigGet(cwd, keyPath, raw) {
  const configPath = path.join(cwd, '.planning', 'config.json');

  if (!keyPath) {
    error('Usage: config-get <key.path>');
  }

  let config = {};
  try {
    if (fs.existsSync(configPath)) {
      config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    } else {
      error('No config.json found at ' + configPath);
    }
  } catch (err) {
    if (err.message.startsWith('No config.json')) throw err;
    error('Failed to read config.json: ' + err.message);
  }

  // Traverse dot-notation path (e.g., "workflow.auto_advance")
  const keys = keyPath.split('.');
  let current = config;
  for (const key of keys) {
    if (current === undefined || current === null || typeof current !== 'object') {
      error(`Key not found: ${keyPath}`);
    }
    current = current[key];
  }

  if (current === undefined) {
    error(`Key not found: ${keyPath}`);
  }

  output(current, raw, String(current));
}

module.exports = {
  cmdConfigEnsureSection,
  cmdConfigSet,
  cmdConfigGet,
};
