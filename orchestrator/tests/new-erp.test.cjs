'use strict';

const { describe, it, before } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const os = require('os');

// ─── Fixture data: 4 agent outputs for a small 4-module ERP ─────────────────

const FIXTURE_MODULE_BOUNDARIES = {
  modules: [
    { name: 'uni_core', description: 'Core institution models', models: ['uni.institution', 'uni.campus', 'uni.department', 'uni.program'], base_depends: ['base', 'mail'], estimated_complexity: 'medium' },
    { name: 'uni_student', description: 'Student management', models: ['uni.student', 'uni.enrollment'], base_depends: ['base', 'mail'], estimated_complexity: 'high' },
    { name: 'uni_fee', description: 'Fee and billing', models: ['uni.fee.structure', 'uni.fee.line'], base_depends: ['base', 'account'], estimated_complexity: 'high' },
    { name: 'uni_notification', description: 'Notification dispatch', models: ['uni.notification'], base_depends: ['base', 'mail', 'sms'], estimated_complexity: 'medium' }
  ]
};

const FIXTURE_OCA_ANALYSIS = {
  findings: [
    { domain: 'core', oca_module: null, odoo_module: 'uni_core', recommendation: 'build_new', reason: 'No OCA equivalent' },
    { domain: 'student', oca_module: null, odoo_module: 'uni_student', recommendation: 'build_new', reason: 'No OCA equivalent' },
    { domain: 'fee', oca_module: 'school_fee', odoo_module: 'uni_fee', recommendation: 'extend', reason: 'OCA school_fee covers basics' },
    { domain: 'notification', oca_module: null, odoo_module: 'uni_notification', recommendation: 'build_new', reason: 'Custom dispatch needed' }
  ]
};

const FIXTURE_DEPENDENCY_MAP = {
  dependencies: [
    { module: 'uni_core', depends_on: [], reason: 'Foundation module' },
    { module: 'uni_student', depends_on: ['uni_core'], reason: 'References institution and program' },
    { module: 'uni_fee', depends_on: ['uni_core', 'uni_student'], reason: 'Fee linked to student enrollment' },
    { module: 'uni_notification', depends_on: ['uni_core'], reason: 'Sends notifications for institution events' }
  ]
};

const FIXTURE_COMPUTATION_CHAINS = {
  chains: [
    { name: 'fee_calculation', description: 'Fee flows from program to enrollment', steps: ['uni_core.program.fee_structure', 'uni_student.enrollment.compute_fees', 'uni_fee.fee_line.calculate'], cross_module: true },
    { name: 'enrollment_notify', description: 'Enrollment triggers notification', steps: ['uni_student.enrollment.confirm', 'uni_notification.dispatch.send'], cross_module: true }
  ]
};

function writeFixtures(dir) {
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'module-boundaries.json'), JSON.stringify(FIXTURE_MODULE_BOUNDARIES));
  fs.writeFileSync(path.join(dir, 'oca-analysis.json'), JSON.stringify(FIXTURE_OCA_ANALYSIS));
  fs.writeFileSync(path.join(dir, 'dependency-map.json'), JSON.stringify(FIXTURE_DEPENDENCY_MAP));
  fs.writeFileSync(path.join(dir, 'computation-chains.json'), JSON.stringify(FIXTURE_COMPUTATION_CHAINS));
}

function makeTmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'new-erp-test-'));
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('decomposition.cjs', () => {
  let mergeDecomposition, formatDecompositionTable, generateRoadmapMarkdown;

  // Load module under test
  before(() => {
    const mod = require('../amil/bin/lib/decomposition.cjs');
    mergeDecomposition = mod.mergeDecomposition;
    formatDecompositionTable = mod.formatDecompositionTable;
    generateRoadmapMarkdown = mod.generateRoadmapMarkdown;
  });

  describe('mergeDecomposition', () => {
    it('reads 4 JSON files and produces valid decomposition', () => {
      const tmp = makeTmpDir();
      const researchDir = path.join(tmp, 'research');
      writeFixtures(researchDir);
      const result = mergeDecomposition(researchDir, tmp);
      assert.ok(result.modules, 'has modules');
      assert.ok(result.tiers, 'has tiers');
      assert.ok(result.generation_order, 'has generation_order');
      assert.ok(result.computation_chains, 'has computation_chains');
      assert.equal(result.modules.length, 4);
      // decomposition.json written
      assert.ok(fs.existsSync(path.join(researchDir, 'decomposition.json')));
      fs.rmSync(tmp, { recursive: true, force: true });
    });

    it('annotates modules with build_recommendation from OCA analysis', () => {
      const tmp = makeTmpDir();
      const researchDir = path.join(tmp, 'research');
      writeFixtures(researchDir);
      const result = mergeDecomposition(researchDir, tmp);
      const fee = result.modules.find(m => m.name === 'uni_fee');
      assert.equal(fee.build_recommendation, 'extend');
      assert.equal(fee.oca_module, 'school_fee');
      const core = result.modules.find(m => m.name === 'uni_core');
      assert.equal(core.build_recommendation, 'build_new');
      assert.equal(core.oca_module, null);
      fs.rmSync(tmp, { recursive: true, force: true });
    });

    it('extracts custom depends from dependency map, preserves base_depends', () => {
      const tmp = makeTmpDir();
      const researchDir = path.join(tmp, 'research');
      writeFixtures(researchDir);
      const result = mergeDecomposition(researchDir, tmp);
      const student = result.modules.find(m => m.name === 'uni_student');
      assert.deepEqual(student.custom_depends, ['uni_core']);
      assert.deepEqual(student.base_depends, ['base', 'mail']);
      const fee = result.modules.find(m => m.name === 'uni_fee');
      assert.deepEqual(fee.custom_depends, ['uni_core', 'uni_student']);
      fs.rmSync(tmp, { recursive: true, force: true });
    });

    it('runs topoSort on custom depends only (not base Odoo deps)', () => {
      const tmp = makeTmpDir();
      const researchDir = path.join(tmp, 'research');
      writeFixtures(researchDir);
      const result = mergeDecomposition(researchDir, tmp);
      // uni_core should come before uni_student in generation_order
      const coreIdx = result.generation_order.indexOf('uni_core');
      const studentIdx = result.generation_order.indexOf('uni_student');
      assert.ok(coreIdx < studentIdx, 'core before student');
      // base deps like "base", "mail" should NOT appear in generation_order
      assert.ok(!result.generation_order.includes('base'));
      assert.ok(!result.generation_order.includes('mail'));
      fs.rmSync(tmp, { recursive: true, force: true });
    });

    it('attaches computation chains to modules by step prefix matching', () => {
      const tmp = makeTmpDir();
      const researchDir = path.join(tmp, 'research');
      writeFixtures(researchDir);
      const result = mergeDecomposition(researchDir, tmp);
      const student = result.modules.find(m => m.name === 'uni_student');
      assert.ok(student.computation_chains.length >= 1);
      const fee = result.modules.find(m => m.name === 'uni_fee');
      assert.ok(fee.computation_chains.length >= 1);
      fs.rmSync(tmp, { recursive: true, force: true });
    });

    it('generates warnings for modules with unknown complexity', () => {
      const tmp = makeTmpDir();
      const researchDir = path.join(tmp, 'research');
      writeFixtures(researchDir);
      // Modify fixture to add unknown complexity
      const boundaries = JSON.parse(JSON.stringify(FIXTURE_MODULE_BOUNDARIES));
      boundaries.modules[0].estimated_complexity = 'unknown';
      fs.writeFileSync(path.join(researchDir, 'module-boundaries.json'), JSON.stringify(boundaries));
      const result = mergeDecomposition(researchDir, tmp);
      assert.ok(result.warnings.some(w => w.includes('unknown') && w.includes('uni_core')));
      fs.rmSync(tmp, { recursive: true, force: true });
    });
  });

  describe('formatDecompositionTable', () => {
    it('produces structured text with tiers and module counts', () => {
      const tmp = makeTmpDir();
      const researchDir = path.join(tmp, 'research');
      writeFixtures(researchDir);
      const decomp = mergeDecomposition(researchDir, tmp);
      const text = formatDecompositionTable(decomp);
      assert.ok(text.includes('ERP MODULE DECOMPOSITION'));
      assert.ok(text.includes('4 modules'));
      assert.ok(text.includes('TIER'));
      assert.ok(text.includes('uni_core'));
      assert.ok(text.includes('COMPUTATION CHAINS'));
      assert.ok(text.includes('Approve this decomposition?'));
      fs.rmSync(tmp, { recursive: true, force: true });
    });
  });

  describe('generateRoadmapMarkdown', () => {
    it('produces parseable ### Phase N: module_name format', () => {
      const tmp = makeTmpDir();
      const researchDir = path.join(tmp, 'research');
      writeFixtures(researchDir);
      const decomp = mergeDecomposition(researchDir, tmp);
      const md = generateRoadmapMarkdown(decomp);
      assert.ok(md.includes('### Phase 1: uni_core'));
      // uni_student should be phase 2
      assert.ok(/### Phase \d+: uni_student/.test(md));
      assert.ok(md.includes('- Tier:'));
      assert.ok(md.includes('- Models:'));
      assert.ok(md.includes('- Depends:'));
      assert.ok(md.includes('- Build:'));
      assert.ok(md.includes('- Status: not_started'));
      fs.rmSync(tmp, { recursive: true, force: true });
    });
  });
});
