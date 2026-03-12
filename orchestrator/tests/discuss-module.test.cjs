'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

// ─── Constants ──────────────────────────────────────────────────────────────

const AGENTS_DIR = path.join(__dirname, '..', 'agents');
const COMMANDS_DIR = path.join(__dirname, '..', 'commands', 'amil');
const WORKFLOWS_DIR = path.join(__dirname, '..', 'amil', 'workflows');
const REFERENCES_DIR = path.join(__dirname, '..', 'amil', 'references');

const MODULE_TYPES = [
  'core', 'student', 'fee', 'exam', 'faculty',
  'hr', 'timetable', 'notification', 'portal', 'generic'
];

const KNOWN_PREFIXES = {
  'uni_core': 'core',
  'uni_student': 'student',
  'uni_fee': 'fee',
  'uni_exam': 'exam',
  'uni_faculty': 'faculty',
  'uni_hr': 'hr',
  'uni_timetable': 'timetable',
  'uni_notification': 'notification',
  'uni_portal': 'portal'
};

// ─── Type Detection Helper (mirrors workflow logic) ─────────────────────────

function detectModuleType(moduleName) {
  const TYPES = {
    'uni_core': 'core', 'uni_student': 'student', 'uni_fee': 'fee',
    'uni_exam': 'exam', 'uni_faculty': 'faculty', 'uni_hr': 'hr',
    'uni_timetable': 'timetable', 'uni_notification': 'notification',
    'uni_portal': 'portal'
  };
  if (TYPES[moduleName]) return TYPES[moduleName];
  for (const [prefix, type] of Object.entries(TYPES)) {
    if (moduleName.startsWith(prefix + '_')) return type;
  }
  return null;
}

// ─── TMPL: module-questions.json schema ─────────────────────────────────────

describe('TMPL: module-questions.json schema', () => {
  const questionsPath = path.join(REFERENCES_DIR, 'module-questions.json');

  it('module-questions.json exists and is valid JSON', () => {
    assert.ok(fs.existsSync(questionsPath), 'module-questions.json must exist');
    const raw = fs.readFileSync(questionsPath, 'utf-8');
    const parsed = JSON.parse(raw);
    assert.equal(typeof parsed, 'object', 'must parse to an object');
  });

  it('contains all 10 module types', () => {
    const data = JSON.parse(fs.readFileSync(questionsPath, 'utf-8'));
    const keys = Object.keys(data);
    for (const type of MODULE_TYPES) {
      assert.ok(keys.includes(type), `missing type: ${type}`);
    }
    assert.equal(keys.length, 10, 'must have exactly 10 types');
  });

  it('each type has 8-12 questions', () => {
    const data = JSON.parse(fs.readFileSync(questionsPath, 'utf-8'));
    for (const type of MODULE_TYPES) {
      const questions = data[type].questions;
      assert.ok(Array.isArray(questions), `${type}.questions must be an array`);
      assert.ok(
        questions.length >= 8 && questions.length <= 12,
        `${type} has ${questions.length} questions (expected 8-12)`
      );
    }
  });

  it('each question has required fields (id, question, context)', () => {
    const data = JSON.parse(fs.readFileSync(questionsPath, 'utf-8'));
    for (const type of MODULE_TYPES) {
      for (const q of data[type].questions) {
        assert.ok(typeof q.id === 'string' && q.id.length > 0, `${type}: question missing id`);
        assert.ok(typeof q.question === 'string' && q.question.length > 0, `${type}: question missing question text`);
        assert.ok(typeof q.context === 'string' && q.context.length > 0, `${type}: question missing context`);
      }
    }
  });

  it('each question id is unique within its type', () => {
    const data = JSON.parse(fs.readFileSync(questionsPath, 'utf-8'));
    for (const type of MODULE_TYPES) {
      const ids = data[type].questions.map(q => q.id);
      const uniqueIds = new Set(ids);
      assert.equal(ids.length, uniqueIds.size, `${type} has duplicate question ids`);
    }
  });

  it('each type has context_hints array', () => {
    const data = JSON.parse(fs.readFileSync(questionsPath, 'utf-8'));
    for (const type of MODULE_TYPES) {
      assert.ok(
        Array.isArray(data[type].context_hints),
        `${type} missing context_hints array`
      );
    }
  });
});

// ─── TYPE: module type detection ────────────────────────────────────────────

