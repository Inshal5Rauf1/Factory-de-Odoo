#!/usr/bin/env node

/**
 * odoo-gsd installer -- Claude Code only
 *
 * Installs the odoo-gsd orchestrator into ~/.claude/ for Claude Code usage.
 * Checks for odoo-gen belt and Python 3.8+ availability.
 *
 * Usage: node odoo-gsd/bin/install.js [--global | --local] [--uninstall]
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// ─── Colors ──────────────────────────────────────────────────────────────────

const cyan = '\x1b[36m';
const green = '\x1b[32m';
const yellow = '\x1b[33m';
const red = '\x1b[31m';
const dim = '\x1b[2m';
const bold = '\x1b[1m';
const reset = '\x1b[0m';

// ─── Constants ───────────────────────────────────────────────────────────────

const CLAUDE_CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
const ODOO_GSD_DIR = 'odoo-gsd';
const ODOO_GEN_DIR = 'odoo-gen';
const COMMANDS_DIR = 'commands/odoo-gsd';
const AGENTS_DIR = 'agents';
const HOOKS_DIR = 'hooks';
const MIN_PYTHON_VERSION = [3, 8];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function log(msg) {
  console.log(msg);
}

function success(msg) {
  log(`${green}[OK]${reset} ${msg}`);
}

function warn(msg) {
  log(`${yellow}[WARN]${reset} ${msg}`);
}

function fail(msg) {
  log(`${red}[ERROR]${reset} ${msg}`);
}

function heading(msg) {
  log(`\n${bold}${cyan}${msg}${reset}`);
}

/**
 * Recursively copy a directory, creating target dirs as needed.
 */
