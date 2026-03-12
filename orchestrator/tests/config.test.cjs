/**
 * Amil Tools Tests - config.cjs
 *
 * CLI integration tests for config-ensure-section, config-set, and config-get
 * commands exercised through amil-tools.cjs via execSync.
 *
 * Requirements: TEST-13
 */

const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { runGsdTools, createTempProject, cleanup } = require('./helpers.cjs');

// ─── helpers ──────────────────────────────────────────────────────────────────

function readConfig(tmpDir) {
  const configPath = path.join(tmpDir, '.planning', 'config.json');
  return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
}

function writeConfig(tmpDir, obj) {
  const configPath = path.join(tmpDir, '.planning', 'config.json');
  fs.writeFileSync(configPath, JSON.stringify(obj, null, 2), 'utf-8');
}

// ─── config-ensure-section ───────────────────────────────────────────────────

describe('config-ensure-section command', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('creates config.json with expected structure and types', () => {
    const result = runGsdTools('config-ensure-section', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    assert.strictEqual(output.created, true);

    const config = readConfig(tmpDir);
    // Verify structure and types — exact values may vary if ~/.amil/defaults.json exists
    assert.strictEqual(typeof config.model_profile, 'string');
    assert.strictEqual(typeof config.commit_docs, 'boolean');
    assert.strictEqual(typeof config.parallelization, 'boolean');
    assert.strictEqual(typeof config.branching_strategy, 'string');
    assert.ok(config.workflow && typeof config.workflow === 'object', 'workflow should be an object');
    assert.strictEqual(typeof config.workflow.research, 'boolean');
    assert.strictEqual(typeof config.workflow.plan_check, 'boolean');
    assert.strictEqual(typeof config.workflow.verifier, 'boolean');
    assert.strictEqual(typeof config.workflow.nyquist_validation, 'boolean');
    // These hardcoded defaults are always present (may be overridden by user defaults)
    assert.ok('model_profile' in config, 'model_profile should exist');
    assert.ok('brave_search' in config, 'brave_search should exist');
    assert.ok('search_gitignored' in config, 'search_gitignored should exist');
  });

  test('is idempotent — returns already_exists on second call', () => {
    const first = runGsdTools('config-ensure-section', tmpDir);
    assert.ok(first.success, `First call failed: ${first.error}`);
    const firstOutput = JSON.parse(first.output);
    assert.strictEqual(firstOutput.created, true);

    const second = runGsdTools('config-ensure-section', tmpDir);
    assert.ok(second.success, `Second call failed: ${second.error}`);
    const secondOutput = JSON.parse(second.output);
    assert.strictEqual(secondOutput.created, false);
    assert.strictEqual(secondOutput.reason, 'already_exists');
  });

  // NOTE: This test touches ~/.amil/ on the real filesystem. It uses save/restore
  // try/finally and skips if the file already exists to avoid corrupting user config.
  test('detects Brave Search from file-based key', () => {
    const homedir = os.homedir();
    const gsdDir = path.join(homedir, '.amil');
    const braveKeyFile = path.join(gsdDir, 'brave_api_key');

    // Skip if file already exists (don't mess with user's real config)
    if (fs.existsSync(braveKeyFile)) {
      return;
    }

    // Create .amil dir and brave_api_key file
    const gsdDirExisted = fs.existsSync(gsdDir);
    try {
      if (!gsdDirExisted) {
        fs.mkdirSync(gsdDir, { recursive: true });
      }
      fs.writeFileSync(braveKeyFile, 'test-key', 'utf-8');

      const result = runGsdTools('config-ensure-section', tmpDir);
      assert.ok(result.success, `Command failed: ${result.error}`);

      const config = readConfig(tmpDir);
      assert.strictEqual(config.brave_search, true);
    } finally {
      // Clean up
      try { fs.unlinkSync(braveKeyFile); } catch { /* ignore */ }
      if (!gsdDirExisted) {
        try { fs.rmdirSync(gsdDir); } catch { /* ignore if not empty */ }
      }
    }
  });

  // NOTE: This test touches ~/.amil/ on the real filesystem. It uses save/restore
  // try/finally and skips if the file already exists to avoid corrupting user config.
  test('merges user defaults from defaults.json', () => {
    const homedir = os.homedir();
    const gsdDir = path.join(homedir, '.amil');
    const defaultsFile = path.join(gsdDir, 'defaults.json');

    // Save existing defaults if present
    let existingDefaults = null;
    const gsdDirExisted = fs.existsSync(gsdDir);
    if (fs.existsSync(defaultsFile)) {
      existingDefaults = fs.readFileSync(defaultsFile, 'utf-8');
    }

    try {
      if (!gsdDirExisted) {
        fs.mkdirSync(gsdDir, { recursive: true });
      }
      fs.writeFileSync(defaultsFile, JSON.stringify({
        model_profile: 'quality',
        commit_docs: false,
      }), 'utf-8');

      const result = runGsdTools('config-ensure-section', tmpDir);
      assert.ok(result.success, `Command failed: ${result.error}`);

      const config = readConfig(tmpDir);
      assert.strictEqual(config.model_profile, 'quality', 'model_profile should be overridden');
      assert.strictEqual(config.commit_docs, false, 'commit_docs should be overridden');
      assert.strictEqual(typeof config.branching_strategy, 'string', 'branching_strategy should be a string');
    } finally {
      // Restore
      if (existingDefaults !== null) {
        fs.writeFileSync(defaultsFile, existingDefaults, 'utf-8');
      } else {
        try { fs.unlinkSync(defaultsFile); } catch { /* ignore */ }
      }
      if (!gsdDirExisted) {
        try { fs.rmdirSync(gsdDir); } catch { /* ignore */ }
      }
    }
  });

  // NOTE: This test touches ~/.amil/ on the real filesystem. It uses save/restore
  // try/finally and skips if the file already exists to avoid corrupting user config.
  test('merges nested workflow keys from defaults.json preserving unset keys', () => {
    const homedir = os.homedir();
    const gsdDir = path.join(homedir, '.amil');
    const defaultsFile = path.join(gsdDir, 'defaults.json');

    let existingDefaults = null;
    const gsdDirExisted = fs.existsSync(gsdDir);
    if (fs.existsSync(defaultsFile)) {
      existingDefaults = fs.readFileSync(defaultsFile, 'utf-8');
    }

    try {
      if (!gsdDirExisted) {
        fs.mkdirSync(gsdDir, { recursive: true });
      }
      fs.writeFileSync(defaultsFile, JSON.stringify({
        workflow: { research: false },
      }), 'utf-8');

      const result = runGsdTools('config-ensure-section', tmpDir);
      assert.ok(result.success, `Command failed: ${result.error}`);

      const config = readConfig(tmpDir);
      assert.strictEqual(config.workflow.research, false, 'research should be overridden');
      assert.strictEqual(typeof config.workflow.plan_check, 'boolean', 'plan_check should be a boolean');
      assert.strictEqual(typeof config.workflow.verifier, 'boolean', 'verifier should be a boolean');
    } finally {
      if (existingDefaults !== null) {
        fs.writeFileSync(defaultsFile, existingDefaults, 'utf-8');
      } else {
        try { fs.unlinkSync(defaultsFile); } catch { /* ignore */ }
      }
      if (!gsdDirExisted) {
        try { fs.rmdirSync(gsdDir); } catch { /* ignore */ }
      }
    }
  });
});

