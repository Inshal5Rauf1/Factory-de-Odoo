# BUGS, FLAWS & TECHNICAL DEBT
## Odoo Development Automation — Repo: Inshal5Rauf1/Odoo-Development-Automation

You are working on this codebase. Every item below is a concrete problem in the current code. Fix them in severity order.

---

## HIGH SEVERITY BUGS

### BUG-H1: mail.thread blindly injected into every model
**File:** `renderer.py` → `_build_model_context()` ~line 310

When `mail` is in `depends`, you inject `mail.thread` and `mail.activity.mixin` into EVERY model's `inherit_list` unconditionally:
```python
if "mail" in spec.get("depends", []):
    for mixin in ("mail.thread", "mail.activity.mixin"):
        if mixin not in inherit_list:
            inherit_list.append(mixin)
```
This is wrong for:
- Lookup/config tables (`course.category`, `grading.scale`) — chatter on a config record is noise
- Line item models (`enrollment.line`, `fee.detail`) — bloats the DB with mail_message rows per line
- TransientModel wizards — mail.thread on a wizard causes schema errors
- Models extending parents that already have mail.thread — duplicate inheritance

**Your fix:** Add a `chatter: true/false` flag per model in spec.json. Default `true` for top-level business models, `false` for everything else. Auto-detect line-item models (models with a required Many2one `_id` field pointing to another model in the same module). Only inject mail mixins when `chatter` is explicitly true.

---

### BUG-H2: [RESOLVED] docker_install_module() used `exec` — race condition
> **RESOLVED:** Fixed in a prior phase. docker_install_module() now uses docker compose run --rm. Tests in TestDockerInstallUsesRunNotExec verify no exec usage.

**Status:** Fixed. See python/src/amil_utils/validation/docker_runner.py lines 148-172.

---

### BUG-H3: Regex-based auto-fix modifies Python source with string operations
**File:** `auto_fix.py` — entire file

Five of six pylint fix functions use regex replacement on Python source:
- `_fix_w8113`: regex removes `string="..."` parameter
- `_fix_w8111`: regex renames field parameters
- `_fix_c8116`: regex removes manifest keys
- `_fix_c8107`: regex inserts manifest keys
- `_fix_w8150`: regex rewrites import paths

Only `fix_unused_imports` uses AST (partially). Regex-based Python modification breaks on:
- Multi-line expressions (field definitions spanning 3+ lines)
- Comments containing the target pattern
- String literals containing the target pattern
- Non-standard formatting (extra spaces, trailing commas)

Python 3.12 gives you `ast.parse()` + `ast.unparse()`. You already use AST elsewhere in this codebase.

**Your fix:** For each fixer:
1. Parse the file with `ast.parse(source, type_comments=True)`
2. Walk the AST to locate the target node using the violation's line number
3. Modify the AST node (remove keyword, rename attribute, etc.)
4. Write back with `ast.unparse()` or use the node's exact `lineno`/`col_offset` for surgical text replacement
5. Preserve formatting as much as possible (ast.unparse normalizes, so targeted text surgery is better for small changes)

---

## MEDIUM SEVERITY BUGS

### BUG-M1: string= removal fails on multi-line field definitions
**File:** `auto_fix.py` → `_fix_w8113_redundant_string()`

You operate on `lines[violation.line - 1]` — a single line. But Odoo fields are typically multi-line:
```python
name = fields.Char(        # ← pylint reports THIS line (violation.line)
    string="Name",         # ← string= is HERE, one or more lines down
    required=True,
)
```
pylint reports the field definition line, not the `string=` line. Your regex searches the wrong line and silently does nothing — the violation persists through auto-fix cycles.

**Your fix:** When the target line doesn't contain `string=`, scan forward up to 10 lines tracking parenthesis depth to stay within the field definition. Find the `string=` keyword argument and remove it. Or — better — use the AST approach from BUG-H3 and find the `keyword` node with `arg='string'` in the field's `Call` node.

---

### BUG-M2: AST analyzer misses _inherit-only models
**File:** `search/analyzer.py` → `_extract_models_from_file()`

You only capture models with explicit `_name`:
```python
if item.targets[0].id == "_name" and isinstance(item.value, ast.Constant):
    model_name = item.value.value
```
Models that only set `_inherit` (extending existing models without creating a new table) are invisible. A module extending `sale.order` with 10 new fields shows as 0 models in gap analysis. This makes your coverage reports inaccurate and the extend workflow blind.

**Your fix:** Also scan for `_inherit = "model.name"` assignments. When found without a corresponding `_name`, record it as an inherited model extension. Add `inherited_models: tuple[str, ...]` to the `ModuleAnalysis` dataclass and populate it.