function copyDirSync(src, dest) {
  if (!fs.existsSync(src)) return;
  fs.mkdirSync(dest, { recursive: true });

  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

/**
 * Remove a directory if it exists.
 */
function removeDirSync(dirPath) {
  if (fs.existsSync(dirPath)) {
    fs.rmSync(dirPath, { recursive: true, force: true });
  }
}

// ─── Checks ──────────────────────────────────────────────────────────────────

/**
 * Verify that Claude Code is installed (~/.claude/ exists).
 */
function checkClaudeCode() {
  if (!fs.existsSync(CLAUDE_CONFIG_DIR)) {
    fail(`Claude Code config directory not found at ${CLAUDE_CONFIG_DIR}`);
    log(`  Install Claude Code first: https://docs.anthropic.com/en/docs/claude-code`);
    log(`  Or set CLAUDE_CONFIG_DIR to a custom location.`);
    return false;
  }
  return true;
}

/**
 * Check for odoo-gen belt at ~/.claude/odoo-gen/.
 * Warns if missing but does not block installation.
 */
function checkOdooGen() {
  const odooGenPath = path.join(CLAUDE_CONFIG_DIR, ODOO_GEN_DIR);

  if (!fs.existsSync(odooGenPath)) {
    warn(`odoo-gen belt not found at ${odooGenPath}`);
    log(`  The odoo-gen belt is required for module generation (Phase 5).`);
    log(`  Install it with:`);
    log(`    ${dim}git clone <odoo-gen-repo> ${odooGenPath}${reset}`);
    log(`  You can continue without it -- generation features will not be available.`);
    return false;
  }

  success(`odoo-gen belt found at ${odooGenPath}`);
  return true;
}

/**
 * Check for Python 3.8+ availability.
 * Warns if missing but does not block installation.
 */
function checkPython() {
  try {
    const versionOutput = execSync('python3 --version', {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    }).trim();

    const match = versionOutput.match(/Python\s+(\d+)\.(\d+)/);
    if (!match) {
      warn(`Could not parse Python version from: ${versionOutput}`);
      return false;
    }

    const major = parseInt(match[1], 10);
    const minor = parseInt(match[2], 10);

    if (major < MIN_PYTHON_VERSION[0] || (major === MIN_PYTHON_VERSION[0] && minor < MIN_PYTHON_VERSION[1])) {
      warn(`Python ${major}.${minor} found but ${MIN_PYTHON_VERSION.join('.')}+ is required`);
      log(`  odoo-gen belt requires Python ${MIN_PYTHON_VERSION.join('.')} or higher.`);
      return false;
    }

    success(`Python ${major}.${minor} found`);
    return true;
  } catch {
    warn('python3 not found on PATH');
    log(`  odoo-gen belt requires Python ${MIN_PYTHON_VERSION.join('.')}+.`);
    log(`  Install Python: https://www.python.org/downloads/`);
    return false;
  }
}

// ─── Installation ────────────────────────────────────────────────────────────

/**
 * Determine the source root directory (where this package is located).
 * Works whether run from npm/npx or directly.
 */
function getSourceRoot() {
  // install.js is at odoo-gsd/bin/install.js, so source root is two levels up
  return path.resolve(__dirname, '..', '..');
}

/**
 * Install odoo-gsd files into the Claude Code config directory.
 */
function installGlobal() {
  const sourceRoot = getSourceRoot();
  const targetBase = CLAUDE_CONFIG_DIR;

  heading('Installing odoo-gsd to Claude Code...');

  // 1. Copy odoo-gsd/ (core tools, workflows, templates, references)
  const odooGsdSrc = path.join(sourceRoot, ODOO_GSD_DIR);
  const odooGsdDest = path.join(targetBase, ODOO_GSD_DIR);

  if (!fs.existsSync(odooGsdSrc)) {
    fail(`Source directory not found: ${odooGsdSrc}`);
    process.exit(1);
  }

  removeDirSync(odooGsdDest);
  copyDirSync(odooGsdSrc, odooGsdDest);
  success(`Installed ${ODOO_GSD_DIR}/ to ${odooGsdDest}`);

  // 2. Register slash commands from commands/odoo-gsd/
  const commandsSrc = path.join(sourceRoot, COMMANDS_DIR);
  const commandsDest = path.join(targetBase, COMMANDS_DIR);

  if (fs.existsSync(commandsSrc)) {
    fs.mkdirSync(path.dirname(commandsDest), { recursive: true });
    removeDirSync(commandsDest);
    copyDirSync(commandsSrc, commandsDest);
    const commandCount = fs.readdirSync(commandsSrc).filter(f => f.endsWith('.md')).length;
    success(`Registered ${commandCount} slash commands to ${commandsDest}`);
  }

  // 3. Copy agents
  const agentsSrc = path.join(sourceRoot, AGENTS_DIR);
  const agentsDest = path.join(targetBase, AGENTS_DIR);

  if (fs.existsSync(agentsSrc)) {
    fs.mkdirSync(agentsDest, { recursive: true });
    const agentFiles = fs.readdirSync(agentsSrc).filter(f => f.startsWith('odoo-gsd-'));
    for (const file of agentFiles) {
      fs.copyFileSync(path.join(agentsSrc, file), path.join(agentsDest, file));
    }
    success(`Installed ${agentFiles.length} agent definitions`);
  }

  // 4. Copy hooks
  const hooksSrc = path.join(sourceRoot, HOOKS_DIR);
  const hooksDest = path.join(targetBase, HOOKS_DIR);

  if (fs.existsSync(hooksSrc)) {
    fs.mkdirSync(hooksDest, { recursive: true });
    const hookFiles = fs.readdirSync(hooksSrc).filter(f => f.startsWith('odoo-gsd-'));
    for (const file of hookFiles) {
      fs.copyFileSync(path.join(hooksSrc, file), path.join(hooksDest, file));
    }
    if (hookFiles.length > 0) {
      success(`Installed ${hookFiles.length} hooks`);
    }
  }

  return true;
}

/**
 * Install odoo-gsd files into the current working directory (local project).
 */
function installLocal() {
  const sourceRoot = getSourceRoot();
  const targetBase = process.cwd();

  heading('Installing odoo-gsd locally...');

  const odooGsdSrc = path.join(sourceRoot, ODOO_GSD_DIR);
  const odooGsdDest = path.join(targetBase, ODOO_GSD_DIR);

  if (!fs.existsSync(odooGsdSrc)) {
    fail(`Source directory not found: ${odooGsdSrc}`);
    process.exit(1);
  }

  removeDirSync(odooGsdDest);
  copyDirSync(odooGsdSrc, odooGsdDest);
  success(`Installed ${ODOO_GSD_DIR}/ to ${odooGsdDest}`);

  return true;
}

/**
 * Uninstall odoo-gsd from Claude Code config directory.
 */
function uninstall() {
  const targetBase = CLAUDE_CONFIG_DIR;

  heading('Uninstalling odoo-gsd from Claude Code...');

  const dirsToRemove = [
    path.join(targetBase, ODOO_GSD_DIR),
    path.join(targetBase, COMMANDS_DIR),
  ];

  for (const dir of dirsToRemove) {
    if (fs.existsSync(dir)) {
      removeDirSync(dir);
      success(`Removed ${dir}`);
    }
  }

  // Remove agent files (only odoo-gsd-* ones)
  const agentsDir = path.join(targetBase, AGENTS_DIR);
  if (fs.existsSync(agentsDir)) {
    const agentFiles = fs.readdirSync(agentsDir).filter(f => f.startsWith('odoo-gsd-'));
    for (const file of agentFiles) {
      fs.unlinkSync(path.join(agentsDir, file));
    }
    if (agentFiles.length > 0) {
      success(`Removed ${agentFiles.length} agent definitions`);
    }
  }

  // Remove hook files (only odoo-gsd-* ones)
  const hooksDir = path.join(targetBase, HOOKS_DIR);
  if (fs.existsSync(hooksDir)) {
    const hookFiles = fs.readdirSync(hooksDir).filter(f => f.startsWith('odoo-gsd-'));
    for (const file of hookFiles) {
      fs.unlinkSync(path.join(hooksDir, file));
    }
    if (hookFiles.length > 0) {
      success(`Removed ${hookFiles.length} hooks`);
    }
  }

  log(`\n${green}odoo-gsd uninstalled successfully.${reset}`);
}

// ─── CLI ─────────────────────────────────────────────────────────────────────

function printHelp() {
  log(`
${bold}odoo-gsd installer${reset} -- Odoo ERP module orchestrator for Claude Code

${yellow}Usage:${reset}
  node odoo-gsd/bin/install.js [options]

${yellow}Options:${reset}
  ${cyan}-g, --global${reset}       Install globally (to ~/.claude/)
  ${cyan}-l, --local${reset}        Install locally (to current directory)
  ${cyan}-u, --uninstall${reset}    Uninstall odoo-gsd from Claude Code
  ${cyan}-h, --help${reset}         Show this help message

${yellow}Examples:${reset}
  ${dim}# Install to Claude Code config${reset}
  node odoo-gsd/bin/install.js --global

  ${dim}# Install to current project${reset}
  node odoo-gsd/bin/install.js --local

  ${dim}# Uninstall${reset}
  node odoo-gsd/bin/install.js --uninstall
`);
}

function printSummary(hasOdooGen, hasPython) {
  heading('Installation Summary');
  log('');

  const sourceRoot = getSourceRoot();
  const commandsSrc = path.join(sourceRoot, COMMANDS_DIR);
  const commandCount = fs.existsSync(commandsSrc)
    ? fs.readdirSync(commandsSrc).filter(f => f.endsWith('.md')).length
    : 0;

  log(`  ${green}Core tools:${reset}     odoo-gsd/bin/odoo-gsd-tools.cjs`);
  log(`  ${green}Commands:${reset}       ${commandCount} slash commands (/odoo-gsd:*)`);
  log(`  ${green}Workflows:${reset}      odoo-gsd/workflows/`);
  log(`  ${green}Templates:${reset}      odoo-gsd/templates/`);
  log('');

  if (!hasOdooGen) {
    log(`  ${yellow}[!]${reset} odoo-gen belt not installed -- module generation unavailable`);
  }
  if (!hasPython) {
    log(`  ${yellow}[!]${reset} Python 3.8+ not found -- odoo-gen belt will not work`);
  }

  log('');
  log(`  ${dim}Get started: /odoo-gsd:new-project${reset}`);
  log('');
}

function main() {
  const args = process.argv.slice(2);

  if (args.includes('-h') || args.includes('--help')) {
    printHelp();
    process.exit(0);
  }

  const isUninstall = args.includes('--uninstall') || args.includes('-u');
  const isLocal = args.includes('--local') || args.includes('-l');
  const isGlobal = args.includes('--global') || args.includes('-g');

  if (isUninstall) {
    if (!checkClaudeCode()) {
      process.exit(1);
    }
    uninstall();
    process.exit(0);
  }

  heading('odoo-gsd Installer');
  log(`${dim}Odoo ERP module orchestrator for Claude Code${reset}\n`);

  // Step 1: Verify Claude Code
  if (!checkClaudeCode()) {
    process.exit(1);
  }
  success('Claude Code detected');

  // Step 2: Check dependencies (non-blocking)
  const hasOdooGen = checkOdooGen();
  const hasPython = checkPython();

  // Step 3: Install
  if (isLocal) {
    installLocal();
  } else {
    installGlobal();
  }

  // Step 4: Summary
  printSummary(hasOdooGen, hasPython);

  log(`${green}${bold}Installation complete.${reset}\n`);
}

main();
