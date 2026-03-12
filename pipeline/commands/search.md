---
name: amil:search
description: Semantically search OCA/GitHub for existing Odoo modules matching your description
argument-hint: "<search query>"
---
<objective>
Search the local OCA module index for Odoo modules that match your description. Returns ranked results with relevance scores and coverage estimates. Select a result for detailed gap analysis, or refine your search with follow-up queries.

If no local index exists, one will be built automatically on first use (~3-5 minutes, requires GitHub authentication).

Use `--github` flag to include broader GitHub search results beyond OCA repositories.
</objective>

<execution_context>
@~/.claude/amil/agents/amil-search.md
</execution_context>