---

### BUG-M3: fix_unused_imports only checks 4 import names
**File:** `auto_fix.py` → `fix_unused_imports()`

`_IMPORT_USAGE_PATTERNS` has exactly 4 entries: `api`, `ValidationError`, `AccessError`, `_`. Everything else defaults to "assume used." So `from odoo.tools import float_compare` is never flagged even when completely unused in the file body.

**Your fix:** Invert the logic. Instead of a whitelist of known names, use `ast.walk()` on the file body (excluding the import statement itself) to find `ast.Name` nodes matching the imported alias. If no reference exists, it's unused. This is what proper unused-import tools do — you have the AST infrastructure already.

---

### BUG-M4: No GitHub API rate limiting in index builder
**File:** `search/index.py` → `build_oca_index()`

You iterate 200+ OCA repos making 400-600+ sequential API calls. No rate limiting, no backoff, no retry on 403/429. GitHub allows 5000/hour for authenticated users. Daily rebuilds or concurrent users will hit limits silently.

**Your fix:**
1. Check `X-RateLimit-Remaining` header after each PyGithub call
2. When remaining < 100, sleep until `X-RateLimit-Reset` timestamp
3. Add exponential backoff retry on `GithubException` with status 403 or 429
4. Log rate limit status in the progress callback

---

### BUG-M5: CLI imports entire dependency tree at module level
**File:** `cli.py`

Top-level imports pull in chromadb (~200MB ONNX runtime), PyGithub, gitpython, Docker wrappers. Running `amil-utils --help` loads everything. This makes CLI startup slow and wastes memory for commands that don't need heavy dependencies.

**Your fix:** Move heavy imports inside command functions:
```python
@main.command("build-index")
def build_index(...):
    from amil_utils.search import build_oca_index, get_github_token
    ...
```
Only the clicked/click core and command definitions should be at module level.

---

### BUG-M6: Wizard template always imports `api` unconditionally
**File:** `templates/shared/wizard.py.j2`

The wizard template hardcodes `from odoo import api, fields, models` regardless of whether `@api` decorators are used. You implemented conditional api import (TMPL-02) for regular models in `model.py.j2` but never applied the same logic to wizards. The wizard default template always generates `default_get` with `@api.model`, so `api` IS needed in the default case — but if someone removes `default_get`, the import becomes unused and pylint W0611 fires.

**Your fix:** Apply the same `needs_api` conditional logic to `wizard.py.j2`. Check if the wizard has a `default_get` or any `@api` decorated method before importing `api`.

---

## LOW SEVERITY BUGS

### BUG-L1: Wizard ACLs missing from ir.model.access.csv
**File:** `templates/shared/access_csv.j2`

The template iterates `models` but not `wizards`. TransientModels need ACL entries too — without them, non-admin users get `AccessError` when opening any wizard.

**Your fix:** Add a second loop in access_csv.j2 for wizards:
```jinja
{% for wizard in spec_wizards %}
access_{{ wizard.name | to_python_var }}_user,{{ wizard.name }}.user,{{ wizard.name | model_ref }},{{ module_technical_name }}.group_{{ module_technical_name }}_user,1,1,1,0
{% endfor %}
```
Confirm `spec_wizards` is passed into the template context from `render_module`.

---

### BUG-L2: Test template uses deprecated name_get()
**File:** `templates/shared/test_model.py.j2`

The template generates `test_name_get()` calling `self.test_record.name_get()`. Your own knowledge base (models.md "Changed in 18.0") documents that `name_get()` is deprecated in Odoo 17 and removed in 18. For 18.0 targets, this test fails at runtime.

**Your fix:** Remove `test_name_get` entirely. Replace with `test_display_name` that checks `self.test_record.display_name` is truthy and contains the expected name string. Gate the old pattern behind `{% if odoo_version < "18.0" %}` if you want backward compatibility.

---

### BUG-L3: Inconsistent error handling across modules
**Files:** `auto_fix.py`, `docker_runner.py`, `pylint_runner.py`, `cli.py`, `context7.py`, `verifier.py`

No unified error handling:
- `auto_fix` functions return `bool`
- `docker_runner` returns `InstallResult` dataclass
- `pylint_runner` returns `tuple[Violation, ...]`
- `cli` uses `sys.exit()`
- `context7` returns `None` / empty list on failure
- `verifier` returns `list[VerificationWarning]`

Some failures are silent (return empty), some logged, some raised. Callers can't distinguish "no problems found" from "couldn't even run the check."

