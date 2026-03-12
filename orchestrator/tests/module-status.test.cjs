'use strict';

const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const { runAmilTools, createTempProject, cleanup } = require('./helpers.cjs');

describe('module-status', () => {
  let tmpDir;

  beforeEach(() => {
    tmpDir = createTempProject();
  });

  afterEach(() => {
    cleanup(tmpDir);
  });

  // ─── Status read ──────────────────────────────────────────────────────────

  describe('read', () => {
    it('returns empty structure when no module_status.json exists', () => {
      const r = runAmilTools(['module-status', 'read', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.deepEqual(data.modules, {});
      assert.deepEqual(data.tiers, {});
      assert.equal(data._meta.version, 0);
    });
  });

  // ─── Module init ──────────────────────────────────────────────────────────

  describe('init', () => {
    it('creates module entry with status "planned"', () => {
      const r = runAmilTools(
        ['module-status', 'init', 'university_student', 'foundation', '[]', '--raw'],
        tmpDir
      );
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.modules.university_student.status, 'planned');
      assert.equal(data.modules.university_student.tier, 'foundation');
      assert.deepEqual(data.modules.university_student.depends, []);
    });

    it('creates artifact directory with CONTEXT.md placeholder', () => {
      runAmilTools(
        ['module-status', 'init', 'university_student', 'foundation', '[]', '--raw'],
        tmpDir
      );
      const contextPath = path.join(tmpDir, '.planning', 'modules', 'university_student', 'CONTEXT.md');
      assert.equal(fs.existsSync(contextPath), true);
      const content = fs.readFileSync(contextPath, 'utf-8');
      assert.ok(content.includes('university_student'));
    });

    it('returns error when module already exists', () => {
      runAmilTools(
        ['module-status', 'init', 'university_student', 'foundation', '[]', '--raw'],
        tmpDir
      );
      const r = runAmilTools(
        ['module-status', 'init', 'university_student', 'foundation', '[]', '--raw'],
        tmpDir
      );
      assert.equal(r.success, false);
      assert.ok(r.error.includes('already exists'));
    });
  });

  // ─── Status transitions ──────────────────────────────────────────────────

  describe('transitions', () => {
    beforeEach(() => {
      runAmilTools(
        ['module-status', 'init', 'test_mod', 'foundation', '[]', '--raw'],
        tmpDir
      );
    });

    it('planned -> spec_approved succeeds', () => {
      const r = runAmilTools(
        ['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'],
        tmpDir
      );
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.modules.test_mod.status, 'spec_approved');
    });

    it('planned -> generated throws invalid transition', () => {
      const r = runAmilTools(
        ['module-status', 'transition', 'test_mod', 'generated', '--raw'],
        tmpDir
      );
      assert.equal(r.success, false);
      assert.ok(r.error.includes('Invalid transition'));
    });

    it('spec_approved -> generated succeeds', () => {
      runAmilTools(['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'], tmpDir);
      const r = runAmilTools(
        ['module-status', 'transition', 'test_mod', 'generated', '--raw'],
        tmpDir
      );
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.modules.test_mod.status, 'generated');
    });

    it('spec_approved -> planned succeeds (re-plan allowed)', () => {
      runAmilTools(['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'], tmpDir);
      const r = runAmilTools(
        ['module-status', 'transition', 'test_mod', 'planned', '--raw'],
        tmpDir
      );
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.modules.test_mod.status, 'planned');
    });

    it('generated -> checked succeeds', () => {
      runAmilTools(['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'test_mod', 'generated', '--raw'], tmpDir);
      const r = runAmilTools(
        ['module-status', 'transition', 'test_mod', 'checked', '--raw'],
        tmpDir
      );
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.modules.test_mod.status, 'checked');
    });

    it('generated -> spec_approved succeeds (revise allowed)', () => {
      runAmilTools(['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'test_mod', 'generated', '--raw'], tmpDir);
      const r = runAmilTools(
        ['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'],
        tmpDir
      );
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.modules.test_mod.status, 'spec_approved');
    });

    it('checked -> shipped succeeds', () => {
      runAmilTools(['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'test_mod', 'generated', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'test_mod', 'checked', '--raw'], tmpDir);
      const r = runAmilTools(
        ['module-status', 'transition', 'test_mod', 'shipped', '--raw'],
        tmpDir
      );
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.modules.test_mod.status, 'shipped');
    });

    it('shipped -> anything throws invalid transition', () => {
      runAmilTools(['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'test_mod', 'generated', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'test_mod', 'checked', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'test_mod', 'shipped', '--raw'], tmpDir);
      const r = runAmilTools(
        ['module-status', 'transition', 'test_mod', 'planned', '--raw'],
        tmpDir
      );
      assert.equal(r.success, false);
      assert.ok(r.error.includes('Invalid transition'));
    });

    it('nonexistent module defaults to planned status on read', () => {
      const r = runAmilTools(
        ['module-status', 'get', 'nonexistent', '--raw'],
        tmpDir
      );
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.status, 'planned');
    });
  });

  // ─── Tier computation ─────────────────────────────────────────────────────

  describe('tiers', () => {
    it('tier with all modules shipped has status "complete"', () => {
      runAmilTools(['module-status', 'init', 'mod_a', 'foundation', '[]', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_a', 'spec_approved', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_a', 'generated', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_a', 'checked', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_a', 'shipped', '--raw'], tmpDir);

      const r = runAmilTools(['module-status', 'tiers', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.tiers.foundation.status, 'complete');
    });

    it('tier with any module not shipped has status "incomplete"', () => {
      runAmilTools(['module-status', 'init', 'mod_a', 'foundation', '[]', '--raw'], tmpDir);
      runAmilTools(['module-status', 'init', 'mod_b', 'foundation', '[]', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_a', 'spec_approved', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_a', 'generated', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_a', 'checked', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_a', 'shipped', '--raw'], tmpDir);

      const r = runAmilTools(['module-status', 'tiers', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.tiers.foundation.status, 'incomplete');
    });

    it('tier reports count by status', () => {
      runAmilTools(['module-status', 'init', 'mod_a', 'core', '[]', '--raw'], tmpDir);
      runAmilTools(['module-status', 'init', 'mod_b', 'core', '[]', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'mod_a', 'spec_approved', '--raw'], tmpDir);

      const r = runAmilTools(['module-status', 'tiers', '--raw'], tmpDir);
      assert.equal(r.success, true);
      const data = JSON.parse(r.output);
      assert.equal(data.tiers.core.counts.planned, 1);
      assert.equal(data.tiers.core.counts.spec_approved, 1);
    });
  });

  // ─── Atomic writes ────────────────────────────────────────────────────────

  describe('atomic writes', () => {
    it('status transition creates .bak before writing', () => {
      runAmilTools(['module-status', 'init', 'test_mod', 'foundation', '[]', '--raw'], tmpDir);
      runAmilTools(['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'], tmpDir);
      const bakPath = path.join(tmpDir, '.planning', 'module_status.json.bak');
      assert.equal(fs.existsSync(bakPath), true);
    });

    it('version increments on each transition', () => {
      runAmilTools(['module-status', 'init', 'test_mod', 'foundation', '[]', '--raw'], tmpDir);
      const r1 = runAmilTools(['module-status', 'read', '--raw'], tmpDir);
      const v1 = JSON.parse(r1.output)._meta.version;

      runAmilTools(['module-status', 'transition', 'test_mod', 'spec_approved', '--raw'], tmpDir);
      const r2 = runAmilTools(['module-status', 'read', '--raw'], tmpDir);
      const v2 = JSON.parse(r2.output)._meta.version;

      assert.ok(v2 > v1, `Expected version ${v2} > ${v1}`);
    });
  });
});
