/**
 * Cycle Log — Append-only markdown log tracking every action in an
 * ERP generation cycle. Each entry is timestamped and includes
 * module name, action, result, and error details.
 *
 * At 90+ modules, the log grows large. The compact summary header
 * at the top is rewritten after each iteration so Claude can resume
 * from the header alone without reading the full log.
 */

const fs = require('fs');
const path = require('path');

const LOG_FILENAME = 'ERP_CYCLE_LOG.md';

function getLogPath(cwd) {
  return path.join(cwd, '.planning', LOG_FILENAME);
}

function initLog(cwd, projectName) {
  const logPath = getLogPath(cwd);
  const header = [
    `# ERP Cycle Log: ${projectName}`,
    ``,
    `**Started:** ${new Date().toISOString()}`,
    `**Status:** In Progress`,
    ``,
    `<!-- COMPACT-SUMMARY-START -->`,
    `## Quick Resume`,
    `- **Last Iteration:** 0`,
    `- **Shipped:** 0/0`,
    `- **In Progress:** 0`,
    `- **Blocked:** 0`,
    `- **Next Action:** decompose PRD`,
    `- **Current Wave:** 0`,
    `<!-- COMPACT-SUMMARY-END -->`,
    ``,
    `---`,
    ``,
    `## Iterations`,
    ``,
  ].join('\n');
  fs.writeFileSync(logPath, header, 'utf8');
  return logPath;
}

function updateCompactSummary(cwd, summary) {
  const logPath = getLogPath(cwd);
  const content = fs.readFileSync(logPath, 'utf8');
  const newSummary = [
    `<!-- COMPACT-SUMMARY-START -->`,
    `## Quick Resume`,
    `- **Last Iteration:** ${summary.iteration}`,
    `- **Shipped:** ${summary.shipped}/${summary.total}`,
    `- **In Progress:** ${summary.in_progress}`,
    `- **Blocked:** ${summary.blocked}`,
    `- **Next Action:** ${summary.next_action}`,
    `- **Current Wave:** ${summary.wave}`,
    `- **Coherence Warnings:** ${summary.coherence_warnings || 0}`,
    `<!-- COMPACT-SUMMARY-END -->`,
  ].join('\n');
  const updated = content.replace(
    /<!-- COMPACT-SUMMARY-START -->[\s\S]*?<!-- COMPACT-SUMMARY-END -->/,
    newSummary
  );
  fs.writeFileSync(logPath, updated, 'utf8');
}

function appendEntry(cwd, entry) {
  // entry: { iteration, module, action, result, errors, stats, wave }
  const logPath = getLogPath(cwd);
  const timestamp = new Date().toISOString();
  const stats = entry.stats || {};
  const block = [
    `### Iteration ${entry.iteration} — ${timestamp}`,
    `- **Module:** ${entry.module || 'N/A'}`,
    `- **Action:** ${entry.action}`,
    `- **Result:** ${entry.result}`,
    entry.wave ? `- **Wave:** ${entry.wave}` : null,
    entry.errors ? `- **Errors:** ${entry.errors}` : null,
    `- **Progress:** ${stats.shipped || 0}/${stats.total || 0} shipped | ${stats.in_progress || 0} in progress | ${stats.remaining || 0} remaining`,
    ``,
  ].filter(Boolean).join('\n');
  fs.appendFileSync(logPath, block + '\n', 'utf8');

  // Update compact summary after every entry
  updateCompactSummary(cwd, {
    iteration: entry.iteration,
    shipped: stats.shipped || 0,
    total: stats.total || 0,
    in_progress: stats.in_progress || 0,
    blocked: stats.blocked || 0,
    next_action: entry.next_action || 'continue',
    wave: entry.wave || 0,
    coherence_warnings: entry.coherence_warnings || 0,
  });
}

function appendBlockedModule(cwd, moduleName, reason) {
  const logPath = getLogPath(cwd);
  const block = [
    ``,
    `> **BLOCKED:** \`${moduleName}\` — ${reason}`,
    ``,
  ].join('\n');
  fs.appendFileSync(logPath, block, 'utf8');
}

function appendCoherenceEvent(cwd, event) {
  // event: { type, source_module, target_module, details, resolution }
  const logPath = getLogPath(cwd);
  const block = [
    ``,
    `> **COHERENCE [${event.type}]:** \`${event.source_module}\` → \`${event.target_module}\``,
    `> ${event.details}`,
    event.resolution ? `> **Resolution:** ${event.resolution}` : null,
    ``,
  ].filter(Boolean).join('\n');
  fs.appendFileSync(logPath, block, 'utf8');
}

function finalizeLog(cwd, summary) {
  const logPath = getLogPath(cwd);
  const footer = [
    ``,
    `---`,
    ``,
    `## Cycle Complete`,
    ``,
    `**Finished:** ${new Date().toISOString()}`,
    `**Total Modules:** ${summary.total}`,
    `**Shipped:** ${summary.shipped}`,
    `**Blocked:** ${summary.blocked}`,
    `**Total Iterations:** ${summary.iterations}`,
    `**Errors Encountered:** ${summary.errors}`,
    `**Coherence Warnings:** ${summary.coherence_warnings || 0}`,
    `**Context Resets:** ${summary.context_resets || 0}`,
    ``,
    `### Shipped Modules`,
    ...(summary.shipped_list || []).map(m => `- ${m}`),
    ``,
    summary.blocked_list?.length ? `### Blocked Modules` : null,
    ...(summary.blocked_list || []).map(m => `- ${m.name}: ${m.reason}`),
  ].filter(Boolean).join('\n');
  fs.appendFileSync(logPath, footer, 'utf8');
}

module.exports = {
  LOG_FILENAME,
  getLogPath,
  initLog,
  appendEntry,
  appendBlockedModule,
  appendCoherenceEvent,
  updateCompactSummary,
  finalizeLog,
};