**Your fix:** Define a `Result[T]` generic or a consistent pattern where every validation/check function returns a dataclass with `success: bool`, `data: T | None`, `errors: list[str]`. Start with the validation pipeline where this matters most. Don't boil the ocean — refactor one subsystem at a time.

---

## TECHNICAL DEBT

### DEBT-01 [HIGH]: render_module() is a 200+ line monolith
**File:** `renderer.py` → `render_module()`

This function has 15+ responsibilities in a single body: manifest, root init, models init, per-model rendering, view rendering, action rendering, menu rendering, security groups, ACLs, record rules, data.xml stub, sequences.xml, wizard init, per-wizard rendering, wizard form views, tests init, per-model tests, demo data, static HTML, README, artifact state tracking. Deeply nested detection logic (sequence fields, company fields, wizard existence) is interleaved with rendering calls.

You can't test "does sequence.xml render correctly" without running the entire pipeline.

**Your fix:** Decompose into a pipeline of independently testable stages:
```python
def render_module(spec, template_dir, output_dir, verifier=None):
    env = create_versioned_renderer(spec.get("odoo_version", "17.0"))
    ctx = build_module_context(spec)
    
    files = []
    files += render_manifest(env, ctx, output_dir)
    files += render_init_files(env, ctx, output_dir)
    files += render_models(env, ctx, output_dir, verifier)
    files += render_views(env, ctx, output_dir)
    files += render_security(env, ctx, output_dir)
    files += render_data(env, ctx, output_dir)
    files += render_wizards(env, ctx, output_dir)
    files += render_tests(env, ctx, output_dir)
    files += render_static(env, ctx, output_dir)
    
    save_artifact_state(ctx, output_dir, files)
    return files, ctx.warnings
```
Each `render_*` function gets its own unit tests.

---

### DEBT-02 [MEDIUM]: Docker compose path uses 5 parent traversals
**File:** `validation/docker_runner.py` → `get_compose_file()`

```python
Path(__file__).parent.parent.parent.parent.parent / "docker" / "docker-compose.yml"
```
Breaks if the package is installed via pip, restructured, or used as a library from a different location.

**Your fix:** Use `importlib.resources` to locate the compose file relative to the package, or store the path in a config that's set during `install.sh`. Alternatively, use `pkg_resources` or a `__data__` directory pattern.

---

### DEBT-03 [MEDIUM]: No unified Result type across the codebase
Same root cause as BUG-L3. The inconsistency is debt because fixing it requires a cross-cutting refactor touching every module boundary. Start with the validation pipeline (pylint → auto-fix → docker install → docker test) where the bool/None/dataclass/tuple inconsistency causes the most confusion.

---

### DEBT-04 [LOW]: GitHub rate limiting is architectural debt
Same as BUG-M4, but the proper fix (retry infrastructure with backoff, circuit breaker, rate-limit-aware request queue) is bigger than a point fix. For now, BUG-M4's fix (check headers + sleep) is sufficient. Long-term, build a `GithubClient` wrapper class that handles rate limits, retries, and caching internally, and use it everywhere PyGithub is called.

---

## FLAWS (Design-Level Problems)

These aren't bugs (the code works as written) but the design choices cause problems at scale. Each flaw has a corresponding improvement in IMPROVEMENTS.md with the full execution plan. The "Your fix" here tells you what to do; the improvement doc tells you how.

### FLAW-01: No relationship pattern awareness
**The problem:** The spec infers fields from keywords ("partner" → Many2one to res.partner) but has zero awareness of relationship patterns. You generate flat, unrelated models. A Student-Section-Enrollment triangle, Course prerequisites (self-referential Many2many with through-model and min_grade), hierarchical departments with parent_id — none expressible in current spec.json. Every relationship needs manual wiring.

**Your fix:** Add a `relationships` section to spec.json that supports: through-models for M2M with extra fields, self-referential M2M (prerequisites), hierarchical parent_id patterns, and composite uniqueness constraints across relationships. When the spec says `enrollment_pattern(student, section, through=enrollment)`, generate the through-model with both Many2one fields, the composite unique constraint, and the reverse One2many on both parent models. See IMP-01 (business logic generation) for the full spec format.

---

### FLAW-02: No computed field dependency chain support
**The problem:** The spec supports `compute` + `depends` for single-level computation. University ERPs need multi-level chains: `enrollment.grade` → `grade_points` → `quality_points` → `student.cgpa` → `academic_standing` → `dean_list`. You generate each as an isolated field with a TODO stub. You can't trace the chain or generate computation order.

