/**
 * Plan-Module Structural Validation Tests
 *
 * Validates:
 * - Command file structure (SPEC-01)
 * - Workflow file 10-step completeness (SPEC-01)
 * - Spec schema section coverage (SPEC-03)
 * - Tiered registry injection references (SPEC-04)
 */

const { test, describe } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const CMD_PATH = path.join(__dirname, '..', 'commands', 'amil', 'plan-module.md');
const WORKFLOW_PATH = path.join(__dirname, '..', 'amil', 'workflows', 'plan-module.md');
const SPEC_GEN_PATH = path.join(__dirname, '..', 'agents', 'amil-spec-generator.md');

// ─── Command File Structure (SPEC-01) ──────────────────────────────────────

describe('PLAN-CMD: plan-module command file structure', () => {
  const content = fs.readFileSync(CMD_PATH, 'utf-8');

  test('command file exists', () => {
    assert.ok(fs.existsSync(CMD_PATH), 'commands/amil/plan-module.md should exist');
  });

  test('frontmatter contains name amil:plan-module', () => {
    assert.ok(
      content.includes('name: amil:plan-module'),
      'should have name: amil:plan-module in frontmatter'
    );
  });

  test('frontmatter contains argument-hint with module_name', () => {
    assert.ok(
      content.includes('module_name'),
      'should have argument-hint referencing module_name'
    );
  });

  test('references the workflow file', () => {
    assert.ok(
      content.includes('plan-module.md'),
      'should reference plan-module.md workflow'
    );
  });

  test('has allowed-tools including Task and AskUserQuestion', () => {
    assert.ok(content.includes('Task'), 'should list Task in allowed-tools');
    assert.ok(content.includes('AskUserQuestion'), 'should list AskUserQuestion in allowed-tools');
  });

  test('mentions next step generate-module', () => {
    assert.ok(
      content.includes('generate-module'),
      'should mention generate-module as next step'
    );
  });
});

// ─── Workflow File Structure (SPEC-01) ──────────────────────────────────────

describe('PLAN-WF: plan-module workflow 10-step completeness', () => {
  const content = fs.readFileSync(WORKFLOW_PATH, 'utf-8');

  test('workflow file exists', () => {
    assert.ok(fs.existsSync(WORKFLOW_PATH), 'amil/workflows/plan-module.md should exist');
  });

  test('contains all 10 steps', () => {
    for (let i = 1; i <= 10; i++) {
      assert.ok(
        content.includes(`Step ${i}:`),
        `should contain "Step ${i}:" heading`
      );
    }
  });

  test('Step 1 validates module status', () => {
    assert.ok(
      content.includes('module-status get'),
      'Step 1 should invoke module-status get CLI'
    );
  });

  test('references coherence check CLI invocation', () => {
    assert.ok(
      content.includes('coherence check'),
      'should reference coherence check CLI command'
    );
  });

  test('references spec-generator subagent_type', () => {
    assert.ok(
      content.includes('spec-generator'),
      'should reference amil-spec-generator subagent_type'
    );
  });

  test('references spec-reviewer subagent_type', () => {
    assert.ok(
      content.includes('spec-reviewer'),
      'should reference amil-spec-reviewer subagent_type'
    );
  });

  test('references module-status transition to spec_approved', () => {
    assert.ok(
      content.includes('module-status transition'),
      'should reference module-status transition CLI'
    );
    assert.ok(
      content.includes('spec_approved'),
      'should transition to spec_approved status'
    );
  });

  test('references researcher agent', () => {
    assert.ok(
      content.includes('module-researcher'),
      'should reference amil-module-researcher subagent_type'
    );
  });

  test('references decomposition.json', () => {
    assert.ok(
      content.includes('decomposition.json'),
      'should load decomposition.json for module metadata'
    );
  });

  test('references CONTEXT.md loading', () => {
    assert.ok(
      content.includes('CONTEXT.md'),
      'should load module CONTEXT.md'
    );
  });

  test('references RESEARCH.md', () => {
    assert.ok(
      content.includes('RESEARCH.md'),
      'should produce and read RESEARCH.md'
    );
  });

  test('has error handling for missing context', () => {
    assert.ok(
      content.includes('discuss-module'),
      'should suggest running discuss-module if CONTEXT.md is missing'
    );
  });

  test('has revise option looping back to researcher', () => {
    assert.ok(
      content.includes('revise'),
      'should offer revise option in approval step'
    );
    assert.ok(
      content.includes('Step 5'),
      'revise should reference going back to Step 5'
    );
  });
});

// ─── Spec Schema Coverage (SPEC-03) ────────────────────────────────────────

describe('PLAN-SCHEMA: spec.json 12-section coverage', () => {
  // Check in workflow OR spec generator agent (generator enforces schema)
  const workflowContent = fs.readFileSync(WORKFLOW_PATH, 'utf-8');
  const specGenContent = fs.readFileSync(SPEC_GEN_PATH, 'utf-8');
  const combined = workflowContent + '\n' + specGenContent;

  const SPEC_SECTIONS = [
    'module_name',
    'module_title',
    'odoo_version',
    'depends',
    'models',
    'business_rules',
    'computation_chains',
    'workflow',
    'view_hints',
    'reports',
    'notifications',
    'cron_jobs',
    'security',
    'portal',
    'controllers',
  ];

  for (const section of SPEC_SECTIONS) {
    test(`references spec section: ${section}`, () => {
      assert.ok(
        combined.includes(section),
        `workflow or spec-generator should reference "${section}" section`
      );
    });
  }
});

// ─── Tiered Registry Injection (SPEC-04) ────────────────────────────────────

describe('PLAN-REGISTRY: tiered registry injection', () => {
  const content = fs.readFileSync(WORKFLOW_PATH, 'utf-8');

  test('workflow mentions tiered registry injection step', () => {
    assert.ok(
      content.includes('tiered') || content.includes('Tiered'),
      'should mention tiered registry in workflow'
    );
  });

  test('workflow mentions _available_models', () => {
    assert.ok(
      content.includes('_available_models'),
      'should reference _available_models for registry context'
    );
  });

  test('workflow invokes registry tiered-injection CLI', () => {
    assert.ok(
      content.includes('registry tiered-injection'),
      'should invoke registry tiered-injection CLI command'
    );
  });

  test('handles empty registry for first module', () => {
    assert.ok(
      content.includes('"direct": {}') || content.includes("'direct': {}"),
      'should handle empty registry case with empty direct object'
    );
  });
});
