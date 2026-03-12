/**
 * Amil Tools Tests - generate-module belt integration
 *
 * Tests for: command file structure, workflow file structure,
 * belt executor agent frontmatter, belt verifier agent frontmatter.
 *
 * Requirements: BELT-01 through BELT-07, AGNT-05
 */

const { test, describe } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const CMD_PATH = path.join(__dirname, '..', 'commands', 'amil', 'generate-module.md');
const WORKFLOW_PATH = path.join(__dirname, '..', 'amil', 'workflows', 'generate-module.md');
const BELT_EXECUTOR_PATH = path.join(__dirname, '..', 'agents', 'amil-belt-executor.md');
const BELT_VERIFIER_PATH = path.join(__dirname, '..', 'agents', 'amil-belt-verifier.md');

// ─── Command File Tests (BELT-01) ──────────────────────────────────────────

describe('BELT-CMD: generate-module command file structure', () => {
  const content = fs.readFileSync(CMD_PATH, 'utf-8');

  test('command file exists', () => {
    assert.ok(fs.existsSync(CMD_PATH), 'generate-module.md should exist');
  });

  test('frontmatter contains name field', () => {
    assert.ok(content.includes('name: amil:generate-module'), 'should have correct name');
  });

  test('frontmatter contains description', () => {
    assert.ok(content.includes('description:'), 'should have description');
  });

  test('frontmatter contains argument-hint', () => {
    assert.ok(content.includes('argument-hint:'), 'should have argument-hint');
    assert.ok(content.includes('module_name'), 'argument-hint should reference module_name');
  });

  test('allowed-tools includes Task for agent spawning', () => {
    assert.ok(content.includes('Task'), 'should allow Task tool for agent spawning');
  });

  test('allowed-tools includes Bash for CLI operations', () => {
    assert.ok(content.includes('Bash'), 'should allow Bash tool');
  });

  test('references generate-module workflow', () => {
    assert.ok(
      content.includes('generate-module.md'),
      'should reference the generate-module workflow'
    );
  });

  test('mentions spec_approved as prerequisite', () => {
    assert.ok(content.includes('spec_approved'), 'should mention spec_approved status');
  });
});

// ─── Workflow File Tests (BELT-02,03) ────────────────────────────────────────

describe('BELT-WF: generate-module workflow structure', () => {
  const content = fs.readFileSync(WORKFLOW_PATH, 'utf-8');

  test('workflow file exists', () => {
    assert.ok(fs.existsSync(WORKFLOW_PATH), 'generate-module.md workflow should exist');
  });

  test('has 10 steps', () => {
    const stepMatches = content.match(/^## Step \d+/gm);
    assert.ok(stepMatches, 'should have numbered steps');
    assert.strictEqual(stepMatches.length, 11, 'should have 11 steps (10 + Step 10.5 persistent Docker)');
  });

  test('Step 1 validates module status', () => {
    assert.ok(content.includes('module-status get'), 'Step 1 should check module status');
    assert.ok(content.includes('spec_approved'), 'should check for spec_approved');
  });

  test('Step 2 loads spec.json', () => {
    assert.ok(content.includes('spec.json'), 'should reference spec.json');
  });

  test('Step 5 spawns belt executor via Task()', () => {
    assert.ok(content.includes('amil-belt-executor'), 'should spawn belt executor agent');
    assert.ok(content.includes('Task('), 'should use Task() for agent spawning');
  });

  test('Step 7 updates model registry', () => {
    assert.ok(content.includes('updateFromSpec'), 'should use updateFromSpec for registry');
  });

  test('Step 9 spawns belt verifier via Task()', () => {
    assert.ok(content.includes('amil-belt-verifier'), 'should spawn belt verifier agent');
  });

  test('Step 10 transitions to generated status', () => {
    assert.ok(content.includes('module-status transition'), 'should transition module status');
    assert.ok(content.includes('generated'), 'should transition to generated');
  });

  test('includes retry/revise/abort error handling', () => {
    assert.ok(content.includes('retry'), 'should have retry option');
    assert.ok(content.includes('revise'), 'should have revise option');
    assert.ok(content.includes('abort'), 'should have abort option');
  });

  test('includes git commit step', () => {
    assert.ok(content.includes('git commit'), 'should include git commit');
    assert.ok(content.includes('git add'), 'should include git add');
  });
});

// ─── Belt Executor Agent Tests (BELT-03) ─────────────────────────────────────

describe('BELT-EXEC: belt executor agent frontmatter', () => {
  const content = fs.readFileSync(BELT_EXECUTOR_PATH, 'utf-8');

  test('agent file exists', () => {
    assert.ok(fs.existsSync(BELT_EXECUTOR_PATH), 'belt-executor.md should exist');
  });

  test('has correct name', () => {
    assert.ok(content.includes('name: amil-belt-executor'), 'should have correct name');
  });

  test('has tools including Bash for CLI execution', () => {
    assert.ok(content.includes('Bash'), 'should have Bash tool for CLI execution');
  });

  test('mentions render-module CLI command', () => {
    assert.ok(content.includes('render-module'), 'should reference render-module CLI');
  });

  test('mentions generation-report.json output', () => {
    assert.ok(content.includes('generation-report.json'), 'should produce generation report');
  });

  test('has error handling section', () => {
    assert.ok(
      content.includes('error_handling') || content.includes('Error') || content.includes('failure'),
      'should have error handling'
    );
  });
});

// ─── Belt Verifier Agent Tests (AGNT-05) ─────────────────────────────────────

describe('BELT-VERIFY: belt verifier agent frontmatter', () => {
  const content = fs.readFileSync(BELT_VERIFIER_PATH, 'utf-8');

  test('agent file exists', () => {
    assert.ok(fs.existsSync(BELT_VERIFIER_PATH), 'belt-verifier.md should exist');
  });

  test('has correct name', () => {
    assert.ok(content.includes('name: amil-belt-verifier'), 'should have correct name');
  });

  test('checks __manifest__.py', () => {
    assert.ok(content.includes('__manifest__.py'), 'should check for manifest file');
  });

  test('checks security CSV', () => {
    assert.ok(content.includes('ir.model.access.csv'), 'should check for security CSV');
  });

  test('checks for placeholder content', () => {
    assert.ok(
      content.includes('TODO') || content.includes('PLACEHOLDER') || content.includes('placeholder'),
      'should check for placeholder content'
    );
  });

  test('mentions verification-report.json output', () => {
    assert.ok(content.includes('verification-report.json'), 'should produce verification report');
  });
});