**Your fix:** Build the computed chain generator (NEW-04 in IMPROVEMENTS.md). Add a `computation_chains` section to spec.json where each chain defines steps across models. The Logic Writer pass (IMP-00B) interprets the chain and generates: `@api.depends` with correct fields, `store=True` on filtered/sorted fields, `read_group` for cross-model aggregations, and correct computation order. The key implementation detail: when a chain spans models (exam result → student CGPA), generate `depends` using related field notation and ensure the `store=True` triggers recomputation when the source changes.

---

### FLAW-03: No constraint complexity beyond single-field
**The problem:** `sql_constraints` and `@api.constrains` handle simple cases. You can't express cross-model constraints, temporal constraints, capacity constraints, or schedule conflicts. These require `create()`/`write()` overrides with multi-model queries.

**Your fix:** This is handled by IMP-01 (business logic) and NEW-06 (orchestrations). Add a `constraints` section to the spec that supports: `cross_model` (prerequisite check queries another model), `temporal` (grade locked after result publication date), `capacity` (enrollment count vs room capacity), and `conflict` (timetable overlap detection). The Logic Writer pass generates `create()`/`write()` overrides with the appropriate validation queries. Each constraint becomes a `ValidationError` with a user-facing message.

---

### FLAW-04: No Monetary field pattern
**The problem:** The template generates `fields.Float` for amounts. You need `fields.Monetary` with `currency_id` linked to `res.currency`.

**Your fix:** In the Model Architect pass (IMP-00B), detect fields with names containing `amount`, `fee`, `salary`, `price`, `cost`, `balance`, `penalty`, or any field explicitly typed as `Monetary` in the spec. For these fields: generate `fields.Monetary` instead of `fields.Float`, add a `currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)` field on the model if one doesn't exist, and add `'currency_id'` to the form view. For Pakistani localization (NEW-02), default the currency to PKR. This is a pattern the Model Architect pass should auto-detect, not something that needs explicit spec configuration.

---

### FLAW-05: Only 2 security groups — no role framework at all
**The problem:** You generate exactly 2 groups (User/Manager). Prescribing fixed roles is equally wrong. GCU Faisalabad has 300+ affiliate colleges — the institution must define its own roles with its own data boundaries. The admin officer of Social Sciences should never see English department data.

**Your fix:** Build the dynamic RBAC framework described in IMP-03. This is a major feature — read IMP-03 in full. The key implementation steps: (1) Generate `uni.security.scope`, `uni.role`, `uni.role.permission`, `uni.user.role` models in the core module. (2) Generate the admin UI (form/tree views for role management). (3) Generate `_sync_to_odoo_security()` method that translates role definitions into `ir.model.access` and `ir.rule` records at runtime. (4) Generate multi-company record rules on every model with `company_id`. (5) Generate cascading scope rules: department scope → sees department data, faculty scope → sees all departments in faculty, etc.

---

### FLAW-06: No field-level security
**The problem:** No `groups=` attributes on fields. CNIC, salary, medical records visible to everyone.

**Your fix:** Part of IMP-03 (dynamic RBAC). In the spec, add a `sensitive_fields` section per model. The View Designer pass (IMP-00B Pass 3) reads this and adds `groups="uni_core.group_<role>"` attributes to field elements in form/tree views. The Security Engineer pass (Pass 4) generates `ir.model.fields` access rules for API-level enforcement. The `uni.role.field.access` model (from IMP-03) allows the institution admin to configure field visibility per role without code changes.

---

### FLAW-07: No audit trail beyond chatter
**The problem:** mail.thread gives "Field X changed from A to B" but not structured, queryable audit logs needed for HEC compliance.

