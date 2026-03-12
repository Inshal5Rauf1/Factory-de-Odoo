'use strict';

const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { runAmilTools, createTempProject, cleanup } = require('./helpers.cjs');

describe('dependency-graph', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  /**
   * Helper: initialize modules with dependencies via CLI,
   * then return the dep-graph order.
   */
  function initModules(modules) {
    for (const [name, { tier, depends }] of Object.entries(modules)) {
      const depsJson = JSON.stringify(depends || []);
      runAmilTools(
        ['module-status', 'init', name, tier || 'foundation', depsJson, '--raw'],
        tmpDir
      );
    }
  }

  // ─── Topological sort ─────────────────────────────────────────────────────

  describe('topological sort', () => {
    it('linear chain A->B->C produces order with dependencies first', () => {
      initModules({
        mod_c: { tier: 'foundation', depends: [] },
        mod_b: { tier: 'core', depends: ['mod_c'] },
        mod_a: { tier: 'operations', depends: ['mod_b'] },
      });

      const r = runAmilTools(['dep-graph', 'order', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const order = JSON.parse(r.output);
      const idxC = order.indexOf('mod_c');
      const idxB = order.indexOf('mod_b');
      const idxA = order.indexOf('mod_a');
      assert.ok(idxC < idxB, 'mod_c should come before mod_b');
      assert.ok(idxB < idxA, 'mod_b should come before mod_a');
    });

    it('diamond A->B, A->C, B->D, C->D produces valid order with D first', () => {
      initModules({
        mod_d: { tier: 'foundation', depends: [] },
        mod_b: { tier: 'core', depends: ['mod_d'] },
        mod_c: { tier: 'core', depends: ['mod_d'] },
        mod_a: { tier: 'operations', depends: ['mod_b', 'mod_c'] },
      });

      const r = runAmilTools(['dep-graph', 'order', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const order = JSON.parse(r.output);
      const idxD = order.indexOf('mod_d');
      const idxB = order.indexOf('mod_b');
      const idxC = order.indexOf('mod_c');
      const idxA = order.indexOf('mod_a');
      assert.ok(idxD < idxB, 'mod_d before mod_b');
      assert.ok(idxD < idxC, 'mod_d before mod_c');
      assert.ok(idxB < idxA, 'mod_b before mod_a');
      assert.ok(idxC < idxA, 'mod_c before mod_a');
    });

    it('independent modules can appear in any order', () => {
      initModules({
        mod_a: { tier: 'foundation', depends: [] },
        mod_b: { tier: 'foundation', depends: [] },
      });

      const r = runAmilTools(['dep-graph', 'order', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const order = JSON.parse(r.output);
      assert.equal(order.length, 2);
      assert.ok(order.includes('mod_a'));
      assert.ok(order.includes('mod_b'));
    });

    it('empty module set returns empty array', () => {
      const r = runAmilTools(['dep-graph', 'order', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const order = JSON.parse(r.output);
      assert.deepEqual(order, []);
    });
  });

  // ─── Circular dependency detection ────────────────────────────────────────

  describe('circular dependency detection', () => {
    it('A->B->A throws with message containing both module names', () => {
      initModules({
        mod_a: { tier: 'foundation', depends: ['mod_b'] },
        mod_b: { tier: 'foundation', depends: ['mod_a'] },
      });

      const r = runAmilTools(['dep-graph', 'order', '--raw'], tmpDir);
      assert.equal(r.success, false);
      assert.ok(r.error.includes('mod_a'), 'Error should mention mod_a');
      assert.ok(r.error.includes('mod_b'), 'Error should mention mod_b');
    });

    it('A->B->C->A throws with message containing cycle path', () => {
      initModules({
        mod_a: { tier: 'foundation', depends: ['mod_c'] },
        mod_b: { tier: 'foundation', depends: ['mod_a'] },
        mod_c: { tier: 'foundation', depends: ['mod_b'] },
      });

      const r = runAmilTools(['dep-graph', 'order', '--raw'], tmpDir);
      assert.equal(r.success, false);
      assert.ok(r.error.includes('Circular'), 'Error should mention circular');
    });

    it('self-dependency A->A throws', () => {
      initModules({
        mod_a: { tier: 'foundation', depends: ['mod_a'] },
      });

      const r = runAmilTools(['dep-graph', 'order', '--raw'], tmpDir);
      assert.equal(r.success, false);
      assert.ok(r.error.includes('mod_a'), 'Error should mention mod_a');
    });
  });

  // ─── Tier grouping ────────────────────────────────────────────────────────

  describe('tier grouping', () => {
    it('modules with no deps -> tier "foundation" (depth 0)', () => {
      initModules({
        mod_a: { tier: 'foundation', depends: [] },
      });

      const r = runAmilTools(['dep-graph', 'tiers', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.ok(data.tiers.foundation.includes('mod_a'));
    });

    it('modules depending on foundation -> tier "core" (depth 1)', () => {
      initModules({
        mod_base: { tier: 'foundation', depends: [] },
        mod_child: { tier: 'core', depends: ['mod_base'] },
      });

      const r = runAmilTools(['dep-graph', 'tiers', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.ok(data.tiers.core.includes('mod_child'));
    });

    it('modules depending on core -> tier "operations" (depth 2)', () => {
      initModules({
        mod_base: { tier: 'foundation', depends: [] },
        mod_mid: { tier: 'core', depends: ['mod_base'] },
        mod_top: { tier: 'operations', depends: ['mod_mid'] },
      });

      const r = runAmilTools(['dep-graph', 'tiers', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.ok(data.tiers.operations.includes('mod_top'));
    });

    it('modules at depth 3+ -> tier "communication"', () => {
      initModules({
        mod_0: { tier: 'foundation', depends: [] },
        mod_1: { tier: 'core', depends: ['mod_0'] },
        mod_2: { tier: 'operations', depends: ['mod_1'] },
        mod_3: { tier: 'communication', depends: ['mod_2'] },
      });

      const r = runAmilTools(['dep-graph', 'tiers', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.ok(data.tiers.communication.includes('mod_3'));
    });
  });

  // ─── Generation blocking (DEPG-05) ───────────────────────────────────────

  describe('generation blocking', () => {
    it('module whose deps are all "generated" or beyond -> can generate', () => {
      initModules({
        mod_base: { tier: 'foundation', depends: [] },
        mod_child: { tier: 'core', depends: ['mod_base'] },
      });

      // Advance mod_base to generated
      runAmilTools(['module-status', 'transition', 'mod_base', 'spec_approved', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_base', 'generated', '--raw'], tmpDir);

      const r = runAmilTools(['dep-graph', 'can-generate', 'mod_child', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.can_generate, true);
      assert.deepEqual(data.blocked_by, []);
    });

    it('module with a dep still "planned" -> blocked', () => {
      initModules({
        mod_base: { tier: 'foundation', depends: [] },
        mod_child: { tier: 'core', depends: ['mod_base'] },
      });

      const r = runAmilTools(['dep-graph', 'can-generate', 'mod_child', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.can_generate, false);
      assert.ok(data.blocked_by.length > 0);
      assert.ok(data.blocked_by.some(b => b.module === 'mod_base'));
    });

    it('module with no deps -> always can generate', () => {
      initModules({
        mod_base: { tier: 'foundation', depends: [] },
      });

      const r = runAmilTools(['dep-graph', 'can-generate', 'mod_base', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.can_generate, true);
      assert.deepEqual(data.blocked_by, []);
    });
  });

  // ─── Build command ────────────────────────────────────────────────────────

  describe('build', () => {
    it('returns graph structure from module_status.json', () => {
      initModules({
        mod_a: { tier: 'foundation', depends: [] },
        mod_b: { tier: 'core', depends: ['mod_a'] },
      });

      const r = runAmilTools(['dep-graph', 'build', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.ok(data.modules);
      assert.deepEqual(data.modules.mod_a.depends, []);
      assert.deepEqual(data.modules.mod_b.depends, ['mod_a']);
    });
  });
});
