/**
 * Amil Agent Frontmatter Tests
 *
 * Validates that all agent .md files have correct frontmatter fields:
 * - Anti-heredoc instruction present in file-writing agents
 * - skills: field in all agents
 * - Commented hooks: pattern in file-writing agents
 * - Spawn type consistency across workflows
 */

const { test, describe } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const AGENTS_DIR = path.join(__dirname, '..', 'agents');
const WORKFLOWS_DIR = path.join(__dirname, '..', 'amil', 'workflows');
const COMMANDS_DIR = path.join(__dirname, '..', 'commands', 'amil');

const ALL_AGENTS = fs.readdirSync(AGENTS_DIR)
  .filter(f => f.startsWith('amil-') && f.endsWith('.md'))
  .map(f => f.replace('.md', ''));

const FILE_WRITING_AGENTS = ALL_AGENTS.filter(name => {
  const content = fs.readFileSync(path.join(AGENTS_DIR, name + '.md'), 'utf-8');
  const toolsMatch = content.match(/^tools:\s*(.+)$/m);
  return toolsMatch && toolsMatch[1].includes('Write');
});

const READ_ONLY_AGENTS = ALL_AGENTS.filter(name => !FILE_WRITING_AGENTS.includes(name));

// ─── Anti-Heredoc Instruction ────────────────────────────────────────────────

describe('HDOC: anti-heredoc instruction', () => {
  for (const agent of FILE_WRITING_AGENTS) {
    test(`${agent} has anti-heredoc instruction`, () => {
      const content = fs.readFileSync(path.join(AGENTS_DIR, agent + '.md'), 'utf-8');
      assert.ok(
        content.includes("never use `Bash(cat << 'EOF')` or heredoc"),
        `${agent} missing anti-heredoc instruction`
      );
    });
  }

  test('no active heredoc patterns in any agent file', () => {
    for (const agent of ALL_AGENTS) {
      const content = fs.readFileSync(path.join(AGENTS_DIR, agent + '.md'), 'utf-8');
      // Match actual heredoc commands (not references in anti-heredoc instruction)
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        // Skip lines that are part of the anti-heredoc instruction or markdown code fences
        if (line.includes('never use') || line.includes('NEVER') || line.trim().startsWith('```')) continue;
        // Check for actual heredoc usage instructions
        if (/^cat\s+<<\s*'?EOF'?\s*>/.test(line.trim())) {
          assert.fail(`${agent}:${i + 1} has active heredoc pattern: ${line.trim()}`);
        }
      }
    }
  });
});

// ─── Skills Frontmatter ──────────────────────────────────────────────────────

describe('SKILL: skills frontmatter', () => {
  for (const agent of ALL_AGENTS) {
    test(`${agent} has skills: in frontmatter`, () => {
      const content = fs.readFileSync(path.join(AGENTS_DIR, agent + '.md'), 'utf-8');
      const frontmatter = content.split('---')[1] || '';
      assert.ok(
        frontmatter.includes('skills:'),
        `${agent} missing skills: in frontmatter`
      );
    });
  }

  test('skill references follow naming convention', () => {
    for (const agent of ALL_AGENTS) {
      const content = fs.readFileSync(path.join(AGENTS_DIR, agent + '.md'), 'utf-8');
      const frontmatter = content.split('---')[1] || '';
      const skillLines = frontmatter.split('\n').filter(l => l.trim().startsWith('- amil-'));
      for (const line of skillLines) {
        const skillName = line.trim().replace('- ', '');
        assert.match(skillName, /^amil-[\w-]+-workflow$/, `Invalid skill name: ${skillName}`);
      }
    }
  });
});

// ─── Hooks Frontmatter ───────────────────────────────────────────────────────

describe('HOOK: hooks frontmatter pattern', () => {
  for (const agent of FILE_WRITING_AGENTS) {
    test(`${agent} has commented hooks pattern`, () => {
      const content = fs.readFileSync(path.join(AGENTS_DIR, agent + '.md'), 'utf-8');
      const frontmatter = content.split('---')[1] || '';
      assert.ok(
        frontmatter.includes('# hooks:'),
        `${agent} missing commented hooks: pattern in frontmatter`
      );
    });
  }

  for (const agent of READ_ONLY_AGENTS) {
    test(`${agent} (read-only) does not need hooks`, () => {
      const content = fs.readFileSync(path.join(AGENTS_DIR, agent + '.md'), 'utf-8');
      const frontmatter = content.split('---')[1] || '';
      // Read-only agents may or may not have hooks — just verify they parse
      assert.ok(frontmatter.includes('name:'), `${agent} has valid frontmatter`);
    });
  }
});

// ─── Spawn Type Consistency ──────────────────────────────────────────────────

describe('SPAWN: spawn type consistency', () => {
  test('no "First, read agent .md" workaround pattern remains', () => {
    const dirs = [WORKFLOWS_DIR, COMMANDS_DIR];
    for (const dir of dirs) {
      if (!fs.existsSync(dir)) continue;
      const files = fs.readdirSync(dir).filter(f => f.endsWith('.md'));
      for (const file of files) {
        const content = fs.readFileSync(path.join(dir, file), 'utf-8');
        const hasWorkaround = content.includes('First, read ~/.claude/agents/amil-');
        assert.ok(
          !hasWorkaround,
          `${file} still has "First, read agent .md" workaround — use named subagent_type instead`
        );
      }
    }
  });

  test('named agent spawns use correct agent names', () => {
    const validAgentTypes = new Set([
      ...ALL_AGENTS,
      'general-purpose',  // Allowed for orchestrator spawns
    ]);

    const dirs = [WORKFLOWS_DIR, COMMANDS_DIR];
    for (const dir of dirs) {
      if (!fs.existsSync(dir)) continue;
      const files = fs.readdirSync(dir).filter(f => f.endsWith('.md'));
      for (const file of files) {
        const content = fs.readFileSync(path.join(dir, file), 'utf-8');
        const matches = content.matchAll(/subagent_type="([^"]+)"/g);
        for (const match of matches) {
          const agentType = match[1];
          assert.ok(
            validAgentTypes.has(agentType),
            `${file} references unknown agent type: ${agentType}`
          );
        }
      }
    }
  });

  test('diagnose-issues uses amil-debugger (not general-purpose)', () => {
    const content = fs.readFileSync(
      path.join(WORKFLOWS_DIR, 'diagnose-issues.md'), 'utf-8'
    );
    assert.ok(
      content.includes('subagent_type="amil-debugger"'),
      'diagnose-issues should spawn amil-debugger, not general-purpose'
    );
  });
});