**Your fix:** Generate a `uni.audit.log` model in the core module: `model_name`, `record_id`, `field_name`, `old_value`, `new_value`, `user_id`, `timestamp`, `justification` (Text field for grade changes, fee waivers). Generate a mixin `uni.audit.mixin` that overrides `write()` to log changes to sensitive fields (defined in spec's `audited_fields` section). The mixin uses `sudo()` to write audit records regardless of the user's permissions. Generate a tree view for the audit log with search filters by model, user, date range. Generate a report template for audit trail export (needed for HEC accreditation visits). Key detail: the audit log should be in a separate model, not mail.message, so it can be queried efficiently and doesn't bloat the chatter.

---

### FLAW-08: No QWeb report template generation
**The problem:** Zero report templates generated. Universities need transcripts, challans, admit cards, certificates.

**Your fix:** Build IMP-04 (QWeb report generation). Add a `reports` section to spec.json. The Report Builder pass (IMP-00B Pass 5) generates: `ir.actions.report` XML record, QWeb template with proper `t-foreach`/`t-field` syntax, paper format definition, and a button on the form view to trigger the report. Start with a generic tabular report template, then add specialized templates for Pakistani formats (transcript, challan) via NEW-02. The Pattern Retriever (IMP-00A) should index successful QWeb patterns from the knowledge base so the LLM has examples to follow.

---

### FLAW-09: No dashboard/analytics view generation
**The problem:** No graph, pivot, dashboard, or cohort views generated.

**Your fix:** Build IMP-15 (dashboard generation). Add a `dashboards` section to spec.json with measures, dimensions, and chart types. The View Designer pass generates: graph view XML, pivot view XML, `ir.actions.act_window` with `view_mode` including graph/pivot, and a menu item under a "Reporting" parent menu. For the parent institution dashboard (IMP-03B), generate PostgreSQL VIEW-backed models that aggregate across companies using `_auto = False` and a custom `init()` method.

---

### FLAW-10: No HTTP controller / REST endpoint generation
**The problem:** Zero HTTP controllers. Modules need `ir.http` routes to expose data to middleware, receive webhooks, serve portal pages.

**Your fix:** Build IMP-09 (REST endpoint generation). Add an `api_endpoints` section to spec.json. A new pass in the pipeline (or sub-pass of the View Designer) generates: `controllers/main.py` with `@http.route` decorated methods, JSON serialization/deserialization, authentication (`auth='api_key'` or `auth='public'`), input validation, error handling with proper HTTP status codes. Use the knowledge base's controllers.md for patterns. For portal controllers (NEW-01), generate routes inheriting `portal.CustomerPortal` with QWeb templates inheriting `portal.portal_my_home`.

---

### FLAW-11: No webhook/event pattern
**The problem:** No event-driven hooks. Enrollment happens → nothing else triggered. Every integration point needs manual coding.

**Your fix:** This is handled by IMP-01 (business logic) + IMP-10 (notifications) + NEW-06 (orchestrations). When the spec defines a business rule with a `notify` action or an orchestration with post-actions, the Logic Writer pass generates hook methods in the model's `create()`/`write()` overrides. The hook methods call a notification dispatcher that routes to the configured channels (email via `mail.template`, WhatsApp via a Waha hook method, SMS via a TextBelt hook). The tool generates the Odoo-side hook methods and notification templates — not the external API clients.

---

### FLAW-12: No import/export wizard generation
**The problem:** Can't generate import/export wizards for bulk data operations.

**Your fix:** Build IMP-14. Add an `import_export` section to spec.json. Generate: TransientModel with `fields.Binary` for file upload, a `_parse_file()` method using openpyxl for xlsx (or csv module for CSV), row-by-row validation with error collection into a `line_ids` One2many, a preview step showing parsed data, and a `_do_import()` method that creates records in batches. For export: generate a method that queries the model, builds an xlsx file using openpyxl, and returns it as a download. Wire both to menu items under an "Import/Export" sub-menu.

---

### FLAW-13: No bulk operation patterns for scale
**The problem:** Single-record operations everywhere. 10K fee invoices timeout.

**Your fix:** Build IMP-06 (bulk operations) + NEW-05 (bulk wizards). Two changes: (1) When a model's spec has `bulk: true` or when the model is involved in a bulk operation, the Model Architect pass generates `@api.model_create_multi` on `create()` with batched post-processing. (2) NEW-05 generates TransientModel bulk wizards with: record selection (domain-based), preview step, `_process_batch(records, batch_size=100)` helper that chunks processing, `bus.bus` progress notifications, error collection, and post-processing hooks (notifications sent after all records processed, not per-record).

---

### FLAW-14: No database performance patterns
**The problem:** No indexes, no composite constraints, `_order` defaults to `name`, no `store=True` strategy.

**Your fix:** Build IMP-16. In the Model Architect pass, auto-detect performance patterns: (1) Add `index=True` to every field used in search view filters, record rule domains, or `_order`. (2) Generate composite `sql_constraints` when the spec mentions uniqueness across fields. (3) Generate `_order` based on model semantics — result models order by `semester desc, course`, student models by `roll_number`, fee models by `due_date desc`. (4) Add `store=True` to computed fields that appear in tree views, search filters, or `_order`. (5) For TransientModels, generate `_transient_max_hours` and `_transient_max_count` to prevent table bloat.

---

### FLAW-15: No caching for reference data
**The problem:** Grading scales, fee structures, department hierarchy — queried constantly, change rarely. No caching.

**Your fix:** Build IMP-17. Detect near-static reference models (models with `cache: true` in spec, or auto-detected: few records, rarely written, many reads). Generate: `@tools.ormcache('self.id')` on frequently-called lookup methods, cache invalidation in `write()` and `create()` via `self.env.registry.clear_cache()`, and a `_get_current_semester()` classmethod-style cached lookup pattern for temporal references. Key detail: only cache ID-based lookups, not search queries.

---

### FLAW-16: No archival/partitioning strategy
**The problem:** After 5 years: 250K+ enrollment records, 1M+ attendance records. `active` field is basic archiving.

**Your fix:** Build IMP-27. When a model has `archival: true` in the spec, generate: (1) `active` field with archive/unarchive server actions. (2) An archival wizard (TransientModel) that moves records older than N semesters to archived state. (3) A scheduled action (ir.cron) that runs the archival wizard quarterly. (4) For `mail.message`: generate a cleanup cron that deletes tracking messages older than a configurable retention period (default 2 years). (5) On `uni.student`: generate a `_cron_archive_graduated()` method that archives students whose graduation date is older than the configured retention period.

---

### FLAW-17: No migration script generation
**The problem:** After first deployment, every schema change needs migration scripts. No version bump or migration tooling.

**Your fix:** Build IMP-12. Add a `/amil:migrate` command that: (1) Diffs old spec.json vs new spec.json. (2) For added fields: generates `post-migration.py` that sets default values. (3) For renamed fields: generates `pre-migration.py` that renames the column before ORM sees it. (4) For changed field types: generates `pre-migration.py` that casts data. (5) Bumps version in `__manifest__.py`. (6) Creates the `migrations/<version>/` directory structure. The diff engine should be AST-based (compare spec structures), not text-based.

---

### FLAW-18: No multi-level approval workflows
**The problem:** Only `draft → confirmed → done`. No conditional branching, no multi-level approvers.

**Your fix:** Build IMP-05. Add a `workflow` section to spec.json with `states`, `transitions` (with `group`, `condition`, `button`), and `on_transition` hooks. The Logic Writer pass generates: state Selection field, button methods with group-based access checks, `attrs` visibility conditions on buttons in the form view, and notification hooks on transitions. Key detail: for conditional transitions (Dean approves only if >7 days), generate an `if` condition in the button method that checks the relevant field and routes to the appropriate next state.

---

### FLAW-19: No notification/alert generation
**The problem:** No email templates, no WhatsApp hooks, no alert rules for state transitions.

**Your fix:** Build IMP-10. Add a `notifications` section to spec.json with trigger (state_change, threshold, scheduled), channels (email, whatsapp), template name, and recipient field path. Generate: `mail.template` XML records with proper `${object.field}` syntax, a `_send_notification()` method on the model that dispatches to configured channels, and for WhatsApp: a `_send_whatsapp()` stub method that calls the Waha endpoint URL from system parameters. The tool generates the Odoo-side templates and hook methods — not the Waha client.

---

### FLAW-20: No scheduled action generation
**The problem:** ir.cron is in the knowledge base but never generated.

**Your fix:** Build IMP-11. Add a `cron_jobs` section to spec.json. Generate: ir.cron XML records in `data/data.xml` with proper interval, model reference, and method name. Generate the stub method on the model with `@api.model` decorator and TODO comments describing the expected logic. When `business_rules` also define a scheduled trigger for the same model, connect them — the cron method should implement the business rule logic, not just be a stub.

---

### FLAW-21: No document management pattern
**The problem:** `fields.Binary` for uploads but no classification, verification workflow, or expiry tracking.

**Your fix:** Build IMP-28. When a model has `documents: true` in the spec, generate: `document_type = fields.Selection(...)`, `document = fields.Binary(attachment=True)`, `filename = fields.Char()`, `verification_state = fields.Selection([('draft','Uploaded'), ('verified','Verified'), ('rejected','Rejected')])`, `expiry_date = fields.Date()`, `verified_by = fields.Many2one('res.users')`. Generate a cron job that checks `expiry_date < today` and sends alerts. Generate a verification button workflow in the form view with group restrictions (only registrar/admin can verify).

---

### FLAW-22: No Pakistan/HEC localization framework
**The problem:** No CNIC validation, no HEC codes, no Pakistani phone format, no PKR default.

**Your fix:** Build NEW-02. Create a localization preset that activates when `localization: "pk"` is set in the spec. The preset tells each generation pass: Model Architect adds `cnic = fields.Char(size=15)` with a `@api.constrains('cnic')` regex validator, adds Pakistani phone format constraint, defaults `currency_id` to PKR. View Designer groups CNIC/NTN fields under a "Pakistan" label. Report Builder uses HEC transcript format. Ship pre-built template specs (`pk/student_management`, `pk/fee_management`, etc.) that are 70-80% complete with Pakistani conventions baked in.

---

### FLAW-23: No semester/academic calendar awareness
**The problem:** No concept of temporal business cycles. University ERPs are structured around semesters.

**Your fix:** Generate a `uni.semester` model in the core module with: `name`, `code`, `start_date`, `end_date`, `state` (planning→registration→active→exams→grading→closed), `academic_year`, and `is_current` (computed Boolean). Generate state transition buttons with group restrictions. Generate a `_get_current_semester()` cached classmethod. Make every academic model reference `semester_id`. The semester state machine drives everything else: `registration` state enables enrollment, `grading` state enables grade entry, `closed` state locks everything. This should be part of the domain templates (IMP-13 / NEW-02) — every Pakistani university spec starts with a semester model.

---

### FLAW-24: No dev environment setup generation
**The problem:** No docker-compose.dev.yml, no devcontainer, no pre-commit hooks, no CI/CD templates.

**Your fix:** Build IMP-24. Add a `/amil:devenv` command that generates: `docker-compose.dev.yml` (Odoo + PostgreSQL + Redis + pgAdmin), `.devcontainer/devcontainer.json` (for VS Code remote containers), `.pre-commit-config.yaml` (pylint-odoo + black + isort), `.github/workflows/ci.yml` (lint + test on PR), `.env.example` (documented environment variables). Generate these at project level (once per project), not per module.

---

### FLAW-25: No module dependency visualization
**The problem:** With 10-20 modules, you can't see the dependency graph.

**Your fix:** Build IMP-25. Add a `/amil:graph` command that: (1) Reads `__manifest__.py` from all generated modules. (2) Builds a directed graph of dependencies. (3) Outputs a Mermaid diagram. (4) Detects cycles (error). (5) Lists leaf modules (can install independently). (6) For a given module, shows impact: "If you change uni_core, these 8 modules are affected." Use `graphlib.TopologicalSorter` from Python 3.12 stdlib for the graph operations.

---

### FLAW-26: No spec diffing between versions
**The problem:** No way to see what changed between spec iterations.

**Your fix:** Build IMP-26. Add a `/amil:diff old_spec.json new_spec.json` command that compares: added/removed models, added/removed/changed fields (with type change highlighting), workflow state changes, new dependencies, new business rules. Output as a structured report (JSON + human-readable summary). Suggest migration actions based on the diff: "Field `fee_amount` changed from Float to Monetary — needs pre-migration script to add currency_id."

---

### FLAW-27: No orchestrator input — belt can't receive project context
**The problem:** The belt generates one module at a time with no awareness of the larger project. No way to pass a model registry, cross-module constraints, or project context.

**Your fix:** Add an `_available_models` key to spec.json that **amil** populates before sending each spec to the belt. The model registry is a dict: `{"uni.student": {"fields": ["name", "cnic", ...], "module": "uni_student"}, ...}`. In the Model Architect pass (IMP-00B), when generating a Many2one field, check the registry to verify the target model exists. If it doesn't, flag a warning in the generation result (don't silently generate a broken reference). In `generate_module()`, accept an optional `project_context: dict` parameter with: model registry, security scope configuration, localization settings, and any cross-module constraints. Thread this context through all passes.

