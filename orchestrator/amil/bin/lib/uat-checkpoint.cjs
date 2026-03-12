/**
 * UAT Checkpoint Manager — Tracks verification checkpoints and
 * generates verification checklists for live UAT sessions.
 */

const fs = require('fs');
const path = require('path');

const MODULE_NAME_RE = /^[a-z][a-z0-9_]*$/;

/**
 * Determine if a wave checkpoint is due.
 *
 * @param {string[]} installedModules - Modules in Docker
 * @param {number} lastCheckpointAt - Module count at last checkpoint
 * @param {number} interval - Modules between checkpoints (default 10)
 * @returns {boolean}
 */
function isCheckpointDue(installedModules, lastCheckpointAt, interval = 10) {
  return installedModules.length - lastCheckpointAt >= interval;
}

/**
 * Generate verification checklist for a set of modules.
 *
 * @param {Object[]} modules - Modules to verify (from decomposition/spec)
 * @param {Object} registry - Model registry for cross-module flow detection
 * @returns {Object} { perModule: [], crossModule: [] }
 */
function generateChecklist(modules, registry) {
  const perModule = [];
  const crossModule = [];

  for (const mod of modules) {
    const flows = [];

    // Generate flows based on module characteristics
    for (const model of (mod.models || [])) {
      // Workflow model → test state transitions
      if (mod.workflow?.some(w => w.model === model.name)) {
        const wf = mod.workflow.find(w => w.model === model.name);
        flows.push(
          `Create a ${model.description || model.name} → ` +
          `transition through states: ${wf.states.join(' → ')}`
        );
      }

      // Computed fields → test computation
      const computedFields = (model.fields || []).filter(f => f.compute);
      if (computedFields.length > 0) {
        flows.push(
          `Enter data → verify computed fields update: ` +
          computedFields.map(f => f.name).join(', ')
        );
      }
    }

    // Report → test generation
    if ((mod.reports || []).length > 0) {
      flows.push(`Generate report(s): ${mod.reports.map(r => r.name).join(', ')}`);
    }

    perModule.push({
      module: mod.module_name || mod.name,
      description: mod.summary || mod.description || '',
      flows: flows.length > 0 ? flows : ['Create a record → verify form and list views work'],
    });
  }

  // Detect cross-module flows by finding shared model references
  for (const mod of modules) {
    for (const model of (mod.models || [])) {
      for (const field of (model.fields || [])) {
        if (field.comodel_name) {
          const otherMod = modules.find(m =>
            m !== mod && (m.models || []).some(mm => mm.name === field.comodel_name)
          );
          if (otherMod) {
            crossModule.push({
              modules: [mod.module_name || mod.name, otherMod.module_name || otherMod.name],
              flow: `Create ${model.name} with reference to ${field.comodel_name} → verify data flows correctly`,
            });
          }
        }
      }
    }
  }

  return { perModule, crossModule };
}

/**
 * Record UAT result for a module.
 *
 * @param {string} cwd - Working directory
 * @param {string} moduleName
 * @param {string} result - 'pass', 'minor', 'fail', 'skip'
 * @param {string} [feedback] - User feedback for minor/fail
 */
function recordResult(cwd, moduleName, result, feedback) {
  if (!MODULE_NAME_RE.test(moduleName)) {
    throw new Error(`Invalid module name: '${moduleName}' (must match [a-z][a-z0-9_]*)`);
  }
  const uatDir = path.join(cwd, '.planning', 'modules', moduleName);
  if (!fs.existsSync(uatDir)) {
    fs.mkdirSync(uatDir, { recursive: true });
  }

  const resultFile = path.join(uatDir, 'uat-result.json');
  const data = {
    module: moduleName,
    result,
    feedback: feedback || null,
    timestamp: new Date().toISOString(),
  };
  fs.writeFileSync(resultFile, JSON.stringify(data, null, 2), 'utf8');

  // Write detailed feedback for failures
  if (result === 'fail' && feedback) {
    const feedbackFile = path.join(uatDir, 'uat-feedback.md');
    const content = [
      `# UAT Failure: ${moduleName}`,
      ``,
      `**Date:** ${new Date().toISOString()}`,
      `**Result:** FAIL`,
      ``,
      `## Feedback`,
      ``,
      feedback,
      ``,
      `## Action Required`,
      ``,
      `Module will be re-generated with this feedback incorporated.`,
    ].join('\n');
    fs.writeFileSync(feedbackFile, content, 'utf8');
  }

  return data;
}

/**
 * Get UAT summary for all modules.
 */
function getUATSummary(cwd, moduleNames) {
  const results = { pass: 0, minor: 0, fail: 0, skip: 0, untested: 0 };
  const details = [];

  for (const name of moduleNames) {
    const resultFile = path.join(cwd, '.planning', 'modules', name, 'uat-result.json');
    if (fs.existsSync(resultFile)) {
      const data = JSON.parse(fs.readFileSync(resultFile, 'utf8'));
      results[data.result] = (results[data.result] || 0) + 1;
      details.push(data);
    } else {
      results.untested += 1;
      details.push({ module: name, result: 'untested' });
    }
  }

  return { summary: results, details };
}

module.exports = {
  isCheckpointDue,
  generateChecklist,
  recordResult,
  getUATSummary,
};
