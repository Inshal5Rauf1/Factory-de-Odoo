#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# amil Pipeline Installer
# Sets up the amil pipeline (Python venv, commands, agents, knowledge).
#
# Usage:
#   git clone <repo> ~/.claude/amil
#   cd ~/.claude/amil
#   bash install.sh
# ==============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Determine script directory (the cloned repo root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AMIL_DIR="$SCRIPT_DIR"
VERSION=$(cat "$AMIL_DIR/VERSION" 2>/dev/null || echo "unknown")

# Helpers
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ==============================================================================
# Step 1: Check Prerequisites
# ==============================================================================

info "Checking prerequisites..."

# Check uv is installed
if ! command -v uv &>/dev/null; then
    error "uv (Python package manager) not found."
    error "amil requires uv for Python environment management."
    error ""
    error "Install uv:"
    error "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    error ""
    error "More info: https://docs.astral.sh/uv/#getting-started"
    exit 1
fi
success "uv found: $(uv --version)"

# Check Python 3.12
if ! uv python find 3.12 &>/dev/null; then
    error "Python 3.12 not found."
    error "Factory de Odoo requires Python 3.12 (works across Odoo 17.0-19.0)."
    error ""
    error "Install Python 3.12:"
    error "  uv python install 3.12"
    exit 1
fi
success "Python 3.12 found: $(uv python find 3.12)"

# ==============================================================================
# Step 2: Create Python Virtual Environment
# ==============================================================================

info "Creating Python virtual environment..."

if [ -d "$AMIL_DIR/.venv" ]; then
    warn "Existing venv found at $AMIL_DIR/.venv/ -- recreating..."
    rm -rf "$AMIL_DIR/.venv"
fi

uv venv "$AMIL_DIR/.venv" --python 3.12
success "Python venv created at $AMIL_DIR/.venv/"

# ==============================================================================
# Step 3: Install Python Package
# ==============================================================================

info "Installing amil-utils Python package..."

if [ ! -d "$AMIL_DIR/python" ]; then
    error "Python package directory not found at $AMIL_DIR/python/"
    error "The repository may be incomplete. Try re-cloning."
    exit 1
fi

VIRTUAL_ENV="$AMIL_DIR/.venv" uv pip install -e "$AMIL_DIR/python/"
success "amil-utils package installed"

# ==============================================================================
# Step 4: Create Wrapper Script
# ==============================================================================

info "Creating wrapper script..."

mkdir -p "$AMIL_DIR/bin"
cat > "$AMIL_DIR/bin/amil-utils" << 'WRAPPER_EOF'
#!/usr/bin/env bash
# Thin wrapper that runs amil-utils from the extension's venv.
# This solves path resolution issues across platforms (Pitfall 4).
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "$SCRIPT_DIR/.venv/bin/amil-utils" "$@"
WRAPPER_EOF
chmod +x "$AMIL_DIR/bin/amil-utils"
success "Wrapper script created at $AMIL_DIR/bin/amil-utils"

# ==============================================================================
# Step 5: Register Commands
# ==============================================================================

info "Registering amil commands..."

COMMANDS_TARGET="$HOME/.claude/commands/amil"
mkdir -p "$COMMANDS_TARGET"

if [ -d "$AMIL_DIR/commands" ] && ls "$AMIL_DIR/commands/"*.md &>/dev/null; then
    cp "$AMIL_DIR/commands/"*.md "$COMMANDS_TARGET/"
    COMMAND_COUNT=$(ls "$COMMANDS_TARGET/"*.md 2>/dev/null | wc -l)
    success "Registered $COMMAND_COUNT command(s) to $COMMANDS_TARGET/"
else
    warn "No command .md files found in $AMIL_DIR/commands/ -- skipping command registration"
    warn "Commands will be registered when they are created in later phases."
fi

# ==============================================================================
# Step 6: Symlink Agent Files
# ==============================================================================

info "Symlinking agent files..."

AGENTS_TARGET="$HOME/.claude/agents"
mkdir -p "$AGENTS_TARGET"

AGENT_COUNT=0
if [ -d "$AMIL_DIR/agents" ] && ls "$AMIL_DIR/agents/"*.md &>/dev/null; then
    for f in "$AMIL_DIR/agents/"*.md; do
        ln -sf "$f" "$AGENTS_TARGET/$(basename "$f")"
        AGENT_COUNT=$((AGENT_COUNT + 1))
    done
    success "Symlinked $AGENT_COUNT agent(s) to $AGENTS_TARGET/"
else
    warn "No agent .md files found in $AMIL_DIR/agents/ -- skipping agent registration"
    warn "Agents will be registered when they are created."
fi

# ==============================================================================
# Step 7: Install Knowledge Base
# ==============================================================================

info "Installing knowledge base..."

KB_SOURCE="$AMIL_DIR/knowledge"
KB_TARGET="$HOME/.claude/amil/knowledge"