---

### FLAW-28: No structured output for checker consumption
**The problem:** Belt output is a file directory. No structured manifest for the checker.

**Your fix:** After all passes complete and files are written, generate a `generation_manifest.json` in the module directory:
```json
{
  "module_name": "uni_student",
  "odoo_version": "17.0",
  "models": [
    {"name": "uni.student", "fields": [...], "computed_fields": [...], "inherits": [], "mail_thread": true},
    {"name": "uni.guardian", "fields": [...], "parent_model": "uni.student"}
  ],
  "security": {"groups": [...], "acl_count": 12, "record_rules": [...]},
  "views": {"form": 2, "tree": 2, "search": 2, "kanban": 0, "graph": 0},
  "reports": [{"name": "student_transcript", "model": "uni.student"}],
  "cron_jobs": [...],
  "controllers": [...],
  "tests": {"unit": 8, "integration": 3},
  "spec_coverage": {
    "models_defined": "4/4",
    "business_rules_implemented": "3/5",
    "business_rules_stubbed": "2/5",
    "reports_generated": "1/1"
  }
}
```
Add this as the final step in `render_module()` or the generation pipeline's `write_to_disk()`. The checker (CHK-01) reads this manifest instead of re-parsing all files.

---

### FLAW-29: No semantic validation beyond pylint + Docker
**The problem:** Pass 7 checks syntax and installability, not semantics. A module where every method body is `pass` would pass validation.

