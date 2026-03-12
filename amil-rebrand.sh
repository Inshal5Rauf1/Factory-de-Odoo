#!/bin/bash
# Amil rebrand — 23 string replacements, most-specific-first
# Run from repo root after git mv renames are done
set -euo pipefail

cd /home/inshal-rauf/Factory-de-Odoo

# Collect target files (text files, excluding auto-generated and historical docs)
FILES=$(find . -type f \
  -not -path './.git/*' \
  -not -path './.venv/*' \
  -not -path '*/node_modules/*' \
  -not -path '*/__pycache__/*' \
  -not -path '*.egg-info/*' \
  -not -path './docs/superpowers/specs/*' \
  -not -path './docs/superpowers/plans/*' \
  \( -name '*.md' -o -name '*.js' -o -name '*.cjs' -o -name '*.json' \
     -o -name '*.py' -o -name '*.toml' -o -name '*.sh' -o -name '*.yml' \
     -o -name '*.yaml' -o -name '*.cfg' -o -name '*.txt' -o -name '*.ini' \))

COUNT=0
for f in $FILES; do
  sed -i -E \
    -e 's/amil-tools\.cjs/amil-tools.cjs/g' \
    -e 's/amil_utils/amil_utils/g' \
    -e 's/amil-utils/amil-utils/g' \
    -e 's/amil-manifest\.json/amil-manifest.json/g' \
    -e 's/AMIL_PRD/AMIL_PRD/g' \
    -e 's/AMIL/AMIL/g' \
    -e 's/AMIL_GEN_PATH/AMIL_GEN_PATH/g' \
    -e 's/amil-/amil-/g' \
    -e 's/amil:/amil:/g' \
    -e 's/amil/amil/g' \
    -e 's/amil:/amil:/g' \
    -e 's/amil/amil/g' \
    -e 's/amil-scaffold/amil-scaffold/g' \
    -e 's/amil-validator/amil-validator/g' \
    -e 's/amil-model-gen/amil-model-gen/g' \
    -e 's/amil-view-gen/amil-view-gen/g' \
    -e 's/amil-security-gen/amil-security-gen/g' \
    -e 's/amil-test-gen/amil-test-gen/g' \
    -e 's/amil-search/amil-search/g' \
    -e 's/amil-extend/amil-extend/g' \
    -e 's/amil-logic-writer/amil-logic-writer/g' \
    -e 's/amil:/amil:/g' \
    -e 's/\bGSD\b/Amil/g' \
    "$f"
  COUNT=$((COUNT + 1))
done
echo "Processed $COUNT files"

# Handle extensionless files that the find command misses
# pipeline/bin/amil-utils has no .sh extension but contains brand references
sed -i -E \
  -e 's/amil_utils/amil_utils/g' \
  -e 's/amil-utils/amil-utils/g' \
  -e 's/amil/amil/g' \
  pipeline/bin/amil-utils

echo "Processed extensionless files"
