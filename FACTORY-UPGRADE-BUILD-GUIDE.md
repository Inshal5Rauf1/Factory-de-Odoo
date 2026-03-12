# Factory de Odoo — Upgrade Build Guide

## Full PRD-to-ERP Pipeline with Ralph Loop Integration

**Target:** Claude Code implementation guide. All file paths, function signatures, and
dependencies are exact. Follow this guide sequentially — each gap builds on the previous.

**Scope:** 8 gaps to close + 8 codebase fixes + Ralph Loop integration for 90+ module ERP generation.

**Factory Repo:** `https://github.com/Inshal5Rauf1/Factory-de-Odoo`
**Factory Local:** `/home/inshal-rauf/Factory-de-Odoo/`
**Ralph Loop Plugin:** `https://github.com/frankbria/ralph-claude-code` (Claude Code plugin for outer loop)

### Key Paths

| Component | Path |
|-----------|------|
| Orchestrator root | `/home/inshal-rauf/Factory-de-Odoo/orchestrator/` |
| Orchestrator lib | `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/` |
| Orchestrator tests | `/home/inshal-rauf/Factory-de-Odoo/orchestrator/tests/` |
| Orchestrator commands | `/home/inshal-rauf/Factory-de-Odoo/orchestrator/commands/amil/` |
| Orchestrator workflows | `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/workflows/` |
| Pipeline root | `/home/inshal-rauf/Factory-de-Odoo/pipeline/` |
| Pipeline Python src | `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/` |
| Pipeline tests | `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/tests/` |
| Pipeline templates 17.0 | `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/17.0/` |
| Pipeline templates shared | `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/shared/` |
| Existing coherence checker | `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/coherence.cjs` |
| Existing registry | `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/registry.cjs` |
| Existing dep graph | `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/dependency-graph.cjs` |
| Existing module status | `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/module-status.cjs` |
| Renderer context | `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/renderer_context.py` |
| Docker runner | `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/validation/docker_runner.py` |

---

## Table of Contents