describe('TYPE: module type detection', () => {
  it('detects correct type for all 9 known exact prefixes', () => {
    for (const [name, expectedType] of Object.entries(KNOWN_PREFIXES)) {
      assert.equal(
        detectModuleType(name),
        expectedType,
        `${name} should detect as ${expectedType}`
      );
    }
  });

  it('detects type for sub-module names (prefix + underscore)', () => {
    assert.equal(detectModuleType('uni_fee_structure'), 'fee');
    assert.equal(detectModuleType('uni_student_portal'), 'student');
    assert.equal(detectModuleType('uni_exam_grading'), 'exam');
  });

  it('returns null for unknown module names', () => {
    assert.equal(detectModuleType('custom_thing'), null);
    assert.equal(detectModuleType('my_module'), null);
    assert.equal(detectModuleType('something_else'), null);
  });
});

// ─── CMD: discuss-module command ────────────────────────────────────────────

describe('CMD: discuss-module command', () => {
  const commandPath = path.join(COMMANDS_DIR, 'discuss-module.md');

  it('discuss-module command file exists', () => {
    assert.ok(fs.existsSync(commandPath), 'commands/amil/discuss-module.md must exist');
  });

  it('has correct name in frontmatter', () => {
    const content = fs.readFileSync(commandPath, 'utf-8');
    assert.ok(
      content.includes('name: amil:discuss-module'),
      'command must have name: amil:discuss-module'
    );
  });

  it('has Task and AskUserQuestion in allowed-tools', () => {
    const content = fs.readFileSync(commandPath, 'utf-8');
    assert.ok(content.includes('Task'), 'allowed-tools must include Task');
    assert.ok(content.includes('AskUserQuestion'), 'allowed-tools must include AskUserQuestion');
  });
});

// ─── WF: discuss-module workflow ────────────────────────────────────────────

describe('WF: discuss-module workflow', () => {
  const workflowPath = path.join(WORKFLOWS_DIR, 'discuss-module.md');

  it('discuss-module workflow file exists', () => {
    assert.ok(fs.existsSync(workflowPath), 'amil/workflows/discuss-module.md must exist');
  });

  it('references the questioner agent', () => {
    const content = fs.readFileSync(workflowPath, 'utf-8');
    assert.ok(
      content.includes('amil-module-questioner'),
      'workflow must reference amil-module-questioner agent'
    );
  });
});

// ─── AGNT: questioner agent ─────────────────────────────────────────────────

describe('AGNT: questioner agent', () => {
  const agentPath = path.join(AGENTS_DIR, 'amil-module-questioner.md');

  it('questioner agent file exists', () => {
    assert.ok(fs.existsSync(agentPath), 'agents/amil-module-questioner.md must exist');
  });

  it('has AskUserQuestion in tools', () => {
    const content = fs.readFileSync(agentPath, 'utf-8');
    assert.ok(
      content.includes('AskUserQuestion'),
      'questioner agent must have AskUserQuestion in tools'
    );
  });

  it('has skills field in frontmatter', () => {
    const content = fs.readFileSync(agentPath, 'utf-8');
    const frontmatter = content.split('---')[1] || '';
    assert.ok(
      frontmatter.includes('skills:'),
      'questioner agent must have skills: in frontmatter'
    );
  });
});

// ─── AGNT: enhanced researcher ──────────────────────────────────────────────

describe('AGNT: enhanced researcher', () => {
  const researcherPath = path.join(AGENTS_DIR, 'amil-module-researcher.md');

  it('researcher agent file exists', () => {
    assert.ok(fs.existsSync(researcherPath), 'agents/amil-module-researcher.md must exist');
  });

  it('contains field type section', () => {
    const content = fs.readFileSync(researcherPath, 'utf-8').toLowerCase();
    assert.ok(
      content.includes('field type'),
      'researcher agent must contain field type section'
    );
  });

  it('contains security pattern section', () => {
    const content = fs.readFileSync(researcherPath, 'utf-8').toLowerCase();
    assert.ok(
      content.includes('security pattern'),
      'researcher agent must contain security pattern section'
    );
  });

  it('contains view inheritance section', () => {
    const content = fs.readFileSync(researcherPath, 'utf-8').toLowerCase();
    assert.ok(
      content.includes('view inheritance'),
      'researcher agent must contain view inheritance section'
    );
  });
});