// ─── config-set ──────────────────────────────────────────────────────────────

describe('config-set command', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
    // Create initial config
    runGsdTools('config-ensure-section', tmpDir);
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('sets a top-level string value', () => {
    const result = runGsdTools('config-set model_profile quality', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    assert.strictEqual(output.updated, true);
    assert.strictEqual(output.key, 'model_profile');
    assert.strictEqual(output.value, 'quality');

    const config = readConfig(tmpDir);
    assert.strictEqual(config.model_profile, 'quality');
  });

  test('coerces true to boolean', () => {
    const result = runGsdTools('config-set commit_docs true', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const config = readConfig(tmpDir);
    assert.strictEqual(config.commit_docs, true);
    assert.strictEqual(typeof config.commit_docs, 'boolean');
  });

  test('coerces false to boolean', () => {
    const result = runGsdTools('config-set commit_docs false', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const config = readConfig(tmpDir);
    assert.strictEqual(config.commit_docs, false);
    assert.strictEqual(typeof config.commit_docs, 'boolean');
  });

  test('coerces numeric strings to numbers', () => {
    const result = runGsdTools('config-set some_number 42', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const config = readConfig(tmpDir);
    assert.strictEqual(config.some_number, 42);
    assert.strictEqual(typeof config.some_number, 'number');
  });

  test('preserves plain strings', () => {
    const result = runGsdTools('config-set some_string hello', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const config = readConfig(tmpDir);
    assert.strictEqual(config.some_string, 'hello');
    assert.strictEqual(typeof config.some_string, 'string');
  });

  test('sets nested values via dot-notation', () => {
    const result = runGsdTools('config-set workflow.research false', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const config = readConfig(tmpDir);
    assert.strictEqual(config.workflow.research, false);
  });

  test('auto-creates nested objects for deep dot-notation', () => {
    // Start with empty config
    writeConfig(tmpDir, {});

    const result = runGsdTools('config-set a.b.c deep_value', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const config = readConfig(tmpDir);
    assert.strictEqual(config.a.b.c, 'deep_value');
    assert.strictEqual(typeof config.a, 'object');
    assert.strictEqual(typeof config.a.b, 'object');
  });

  test('errors when no key path provided', () => {
    const result = runGsdTools('config-set', tmpDir);
    assert.strictEqual(result.success, false);
  });
});

// ─── config-get ──────────────────────────────────────────────────────────────

describe('config-get command', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
    // Create config with known values
    runGsdTools('config-ensure-section', tmpDir);
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('gets a top-level value', () => {
    const result = runGsdTools('config-get model_profile', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    assert.strictEqual(output, 'balanced');
  });

  test('gets a nested value via dot-notation', () => {
    const result = runGsdTools('config-get workflow.research', tmpDir);
    assert.ok(result.success, `Command failed: ${result.error}`);

    const output = JSON.parse(result.output);
    assert.strictEqual(output, true);
  });

  test('errors for nonexistent key', () => {
    const result = runGsdTools('config-get nonexistent_key', tmpDir);
    assert.strictEqual(result.success, false);
    assert.ok(
      result.error.includes('Key not found'),
      `Expected "Key not found" in error: ${result.error}`
    );
  });

  test('errors for deeply nested nonexistent key', () => {
    const result = runGsdTools('config-get workflow.nonexistent', tmpDir);
    assert.strictEqual(result.success, false);
    assert.ok(
      result.error.includes('Key not found'),
      `Expected "Key not found" in error: ${result.error}`
    );
  });

  test('errors when config.json does not exist', () => {
    const emptyTmpDir = createTempProject();
    try {
      const result = runGsdTools('config-get model_profile', emptyTmpDir);
      assert.strictEqual(result.success, false);
      assert.ok(
        result.error.includes('No config.json'),
        `Expected "No config.json" in error: ${result.error}`
      );
    } finally {
      cleanup(emptyTmpDir);
    }
  });

  test('errors when no key path provided', () => {
    const result = runGsdTools('config-get', tmpDir);
    assert.strictEqual(result.success, false);
  });
});

// ─── odoo config extensions (CONF-03) ───────────────────────────────────────

describe('odoo config extensions (CONF-03)', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
    runGsdTools('config-ensure-section', tmpDir);
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  // ── odoo.multi_company (boolean) ──

  test('odoo.multi_company accepts true', () => {
    const result = runGsdTools('config-set odoo.multi_company true', tmpDir);
    assert.ok(result.success, `Should accept true: ${result.error}`);
    const config = readConfig(tmpDir);
    assert.strictEqual(config.odoo.multi_company, true);
  });

  test('odoo.multi_company accepts false', () => {
    const result = runGsdTools('config-set odoo.multi_company false', tmpDir);
    assert.ok(result.success, `Should accept false: ${result.error}`);
    const config = readConfig(tmpDir);
    assert.strictEqual(config.odoo.multi_company, false);
  });

  test('odoo.multi_company rejects "yes"', () => {
    const result = runGsdTools('config-set odoo.multi_company yes', tmpDir);
    assert.strictEqual(result.success, false, 'Should reject "yes"');
    assert.ok(result.error.includes('boolean'), `Error should mention boolean: ${result.error}`);
  });

  test('odoo.multi_company rejects 1', () => {
    const result = runGsdTools('config-set odoo.multi_company 1', tmpDir);
    assert.strictEqual(result.success, false, 'Should reject 1');
  });

  test('odoo.multi_company rejects "true-ish"', () => {
    const result = runGsdTools('config-set odoo.multi_company true-ish', tmpDir);
    assert.strictEqual(result.success, false, 'Should reject "true-ish"');
  });

  // ── odoo.localization (enum) ──

  test('odoo.localization accepts "pk"', () => {
    const result = runGsdTools('config-set odoo.localization pk', tmpDir);
    assert.ok(result.success, `Should accept pk: ${result.error}`);
    const config = readConfig(tmpDir);
    assert.strictEqual(config.odoo.localization, 'pk');
  });

  test('odoo.localization accepts "sa"', () => {
    const result = runGsdTools('config-set odoo.localization sa', tmpDir);
    assert.ok(result.success, `Should accept sa: ${result.error}`);
  });

  test('odoo.localization accepts "ae"', () => {
    const result = runGsdTools('config-set odoo.localization ae', tmpDir);
    assert.ok(result.success, `Should accept ae: ${result.error}`);
  });

  test('odoo.localization accepts "none"', () => {
    const result = runGsdTools('config-set odoo.localization none', tmpDir);
    assert.ok(result.success, `Should accept none: ${result.error}`);
  });

  test('odoo.localization rejects "us"', () => {
    const result = runGsdTools('config-set odoo.localization us', tmpDir);
    assert.strictEqual(result.success, false, 'Should reject "us"');
    assert.ok(result.error.includes('pk') || result.error.includes('localization'),
      `Error should mention valid values: ${result.error}`);
  });

  // ── odoo.canvas_integration (enum) ──

  test('odoo.canvas_integration accepts "canvas"', () => {
    const result = runGsdTools('config-set odoo.canvas_integration canvas', tmpDir);
    assert.ok(result.success, `Should accept canvas: ${result.error}`);
  });

  test('odoo.canvas_integration accepts "moodle"', () => {
    const result = runGsdTools('config-set odoo.canvas_integration moodle', tmpDir);
    assert.ok(result.success, `Should accept moodle: ${result.error}`);
  });

  test('odoo.canvas_integration accepts "none"', () => {
    const result = runGsdTools('config-set odoo.canvas_integration none', tmpDir);
    assert.ok(result.success, `Should accept none: ${result.error}`);
  });

  test('odoo.canvas_integration rejects "blackboard"', () => {
    const result = runGsdTools('config-set odoo.canvas_integration blackboard', tmpDir);
    assert.strictEqual(result.success, false, 'Should reject "blackboard"');
  });

  // ── odoo.deployment_target (enum) ──

  test('odoo.deployment_target accepts "single"', () => {
    const result = runGsdTools('config-set odoo.deployment_target single', tmpDir);
    assert.ok(result.success, `Should accept single: ${result.error}`);
  });

  test('odoo.deployment_target accepts "multi"', () => {
    const result = runGsdTools('config-set odoo.deployment_target multi', tmpDir);
    assert.ok(result.success, `Should accept multi: ${result.error}`);
  });

  test('odoo.deployment_target rejects "cloud"', () => {
    const result = runGsdTools('config-set odoo.deployment_target cloud', tmpDir);
    assert.strictEqual(result.success, false, 'Should reject "cloud"');
  });

  // ── odoo.notification_channels includes whatsapp ──

  test('odoo.notification_channels now accepts whatsapp', () => {
    const result = runGsdTools(
      ['config-set', 'odoo.notification_channels', '["email","whatsapp","sms"]'],
      tmpDir
    );
    assert.ok(result.success, `Should accept whatsapp: ${result.error}`);
    const config = readConfig(tmpDir);
    assert.ok(config.odoo.notification_channels.includes('whatsapp'));
  });

  // ── odoo.existing_modules (free text) ──

  test('odoo.existing_modules accepts any string', () => {
    const result = runGsdTools('config-set odoo.existing_modules base,mail,account', tmpDir);
    assert.ok(result.success, `Should accept free text: ${result.error}`);
    const config = readConfig(tmpDir);
    assert.strictEqual(config.odoo.existing_modules, 'base,mail,account');
  });
});

// ─── odoo config block (CONF-01, CONF-02) ──────────────────────────────────

describe('odoo config block', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
    runGsdTools('config-ensure-section', tmpDir);
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  test('config set odoo.version 17.0 succeeds and config get returns it', () => {
    const set = runGsdTools('config-set odoo.version 17.0', tmpDir);
    assert.ok(set.success, `Set failed: ${set.error}`);

    const get = runGsdTools('config-get odoo.version', tmpDir);
    assert.ok(get.success, `Get failed: ${get.error}`);
    const val = JSON.parse(get.output);
    assert.strictEqual(val, '17.0', 'odoo.version should be stored as string "17.0"');
  });

  test('config set odoo.version 16.0 fails validation (only 17.0/18.0 allowed)', () => {
    const result = runGsdTools('config-set odoo.version 16.0', tmpDir);
    // With validation in config.cjs, this should fail
    assert.strictEqual(result.success, false, 'Should reject version 16.0');
    assert.ok(result.error.includes('17.0') || result.error.includes('18.0'),
      `Error should mention valid versions: ${result.error}`);
  });

  test('config set odoo.scope_levels with valid array succeeds', () => {
    const result = runGsdTools(
      ['config-set', 'odoo.scope_levels', '["foundation","core"]'],
      tmpDir
    );
    assert.ok(result.success, `Set failed: ${result.error}`);

    const config = readConfig(tmpDir);
    assert.ok(Array.isArray(config.odoo.scope_levels), 'scope_levels should be an array');
    assert.deepStrictEqual(config.odoo.scope_levels, ['foundation', 'core']);
  });

  test('config without odoo block does not break existing config operations', () => {
    // Existing config has no odoo block -- verify standard operations still work
    const set = runGsdTools('config-set model_profile quality', tmpDir);
    assert.ok(set.success, `Set failed: ${set.error}`);

    const get = runGsdTools('config-get model_profile', tmpDir);
    assert.ok(get.success, `Get failed: ${get.error}`);
    assert.strictEqual(JSON.parse(get.output), 'quality');
  });
});
