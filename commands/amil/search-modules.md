---
name: amil:search-modules
description: Semantically search OCA/GitHub for existing Odoo modules matching a description
argument-hint: "<natural language description>"
allowed-tools:
  - Read
  - Bash
  - Write
  - Agent
---
<context>
Searches the local ChromaDB index of OCA modules (and optionally GitHub) for existing Odoo modules matching a natural language description. Ranks results by semantic similarity and offers gap analysis.

**Requires:** Local ChromaDB index (built via /amil:index-modules)
**Produces:** Search results with relevance scores and gap analysis
</context>

<objective>
Semantically search for existing Odoo modules matching a natural language description. Rank by relevance, offer gap analysis.

**After this command:** Use `/amil:extend-module` to fork a match, or `/amil:plan-module` to build from scratch.
</objective>

<execution_context>
Spawn the `amil-search` pipeline agent to execute search.
</execution_context>

<process>
1. Parse natural language description into search query
2. Spawn `amil-search` agent with query
3. Agent searches ChromaDB index + optional GitHub API
4. Present ranked results with relevance scores
5. Offer gap analysis comparing matches against requirements
</process>