if [ -d "$KB_SOURCE" ]; then
    # Remove existing knowledge directory (symlink or real dir) to ensure clean state
    if [ -L "$KB_TARGET" ] || [ -d "$KB_TARGET" ]; then
        rm -rf "$KB_TARGET"
    fi

    # Create parent directory if needed
    mkdir -p "$(dirname "$KB_TARGET")"

    # Symlink the knowledge directory (same pattern as agents: keep files in extension dir)
    ln -sf "$KB_SOURCE" "$KB_TARGET"

    # Ensure custom/ subdirectory exists so users can add files without creating it
    mkdir -p "$KB_SOURCE/custom"

    KB_FILE_COUNT=$(ls "$KB_SOURCE/"*.md 2>/dev/null | wc -l)
    success "Knowledge base installed: $KB_TARGET/ ($KB_FILE_COUNT shipped files)"
else
    warn "No knowledge/ directory found in $AMIL_DIR -- skipping knowledge base installation"
    warn "Knowledge base will be installed when knowledge files are created."
fi

# ==============================================================================
# Step 8: Write Manifest for Tracking
# ==============================================================================

info "Writing installation manifest..."

MANIFEST_FILE="$HOME/.claude/amil-manifest.json"

# Build manifest JSON
MANIFEST_COMMANDS="[]"
if [ -d "$COMMANDS_TARGET" ] && ls "$COMMANDS_TARGET/"*.md &>/dev/null; then
    MANIFEST_COMMANDS=$(printf '%s\n' "$COMMANDS_TARGET/"*.md | python3 -c "
import sys, json
files = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(files))
")
fi

MANIFEST_AGENTS="[]"
if [ "$AGENT_COUNT" -gt 0 ]; then
    MANIFEST_AGENTS=$(for f in "$AMIL_DIR/agents/"*.md; do
        echo "$AGENTS_TARGET/$(basename "$f")"
    done | python3 -c "
import sys, json
files = [line.strip() for line in sys.stdin if line.strip()]
print(json.dumps(files))
")
fi

cat > "$MANIFEST_FILE" << MANIFEST_EOF
{
  "extension": "amil",
  "version": "$VERSION",
  "installed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source_dir": "$AMIL_DIR",
  "venv_dir": "$AMIL_DIR/.venv",
  "wrapper_script": "$AMIL_DIR/bin/amil-utils",
  "commands_dir": "$COMMANDS_TARGET",
  "commands": $MANIFEST_COMMANDS,
  "agents": $MANIFEST_AGENTS,
  "manifest_version": 1
}
MANIFEST_EOF

success "Manifest written to $MANIFEST_FILE"

# ==============================================================================
# Step 9: Verify Installation
# ==============================================================================

info "Verifying installation..."

if "$AMIL_DIR/bin/amil-utils" --version &>/dev/null; then
    INSTALLED_VERSION=$("$AMIL_DIR/bin/amil-utils" --version 2>&1)
    success "amil-utils verified: $INSTALLED_VERSION"
else
    error "amil-utils verification failed!"
    error "The wrapper script at $AMIL_DIR/bin/amil-utils could not execute."
    error "Try running manually: $AMIL_DIR/.venv/bin/amil-utils --version"
    exit 1
fi

# ==============================================================================
# Step 10: Success Summary
# ==============================================================================

echo ""
echo -e "${GREEN}${BOLD}============================================${NC}"
echo -e "${GREEN}${BOLD}  amil v${VERSION} installed successfully!${NC}"
echo -e "${GREEN}${BOLD}============================================${NC}"
echo ""
echo -e "  ${BOLD}Extension:${NC}  $AMIL_DIR"
echo -e "  ${BOLD}Venv:${NC}       $AMIL_DIR/.venv"
echo -e "  ${BOLD}Wrapper:${NC}    $AMIL_DIR/bin/amil-utils"
echo -e "  ${BOLD}Commands:${NC}   $COMMANDS_TARGET/ ($COMMAND_COUNT registered)"
echo -e "  ${BOLD}Agents:${NC}     $AGENTS_TARGET/ ($AGENT_COUNT symlinked)"
echo -e "  ${BOLD}Knowledge:${NC}  $KB_TARGET/"
echo -e "  ${BOLD}Manifest:${NC}   $MANIFEST_FILE"
echo ""

if [ "$COMMAND_COUNT" -gt 0 ]; then
    echo -e "  ${BOLD}Available commands:${NC}"
    for f in "$COMMANDS_TARGET/"*.md; do
        CMD_NAME=$(basename "$f" .md)
        echo -e "    /amil:${CMD_NAME}"
    done
    echo ""
fi

echo -e "  ${BOLD}Next steps:${NC}"
echo -e "    1. Open your AI coding assistant (Claude Code, etc.)"
echo -e "    2. Run ${BOLD}/amil:new \"your module description\"${NC}"
echo -e "    3. Review the inferred spec and confirm to generate"
echo ""
