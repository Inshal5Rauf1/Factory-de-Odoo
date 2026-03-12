/**
 * Circular Dependency Breaker — Resolves circular module dependencies
 * that are common in 90+ module ERPs.
 *
 * Strategy: When modules A and B circularly reference each other:
 * 1. Identify which direction is "primary" (A→B or B→A)
 *    - Primary = the Many2one direction (the FK owner)
 *    - Secondary = the One2many/computed direction
 * 2. Build the primary module first WITHOUT the back-reference
 * 3. Build the secondary module WITH its forward reference
 * 4. Update the primary module to add the back-reference
 *
 * This adds a "patch round" after initial generation where modules
 * are updated with back-references that couldn't exist at gen time.
 */

function analyzeCircularPair(circularRisk, provRegistry) {
  const [modA, modB] = circularRisk.modules;
  const refsAtoB = circularRisk.refs_a_to_b;
  const refsBtoA = circularRisk.refs_b_to_a;

  // Count Many2one in each direction — the side with more M2O is "primary"
  const m2oAtoB = refsAtoB.filter(r => r.type === 'Many2one' || r.type === 'many2one');
  const m2oBtoA = refsBtoA.filter(r => r.type === 'Many2one' || r.type === 'many2one');

  let primary, secondary, deferredRefs;
  if (m2oAtoB.length >= m2oBtoA.length) {
    // A has more M2O to B → A is primary (owns the FK), build A first
    primary = modA;
    secondary = modB;
    deferredRefs = refsBtoA; // B→A refs are deferred (added in patch round)
  } else {
    primary = modB;
    secondary = modA;
    deferredRefs = refsAtoB;
  }

  return {
    primary,
    secondary,
    buildOrder: [primary, secondary],
    deferredRefs,
    patchRequired: deferredRefs.length > 0,
  };
}

/**
 * Generate patch spec for deferred references.
 * After both modules are built, this produces the field additions
 * needed to complete the circular reference.
 *
 * @returns {Object} { module, model, fields_to_add[] }
 */
function generatePatchSpec(resolution) {
  if (!resolution.patchRequired) return null;

  const patches = [];
  for (const ref of resolution.deferredRefs) {
    patches.push({
      module: ref.from_module,
      model: ref.from_model,
      field: {
        name: ref.field,
        type: ref.type || 'Many2one',
        comodel_name: ref.to_model,
      },
    });
  }

  return {
    module: resolution.primary,
    patches,
  };
}

/**
 * Plan the build order for all modules considering circular deps.
 * Augments the topological sort with circular dep resolution.
 *
 * @param {Array} topoOrder - Original topological sort order
 * @param {Array} circularRisks - From analyzeForwardReferences()
 * @param {Object} provRegistry
 * @returns {Object} { order[], patchRounds[] }
 */
function planBuildOrder(topoOrder, circularRisks, provRegistry) {
  if (circularRisks.length === 0) {
    return { order: topoOrder, patchRounds: [] };
  }

  // Resolve each circular pair
  const resolutions = circularRisks.map(cr =>
    analyzeCircularPair(cr, provRegistry)
  );

  // Adjust topo order: ensure primary comes before secondary
  const adjustedOrder = [...topoOrder];
  for (const res of resolutions) {
    const priIdx = adjustedOrder.indexOf(res.primary);
    const secIdx = adjustedOrder.indexOf(res.secondary);
    if (priIdx > secIdx) {
      // Swap: move primary before secondary
      adjustedOrder.splice(priIdx, 1);
      adjustedOrder.splice(secIdx, 0, res.primary);
    }
  }

  // Collect patch rounds (deferred back-references)
  const patchRounds = resolutions
    .filter(r => r.patchRequired)
    .map(r => generatePatchSpec(r))
    .filter(Boolean);

  return { order: adjustedOrder, patchRounds };
}

module.exports = {
  analyzeCircularPair,
  generatePatchSpec,
  planBuildOrder,
};