1. [Gap 1: Cycle Log](#gap-1-cycle-log)
2. [Gap 2: Persistent Docker Instance](#gap-2-persistent-docker-instance)
3. [Gap 3: Auto-Question Loop](#gap-3-auto-question-loop)
4. [Gap 4: Full-Cycle Orchestrator (run-prd)](#gap-4-full-cycle-orchestrator)
5. [Gap 5: Cross-Module Coherence Engine](#gap-5-cross-module-coherence-engine)
6. [Gap 6: Live UAT Flow](#gap-6-live-uat-flow)
7. [Gap 7: MCP Server Expansion](#gap-7-mcp-server-expansion)
8. [Gap 8: Auto-Fix Smart Guard](#gap-8-auto-fix-smart-guard)
9. [Ralph Loop Integration](#ralph-loop-integration)
10. [Codebase Fixes Required](#codebase-fixes-required)
11. [90+ Module Scaling Considerations](#90-module-scaling-considerations)
12. [Implementation Order](#implementation-order)
13. [Slash Command Mapping](#slash-command-mapping)

---

## Gap 1: Cycle Log

**Difficulty:** Easy
**Files to create/modify:** 2 new, 1 modified

### Problem

State is scattered across `STATE.md`, `module_status.json`, `model_registry.json`, and per-module `generation-report.json` / `verification-report.json`. No single file captures the full ERP generation cycle history. At 90+ modules, context resets are guaranteed — the cycle log becomes the **primary recovery mechanism**.

### Solution

Create `ERP_CYCLE_LOG.md` in `.planning/` that aggregates every action taken during the PRD-to-ERP cycle. At 90+ modules, this log may reach 2000+ lines — include a **compact summary header** that updates after each iteration so Claude can read just the top to resume.

### File 1: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/cycle-log.cjs`

```javascript
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
```

### File 2: CLI subcommand registration

Add to `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/amil-tools.cjs` in the command dispatch:

```javascript
// In the switch/if chain for subcommands:
case 'cycle-log':
  const cycleLog = require('./lib/cycle-log.cjs');
  const subCmd = args[1]; // init, append, blocked, coherence, finalize
  if (subCmd === 'init') {
    const projectName = args[2] || 'ERP Project';
    console.log(cycleLog.initLog(cwd, projectName));
  } else if (subCmd === 'append') {
    const entryJson = args[2];
    cycleLog.appendEntry(cwd, JSON.parse(entryJson));
  } else if (subCmd === 'blocked') {
    cycleLog.appendBlockedModule(cwd, args[2], args[3]);
  } else if (subCmd === 'coherence') {
    cycleLog.appendCoherenceEvent(cwd, JSON.parse(args[2]));
  } else if (subCmd === 'finalize') {
    cycleLog.finalizeLog(cwd, JSON.parse(args[2]));
  }
  break;
```

### Tests

Add `/home/inshal-rauf/Factory-de-Odoo/orchestrator/tests/cycle-log.test.cjs` with:
- `initLog` creates file with correct header and compact summary
- `appendEntry` appends formatted markdown AND updates compact summary
- `updateCompactSummary` replaces summary block without corrupting log body
- `appendBlockedModule` adds blockquote
- `appendCoherenceEvent` logs coherence warnings
- `finalizeLog` adds summary footer with coherence stats
- Multiple entries accumulate correctly
- Compact summary always reflects latest state

---

## Gap 2: Persistent Docker Instance

**Difficulty:** Medium
**Files to create/modify:** 2 new, 2 modified

### Problem

Currently `docker_runner.py` spins up ephemeral containers per validation (30-60s each). For 90+ modules this means:
- 90 × 30s = **45+ minutes** just on container lifecycle
- No incremental testing (each module validated in isolation)
- Can't test cross-module interactions (critical at 90+ modules)
- No way for the user to interact with the running ERP

### Solution

Add a **persistent Docker mode** that keeps a single Odoo+PostgreSQL instance running and installs modules incrementally. At 90+ modules, this instance becomes the **live UAT environment** where users verify functionality (see [Gap 6](#gap-6-live-uat-flow)).

### File 1: `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/validation/persistent_docker.py`

```python
"""Persistent Docker instance for incremental module installation.

Unlike the ephemeral docker_runner, this keeps a single Odoo+PostgreSQL
instance alive across multiple module installations. Modules accumulate
in the running instance, allowing cross-module interaction testing.

At 90+ modules, the instance holds the full ERP. Users access it via
browser to verify functionality. The manager tracks install order and
can roll back individual modules if needed.

Usage:
    manager = PersistentDockerManager()
    manager.ensure_running()
    result = manager.install_module(module_path)
    result = manager.run_module_tests(module_path)
    # ... install more modules ...
    # User accesses http://localhost:8069 to interact with ERP
    manager.stop()  # Only when human says done
"""

import subprocess
import time
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field

from .types import Result, InstallResult, TestResult

logger = logging.getLogger(__name__)

COMPOSE_FILE = Path(__file__).parent.parent / "data" / "docker" / "persistent-compose.yml"
PROJECT_NAME = "factory-de-odoo"
STATE_FILE = ".factory-docker-state.json"


@dataclass
class PersistentDockerManager:
    """Manages a long-lived Odoo Docker instance for incremental installs.

    At 90+ modules, this instance may run for hours or days. State is
    persisted to disk so it survives process restarts and context resets.
    """

    compose_file: Path = COMPOSE_FILE
    project_name: str = PROJECT_NAME
    installed_modules: list[str] = field(default_factory=list)
    install_order: list[dict] = field(default_factory=list)  # {name, timestamp, success}
    _running: bool = False
    _state_dir: Path | None = None

    def ensure_running(self, state_dir: Path | None = None) -> bool:
        """Start the persistent instance if not already running.

        Args:
            state_dir: Directory to persist state (for resume across context resets).
        """
        self._state_dir = state_dir
        self._load_state()

        if self._running and self._health_check():
            return True

        # Start containers
        result = subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file),
             "-p", self.project_name, "up", "-d", "--wait"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error("Failed to start persistent Docker: %s", result.stderr)
            return False

        # Wait for Odoo to be healthy
        for attempt in range(30):
            if self._health_check():
                self._running = True
                self._save_state()
                return True
            time.sleep(2)

        return False

    def install_module(self, module_path: Path) -> Result[InstallResult]:
        """Install a module into the running instance incrementally."""
        if not self._running:
            return Result(success=False, errors=("Persistent Docker not running",))

        module_name = module_path.name

        # Copy module into the running container's addons path
        copy_result = subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file),
             "-p", self.project_name,
             "cp", str(module_path), f"odoo:/mnt/extra-addons/{module_name}"],
            capture_output=True, text=True, timeout=30,
        )
        if copy_result.returncode != 0:
            return Result(success=False,
                          errors=(f"Failed to copy module: {copy_result.stderr}",))

        # Install via odoo CLI (update module list + install)
        install_cmd = (
            f"odoo -c /etc/odoo/odoo.conf -d odoo_factory "
            f"--no-http --stop-after-init "
            f"-i {module_name}"
        )
        install_result = subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file),
             "-p", self.project_name,
             "exec", "-T", "odoo", "bash", "-c", install_cmd],
            capture_output=True, text=True, timeout=300,
        )

        from .log_parser import parse_install_log
        success, error_msg = parse_install_log(install_result.stdout)

        install = InstallResult(
            success=success,
            log_output=install_result.stdout,
            error_message=error_msg,
        )

        entry = {
            "name": module_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "success": success,
            "error": error_msg if not success else None,
        }
        self.install_order.append(entry)

        if success:
            self.installed_modules.append(module_name)

        self._save_state()
        return Result(success=True, data=install)

    def run_module_tests(self, module_path: Path) -> Result[tuple[TestResult, ...]]:
        """Run tests for a specific module in the persistent instance."""
        module_name = module_path.name

        test_cmd = (
            f"odoo -c /etc/odoo/odoo.conf -d odoo_factory "
            f"--no-http --stop-after-init "
            f"--test-tags={module_name} "
            f"-u {module_name}"
        )
        test_result = subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file),
             "-p", self.project_name,
             "exec", "-T", "odoo", "bash", "-c", test_cmd],
            capture_output=True, text=True, timeout=600,
        )

        from .log_parser import parse_test_log
        test_results = parse_test_log(test_result.stdout)

        return Result(success=True, data=test_results)

    def run_cross_module_test(self, module_names: list[str]) -> Result[tuple[TestResult, ...]]:
        """Run tests that span multiple installed modules.

        At 90+ modules, cross-module interactions are common. This runs
        tests for a set of modules together, catching integration issues
        that per-module tests miss.
        """
        tags = ",".join(module_names)
        modules = ",".join(module_names)

        test_cmd = (
            f"odoo -c /etc/odoo/odoo.conf -d odoo_factory "
            f"--no-http --stop-after-init "
            f"--test-tags={tags} "
            f"-u {modules}"
        )
        test_result = subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file),
             "-p", self.project_name,
             "exec", "-T", "odoo", "bash", "-c", test_cmd],
            capture_output=True, text=True, timeout=900,
        )

        from .log_parser import parse_test_log
        test_results = parse_test_log(test_result.stdout)

        return Result(success=True, data=test_results)

    def get_installed_modules(self) -> list[str]:
        """Return list of successfully installed modules."""
        return list(self.installed_modules)

    def get_install_history(self) -> list[dict]:
        """Return full install history with timestamps and errors."""
        return list(self.install_order)

    def get_web_url(self) -> str:
        """Return the URL for the user to access the running Odoo instance."""
        return "http://localhost:8069"

    def stop(self) -> None:
        """Stop the persistent instance (data preserved in volumes)."""
        subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file),
             "-p", self.project_name, "stop"],
            capture_output=True, timeout=30,
        )
        self._running = False
        self._save_state()

    def reset(self) -> None:
        """Destroy the persistent instance and all data."""
        subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file),
             "-p", self.project_name, "down", "-v"],
            capture_output=True, timeout=30,
        )
        self._running = False
        self.installed_modules.clear()
        self.install_order.clear()
        self._save_state()

    def _health_check(self) -> bool:
        """Check if the Odoo instance is responding."""
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", str(self.compose_file),
                 "-p", self.project_name,
                 "exec", "-T", "odoo", "curl", "-sf", "http://localhost:8069/web/health"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _save_state(self) -> None:
        """Persist state to disk for resume across context resets."""
        if not self._state_dir:
            return
        state_path = self._state_dir / STATE_FILE
        state = {
            "running": self._running,
            "installed_modules": self.installed_modules,
            "install_order": self.install_order,
        }
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _load_state(self) -> None:
        """Load state from disk if available."""
        if not self._state_dir:
            return
        state_path = self._state_dir / STATE_FILE
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.installed_modules = state.get("installed_modules", [])
            self.install_order = state.get("install_order", [])
            self._running = state.get("running", False)
```

### File 2: `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/data/docker/persistent-compose.yml`

```yaml
version: "3.8"

services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: odoo_factory
    volumes:
      - factory-db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odoo"]
      interval: 5s
      timeout: 3s
      retries: 10
    # At 90+ modules, PostgreSQL needs more resources
    shm_size: '512mb'
    command: >
      postgres
        -c shared_buffers=256MB
        -c work_mem=16MB
        -c maintenance_work_mem=128MB
        -c max_connections=100

  odoo:
    image: odoo:17.0
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "${FACTORY_PORT:-8069}:8069"
    volumes:
      - factory-addons:/mnt/extra-addons
      - factory-odoo-data:/var/lib/odoo
    environment:
      HOST: db
      USER: odoo
      PASSWORD: odoo
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8069/web/health"]
      interval: 10s
      timeout: 5s
      retries: 12
    # At 90+ modules, Odoo needs more memory for module loading
    deploy:
      resources:
        limits:
          memory: 2G

volumes:
  factory-db-data:
  factory-addons:
  factory-odoo-data:
```

### Modifications

**`/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/cli.py`** — Add CLI command:

```python
@cli.command()
@click.option("--action", type=click.Choice(["start", "stop", "reset", "status"]))
@click.option("--install", type=click.Path(exists=True), help="Module path to install")
@click.option("--test", type=click.Path(exists=True), help="Module path to test")
@click.option("--cross-test", multiple=True, help="Module names for cross-module testing")
@click.option("--url", is_flag=True, help="Print the Odoo web URL")
@click.option("--history", is_flag=True, help="Print install history")
def factory_docker(action, install, test, cross_test, url, history):
    """Manage the persistent Docker factory instance."""
    from amil_utils.validation.persistent_docker import PersistentDockerManager
    manager = PersistentDockerManager()
    # ... dispatch based on action/install/test/cross_test/url/history
```

**`/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/workflows/generate-module.md`** — Add step 10.5:

After status transition to "generated", if persistent Docker is running, auto-install:
```markdown
## Step 10.5: Persistent Docker Install (if running)

If the factory Docker instance is running (check via `factory-docker --action status`):
1. Install the generated module: `factory-docker --install {MODULE_DIR}`
2. If install fails, log to cycle log but don't block status transition
3. If install succeeds, log success with installed module count
4. After every 10th module install: run cross-module tests on last 10 modules
```

### Tests

- `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/tests/test_persistent_docker.py` with `@pytest.mark.docker`:
  - `ensure_running` starts containers
  - `install_module` copies and installs
  - Multiple modules accumulate (test with 5+)
  - `run_cross_module_test` tests multiple modules together
  - `stop` preserves data, `_load_state` recovers installed list
  - `reset` destroys volumes
  - State persists to disk and recovers across process restarts
  - Health check detects running/stopped state
  - `get_web_url` returns correct URL
  - `get_install_history` returns chronological install log

---

## Gap 3: Auto-Question Loop

**Difficulty:** Medium
**Files to create/modify:** 2 new, 1 modified

### Problem

`/amil:discuss-module` is manual — requires the user to pick which module to discuss. For 90+ modules, manually triggering discussion for each is impossible. Need auto-detection of underspecified modules and batch questioning.

At 90+ modules, **most modules will be underspecified** after initial PRD decomposition. A university ERP might have 90 modules where only 10-15 are described in detail in the PRD. The rest are inferred by the decomposer and need human input.

### Solution

Add a **spec completeness scorer** that analyzes each module's decomposition data and identifies gaps. Then batch discussion by wave (related modules together). At 90 modules, expect ~15-20 discussion batches of 5 modules each.

### File 1: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/spec-completeness.cjs`

```javascript
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
    const allModelNames = new Set();
    // Collect model names from all modules in decomposition
    // (This checks forward references — does module X reference a model
    //  that will be provided by some other module in the decomposition?)
    let unresolvedRefs = [];
    for (const field of models.flatMap(m => m.fields || [])) {
      if (field.comodel_name && !field.comodel_name.startsWith('res.') &&
          !field.comodel_name.startsWith('ir.') &&
          !field.comodel_name.startsWith('mail.')) {
        // This is a reference to a non-base model — check if it's in the decomposition
        // We can't check here without all model names, so flag for the caller
        unresolvedRefs.push(field.comodel_name);
      }
    }
    if (unresolvedRefs.length === 0) {
      score += 5;
    } else {
      crossModuleIssues.push(`Unresolved comodel references: ${unresolvedRefs.join(', ')}`);
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
  // At 90+ modules: separate full-discussion from brief-discussion
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
  // Full-discussion batches first (they take longer)
  const batches = [];
  const sortedKeys = Object.keys(tiers).sort((a, b) => {
    // full before brief, then by tier number
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
  const avgScore = Math.round(
    Object.values(scores).reduce((sum, s) => sum + s.score, 0) / total
  );
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
```

### File 2: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/commands/amil/batch-discuss.md`

New slash command that auto-detects underspecified modules and batches discussion:

```yaml
---
name: batch-discuss
description: Auto-detect underspecified modules and discuss in batches
allowed-tools:
  - Read
  - Write
  - Bash
  - Agent
  - AskUserQuestion
---
```

Process:
1. Load `decomposition.json`
2. Run `scoreAllModules()` on all modules
3. Print discussion summary: "47 of 90 modules need discussion (12 full, 35 brief) — ~15 batches"
4. Generate discussion batches by tier and depth
5. For each batch: present gaps to user, ask focused questions, write CONTEXT.md
6. Re-score after each batch — stop when all modules reach score >= 70
7. For brief-discussion modules: present only the 1-2 specific gaps, not full question templates

### Modification

**`/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/workflows/discuss-module.md`** — Add batch mode:

Add a `--batch` flag that:
1. Scores all `planned` modules
2. Groups by tier and discussion depth
3. Discusses 5 at a time (full) or 8 at a time (brief)
4. Presents gaps as focused questions instead of full question templates
5. For brief discussions, suggests reasonable defaults the user can accept or override

---

## Gap 4: Full-Cycle Orchestrator

**Difficulty:** Medium-Hard
**Files to create/modify:** 2 new

### Problem

No single command chains the full PRD-to-ERP lifecycle. User must manually invoke `/amil:new-erp` → `discuss-module` × N → `plan-module` × N → `generate-module` × N → `verify-work` × N. At 90+ modules, this is hundreds of manual invocations.

### Solution

Create `/amil:run-prd` that drives the full cycle. This is the **outer loop** that Ralph Loop will power.

### File 1: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/commands/amil/run-prd.md`

```yaml
---
name: run-prd
description: Run full PRD-to-ERP generation cycle
argument-hint: "<path-to-prd>"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
  - Skill
---
```

### File 2: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/workflows/run-prd.md`

```markdown
# run-prd — Full PRD-to-ERP Cycle

## Overview

Single command that drives the entire ERP generation pipeline from
a PRD document to shipped modules. Designed to work with Ralph Loop
for autonomous iteration. Handles 90+ modules with wave-based generation,
coherence tracking, and automatic context recovery.

## Init

Read current state:
- `.planning/module_status.json` (if exists)
- `.planning/ERP_CYCLE_LOG.md` — read ONLY the compact summary header
- `.planning/research/decomposition.json` (if exists)
- `.planning/model_registry.json` (if exists — check size)
- `.planning/provisional_registry.json` (if exists — see Gap 5)

Determine current iteration number from cycle log compact summary (0 if new).

## Priority-Based Action Selection

Each iteration selects ONE action based on this priority table:

| Priority | Condition | Action |
|----------|-----------|--------|
| 0 | No modules exist | `/amil:new-erp` with PRD |
| 0.5 | Modules exist but no provisional registry | Build provisional registry from decomposition |
| 1 | Any module at `generated` | `/amil:verify-work` (unblock belt) |
| 2 | Any module at `checked` | Transition to `shipped`, install to Docker |
| 3 | Belt is free AND any `spec_approved` with deps met | `/amil:generate-module` (dep order) |
| 3.5 | Belt free AND spec_approved but deps NOT met | Log blocked, skip to next ready module |
| 4 | Any `planned` with score < 70 | `/amil:batch-discuss` (wave of 5) |
| 4b | Any `planned` with score >= 70 | `/amil:plan-module` |
| 5 | ALL modules `shipped` or `blocked` | Finalize cycle log, output completion |
| 5.5 | Blocked modules remain with retries available | Retry blocked (max 2 retries each) |

## Step-by-Step

### Step 1: Read State

```bash
node amil-tools.cjs module-status read --raw
# Read ONLY the compact summary (first 15 lines) for context efficiency
head -15 .planning/ERP_CYCLE_LOG.md
```

Parse module statuses into counts:
- planned_count, spec_approved_count, generated_count
- checked_count, shipped_count, blocked_count, total

### Step 2: Select Action (Priority Table)

Apply priority table top-to-bottom. First match wins.

### Step 3: Execute Action

Run the selected slash command. Log result to cycle log:
```bash
node amil-tools.cjs cycle-log append '{
  "iteration": N,
  "module": "uni_fee",
  "action": "generate-module",
  "result": "success",
  "wave": 3,
  "stats": {"shipped": 25, "total": 92, "in_progress": 3, "remaining": 64},
  "next_action": "verify-work for uni_fee"
}'
```

### Step 4: Coherence Check (after generation)

After every module generation, run coherence validation:
```bash
node amil-tools.cjs coherence check --registry .planning/model_registry.json
```

If coherence warnings found:
1. Log warning to cycle log via `cycle-log coherence`
2. If CRITICAL (duplicate model name, circular dep): BLOCK module
3. If WARNING (unresolved Many2one): check provisional registry — may resolve when target builds

### Step 5: Error Handling

On failure:
1. Log error to cycle log
2. If first failure for this module: retry once
3. If second failure: mark as BLOCKED in cycle log, skip
4. If 3+ modules blocked in a row: pause and ask human for guidance
5. Continue to next module

```bash
node amil-tools.cjs cycle-log blocked "uni_fee" "Docker install failed: missing depends"
```

### Step 6: Completion Check

If all modules are `shipped` or `blocked`:
1. Finalize cycle log with summary
2. Print completion report including coherence stats
3. If blocked modules exist: report them with reasons
4. Notify user to check Docker instance at http://localhost:8069
5. If using Ralph Loop: output `<promise>ERP COMPLETE</promise>`

## Wave Strategy (90+ modules)

The dependency graph + tier system already handles ordering:
- `dep-graph order` returns topological sort
- `dep-graph can-generate {name}` checks readiness
- `module-status tiers` groups by tier

For 90+ modules, generation follows a 6-wave strategy:

| Wave | Tier | Module Count | Description |
|------|------|-------------|-------------|
| 1 | Foundation | 5-8 | Base modules: core, contacts, settings |
| 2 | Domain Core | 10-15 | Primary domains: HR, Finance, Academic, Inventory |
| 3 | Domain Extensions | 15-20 | Extensions: Payroll, Budgeting, Grading, Warehouse |
| 4 | Operations | 15-20 | Cross-domain: Scheduling, Reporting, Communication |
| 5 | Support | 12-15 | Support: Helpdesk, Document Mgmt, Quality Control |
| 6 | Integration | 10-15 | Glue: Dashboards, Portals, Workflows, Admin |

Discussion batching follows the same wave order:
- Wave 1 discussed first (3-5 modules, full depth)
- Wave 2 discussed next (10-15 modules, 2-3 batches)
- Brief-discussion modules discussed last (8 at a time)

Generation is strictly sequential (one at a time through belt).
Verification and shipping happen between generations to keep belt unblocked.

## Human Interaction Points

The workflow STOPS and waits for human input at:
1. PRD decomposition approval (after `new-erp`)
2. Module discussion questions (during `batch-discuss`)
3. Spec approval (during `plan-module`)
4. Generation approval (during `generate-module` step 10)
5. UAT verification (during `verify-work`)
6. **Live UAT checkpoints** — after every 10 modules shipped (see Gap 6)
7. **Blocked module triage** — after 3+ consecutive blocks

Ralph Loop handles this naturally — when Claude asks a question,
the loop pauses until the human responds.

## Docker Integration

Before starting the generation loop:
```bash
amil-utils factory-docker --action start
```

After each module ships:
```bash
amil-utils factory-docker --install /path/to/module
```

After every 10 modules shipped — cross-module integration test:
```bash
amil-utils factory-docker --cross-test mod1 mod2 mod3 ... mod10
```

Docker stays alive until human runs:
```bash
amil-utils factory-docker --action stop
```
```

---

## Gap 5: Cross-Module Coherence Engine

**Difficulty:** Hard
**Files to create/modify:** 3 new, 2 modified

### Problem

At 90+ modules, **coherence is the #1 risk**. The existing coherence checker (`coherence.cjs`) validates 4 things: Many2one targets exist, no duplicate models, dependency graph is valid, security groups are defined. This works when checking a newly generated module against already-built modules. But at 90+ modules, a critical gap emerges:

**Forward References:** Module 15 may need a Many2one to a model defined in module 60. When module 15 is being generated, module 60 doesn't exist yet. The current system would flag this as an error and either block module 15 or generate it without the reference — both wrong.

**Dependency Chains:** At 90+, chains like `A → B → C → D → E → F` are common. If module C fails, modules D, E, F are all blocked. Need early detection of fragile chains.

**Circular Dependencies:** In ERP domains, HR references Payroll, Payroll references HR. Attendance references Leave, Leave references Attendance. These circular dependencies are unavoidable in business logic but the topological sort can't handle them.

### Solution

Build a **Provisional Registry** + **Forward Reference Resolver** + **Circular Dependency Breaker**.

### Concept: Provisional Registry

The Provisional Registry holds **promised models** — models that are declared in module specs/decomposition but not yet generated. When module 15 references `hr.payroll.slip`, the system checks:

1. Real Registry (built modules) — model exists? → valid reference
2. Provisional Registry (planned modules) — model promised? → valid forward reference, flag dependency
3. Neither — invalid reference, flag error

As modules are built, their models move from provisional → real.

### File 1: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/provisional-registry.cjs`

```javascript
/**
 * Provisional Registry — Tracks "promised" models from modules that
 * haven't been generated yet. Populated from decomposition data and
 * spec.json files. Models move to the real registry when generated.
 *
 * This solves the forward reference problem at 90+ modules:
 * Module 15 can reference module 60's model because the provisional
 * registry knows module 60 WILL provide that model.
 */

const fs = require('fs');
const path = require('path');

const PROV_REGISTRY_FILE = 'provisional_registry.json';

function getProvRegistryPath(cwd) {
  return path.join(cwd, '.planning', PROV_REGISTRY_FILE);
}

/**
 * Build provisional registry from decomposition data.
 * Called once after PRD decomposition, updated after each spec.
 *
 * @param {Object} decomposition - The full decomposition.json
 * @returns {Object} provisionalRegistry
 */
function buildFromDecomposition(decomposition) {
  const registry = {
    version: 1,
    built_at: new Date().toISOString(),
    source: 'decomposition',
    modules: {},
    models: {},       // model_name -> { module, fields[], confidence }
    references: [],   // { from_module, from_model, to_model, type }
  };

  for (const mod of (decomposition.modules || [])) {
    const moduleName = mod.name;
    registry.modules[moduleName] = {
      status: 'provisional',
      model_count: (mod.models || []).length,
      depends: mod.depends || mod.base_depends || [],
    };

    for (const model of (mod.models || [])) {
      const modelName = model.name;
      const fields = (model.fields || []).map(f => ({
        name: f.name,
        type: f.type,
        comodel_name: f.comodel_name || null,
      }));

      registry.models[modelName] = {
        module: moduleName,
        fields,
        confidence: model.fields?.length > 2 ? 'high' : 'low',
        source: 'decomposition',
      };

      // Track cross-module references
      for (const field of (model.fields || [])) {
        if (field.comodel_name) {
          registry.references.push({
            from_module: moduleName,
            from_model: modelName,
            to_model: field.comodel_name,
            field_name: field.name,
            type: field.type, // Many2one, One2many, Many2many
          });
        }
      }
    }
  }

  return registry;
}

/**
 * Update provisional registry when a spec.json is approved.
 * Spec data is more detailed than decomposition, so it overwrites.
 *
 * @param {Object} registry - Current provisional registry
 * @param {Object} spec - The approved spec.json
 * @returns {Object} Updated registry
 */
function updateFromSpec(registry, spec) {
  const moduleName = spec.module_name;
  const newRegistry = JSON.parse(JSON.stringify(registry)); // immutable

  newRegistry.modules[moduleName] = {
    ...newRegistry.modules[moduleName],
    status: 'spec_approved',
    model_count: (spec.models || []).length,
    depends: spec.depends || [],
  };

  for (const model of (spec.models || [])) {
    const modelName = model.name;
    const fields = (model.fields || []).map(f => ({
      name: f.name,
      type: f.type,
      comodel_name: f.comodel_name || null,
    }));

    newRegistry.models[modelName] = {
      module: moduleName,
      fields,
      confidence: 'high', // spec-level detail
      source: 'spec',
    };

    // Update references
    newRegistry.references = newRegistry.references.filter(
      r => r.from_module !== moduleName || r.from_model !== modelName
    );
    for (const field of (model.fields || [])) {
      if (field.comodel_name) {
        newRegistry.references.push({
          from_module: moduleName,
          from_model: modelName,
          to_model: field.comodel_name,
          field_name: field.name,
          type: field.type,
        });
      }
    }
  }

  return newRegistry;
}

/**
 * Mark a module as "built" — its models graduate from provisional
 * to the real registry. Called after successful generation.
 *
 * @param {Object} registry - Current provisional registry
 * @param {string} moduleName - The module that was just generated
 * @returns {Object} Updated registry with module marked as built
 */
function markBuilt(registry, moduleName) {
  const newRegistry = JSON.parse(JSON.stringify(registry));

  if (newRegistry.modules[moduleName]) {
    newRegistry.modules[moduleName].status = 'built';
  }

  // Models for this module are now in the real registry
  // Keep them in provisional for reference resolution, but mark as built
  for (const [modelName, modelData] of Object.entries(newRegistry.models)) {
    if (modelData.module === moduleName) {
      newRegistry.models[modelName] = {
        ...modelData,
        source: 'built',
      };
    }
  }

  return newRegistry;
}

/**
 * Resolve a model reference — check both real and provisional registries.
 *
 * @param {string} modelName - The model being referenced (e.g., 'hr.payroll.slip')
 * @param {Object} realRegistry - The real model_registry.json
 * @param {Object} provRegistry - The provisional registry
 * @returns {Object} { found, source, module, confidence }
 */
function resolveReference(modelName, realRegistry, provRegistry) {
  // Check base Odoo models (always valid)
  const BASE_PREFIXES = ['res.', 'ir.', 'mail.', 'base.', 'account.', 'sale.', 'purchase.', 'hr.', 'stock.'];
  if (BASE_PREFIXES.some(p => modelName.startsWith(p))) {
    // Check if it's a standard Odoo model vs a custom one
    // Standard models like res.partner, ir.cron are always valid
    const STANDARD_MODELS = [
      'res.partner', 'res.users', 'res.company', 'res.currency',
      'res.country', 'res.country.state', 'res.config.settings',
      'ir.cron', 'ir.attachment', 'ir.sequence', 'ir.mail_server',
      'mail.thread', 'mail.activity.mixin', 'mail.message',
    ];
    if (STANDARD_MODELS.includes(modelName)) {
      return { found: true, source: 'odoo_base', module: 'base', confidence: 'certain' };
    }
  }

  // Check real registry (built modules)
  if (realRegistry?.models?.[modelName]) {
    return {
      found: true,
      source: 'built',
      module: realRegistry.models[modelName].module,
      confidence: 'certain',
    };
  }

  // Check provisional registry (planned/spec'd modules)
  if (provRegistry?.models?.[modelName]) {
    const provModel = provRegistry.models[modelName];
    return {
      found: true,
      source: provModel.source, // 'decomposition', 'spec', or 'built'
      module: provModel.module,
      confidence: provModel.confidence,
    };
  }

  return { found: false, source: null, module: null, confidence: null };
}

/**
 * Analyze all forward references — find which planned modules
 * reference models in other planned modules. Returns a dependency
 * map that informs generation order.
 *
 * @param {Object} provRegistry - The provisional registry
 * @returns {Object} { forwardRefs, unresolvedRefs, circularRisks }
 */
function analyzeForwardReferences(provRegistry) {
  const forwardRefs = [];   // references from unbuilt → unbuilt
  const unresolvedRefs = []; // references to models that don't exist anywhere
  const circularRisks = [];  // pairs of modules that reference each other

  // Build module → referenced_modules map
  const moduleRefs = {}; // moduleName -> Set of referenced module names

  for (const ref of (provRegistry.references || [])) {
    const sourceModule = ref.from_module;
    const targetModel = ref.to_model;

    // Find which module provides the target model
    const targetModelData = provRegistry.models[targetModel];
    if (!targetModelData) {
      // Check if it's an Odoo base model
      const resolved = resolveReference(targetModel, null, provRegistry);
      if (!resolved.found) {
        unresolvedRefs.push({
          from_module: sourceModule,
          from_model: ref.from_model,
          to_model: targetModel,
          field: ref.field_name,
        });
      }
      continue;
    }

    const targetModule = targetModelData.module;
    if (targetModule === sourceModule) continue; // same module, not cross-module

    // Track forward reference
    if (targetModelData.source !== 'built') {
      forwardRefs.push({
        from_module: sourceModule,
        to_module: targetModule,
        from_model: ref.from_model,
        to_model: targetModel,
        field: ref.field_name,
      });
    }

    // Track module-level references for circular detection
    if (!moduleRefs[sourceModule]) moduleRefs[sourceModule] = new Set();
    moduleRefs[sourceModule].add(targetModule);
  }

  // Detect circular references (A→B and B→A)
  for (const [modA, refsA] of Object.entries(moduleRefs)) {
    for (const modB of refsA) {
      if (moduleRefs[modB]?.has(modA)) {
        // Only add each pair once
        const pair = [modA, modB].sort().join(':');
        if (!circularRisks.find(c => c.pair === pair)) {
          circularRisks.push({
            pair,
            modules: [modA, modB],
            refs_a_to_b: forwardRefs.filter(r => r.from_module === modA && r.to_module === modB),
            refs_b_to_a: forwardRefs.filter(r => r.from_module === modB && r.to_module === modA),
          });
        }
      }
    }
  }

  return { forwardRefs, unresolvedRefs, circularRisks };
}

/**
 * Find critical dependency chains — sequences of 4+ modules where
 * each depends on the previous. If any module in the chain fails,
 * everything downstream is blocked.
 *
 * @param {Object} provRegistry - The provisional registry
 * @returns {Array} chains sorted by length (longest = highest risk)
 */
function findCriticalChains(provRegistry) {
  // Build adjacency list from module dependencies
  const adj = {};
  for (const [modName, modData] of Object.entries(provRegistry.modules || {})) {
    adj[modName] = (modData.depends || []).filter(d =>
      provRegistry.modules[d] // Only count deps within our module set
    );
  }

  // DFS to find longest chain through each node
  const chains = [];
  const visited = new Set();

  function dfs(node, chain) {
    if (visited.has(node)) return;
    visited.add(node);
    chain.push(node);

    const deps = adj[node] || [];
    if (deps.length === 0 || deps.every(d => visited.has(d))) {
      if (chain.length >= 4) {
        chains.push([...chain]);
      }
    } else {
      for (const dep of deps) {
        if (!visited.has(dep)) {
          dfs(dep, chain);
        }
      }
    }

    chain.pop();
    visited.delete(node);
  }

  for (const mod of Object.keys(adj)) {
    dfs(mod, []);
  }

  // Sort by length descending
  chains.sort((a, b) => b.length - a.length);
  return chains.slice(0, 10); // Top 10 critical chains
}

/**
 * Save provisional registry to disk.
 */
function save(cwd, registry) {
  const registryPath = getProvRegistryPath(cwd);
  fs.writeFileSync(registryPath, JSON.stringify(registry, null, 2), 'utf8');
}

/**
 * Load provisional registry from disk.
 */
function load(cwd) {
  const registryPath = getProvRegistryPath(cwd);
  if (!fs.existsSync(registryPath)) return null;
  return JSON.parse(fs.readFileSync(registryPath, 'utf8'));
}

module.exports = {
  PROV_REGISTRY_FILE,
  getProvRegistryPath,
  buildFromDecomposition,
  updateFromSpec,
  markBuilt,
  resolveReference,
  analyzeForwardReferences,
  findCriticalChains,
  save,
  load,
};
```

### File 2: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/circular-dep-breaker.cjs`

```javascript
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
        // This will be added via model inheritance in a patch module
        // or via direct file edit if the module is still being built
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
```

### File 3: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/commands/amil/coherence-report.md`

New slash command for on-demand coherence analysis:

```yaml
---
name: coherence-report
description: Analyze cross-module coherence for the full ERP
allowed-tools:
  - Read
  - Bash
  - Glob
---
```

Process:
1. Load real registry + provisional registry
2. Run `analyzeForwardReferences()` — report unresolved refs
3. Run `findCriticalChains()` — report fragile dependency chains
4. Detect circular dependencies — report resolution strategy
5. Output coherence health score: `(resolved_refs / total_refs) × 100`
6. Flag modules that are "coherence bottlenecks" (many modules depend on them)

### Modifications

**`/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/coherence.cjs`** — Integrate provisional registry:

Add a `checkWithProvisional(module, realRegistry, provRegistry)` function that:
1. For each Many2one in the module, check real registry first
2. If not found, check provisional registry
3. If found in provisional: WARNING (valid forward reference, but target not built yet)
4. If found nowhere: ERROR (invalid reference)

**`/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/workflows/plan-module.md`** — After generating spec.json:

Add step to update provisional registry:
```bash
node amil-tools.cjs provisional-registry update-from-spec --spec .planning/modules/{name}/spec.json
```

### Tests

Add `/home/inshal-rauf/Factory-de-Odoo/orchestrator/tests/provisional-registry.test.cjs`:
- `buildFromDecomposition` creates registry from decomposition data
- `updateFromSpec` overwrites provisional data with spec data
- `markBuilt` transitions module from provisional to built
- `resolveReference` checks real → provisional → not found
- `analyzeForwardReferences` detects forward refs and circular risks
- `findCriticalChains` finds chains of 4+

Add `/home/inshal-rauf/Factory-de-Odoo/orchestrator/tests/circular-dep-breaker.test.cjs`:
- `analyzeCircularPair` correctly identifies primary/secondary
- `planBuildOrder` adjusts topological sort
- `generatePatchSpec` produces valid field additions
- Multiple circular pairs don't conflict

---

## Gap 6: Live UAT Flow

**Difficulty:** Medium
**Files to create/modify:** 2 new, 1 modified

### Problem

The current `verify-work` command is **conversational UAT** — Claude asks the user questions about whether the module works, and the user answers based on reading the code. At 90+ modules, this is:
1. Too slow — reading code for 90 modules is weeks of work
2. Not realistic — code review doesn't catch runtime behavior
3. Missing integration issues — modules that work alone but break together

Users need to **interact with the running ERP** — create records, trigger workflows, test cross-module flows — and report issues back to the pipeline for re-generation.

### Solution

Add a **Live UAT Flow** that:
1. Presents the user with a running Odoo instance at `http://localhost:8069`
2. Guides them through verification checkpoints per module wave
3. Captures feedback (pass/fail/issues) per module
4. Routes failed modules back through the generation pipeline
5. Runs cross-module interaction tests automatically

### File 1: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/workflows/live-uat.md`

```markdown
# Live UAT Flow — Interactive Module Verification

## Overview

After modules are installed in the persistent Docker instance, guide the
user through interactive verification. The user accesses the running Odoo
ERP via browser and tests real functionality.

This replaces the code-based conversational UAT for "checked" verification.
The conversational UAT remains for quick spec validation, but live UAT is
required for the final "checked → shipped" transition at scale.

## Prerequisites

- Persistent Docker instance running (`factory-docker --action status`)
- Module(s) installed in the instance
- User has browser access to http://localhost:8069

## UAT Checkpoint Triggers

Live UAT checkpoints are triggered:
1. After every **10 modules** are installed (wave checkpoint)
2. After a **critical dependency chain** completes (chain checkpoint)
3. After **all modules** are installed (final checkpoint)
4. On **user request** (ad-hoc checkpoint)

## Wave Checkpoint Flow

### Step 1: Present Checkpoint Summary

```
=== LIVE UAT CHECKPOINT: Wave 3 ===

Modules installed since last checkpoint:
  1. uni_exam_scheduling (exam creation, scheduling, room assignment)
  2. uni_exam_grading (grade entry, GPA computation, transcripts)
  3. uni_exam_results (result publication, student notifications)
  4. uni_timetable_core (class scheduling, room allocation)
  5. uni_timetable_conflicts (conflict detection, resolution)
  ... (up to 10)

Odoo instance: http://localhost:8069
Credentials: admin / admin

Please test the following flows and report results:
```

### Step 2: Generate Verification Checklist

For each module in the checkpoint, generate 2-3 key flows to test:

```
[ ] uni_exam_scheduling:
    1. Create an exam → assign room → check calendar view
    2. Schedule conflicting exam → verify conflict warning

[ ] uni_exam_grading:
    1. Enter grades for students → verify GPA computation
    2. Generate transcript PDF → check formatting

[ ] uni_timetable_core:
    1. Create class schedule → verify room not double-booked
    2. View weekly timetable → check all classes appear
```

Also generate cross-module flows:
```
[ ] CROSS-MODULE: Exam + Timetable
    1. Schedule exam during class time → verify conflict detected
    2. View student's weekly schedule → verify both classes and exams appear
```

### Step 3: Collect Feedback

Present options per module:
- **PASS** — Module works as expected
- **MINOR** — Works but has cosmetic/UX issues (logged, not re-generated)
- **FAIL** — Critical functionality broken (triggers re-generation)
- **SKIP** — Can't test right now (stays at "checked")

For FAIL results, capture:
- What was attempted
- What happened vs what was expected
- Error messages (if any)
- Screenshot description

### Step 4: Route Failures

For each FAIL result:
1. Transition module back to `spec_approved` (allows re-generation)
2. Create `.planning/modules/{name}/uat-feedback.md` with failure details
3. Append to cycle log as a coherence event
4. The run-prd loop will pick it up and re-generate with the feedback

For MINOR results:
1. Create `.planning/modules/{name}/uat-minor-issues.md`
2. Transition to `shipped` (issues logged for future improvement)

### Step 5: Cross-Module Integration Test

After collecting per-module feedback, run automated cross-module tests:

```bash
amil-utils factory-docker --cross-test mod1 mod2 mod3 ... mod10
```

Report results to user. If integration tests fail, identify which
module pair is causing the issue.

## Final Checkpoint (All Modules)

After all 90+ modules are installed and per-wave UAT is complete:

1. Present full ERP summary:
   - Total modules: 92
   - Passed UAT: 85
   - Minor issues: 4
   - Re-generated: 3
   - Blocked: 0

2. Full cross-module integration test

3. Present the complete ERP for final sign-off:
   ```
   Your ERP is ready for review at http://localhost:8069

   Key flows to test end-to-end:
   [ ] Student enrollment → fee generation → payment → receipt
   [ ] Course creation → timetable → exam scheduling → grading → transcript
   [ ] Employee onboarding → payroll → attendance → leave management
   ```

4. On final approval: transition all remaining `checked` → `shipped`
```

### File 2: `/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/bin/lib/uat-checkpoint.cjs`

```javascript
/**
 * UAT Checkpoint Manager — Tracks verification checkpoints and
 * generates verification checklists for live UAT sessions.
 */

const fs = require('fs');
const path = require('path');

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
  const moduleModels = {};
  for (const mod of modules) {
    for (const model of (mod.models || [])) {
      for (const field of (model.fields || [])) {
        if (field.comodel_name) {
          // Find if comodel belongs to another module in this checkpoint
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
```

### Modification

**`/home/inshal-rauf/Factory-de-Odoo/orchestrator/amil/workflows/verify-work.md`** — Add live UAT option:

After the existing conversational UAT, add:

```markdown
## Step 8: Live UAT Option (for persistent Docker)

If the persistent Docker instance is running and the module is installed:

1. Ask user: "Would you like to do live UAT in the browser? The module is
   installed at http://localhost:8069"

2. If yes: switch to live UAT flow
   - Present verification checklist for this specific module
   - Collect pass/minor/fail feedback
   - Route failures back to generation

3. If no: continue with conversational UAT (existing flow)

For the `--wave` flag (batch verification):
- Present all modules in the wave together
- Include cross-module flows
- Collect feedback per module
```

### Tests

Add `/home/inshal-rauf/Factory-de-Odoo/orchestrator/tests/uat-checkpoint.test.cjs`:
- `isCheckpointDue` returns true after interval modules
- `generateChecklist` produces per-module and cross-module flows
- `recordResult` writes correct files for pass/minor/fail/skip
- `getUATSummary` aggregates results correctly
- Failure feedback creates `uat-feedback.md`
- Cross-module flow detection finds shared references

---

## Gap 7: MCP Server Expansion

**Difficulty:** Medium
**Files to modify:** 1 existing, 1 new test file

### Problem

The MCP server at `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/mcp/server.py` exposes 6 tools. At 90+ modules, the coherence engine and generators need answers to 3 questions the existing tools cannot answer:

1. **View inheritance chain** — Which views inherit from which? When generating module #45, the view generator needs to know the full inheritance chain for `res.partner` form view to avoid conflicting XPATHs.
2. **Model relations** — What models point to this model, and what does this model point to? The coherence checker needs this to validate Many2one targets without scanning every module's Python files.
3. **Field conflicts** — Does this field already exist on this model (defined by another module)? Prevents duplicate field definitions across 90+ modules.

### Existing Code Pattern

All 6 existing tools follow the same pattern:
```python
@mcp.tool()
def tool_name(param: str) -> str:
    """Docstring with Args and Returns."""
    try:
        client = _get_client()
        result = client.search_read("ir.model", domain, fields)
        # Format result as readable string
        return formatted_string
    except Exception as exc:
        return _handle_error(exc)
```

### Implementation

Add 3 new tools to `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/mcp/server.py`, inserting after the `get_view_arch` function (after line 293, before the `# Entry point` comment at line 296):

#### Tool 1: `get_view_inheritance_chain`

```python
@mcp.tool()
def get_view_inheritance_chain(model_name: str, view_type: str = "form") -> str:
    """Trace the full view inheritance chain for an Odoo model.

    Queries ir.ui.view to find the base view (inherit_id=False) and all
    inherited views, sorted by priority. Essential for avoiding XPATH
    conflicts when multiple modules extend the same view.

    Args:
        model_name: Technical model name (e.g. 'res.partner').
        view_type: View type to trace ('form', 'tree', 'kanban', 'search').
                   Defaults to 'form'.

    Returns:
        Chain showing base view → inherited views with priority and module.
    """
    try:
        client = _get_client()
        # Get ALL views for this model+type
        all_views = client.search_read(
            "ir.ui.view",
            [["model", "=", model_name], ["type", "=", view_type]],
            ["name", "inherit_id", "priority", "arch", "xml_id"],
        )
        if not all_views:
            return f"No {view_type} views found for model '{model_name}'"

        # Separate base views (no inherit_id) from inherited views
        base_views = [v for v in all_views if not v.get("inherit_id")]
        inherited = [v for v in all_views if v.get("inherit_id")]
        inherited.sort(key=lambda v: v.get("priority", 16))

        parts = [f"View inheritance chain for {model_name} ({view_type}):"]
        parts.append(f"Total views: {len(all_views)} ({len(base_views)} base, {len(inherited)} inherited)")
        parts.append("")

        for bv in base_views:
            parts.append(f"BASE: {bv['name']} (xml_id: {bv.get('xml_id', 'N/A')}, priority: {bv.get('priority', 16)})")

        parts.append("")
        for iv in inherited:
            parent_name = iv["inherit_id"][1] if iv.get("inherit_id") else "unknown"
            parts.append(
                f"  INHERITS: {iv['name']} → parent: {parent_name} "
                f"(priority: {iv.get('priority', 16)}, xml_id: {iv.get('xml_id', 'N/A')})"
            )

        return "\n".join(parts)
    except Exception as exc:
        return _handle_error(exc)
```

#### Tool 2: `get_model_relations`

```python
@mcp.tool()
def get_model_relations(model_name: str) -> str:
    """Get all relational fields pointing to/from an Odoo model.

    Queries ir.model.fields to find:
    - Outgoing relations: Many2one/One2many/Many2many fields ON this model
    - Incoming relations: Many2one/One2many/Many2many fields on OTHER models pointing TO this model

    Essential for the coherence engine to validate cross-module references
    without scanning Python source files.

    Args:
        model_name: Technical model name (e.g. 'res.partner').

    Returns:
        Formatted list of outgoing and incoming relational fields.
    """
    try:
        client = _get_client()
        relation_types = ["many2one", "one2many", "many2many"]

        # Outgoing: relational fields defined ON this model
        outgoing = client.search_read(
            "ir.model.fields",
            [["model", "=", model_name], ["ttype", "in", relation_types]],
            ["name", "ttype", "relation", "field_description"],
        )

        # Incoming: fields on OTHER models that point TO this model
        incoming = client.search_read(
            "ir.model.fields",
            [["relation", "=", model_name], ["ttype", "in", relation_types]],
            ["name", "ttype", "model", "field_description"],
        )

        parts = [f"Relations for {model_name}:"]
        parts.append(f"\nOutgoing ({len(outgoing)} fields — this model references others):")
        if outgoing:
            for f in outgoing:
                parts.append(f"  {f['name']} ({f['ttype']}) → {f['relation']}")
        else:
            parts.append("  (none)")

        parts.append(f"\nIncoming ({len(incoming)} fields — other models reference this):")
        if incoming:
            for f in incoming:
                parts.append(f"  {f['model']}.{f['name']} ({f['ttype']}) → {model_name}")
        else:
            parts.append("  (none)")

        return "\n".join(parts)
    except Exception as exc:
        return _handle_error(exc)
```

#### Tool 3: `find_field_conflicts`

```python
@mcp.tool()
def find_field_conflicts(model_name: str, field_name: str) -> str:
    """Check if a field already exists on an Odoo model (potential conflict).

    Queries ir.model.fields to see if field_name is already defined on
    model_name by any installed module. Prevents duplicate field definitions
    across 90+ generated modules.

    Args:
        model_name: Technical model name (e.g. 'res.partner').
        field_name: Field name to check (e.g. 'x_custom_score').

    Returns:
        CONFLICT with details if field exists, CLEAR if not.
    """
    try:
        client = _get_client()
        existing = client.search_read(
            "ir.model.fields",
            [["model", "=", model_name], ["name", "=", field_name]],
            ["name", "ttype", "field_description", "modules"],
        )
        if existing:
            f = existing[0]
            modules = f.get("modules", "unknown")
            return (
                f"CONFLICT: Field '{field_name}' already exists on '{model_name}' "
                f"(type: {f['ttype']}, label: {f.get('field_description', 'N/A')}, "
                f"defined by: {modules})"
            )
        return f"CLEAR: Field '{field_name}' does not exist on '{model_name}'"
    except Exception as exc:
        return _handle_error(exc)
```

### How These Tools Integrate

| Tool | Used By | When |
|------|---------|------|
| `get_view_inheritance_chain` | `amil-view-gen` agent | Before generating inherited views, to check existing XPATH targets |
| `get_model_relations` | Coherence engine (`coherence.cjs`) | During cross-module coherence check, replaces Python file scanning |
| `find_field_conflicts` | `amil-model-gen` agent | Before adding fields to existing models, prevents duplicates |

The coherence engine calls these tools via the MCP client when the persistent Docker instance (Gap 2) is running. If Docker is not running, the engine falls back to registry-only checks (existing behavior).

### Tests

Add `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/tests/test_mcp_server_expansion.py`:

Follow the existing test pattern in `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/tests/test_mcp_server.py` — mock `_get_client()` to return a `MagicMock`, then assert each tool formats output correctly.

- `test_get_view_inheritance_chain_base_and_inherited` — mock returns 1 base + 2 inherited views, assert output contains "BASE:" and "INHERITS:" lines with correct priority ordering
- `test_get_view_inheritance_chain_no_views` — mock returns empty list, assert "No form views found"
- `test_get_model_relations_outgoing_and_incoming` — mock returns outgoing Many2one + incoming One2many, assert both sections populated
- `test_get_model_relations_no_relations` — mock returns empty for both queries, assert "(none)" in both sections
- `test_find_field_conflicts_exists` — mock returns existing field, assert output starts with "CONFLICT:"
- `test_find_field_conflicts_clear` — mock returns empty, assert output starts with "CLEAR:"
- `test_all_new_tools_handle_errors` — mock `_get_client()` raising `ConnectionRefusedError`, assert each tool returns error message without crashing

---

## Gap 8: Auto-Fix Smart Guard

**Difficulty:** Easy
**Files to modify:** 1 existing (`auto_fix.py`), 1 existing test file

### Problem

The auto-fix loop at `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/auto_fix.py` has a 5-iteration cap (`DEFAULT_MAX_FIX_ITERATIONS = 5`). Currently, if a fix for pattern X fails on iteration 1, the loop will re-identify pattern X and retry the same fix on iteration 2, 3, 4, and 5 — wasting 4 iterations.

At 90+ modules (90+ Docker validation passes), this waste compounds. A module with 2 fixable errors and 1 unfixable error currently wastes 3 iterations retrying the unfixable one.

### Current Behavior

```
Iteration 1: identify "missing_acl" → fix_missing_acl() → re-validate → still failing
Iteration 2: identify "missing_acl" → fix_missing_acl() → re-validate → still failing (WASTED)
Iteration 3: identify "missing_acl" → fix_missing_acl() → re-validate → still failing (WASTED)
Iteration 4: identify "missing_acl" → fix_missing_acl() → re-validate → still failing (WASTED)
Iteration 5: cap reached, escalate
```

### Target Behavior

```
Iteration 1: identify "missing_acl" → fix_missing_acl() → re-validate → still failing
Iteration 2: "missing_acl" in tried_patterns, SKIP → identify "xml_parse_error" → fix → re-validate → fixed!
Iteration 3: no more fixable patterns → break early
```

### Implementation

Modify `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/auto_fix.py`:

#### Step 1: Update `_dispatch_docker_fix` signature

Change the function signature and return type. The function currently returns `bool`. Change it to return `tuple[bool, str | None]` where the second element is the pattern ID that was attempted (or `None` if no fix applied):

```python
def _dispatch_docker_fix(
    module_path: Path,
    error_output: str,
    tried_patterns: set[str] | None = None,
) -> tuple[bool, str | None]:
    """Dispatch a single Docker fix based on error pattern identification.

    Args:
        module_path: Root path of the Odoo module.
        error_output: The error text from Docker validation.
        tried_patterns: Set of pattern IDs already attempted. These are
            skipped to avoid wasting iterations. None means no filtering.
            The "unused_import" pattern is exempt (cumulative fix).

    Returns:
        Tuple of (fix_applied, pattern_id). pattern_id is the ID of the
        pattern that was attempted, or None if no fix was applied.
    """
```

#### Step 2: Add skip logic inside `_dispatch_docker_fix`

After the existing unused-import check (which remains exempt from deduplication — unused imports are cumulative fixes that can succeed on retry), add the skip logic before the dispatch dict lookup:

```python
    # Standard Docker pattern identification
    pattern_id = identify_docker_fix(error_output)

    if pattern_id is None:
        logger.debug("run_docker_fix_loop: no fixable pattern identified")
        return (False, None)

    # Skip patterns already tried (except unused_import which is cumulative)
    if tried_patterns is not None and pattern_id in tried_patterns:
        logger.info(
            "run_docker_fix_loop: skipping already-tried pattern '%s'",
            pattern_id,
        )
        return (False, pattern_id)

    logger.info("run_docker_fix_loop: detected pattern '%s'", pattern_id)
```

Update the return statements at the end of `_dispatch_docker_fix` to return tuples:

```python
    # Where it currently returns False:
    return (False, pattern_id)

    # Where it currently returns result:
    return (result, pattern_id)
```

#### Step 3: Update `run_docker_fix_loop` to track tried patterns

Add `tried_patterns` set initialization and update the call to `_dispatch_docker_fix`:

```python
def run_docker_fix_loop(
    module_path: Path,
    error_output: str,
    max_iterations: int = DEFAULT_MAX_FIX_ITERATIONS,
    revalidate_fn: object | None = None,
) -> Result[tuple[bool, str]]:
    # ... existing docstring ...
    import logging
    logger = logging.getLogger(__name__)

    any_fix_applied = False
    current_error = error_output
    tried_patterns: set[str] = set()  # <-- ADD THIS LINE

    for iteration in range(max_iterations):
        logger.debug("run_docker_fix_loop: iteration %d/%d", iteration + 1, max_iterations)

        fixed, pattern_id = _dispatch_docker_fix(  # <-- UNPACK TUPLE
            module_path, current_error, tried_patterns,
        )

        if not fixed:
            # If a pattern was identified but skipped (in tried_patterns),
            # that's also "not fixed" — we break to avoid infinite skip loops
            logger.debug("run_docker_fix_loop: no fix applied in iteration %d", iteration + 1)
            break

        any_fix_applied = True
        if pattern_id is not None:
            tried_patterns.add(pattern_id)  # <-- TRACK IT

        # ... rest of loop unchanged (revalidate logic) ...
```

### Backward Compatibility

The `tried_patterns` parameter on `_dispatch_docker_fix` defaults to `None`, so any external caller that imports and calls `_dispatch_docker_fix(module_path, error_output)` directly continues to work with no filtering. The return type changes from `bool` to `tuple[bool, str | None]`, which is a breaking change for direct callers — but this is an internal `_` prefixed function with no external consumers.

### Tests

Update `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/tests/test_auto_fix.py` with these new test cases:

- `test_dispatch_docker_fix_returns_tuple` — call `_dispatch_docker_fix` with a known error pattern, assert result is `(True, "pattern_id")` tuple
- `test_dispatch_docker_fix_skips_tried_pattern` — pass `tried_patterns={"missing_acl"}`, feed error matching `missing_acl`, assert result is `(False, "missing_acl")`
- `test_dispatch_docker_fix_unused_import_exempt` — pass `tried_patterns` containing unused-import indicator, verify unused imports are still fixed (cumulative fix exempt from dedup)
- `test_dispatch_docker_fix_tried_patterns_none` — pass `tried_patterns=None`, verify no filtering occurs (backward compat)
- `test_run_docker_fix_loop_tracks_tried_patterns` — mock dispatch to succeed on first pattern, fail (same pattern) on second, assert loop breaks after 2 iterations instead of hitting cap
- `test_run_docker_fix_loop_breaks_early_when_all_tried` — mock 2 patterns, both tried, assert loop breaks on iteration 1

---

## Ralph Loop Integration

### Prerequisites

Install the Ralph Loop Claude Code plugin from `https://github.com/frankbria/ralph-claude-code`:

```bash
# Install as Claude Code plugin (follow the repo's README for exact steps)
# This provides /ralph-loop and /cancel-ralph slash commands in Claude Code
```

Once installed, `/ralph-loop` and `/cancel-ralph` are available as slash commands.

### How It Works

Ralph Loop (`/ralph-loop`) feeds the SAME prompt to Claude repeatedly. Each iteration:
1. Claude receives the prompt
2. Reads file state (module_status.json, ERP_CYCLE_LOG.md compact summary)
3. Picks the next action from the priority table
4. Executes it
5. Claude tries to exit → stop hook re-feeds the prompt
6. Next iteration sees updated files

### The Ralph Prompt

```
/ralph-loop "
You are the Factory de Odoo orchestrator. Run /amil:run-prd to
execute the next iteration of the ERP generation cycle.

BEFORE EACH ITERATION:
1. Read .planning/ERP_CYCLE_LOG.md — ONLY the compact summary (first 15 lines)
2. Read .planning/module_status.json for current state
3. The run-prd workflow will select the right action automatically

RULES:
- Follow the priority table in the run-prd workflow
- NEVER skip human interaction points — wait for answers
- Log every action to the cycle log
- After every 10 modules shipped: trigger live UAT checkpoint
- If all modules shipped: output <promise>ERP COMPLETE</promise>
- If context resets: read ERP_CYCLE_LOG.md compact summary first — it has enough to resume
- If 3+ modules blocked in a row: STOP and ask human for guidance

COHERENCE:
- After every generation: run coherence check
- If forward reference found: check provisional registry
- If circular dep detected: follow circular-dep-breaker resolution

DOCKER: ensure factory Docker is running before first generation.
User verifies at http://localhost:8069 during live UAT checkpoints.
" --completion-promise "ERP COMPLETE" --max-iterations 500
```

### Why Ralph Works Here

| Ralph Feature | How It Helps |
|--------------|-------------|
| Same prompt repeated | Each iteration reads file state — naturally picks up where last left off |
| Self-referential via files | module_status.json, cycle log, registries all persist between iterations |
| Completion promise | `<promise>ERP COMPLETE</promise>` when all modules shipped |
| Max iterations cap | Safety net — 500 iterations for 90+ modules |
| Stop hook intercept | Keeps the loop going without manual re-invocation |
| Human input pauses | Ralph naturally pauses when Claude asks a question |

### Context Reset Handling

At 90+ modules, context resets **will** happen frequently (every ~15-20 iterations). The compact summary header is the lifeline:

```
<!-- COMPACT-SUMMARY-START -->
## Quick Resume
- **Last Iteration:** 147
- **Shipped:** 52/92
- **In Progress:** 1
- **Blocked:** 3
- **Next Action:** generate-module for uni_portal
- **Current Wave:** 4
- **Coherence Warnings:** 2
<!-- COMPACT-SUMMARY-END -->
```

After context reset, Claude reads just these 10 lines and knows exactly where to resume. No need to read the full 2000+ line log.

### Iteration Budget for 90+ Modules

| Phase | Iterations per Module | Total for 90 Modules |
|-------|----------------------|---------------------|
| Decomposition | 1 (one-time) | 1 |
| Discussion | 0.5 avg (batched in groups of 5) | ~9 batches = 9 |
| Spec generation | 1 | 90 |
| Generation | 1 | 90 |
| Verification | 0.5 avg (some pass, some fail) | ~60 |
| Shipping | 0.3 avg (auto for many) | ~30 |
| Retries | 0.2 avg (re-gen failures) | ~18 |
| UAT checkpoints | 1 per 10 modules | ~9 |
| Coherence checks | included in generation | 0 |
| **Total** | | **~307** |

500 max iterations provides ~60% headroom for errors, human delays, and re-generations.

---

## Codebase Fixes Required

These are bugs discovered during Phase C E2E verification that should be fixed
before running 90+ module generation.

### Fix 1: Chatter Template Mismatch (CRITICAL)

**File 1:** `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/17.0/view_form.xml.j2` line 188
**File 2:** `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/18.0/view_form.xml.j2` (same line)

**Current (buggy):**
```jinja2
{% if 'mail' in depends %}
```

**Replace with:**
```jinja2
{% if chatter %}
```

**Context:** The `chatter` variable is computed in `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/renderer_context.py` lines 110-122. It is `False` for line-item models (models with required Many2one `_id` to another in-module model). The template ignores this and checks module-level `depends` instead, adding chatter XML to ALL models. This causes Docker install failures because `message_follower_ids` doesn't exist on models without `mail.thread` inheritance.

**Impact at 90+ modules:** Estimated **60+ of 90 modules** affected — every module with a line-item model.

### Fix 2: Cron model vs model_name Mismatch

**File:** `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/shared/cron_data.xml.j2` line 18

The template uses `cron.model_name` but the Pydantic `CronJobSpec` schema outputs
`model` after `model_dump()`. User-supplied crons use the `model` key.

**Fix options:**
- A) Add a preprocessor that copies `model` → `model_name` for cron jobs
- B) Change the template to `{{ cron.model_name | default(cron.model) }}`

Option B is simpler:
```jinja2
<field name="model_id" ref="model_{{ (cron.model_name | default(cron.model)) | replace('.', '_') }}"/>
```

### Fix 3: Portal Empty Class Body

**File:** `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/shared/portal_controller.py.j2`

When `portal: {}` (empty dict) is passed, the template generates an empty class body
which is a Python syntax error. Add a `pass` statement:

```jinja2
class CustomerPortal(portal.CustomerPortal):
{% if portal_routes %}
    ... existing route rendering ...
{% else %}
    pass
{% endif %}
```

### Fix 4: Manifest Load Order — Wizard Views After Model Views (CRITICAL)

**Discovered:** 2026-03-10, employee_training module generation session.
**File:** `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/renderer_context.py` lines 586-587

**Current (buggy):**
```python
# Line 567-587 in _compute_manifest_data():
for model in spec.get("models", []):
    model_var = _to_python_var(model["name"])
    manifest_files.append(f"views/{model_var}_views.xml")       # Position 5
    manifest_files.append(f"views/{model_var}_action.xml")

# ... dashboard views ...

manifest_files.append("views/menu.xml")                          # Position 6
manifest_files.extend(wizard_view_files)                          # Position 7 ← TOO LATE!
```

**Root Cause:** Wizard view files define `ir.actions.act_window` records (e.g., `employee_training_attendance_wizard_action`). Model view files reference these wizard actions via `%(module.wizard_action_id)d` in button definitions. Because Odoo loads data files sequentially, the wizard action XML ID doesn't exist yet when the model view tries to resolve it.

**Error message:** `ValueError: External ID not found in the system: employee_training.employee_training_attendance_wizard_action`

**Impact at 90+ modules:** Every module with a wizard action referenced from a model view button will fail Docker install. Estimated **30-40 of 90 modules** affected (any module with wizard-triggered buttons in form views).

**Fix:** Move `wizard_view_files` BEFORE model view files:

```python
# Correct order in _compute_manifest_data():
manifest_files.extend(wizard_view_files)                          # Wizards FIRST (define actions)

for model in spec.get("models", []):
    model_var = _to_python_var(model["name"])
    manifest_files.append(f"views/{model_var}_views.xml")         # Model views SECOND (reference wizard actions)
    manifest_files.append(f"views/{model_var}_action.xml")

# ... dashboard views ...

manifest_files.append("views/menu.xml")                           # Menu LAST (references all actions)
```

**Note:** The auto-fix system (`auto_fix.py:fix_manifest_load_order()`) already handles this as a reactive post-failure fix, but fixing `_compute_manifest_data()` eliminates the error at generation time — no auto-fix round needed. The auto-fix remains as a safety net for edge cases.

**Canonical load order (corrected):**
```
1. security/security.xml           (groups, categories)
2. security/ir.model.access.csv   (ACLs reference groups)
3. security/record_rules.xml      (if has_company_modules)
4. data files                      (sequences, data, cron, reports, mail templates)
5. wizard view files               (define wizard actions — BEFORE model views)
6. per-model view + action files   (may reference wizard actions via %(action_id)d)
7. dashboard view files            (graph, pivot, kanban, cohort)
8. views/menu.xml                  (references all actions)
```

### Fix 5: Templates Use `_()` Instead of `self.env._()` — W8161 on Every Generated Module (CRITICAL)

**Discovered:** 2026-03-10, employee_training module generation session (22 pylint violations from W8113/W8161).
**Files affected:**
- `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/17.0/model.py.j2` (lines 9-11, ~8 usages)
- `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/18.0/model.py.j2` (~8 usages)
- `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/shared/bulk_wizard_model.py.j2` (1 usage)
- `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/templates/shared/import_wizard.py.j2` (2 usages, also missing `_()` wrapping entirely)

**Current (buggy) in 17.0/model.py.j2:**
```jinja2
{% if needs_translate %}
from odoo.tools.translate import _
{% endif %}

# ... later in constraints/approvals:
raise ValidationError(_("{{ constraint.message }}"))
raise UserError(_("State transitions must use action buttons."))
raise UserError(_("Record must be in '{{ state }}' state to submit."))
```

**Root Cause:** Since Odoo 17.0, pylint-odoo rule **W8161** enforces `self.env._()` over the standalone `_()` function (ref: `odoo/odoo#174844`). The templates still use the pre-17.0 pattern. Every generated module triggers W8161 on every translatable string — typically 5-15 violations per module.

**Impact at 90+ modules:** 90 × ~10 violations = **~900 pylint violations** that must be auto-fixed post-generation. The auto-fix system doesn't currently handle W8161 (see Fix 7 below), so these remain as unfixed warnings in every validation report.

**Fix for 17.0/model.py.j2:**
```jinja2
{# Remove the standalone _ import entirely: #}
{# OLD: from odoo.tools.translate import _ #}
{# The needs_translate flag is no longer needed for the import #}

{# In method bodies, change all _("...") to self.env._("..."): #}
raise ValidationError(self.env._("{{ constraint.message }}"))
raise UserError(self.env._("State transitions must use action buttons."))
raise UserError(self.env._("Record must be in '{{ state }}' state to submit."))
```

**Fix for shared/import_wizard.py.j2:**
```jinja2
{# Add self.env._() wrapping to ValidationError strings: #}
raise ValidationError(self.env._("No file uploaded."))
raise ValidationError(self.env._("..."))
```

**Fix for shared/bulk_wizard_model.py.j2:**
```jinja2
{# Change: #}
_("Batch processing failed at record '%(record)s': %(error)s\n"...)
{# To: #}
self.env._("Batch processing failed at record '%(record)s': %(error)s\n"...)
```

**Note for 18.0:** Check whether pylint-odoo enforces W8161 for Odoo 18.0 as well. If 18.0 reverts to standalone `_()`, keep the 18.0 template as-is. The version-specific template directories (`17.0/` vs `18.0/`) already handle this divergence.

### Fix 6: Knowledge Base i18n.md Gives Wrong Translation Advice

**Discovered:** 2026-03-10, cross-referencing pylint-odoo W8161 fix with knowledge base.
**File:** `/home/inshal-rauf/Factory-de-Odoo/pipeline/knowledge/i18n.md` line 166

**Current (wrong):**
```markdown
| Translation markup | `_()` function | Same, unchanged | Always use `from odoo import _` |
```

**Fix:**
```markdown
| Translation markup | `_()` function | **Changed:** use `self.env._()` in model methods | `_()` still works but triggers pylint-odoo W8161. Use `self.env._()` in all model/wizard methods. Standalone `_()` is only appropriate in standalone scripts. |
```

Also add W8161 to the pylint-odoo rules table (currently only W8160 is documented):
```markdown
| W8161 | Use `self.env._()` instead of `_()` in model methods | Replace `_("msg")` with `self.env._("msg")` and remove the `_` import |
```

**Impact:** The knowledge base feeds AI agents generating Odoo modules. Wrong advice here propagates W8161 violations into every generated module's code. The AI agents read `knowledge/i18n.md` during code generation and follow its guidance.

### Fix 7: W8161 Not in Auto-Fix `FIXABLE_PYLINT_CODES` — Auto-Fix Can't Repair Template Output

**Discovered:** 2026-03-10, employee_training module required 3 manual fix rounds to clear W8161.
**File:** `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/auto_fix.py` lines 33-39

**Current:**
```python
FIXABLE_PYLINT_CODES: frozenset[str] = frozenset({
    "W8113",  # redundant string= parameter on field
    "W8111",  # renamed field parameter
    "C8116",  # superfluous manifest key
    "W8150",  # absolute import should be relative
    "C8107",  # missing required manifest key
})
```

**Missing:** `W8161` — `self.env._()` vs `_()`. This is a mechanical AST transformation:
1. Find `from odoo import _` or `from odoo.tools.translate import _` → remove the `_` from the import
2. Find all `_("...")` calls inside method bodies → replace with `self.env._("...")`
3. Edge case: `_("...")` in class-level code (e.g., `_description = _("...")`) should NOT be transformed — only calls inside `def` blocks

**Implementation approach:**
```python
"W8161": _fix_env_translate,  # Add to FIXABLE_PYLINT_CODES and dispatch

def _fix_env_translate(file_path: Path, violations: list[Violation]) -> bool:
    """Replace _('msg') with self.env._('msg') in method bodies.

    Uses AST to find FunctionDef nodes containing Name('_') calls,
    and replaces them with Attribute(Name('self'), Attribute(Name('env'), '_')).
    Also removes the standalone _ import.
    """
    # 1. Parse AST
    # 2. Walk FunctionDef nodes
    # 3. For each Call where func is Name('_'), replace with self.env._
    # 4. Remove 'from odoo import _' or 'from odoo.tools.translate import _'
    # 5. Write back
```

**Impact at 90+ modules:** Without this fixer, every module goes through the full 5-iteration auto-fix loop without resolving W8161, then escalates. With this fixer, W8161 is resolved in iteration 1. At 90 modules: saves **~270 wasted Docker validation cycles** (90 modules × 3 wasted iterations each).

### Fix 8: `_MANIFEST_KEY_DEFAULTS` Contains `installable` — Contradicts C8116

**Discovered:** 2026-03-10, reviewing auto_fix.py after C8116 violation experience.
**File:** `/home/inshal-rauf/Factory-de-Odoo/pipeline/python/src/amil_utils/auto_fix.py` line 67

**Current (contradictory):**
```python
_MANIFEST_KEY_DEFAULTS: dict[str, str] = {
    "license": "LGPL-3",
    "author": "",
    "website": "",
    "category": "Uncategorized",
    "version": "17.0.1.0.0",
    "application": "False",
    "installable": "True",  # ← Adding this triggers C8116!
}
```

**Root Cause:** If a module is missing the `installable` key (C8107) and the auto-fixer adds it with value `"True"`, the next pylint run will flag C8116 (superfluous `installable` key — `True` is the default). The fixer creates the very violation it should prevent.

**Fix:** Remove `"installable"` from `_MANIFEST_KEY_DEFAULTS`:
```python
_MANIFEST_KEY_DEFAULTS: dict[str, str] = {
    "license": "LGPL-3",
    "author": "",
    "website": "",
    "category": "Uncategorized",
    "version": "17.0.1.0.0",
    "application": "False",
    # "installable" intentionally omitted — True is the default (C8116)
}
```

**Impact:** Low individually, but at 90+ modules this prevents a ping-pong fix loop where C8107 adds the key and C8116 removes it on alternating iterations.

---

## 90+ Module Scaling Considerations

### Already Handled (No Changes Needed)

| Feature | Component | How It Works |
|---------|-----------|-------------|
| Dependency ordering | `dependency-graph.cjs` | DFS topological sort handles any graph size |
| Tier grouping | `computeTiers()` | Auto-groups by depth (foundation/core/operations/communication) |
| Generation blocking | `canGenerate()` | Checks all deps are `generated` or beyond |
| State tracking | `module_status.json` | Works for any number of modules |
| Registry growth | `model_registry.json` | Object-keyed models, no array limits |
| Coherence checking | `coherence.cjs` | Checks against full registry regardless of size |
| Tiered injection | `tieredRegistryInjection()` | BFS-based, scales with graph size |

### New at 90+ Scale (Addressed by Gaps 5, 6, 7 & 8)

| Concern | Impact | Solution |
|---------|--------|----------|
| **Forward references** | Module 15 references module 60's model that doesn't exist yet | Provisional Registry (Gap 5) resolves forward refs against planned models |
| **Circular dependencies** | HR↔Payroll, Attendance↔Leave — common in ERP | Circular Dep Breaker (Gap 5) identifies primary direction, defers back-refs |
| **Critical chains** | A→B→C→D→E — if C fails, D+E are blocked | Chain analysis (Gap 5) identifies fragile chains so they're prioritized |
| **Context window pressure** | 90 module statuses + registry + log > context limit | Compact summary header (Gap 1) — Claude reads 10 lines to resume |
| **Registry injection size** | 90 modules × ~5 models × ~10 fields = 4500+ fields | `tieredRegistryInjection` already filters to relevant subset. At 90+, limit to 2-hop neighbors |
| **Docker install time** | 90 × 30s = 45 min ephemeral | Persistent Docker (Gap 2) — incremental install is 5-10s per module |
| **Cross-module integration** | Modules that work alone but break together | Cross-module tests every 10 modules (Gap 2) + Live UAT (Gap 6) |
| **Human verification** | Reading code for 90 modules is impossible | Live UAT Flow (Gap 6) — user tests in browser, reports issues |
| **Coherence check growth** | O(models × fields) for Many2one validation | At 450+ models: still < 2s. Provisional registry adds O(refs) for forward checks |
| **Human fatigue** | 90 module discussions = days of Q&A | Batch discussion (Gap 3) with depth triage — ~15 batches instead of 90 individual sessions |
| **Failure cascading** | Module 15 fails → blocks modules 16-90 | Skip-and-continue + retry strategy. Provisional registry allows out-of-order generation |
| **Re-generation loops** | Failed UAT → re-generate → fail again | Max 2 retries per module. After that, BLOCKED with feedback for human review |
| **MCP introspection gaps** | View gen can't see inheritance chains, coherence can't query relations live | 3 new MCP tools (Gap 7) — view chain, model relations, field conflicts |
| **Auto-fix wasted iterations** | Same broken fix retried 4 times, wasting Docker validation cycles | Tried-patterns guard (Gap 8) — skip already-attempted fixes, break early |
| **Git history bloat** | 90 × 3 commits = 270+ commits per cycle | Use milestone branches. Squash optional on merge |

### Recommended Config for 90+ Modules

In `.planning/config.json`:
```json
{
  "model_profile": "quality",
  "parallelization": true,
  "workflow": {
    "research": true,
    "plan_check": true,
    "verifier": true,
    "nyquist_validation": false,
    "auto_advance": false
  },
  "odoo": {
    "version": "17.0",
    "gen_path": "/home/inshal-rauf/Factory-de-Odoo/pipeline",
    "addons_path": "./addons"
  },
  "scaling": {
    "uat_checkpoint_interval": 10,
    "max_retries_per_module": 2,
    "discussion_batch_size": 5,
    "brief_discussion_batch_size": 8,
    "registry_injection_hop_limit": 2,
    "cross_module_test_interval": 10,
    "max_blocked_before_pause": 3,
    "ralph_max_iterations": 500
  }
}
```

Key settings:
- `quality` profile — use Opus for all agents (90 modules need accuracy over speed)
- `nyquist_validation: false` — skip statistical validation (too slow at scale)
- `auto_advance: false` — human controls progression
- `uat_checkpoint_interval: 10` — live UAT every 10 modules shipped
- `registry_injection_hop_limit: 2` — only inject 2-hop neighbors into context
- `max_blocked_before_pause: 3` — stop and ask human after 3 consecutive blocks

### Registry Injection Optimization for 90+ Modules

At 90 modules, the model registry may contain 450+ models with 4500+ fields.
Injecting the full registry into the pipeline context for each module generation
would consume too much context window.

The existing `tieredRegistryInjection()` in `registry.cjs` uses BFS to find
related models. At 90+ modules, add a **hop limit**:

```javascript
// In registry.cjs — tieredRegistryInjection()
// Existing: BFS from the module's direct dependencies
// Enhancement: limit BFS depth to config.scaling.registry_injection_hop_limit (default 2)

function tieredRegistryInjection(moduleName, registry, depGraph, maxHops = 2) {
  const relevant = new Set();
  const queue = [{ name: moduleName, depth: 0 }];
  const visited = new Set();

  while (queue.length > 0) {
    const { name, depth } = queue.shift();
    if (visited.has(name) || depth > maxHops) continue;
    visited.add(name);

    // Add all models from this module
    for (const [modelName, modelData] of Object.entries(registry.models || {})) {
      if (modelData.module === name) {
        relevant.add(modelName);
      }
    }

    // Enqueue dependencies
    const deps = depGraph.getDependencies(name) || [];
    for (const dep of deps) {
      queue.push({ name: dep, depth: depth + 1 });
    }
  }

  // Return filtered registry containing only relevant models
  const filtered = { models: {} };
  for (const modelName of relevant) {
    filtered.models[modelName] = registry.models[modelName];
  }
  return filtered;
}
```

This ensures that even at 90+ modules, each generation only sees the ~20-50 models
that are actually relevant (direct deps + their deps), not all 450+.

---

## Implementation Order

Build these in sequence — each depends on the previous:

| Order | Gap | Effort | Depends On |
|-------|-----|--------|------------|
| **0** | Fix 1: Chatter template | 10 min | Nothing — do this FIRST |
| **0** | Fix 2: Cron model_name | 10 min | Nothing |
| **0** | Fix 3: Portal empty body | 10 min | Nothing |
| **0** | Fix 4: Manifest load order (wizard before views) | 15 min | Nothing — CRITICAL |
| **0** | Fix 5: Templates `_()` → `self.env._()` (W8161) | 30 min | Nothing — CRITICAL |
| **0** | Fix 6: Knowledge base i18n.md correction | 5 min | Nothing |
| **0** | Fix 7: Add W8161 to auto-fix FIXABLE_PYLINT_CODES | 1-2 hrs | Fix 5 (safety net for Fix 5) |
| **0** | Fix 8: Remove `installable` from _MANIFEST_KEY_DEFAULTS | 2 min | Nothing |
| **1** | Gap 1: Cycle Log | 2-3 hrs | Nothing |
| **2** | Gap 2: Persistent Docker | 4-6 hrs | Nothing (parallel with Gap 1) |
| **3** | Gap 5: Coherence Engine | 5-7 hrs | Gap 1 (logs coherence events) |
| **4** | Gap 3: Auto-Question Loop | 3-4 hrs | Gap 5 (uses provisional registry for scoring) |
| **5** | Gap 4: run-prd Workflow | 5-7 hrs | Gaps 1, 2, 3, 5 |
| **6** | Gap 6: Live UAT Flow | 4-5 hrs | Gaps 2, 4 |
| **6** | Gap 7: MCP Server Expansion | 3-4 hrs | Gap 2 (persistent Docker must be running for MCP queries) |
| **6** | Gap 8: Auto-Fix Smart Guard | 1-2 hrs | Nothing (can be done in parallel with Gap 7) |
| **7** | Ralph Loop Integration | 1-2 hrs | Gap 4 (just the prompt + testing) |

**Total estimated effort: 29-42 hours of implementation**

### Quick Win Path (Minimum Viable for 90+)

If you want to start generating 90+ modules ASAP:

1. Fix all 8 codebase bugs (~1.5 hrs) — Fixes 1-8 eliminate the most common generation failures
2. Build the cycle log with compact summary (3 hrs)
3. Build the provisional registry (4 hrs) — **critical for 90+ forward references**
4. Write the run-prd workflow (5 hrs)
5. Use Ralph Loop with the prompt (1 hr)
6. Skip persistent Docker initially (use ephemeral — slower but works)
7. Skip live UAT initially (use conversational UAT — less thorough but works)
8. Add persistent Docker + live UAT + MCP expansion + auto-fix guard after first successful 90+ run

**Minimum viable for 90+: ~15 hours**

### Critical Path (what MUST be built for 90+ to work)

Without these, a 90+ module run **will fail**:

1. **Chatter template fix (Fix 1)** — without this, 60+ modules fail Docker install
2. **Manifest load order fix (Fix 4)** — without this, every module with a wizard action button fails Docker install (est. 30-40 modules)
3. **Template `self.env._()` fix (Fix 5)** — without this, every module triggers 5-15 pylint W8161 violations that can't be auto-fixed
4. **Provisional registry** — without this, forward references cause cascading blocks
5. **Cycle log with compact summary** — without this, context resets lose all progress
6. **run-prd workflow** — without this, 500+ manual command invocations needed

Everything else (persistent Docker, live UAT, auto-question, circular dep breaker, W8161 auto-fixer) improves the experience but isn't strictly required for the first run.

---

## Slash Command Mapping

### Existing Commands Used by the Pipeline

| Command | Phase | Role in Pipeline |
|---------|-------|-----------------|
| `/amil:new-erp` | Decomposition | PRD → modules + dependency graph |
| `/amil:discuss-module` | Specification | Per-module Q&A with domain templates |
| `/amil:plan-module` | Specification | CONTEXT.md → spec.json + coherence check |
| `/amil:generate-module` | Generation | spec.json → Odoo module via pipeline belt |
| `/amil:verify-work` | Verification | Conversational UAT per module |
| `/amil:progress` | Monitoring | Status dashboard with routing |
| `/amil:health` | Monitoring | Planning directory diagnostics |
| `/amil:validate` | Validation | pylint-odoo + Docker + auto-fix |
| `/amil:search` | Research | OCA semantic search |

### New Commands to Build

| Command | Phase | Role in Pipeline |
|---------|-------|-----------------|
| `/amil:run-prd` | **Full cycle** | Big red button — chains everything |
| `/amil:batch-discuss` | Specification | Auto-detect gaps, discuss in waves |
| `/amil:coherence-report` | Monitoring | Full cross-module coherence analysis |
| `/amil:live-uat` | Verification | Interactive browser-based UAT |
| `/ralph-loop` | **Outer loop** | Drives run-prd repeatedly until complete |
| `/cancel-ralph` | Control | Emergency stop for the loop |

### Full Lifecycle Flow

```
User provides PRD.md (describing 90+ module ERP)
        |
/ralph-loop (outer loop — repeats until <promise>ERP COMPLETE</promise>)
        |
   /amil:run-prd (inner orchestrator — picks next action)
        |
   +--> /amil:new-erp (once — decompose PRD into 90+ modules)
   |        |
   |        +--> Build provisional registry from decomposition
   |        +--> Detect circular dependencies, plan resolution
   |        +--> Identify critical chains, flag risks
   |
   +--> /amil:batch-discuss (waves — specify modules)
   |        |
   |        +--> spec-completeness scoring with cross-module checks
   |        +--> batch 5 related modules (full depth)
   |        +--> batch 8 related modules (brief depth)
   |        +--> human answers questions
   |
   +--> /amil:plan-module (per module — generate spec.json)
   |        |
   |        +--> coherence check against BOTH real + provisional registry
   |        +--> update provisional registry with spec details
   |        +--> human approves spec
   |
   +--> /amil:generate-module (per module — belt invocation)
   |        |
   |        +--> inject filtered registry (2-hop neighbors only)
   |        +--> /amil:validate (pylint + Docker)
   |        +--> auto-fix loop (5 iterations max)
   |        +--> update real registry, mark provisional as built
   |        +--> persistent Docker install
   |        +--> coherence check (forward refs may now resolve)
   |
   +--> /amil:verify-work (per module — conversational UAT)
   |        |
   |        +--> human verifies behavior
   |        +--> transition: checked → shipped
   |
   +--> /amil:live-uat (every 10 modules — browser UAT)
   |        |
   |        +--> present verification checklist
   |        +--> user tests at http://localhost:8069
   |        +--> collect pass/minor/fail per module
   |        +--> cross-module integration tests
   |        +--> route failures back to generation
   |
   +--> cycle-log append (every iteration)
   |
   +--> /amil:coherence-report (on demand — full analysis)
   |
   +--> <promise>ERP COMPLETE</promise> (when all shipped)
```

### Coherence Flow (runs continuously)

```
Provisional Registry (decomposition)     Real Registry (built modules)
        |                                        |
        |  ---- spec approved ---->              |
        |  (update provisional with              |
        |   spec-level detail)                   |
        |                                        |
        |  ---- module generated --->            |
        |  (move from provisional to real)       |
        |                                        |
        v                                        v
   Forward Reference Check              Backward Reference Check
   (does my target exist                (does anything reference
    in provisional?)                     a model I just built?)
        |                                        |
        +----------> Coherence Report <----------+
                          |
              Unresolved refs? → BLOCK or WARN
              Circular detected? → Break strategy
              Chain fragile? → Prioritize foundation
```

---

## Summary

The Factory de Odoo pipeline already has **85% of the building blocks** for 90+ module
ERP generation. The gaps are:

1. **Cycle Log** — easy, tracks full history with compact summary for context resets
2. **Persistent Docker** — medium, eliminates per-module container overhead + enables live UAT
3. **Auto-Question Loop** — medium, reduces human burden from 90 discussions to ~15 batches
4. **run-prd Workflow** — medium-hard, chains existing commands with priority-based action selection
5. **Coherence Engine** — hard, solves forward references, circular deps, and critical chains
6. **Live UAT Flow** — medium, lets users verify modules in browser instead of reading code

The **8 codebase fixes are critical prerequisites** — without them, the majority of generated
modules will fail:

| Fix | Impact | Effort |
|-----|--------|--------|
| Fix 1: Chatter template | 60+ modules fail Docker install | 10 min |
| Fix 2: Cron model_name | Modules with cron jobs fail | 10 min |
| Fix 3: Portal empty body | Portal modules have syntax errors | 10 min |
| **Fix 4: Manifest load order** | **30-40 modules fail Docker install** (wizard actions) | **15 min** |
| **Fix 5: Template `self.env._()`** | **~900 pylint violations across 90 modules** (W8161) | **30 min** |
| Fix 6: Knowledge base i18n.md | AI agents generate wrong translation pattern | 5 min |
| Fix 7: W8161 auto-fixer | ~270 wasted Docker validation cycles | 1-2 hrs |
| Fix 8: installable key contradiction | Ping-pong fix loop on C8107↔C8116 | 2 min |

Fixes 4-8 were discovered during the employee_training E2E module generation session
(2026-03-10) where every error was traced to its root cause in the pipeline codebase.

The **Coherence Engine (Gap 5)** is the most important new system for 90+ scale. Without it,
forward references cause cascading blocks and circular dependencies halt generation entirely.

Total implementation: **27-37 hours** (full) or **15 hours** (minimum viable).
