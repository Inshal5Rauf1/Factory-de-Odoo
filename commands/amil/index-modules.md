---
name: amil:index-modules
description: Build or update local ChromaDB index of OCA Odoo modules for semantic search
allowed-tools:
  - Read
  - Bash
  - Write
---
<context>
Builds or updates a local ChromaDB vector index of OCA Odoo modules. Crawls GitHub repos, extracts manifests and READMEs, generates embeddings, and stores them for semantic search.

**Requires:** Python environment with amil_utils[search] installed
**Produces:** ChromaDB index at `~/.claude/amil/search-index/`
</context>

<objective>
Build or update the local ChromaDB index of OCA modules for semantic search.

**After this command:** Use `/amil:search-modules` to query the index.
</objective>

<process>
1. Verify Python environment has `amil_utils[search]` installed
2. Run the indexing CLI:
   ```bash
   python -m amil_utils index-oca
   ```
3. CLI crawls OCA GitHub repos, extracts manifests and READMEs
4. Generates embeddings using ChromaDB's built-in ONNX model
5. Stores vectors in `~/.claude/amil/search-index/`
6. Report indexing statistics (modules indexed, repos crawled, duration)
</process>
