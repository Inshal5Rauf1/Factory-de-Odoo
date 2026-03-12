/**
 * Spec Completeness — Scores how well-specified a module is based on
 * its decomposition data. Identifies gaps that need human input.
 *
 * At 90+ modules, this scoring drives automated triage:
 * - Score >= 70: ready for spec generation (no discussion needed)
 * - Score 40-69: needs brief discussion (1-2 questions)
 * - Score < 40: needs full discussion (5+ questions)
 *
 * Scoring (0-100):
 *   - Has models defined: +20
 *   - Each model has >2 fields: +15
 *   - Has security roles: +15
 *   - Has workflow states: +10
 *   - Has depends listed: +10
 *   - Has description >20 chars: +10
 *   - Has computation chains: +10
 *   - Has view hints: +10
 *
 * Cross-module bonus (90+ scale):
 *   - All referenced comodels exist in decomposition: +5
 *   - No circular dependency risk flagged: +5
 */

function scoreModule(moduleData, allModuleNames) {
  let score = 0;
  const gaps = [];
  const crossModuleIssues = [];

  // --- Core scoring (same as before) ---

  // Models defined
  const models = moduleData.models || [];
  if (models.length > 0) {
    score += 20;
  } else {
    gaps.push('No models defined — need model names and primary fields');
  }

  // Model detail
  const detailedModels = models.filter(m =>
    (m.fields || []).length > 2
  );
  if (detailedModels.length === models.length && models.length > 0) {
    score += 15;
  } else {
    const underspecified = models.filter(m => (m.fields || []).length <= 2);
    gaps.push(`${underspecified.length} model(s) have <=2 fields: ${underspecified.map(m => m.name || m).join(', ')}`);
  }

  // Security
  if (moduleData.security?.roles?.length > 0) {
    score += 15;
  } else {
    gaps.push('No security roles defined — who can CRUD?');
  }

  // Workflow
  if (moduleData.workflow?.length > 0 || moduleData.states?.length > 0) {
    score += 10;
  } else {
    gaps.push('No workflow/states — is this a simple CRUD or stateful?');
  }

  // Dependencies
  if ((moduleData.depends || moduleData.base_depends || []).length > 0) {
    score += 10;
  } else {
    gaps.push('No dependencies listed');
  }

  // Description quality
  if ((moduleData.description || '').length > 20) {
    score += 10;
  } else {
    gaps.push('Description too brief — need functional purpose');
  }

  // Computation chains
  if ((moduleData.computation_chains || []).length > 0) {
    score += 10;
  }

  // View hints
  if ((moduleData.view_hints || []).length > 0) {
    score += 10;
  }

  // --- Cross-module scoring (90+ scale) ---

  if (allModuleNames && allModuleNames.length > 0) {
    // Check if referenced comodels exist in decomposition
    let unresolvedRefs = [];
    for (const field of models.flatMap(m => m.fields || [])) {
      if (field.comodel_name && !field.comodel_name.startsWith('res.') &&
          !field.comodel_name.startsWith('ir.') &&
          !field.comodel_name.startsWith('mail.')) {
        unresolvedRefs.push(field.comodel_name);
      }
    }
    if (unresolvedRefs.length === 0) {
      score += 5;
    } else {
      crossModuleIssues.push(`Unresolved comodel references: ${unresolvedRefs.join(', ')}`);
    }

    // Circular dependency risk: does this module's unresolved comodel
    // references point to its own models (self-dependency via external path)?
    const ownModelNames = new Set(models.map(m => m.name || m));
    const hasCircularRisk = unresolvedRefs.some(ref => ownModelNames.has(ref));
    if (!hasCircularRisk) {
      score += 5;
    } else {
      crossModuleIssues.push('Circular dependency risk: comodel references own models via external path');
    }
  }

  // Determine discussion depth
  let discussionDepth;
  if (score >= 70) {
    discussionDepth = 'none';
  } else if (score >= 40) {
    discussionDepth = 'brief';  // 1-2 focused questions
  } else {
    discussionDepth = 'full';   // 5+ questions with domain templates
  }

  return {
    score,
    gaps,
    crossModuleIssues,
    ready: score >= 70,
    needs_discussion: score < 70,
    discussionDepth,
  };
}

function scoreAllModules(decomposition, allModuleNames) {
  const results = {};
  const names = allModuleNames || (decomposition.modules || []).map(m => m.name);
  for (const mod of (decomposition.modules || [])) {
    results[mod.name] = scoreModule(mod, names);
  }
  return results;
}

function getDiscussionBatches(scores, moduleData) {
  // Group underspecified modules by tier for batch discussion
  const fullDiscussion = [];
  const briefDiscussion = [];

  for (const [name, s] of Object.entries(scores)) {
    if (s.discussionDepth === 'full') {
      fullDiscussion.push(name);
    } else if (s.discussionDepth === 'brief') {
      briefDiscussion.push(name);
    }
  }

  const tiers = {};
  for (const mod of (moduleData.modules || [])) {
    const inFull = fullDiscussion.includes(mod.name);
    const inBrief = briefDiscussion.includes(mod.name);
    if (!inFull && !inBrief) continue;

    const tier = mod.tier || 'unknown';
    const depth = inFull ? 'full' : 'brief';
    const key = `${tier}-${depth}`;
    if (!tiers[key]) tiers[key] = { tier, depth, modules: [] };
    tiers[key].modules.push({
      name: mod.name,
      score: scores[mod.name].score,
      gaps: scores[mod.name].gaps,
      crossModuleIssues: scores[mod.name].crossModuleIssues,
    });
  }

  // Return batches of 5, grouped by tier and depth
  const batches = [];
  const sortedKeys = Object.keys(tiers).sort((a, b) => {
    const [tierA, depthA] = a.split('-');
    const [tierB, depthB] = b.split('-');
    if (depthA !== depthB) return depthA === 'full' ? -1 : 1;
    return tierA.localeCompare(tierB);
  });

  for (const key of sortedKeys) {
    const { tier, depth, modules } = tiers[key];
    for (let i = 0; i < modules.length; i += 5) {
      batches.push({
        tier,
        depth,
        modules: modules.slice(i, i + 5),
      });
    }
  }

  return batches;
}

function getDiscussionSummary(scores) {
  const total = Object.keys(scores).length;
  const ready = Object.values(scores).filter(s => s.ready).length;
  const brief = Object.values(scores).filter(s => s.discussionDepth === 'brief').length;
  const full = Object.values(scores).filter(s => s.discussionDepth === 'full').length;
  const avgScore = total > 0
    ? Math.round(Object.values(scores).reduce((sum, s) => sum + s.score, 0) / total)
    : 0;
  return {
    total,
    ready,
    brief,
    full,
    avgScore,
    estimatedBatches: Math.ceil(full / 5) + Math.ceil(brief / 5),
    estimatedQuestions: full * 5 + brief * 2,
  };
}

module.exports = {
  scoreModule,
  scoreAllModules,
  getDiscussionBatches,
  getDiscussionSummary,
};