// ─── Required Frontmatter Fields ─────────────────────────────────────────────

describe('AGENT: required frontmatter fields', () => {
  for (const agent of ALL_AGENTS) {
    test(`${agent} has name, description, tools, color`, () => {
      const content = fs.readFileSync(path.join(AGENTS_DIR, agent + '.md'), 'utf-8');
      const frontmatter = content.split('---')[1] || '';
      assert.ok(frontmatter.includes('name:'), `${agent} missing name:`);
      assert.ok(frontmatter.includes('description:'), `${agent} missing description:`);
      assert.ok(frontmatter.includes('tools:'), `${agent} missing tools:`);
      assert.ok(frontmatter.includes('color:'), `${agent} missing color:`);
    });
  }
});

// ─── Spec Generator Agent ───────────────────────────────────────────────────

describe('SPEC-GEN: spec generator agent', () => {
  const SPEC_GEN_FILE = path.join(AGENTS_DIR, 'amil-spec-generator.md');

  test('amil-spec-generator.md exists', () => {
    assert.ok(fs.existsSync(SPEC_GEN_FILE), 'spec generator agent file missing');
  });

  test('frontmatter has name containing spec-generator', () => {
    const content = fs.readFileSync(SPEC_GEN_FILE, 'utf-8');
    const frontmatter = content.split('---')[1] || '';
    assert.ok(
      frontmatter.includes('name: amil-spec-generator') || frontmatter.includes("name: 'amil-spec-generator'"),
      'spec generator name field must contain spec-generator'
    );
  });

  test('frontmatter has description', () => {
    const content = fs.readFileSync(SPEC_GEN_FILE, 'utf-8');
    const frontmatter = content.split('---')[1] || '';
    assert.ok(frontmatter.includes('description:'), 'spec generator missing description');
  });

  test('tools include Write (file-writing agent)', () => {
    const content = fs.readFileSync(SPEC_GEN_FILE, 'utf-8');
    const toolsMatch = content.match(/^tools:\s*(.+)$/m);
    assert.ok(toolsMatch, 'spec generator missing tools field');
    assert.ok(toolsMatch[1].includes('Write'), 'spec generator must have Write tool (produces spec.json)');
  });

  test('instructions mention all ModuleSpec metadata and content sections', () => {
    const content = fs.readFileSync(SPEC_GEN_FILE, 'utf-8');
    const requiredSections = [
      'module_name', 'module_title', 'odoo_version', 'depends',
      'models', 'business_rules', 'computation_chains', 'workflow',
      'view_hints', 'reports', 'notifications', 'cron_jobs',
      'security', 'portal', 'controllers'
    ];
    for (const section of requiredSections) {
      assert.ok(
        content.includes(section),
        `spec generator missing section reference: ${section}`
      );
    }
  });
});

// ─── Spec Reviewer Agent ────────────────────────────────────────────────────

describe('SPEC-REV: spec reviewer agent', () => {
  const SPEC_REV_FILE = path.join(AGENTS_DIR, 'amil-spec-reviewer.md');

  test('amil-spec-reviewer.md exists', () => {
    assert.ok(fs.existsSync(SPEC_REV_FILE), 'spec reviewer agent file missing');
  });

  test('frontmatter has name containing spec-reviewer', () => {
    const content = fs.readFileSync(SPEC_REV_FILE, 'utf-8');
    const frontmatter = content.split('---')[1] || '';
    assert.ok(
      frontmatter.includes('name: amil-spec-reviewer') || frontmatter.includes("name: 'amil-spec-reviewer'"),
      'spec reviewer name field must contain spec-reviewer'
    );
  });

  test('frontmatter has description', () => {
    const content = fs.readFileSync(SPEC_REV_FILE, 'utf-8');
    const frontmatter = content.split('---')[1] || '';
    assert.ok(frontmatter.includes('description:'), 'spec reviewer missing description');
  });

  test('tools do NOT include Write (read-only agent)', () => {
    const content = fs.readFileSync(SPEC_REV_FILE, 'utf-8');
    const toolsMatch = content.match(/^tools:\s*(.+)$/m);
    assert.ok(toolsMatch, 'spec reviewer missing tools field');
    assert.ok(
      !toolsMatch[1].includes('Write'),
      'spec reviewer must NOT have Write tool (read-only presentation agent)'
    );
  });

  test('instructions reference coherence report checks', () => {
    const content = fs.readFileSync(SPEC_REV_FILE, 'utf-8');
    const requiredChecks = [
      'many2one_targets', 'duplicate_models', 'computed_depends', 'security_groups'
    ];
    for (const check of requiredChecks) {
      assert.ok(
        content.includes(check),
        `spec reviewer missing coherence check reference: ${check}`
      );
    }
  });
});
