---
name: amil:index
description: Build or update the local ChromaDB index of OCA Odoo modules for semantic search
argument-hint: "[--update]"
---
<objective>
Build or refresh the local vector index of OCA Odoo modules. The index powers `/amil:search` for fast semantic matching.

On first run, crawls all OCA GitHub repositories with a 17.0 branch, extracts module metadata from __manifest__.py files, and stores embeddings in a local ChromaDB database.

Use `--update` flag to incrementally re-index only repos that changed since the last build.
</objective>

<workflow>
1. Verify GitHub authentication (GITHUB_TOKEN env var or gh auth token)
2. Crawl OCA organization repos via GitHub API
3. Extract __manifest__.py metadata from each module with a 17.0 branch
4. Embed and store module descriptions in ChromaDB at ~/.local/share/amil/chromadb/
5. Report indexed module count and storage location
</workflow>