**Your fix:** Add a semantic validation step after Pass 7 (or make it Pass 8). Two parts: (1) **Spec coverage check:** Compare the `generation_manifest.json` (from FLAW-28 fix) against the input spec. Every model in spec → exists in manifest. Every business rule → has a non-stub implementation (AST-parse the Python methods, check they contain more than `pass` or `return` or a `# TODO` comment). Every report → has a QWeb template. Report coverage as a percentage. (2) **LLM-assisted semantic check:** Send the generated code + the spec to the LLM with the prompt: "Does this code implement these business rules? List any rules that are missing or incorrectly implemented." This is expensive (an extra LLM call per module) but catches the most dangerous errors — code that looks right but doesn't do what the spec says.

---

### FLAW-30: No human checkpoint hooks in the pipeline
**The problem:** Belt runs autonomously. No mechanism to pause and ask the human about ambiguities.

**Your fix:** Add an `ambiguity_handler` callback to the `GenerationPipeline` class. When any pass encounters an ambiguity (the LLM response contains phrases like "unclear whether," "could be interpreted as," "assuming X" — detect these via keyword scan), it pauses and calls the handler:
```python
class GenerationPipeline:
    def __init__(self, ..., ambiguity_handler=None):
        self.on_ambiguity = ambiguity_handler or (lambda q: input(q))
    
    def _run_pass(self, pass_type, spec, patterns, ctx):
        response = self.llm.generate(prompt)
        ambiguities = self._detect_ambiguities(response)
        if ambiguities:
            for amb in ambiguities:
                resolution = self.on_ambiguity(amb.question)
                response = self._re_run_with_resolution(pass_type, prompt, amb, resolution)
        return self._parse_pass_output(pass_type, response)
```
**amil** provides the handler implementation that routes questions to the human. In standalone mode (no orchestrator), default to `input()` on the CLI.

---

### FLAW-31: No generation state persistence
**The problem:** Belt fails mid-generation → starts from scratch. 20-module project, 2+ hours, transient failure = all progress lost.

**Your fix:** After each pass and each module, save a checkpoint to disk:
```python
def _save_checkpoint(self, module_name, pass_name, ctx):
    checkpoint = {
        "module": module_name,
        "completed_pass": pass_name,
        "context": ctx.serialize(),  # models, views, security generated so far
        "model_registry": self.model_registry,
        "timestamp": datetime.now().isoformat()
    }
    Path(f".amil-checkpoints/{module_name}/{pass_name}.json").write_text(
        json.dumps(checkpoint))

def generate_module(self, spec, output_dir, resume_from=None):
    if resume_from:
        ctx = ModuleContext.deserialize(resume_from.context)
        start_pass = self._next_pass_after(resume_from.completed_pass)
    else:
        ctx = ModuleContext(spec, output_dir, self.version)
        start_pass = "model_architect"
    
    for pass_name in self._passes_from(start_pass):
        ctx = self._run_pass(pass_name, spec, ctx)
        self._save_checkpoint(spec["name"], pass_name, ctx)
```
Add a `--resume` flag to the CLI that detects the latest checkpoint and resumes. For project-level generation, **amil**'s state (which modules completed, current model registry) is also checkpointed via amil's built-in pause/resume (inherited from Amil).

---

### FLAW-32: Belt repo still references Amil instead of amil

**Category:** DEBT — stale dependency references
**Severity:** Blocks integration — belt and orchestrator won't wire up cleanly
**When:** Day 1 of amil fork creation

**What's wrong:** The belt repo (Odoo-Development-Automation) was originally designed to be driven by Amil. Now that the orchestrator is amil (a specialized fork), the belt repo has stale references: README, code imports, config files, CLI flags, Docker setup, and CI/CD workflows may still point to `get-shit-done` / `gsd` instead of `amil`.

**Your fix:** Grep the entire belt repo for `gsd`, `Amil`, `get-shit-done`, `get_shit_done`. Update every hit:
- README.md: architecture diagram, installation instructions, orchestrator references
- Python code: imports, subprocess calls, config keys, environment variables, string literals
- Dependencies: package.json / pyproject.toml / requirements.txt
- Docker / docker-compose: container mounts, repo paths
- GitHub Actions: workflow steps that install or invoke the orchestrator
- spec.json schema: add `"orchestrator": "amil"` field
- generation_manifest.json: add `"orchestrator": "amil"` for traceability

Do NOT rename Amil's inherited state files (PROJECT.md, STATE.md, etc.) — those names stay. Only update references to the *tool* that manages them.

See IMPROVEMENTS.md → "MIGRATION: Belt Repo → amil Dependency" for the full checklist.
