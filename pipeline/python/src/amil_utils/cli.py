"""Click CLI for amil-utils: render templates and scaffold Odoo modules."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_logger = logging.getLogger(__name__)

import click

from amil_utils import __version__


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """amil-utils: Python utilities for the amil Amil extension."""


@main.command()
@click.option("--template", required=True, help="Template file name (e.g., manifest.py.j2)")
@click.option("--output", required=True, type=click.Path(), help="Output file path")
@click.option("--var", multiple=True, help="Variable in key=value format (repeatable)")
@click.option("--var-file", type=click.Path(exists=True), help="JSON file with template variables")
def render(template: str, output: str, var: tuple[str, ...], var_file: str | None) -> None:
    """Render a single Jinja2 template to a file."""
    from amil_utils.renderer import (
        create_renderer,
        create_versioned_renderer,
        get_template_dir,
        render_template,
    )

    context: dict = {}

    if var_file:
        try:
            context = json.loads(Path(var_file).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            click.echo(f"Error reading var-file: {exc}", err=True)
            sys.exit(1)

    for v in var:
        if "=" not in v:
            click.echo(f"Invalid --var format (expected key=value): {v}", err=True)
            sys.exit(1)
        key, value = v.split("=", 1)
        if not key.isidentifier() or key.startswith("_"):
            click.echo(
                f"Invalid --var key: {key!r}. "
                "Must be a valid Python identifier and not start with '_'.",
                err=True,
            )
            sys.exit(1)
        # Attempt to parse JSON values for non-string types
        try:
            context[key] = json.loads(value)
        except json.JSONDecodeError:
            context[key] = value

    # Version-aware renderer: if --var odoo_version=18.0 is provided, use
    # the versioned renderer for that Odoo version.
    odoo_version = context.get("odoo_version")
    if odoo_version:
        env = create_versioned_renderer(odoo_version)
    else:
        template_dir = get_template_dir()
        env = create_renderer(template_dir)

    try:
        output_path = render_template(env, template, Path(output), context)
        click.echo(str(output_path))
    except Exception as exc:
        click.echo(f"Error rendering template: {exc}", err=True)
        sys.exit(1)


@main.command("list-templates")
@click.option("--version", "odoo_version", default=None, help="Odoo version to list templates for (e.g., 17.0, 18.0, 19.0)")
def list_templates(odoo_version: str | None) -> None:
    """List all available Jinja2 templates.

    Lists templates from shared/ plus version-specific directories. Use --version
    to filter to a specific Odoo version.
    """
    from amil_utils.renderer import get_template_dir

    template_dir = get_template_dir()

    if not template_dir.is_dir():
        click.echo(f"Templates directory not found: {template_dir}", err=True)
        sys.exit(1)

    # Collect templates from version directories and shared/
    shared_dir = template_dir / "shared"
    all_templates: list[tuple[str, Path]] = []

    if odoo_version:
        # Show only the specified version + shared
        version_dir = template_dir / odoo_version
        if version_dir.is_dir():
            for tmpl in sorted(version_dir.glob("*.j2")):
                all_templates.append((f"[{odoo_version}]", tmpl))
        if shared_dir.is_dir():
            for tmpl in sorted(shared_dir.glob("*.j2")):
                all_templates.append(("[shared]", tmpl))
    else:
        # Show all version dirs and shared
        for subdir in sorted(template_dir.iterdir()):
            if subdir.is_dir():
                label = f"[{subdir.name}]"
                for tmpl in sorted(subdir.glob("*.j2")):
                    all_templates.append((label, tmpl))

    # Fallback: try flat directory (pre-reorganization layout)
    if not all_templates:
        flat_templates = sorted(template_dir.glob("*.j2"))
        for tmpl in flat_templates:
            all_templates.append(("", tmpl))

    if not all_templates:
        click.echo("No templates found.", err=True)
        sys.exit(1)

    for label, tmpl in all_templates:
        description = _extract_template_description(tmpl)
        prefix = f"{label:10s} " if label else ""
        if description:
            click.echo(f"{prefix}{tmpl.name:30s} {description}")
        else:
            click.echo(f"{prefix}{tmpl.name}")


def _extract_template_description(template_path: Path) -> str:
    """Extract the description from a Jinja2 template's first comment.

    Looks for pattern: {# template_name.j2 -- description #}

    Args:
        template_path: Path to the .j2 template file.

    Returns:
        The description string, or empty string if not found.
    """
    try:
        first_line = template_path.read_text(encoding="utf-8").split("\n", maxsplit=1)[0]
        if first_line.startswith("{#") and first_line.endswith("#}"):
            # Strip comment markers and extract after the dash separator
            content = first_line[2:-2].strip()
            parts = content.split(" -- ", maxsplit=1)
            if len(parts) == 2:
                return parts[1].strip()
            # Try single dash separator
            parts = content.split(" - ", maxsplit=1)
            if len(parts) == 2:
                return parts[1].strip()
    except OSError:
        pass
    return ""


def _find_registry_path() -> Path:
    """Return the path to the model registry JSON file (relative to cwd)."""
    return Path(".planning/model_registry.json")


@main.group()
def registry() -> None:
    """Manage the cross-module model registry."""


main.add_command(registry)


@registry.command("list")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def registry_list(json_output: bool) -> None:
    """List all registered modules and their models."""
    from amil_utils.registry import ModelRegistry

    reg = ModelRegistry(_find_registry_path())
    reg.load()
    modules = reg.list_modules()

    if not modules:
        click.echo("No modules registered.")
        return

    if json_output:
        click.echo(json.dumps(modules, indent=2))
        return

    for mod_name, model_names in sorted(modules.items()):
        click.echo(f"  {mod_name}: {len(model_names)} model(s)")
        for m in sorted(model_names):
            click.echo(f"    - {m}")


@registry.command("show")
@click.argument("model_name")
def registry_show(model_name: str) -> None:
    """Display details for a specific model."""
    from amil_utils.registry import ModelRegistry

    reg = ModelRegistry(_find_registry_path())
    reg.load()
    reg.load_known_models()
    entry = reg.show_model(model_name)

    if entry is None:
        click.echo(f"Model '{model_name}' not found in registry.")
        return

    click.echo(f"Model: {model_name}")
    click.echo(f"Module: {entry.module}")
    if entry.description:
        click.echo(f"Description: {entry.description}")
    if entry.inherits:
        click.echo(f"Inherits: {', '.join(entry.inherits)}")
    if entry.mixins:
        click.echo(f"Mixins: {', '.join(entry.mixins)}")
    if entry.fields:
        click.echo("Fields:")
        for fname, fdef in entry.fields.items():
            ftype = fdef.get("type", "?")
            comodel = fdef.get("comodel_name", "")
            extra = f" -> {comodel}" if comodel else ""
            click.echo(f"  {fname}: {ftype}{extra}")


@registry.command("remove")
@click.argument("module_name")
def registry_remove(module_name: str) -> None:
    """Remove a module from the registry."""
    from amil_utils.registry import ModelRegistry

    reg = ModelRegistry(_find_registry_path())
    reg.load()
    modules = reg.list_modules()

    if module_name not in modules and module_name not in reg._dependency_graph:
        click.echo(f"Warning: Module '{module_name}' not found in registry.")
        return

    reg.remove_module(module_name)
    reg.save()
    click.echo(f"Removed module '{module_name}' from registry.")


@registry.command("rebuild")
@click.option("--scan-root", type=click.Path(exists=True), default=".", help="Root directory to scan for __manifest__.py files")
def registry_rebuild(scan_root: str) -> None:
    """Re-scan generated modules and rebuild registry from scratch."""
    import ast as ast_mod

    from amil_utils.registry import ModelRegistry

    reg = ModelRegistry(_find_registry_path())
    # Start fresh
    scan_path = Path(scan_root).resolve()
    count = 0

    for manifest_path in scan_path.rglob("__manifest__.py"):
        mod_dir = manifest_path.parent
        module_name = mod_dir.name
        try:
            manifest_data = ast_mod.literal_eval(manifest_path.read_text(encoding="utf-8"))
        except (ValueError, SyntaxError):
            click.echo(f"  Skipping {manifest_path}: could not parse manifest")
            continue

        spec = _parse_module_dir_to_spec(module_name, manifest_data, mod_dir)
        reg.register_module(module_name, spec)
        count += 1

    reg.save()
    click.echo(f"Registry rebuilt: {count} module(s) scanned.")


@registry.command("validate")
def registry_validate() -> None:
    """Check for broken comodel references and dependency cycles."""
    from amil_utils.registry import ModelRegistry

    reg = ModelRegistry(_find_registry_path())
    reg.load()
    reg.load_known_models()

    has_errors = False

    # Validate each module's models
    modules = reg.list_modules()
    for mod_name, model_names in modules.items():
        # Reconstruct a minimal spec from registered models
        models_list = []
        for mname in model_names:
            entry = reg.show_model(mname)
            if entry:
                models_list.append({
                    "_name": mname,
                    "fields": entry.fields,
                    "_inherit": entry.inherits + entry.mixins,
                })
        spec = {
            "module_name": mod_name,
            "models": models_list,
            "depends": reg._dependency_graph.get(mod_name, []),
        }
        vr = reg.validate_comodels(spec)
        for w in vr.warnings:
            click.echo(f"  WARNING: {w}")
        for e in vr.errors:
            click.echo(f"  ERROR: {e}")
            has_errors = True

    # Cycle detection
    cycles = reg.detect_cycles()
    for c in cycles:
        click.echo(f"  ERROR: {c}")
        has_errors = True

    if not has_errors and not any(
        reg.validate_comodels({
            "module_name": mn,
            "models": [],
            "depends": reg._dependency_graph.get(mn, []),
        }).warnings
        for mn in modules
    ):
        click.echo("Registry validation passed.")

    if has_errors:
        sys.exit(1)


@registry.command("import")
@click.option("--from-manifest", "manifest_path", required=True, type=click.Path(exists=True),
              help="Path to __manifest__.py file")
def registry_import(manifest_path: str) -> None:
    """Import an existing module into the registry from its manifest."""
    import ast as ast_mod

    from amil_utils.registry import ModelRegistry

    manifest_file = Path(manifest_path).resolve()
    mod_dir = manifest_file.parent
    module_name = mod_dir.name

    try:
        manifest_data = ast_mod.literal_eval(manifest_file.read_text(encoding="utf-8"))
    except (ValueError, SyntaxError) as exc:
        click.echo(f"Error parsing manifest: {exc}", err=True)
        sys.exit(1)

    spec = _parse_module_dir_to_spec(module_name, manifest_data, mod_dir)

    reg = ModelRegistry(_find_registry_path())
    reg.load()
    reg.register_module(module_name, spec)
    reg.save()
    model_count = len(spec.get("models", []))
    click.echo(f"Imported module '{module_name}': {model_count} model(s) registered.")


def _parse_module_dir_to_spec(
    module_name: str, manifest_data: dict, mod_dir: Path
) -> dict:
    """Parse a module directory into a spec dict for registry registration.

    Uses AST to extract _name and field definitions from Python model files.
    """
    import ast as ast_mod

    depends = manifest_data.get("depends", ["base"])
    models_list: list[dict] = []

    # Scan Python files in models/ directory
    models_dir = mod_dir / "models"
    if models_dir.is_dir():
        for py_file in models_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast_mod.parse(source)
            except (SyntaxError, OSError):
                continue

            for node in ast_mod.walk(tree):
                if not isinstance(node, ast_mod.ClassDef):
                    continue
                model_name = None
                model_desc = ""
                fields: dict = {}

                for item in node.body:
                    # Look for _name = 'model.name'
                    if (
                        isinstance(item, ast_mod.Assign)
                        and len(item.targets) == 1
                        and isinstance(item.targets[0], ast_mod.Name)
                    ):
                        attr_name = item.targets[0].id
                        if attr_name == "_name" and isinstance(item.value, ast_mod.Constant):
                            model_name = item.value.value
                        elif attr_name == "_description" and isinstance(item.value, ast_mod.Constant):
                            model_desc = item.value.value

                    # Look for field = fields.Type(...)
                    if (
                        isinstance(item, ast_mod.Assign)
                        and len(item.targets) == 1
                        and isinstance(item.targets[0], ast_mod.Name)
                        and isinstance(item.value, ast_mod.Call)
                        and isinstance(item.value.func, ast_mod.Attribute)
                    ):
                        field_name = item.targets[0].id
                        if field_name.startswith("_"):
                            continue
                        field_type = item.value.func.attr
                        field_def: dict = {"type": field_type}

                        # Extract comodel_name from first positional arg or keyword
                        if item.value.args and isinstance(item.value.args[0], ast_mod.Constant):
                            if field_type in ("Many2one", "One2many", "Many2many"):
                                field_def["comodel_name"] = item.value.args[0].value
                        for kw in item.value.keywords:
                            if kw.arg == "comodel_name" and isinstance(kw.value, ast_mod.Constant):
                                field_def["comodel_name"] = kw.value.value

                        fields[field_name] = field_def

                if model_name:
                    models_list.append({
                        "_name": model_name,
                        "fields": fields,
                        "description": model_desc,
                    })

    return {
        "module_name": module_name,
        "models": models_list,
        "depends": depends,
    }


@main.command("render-module")
@click.option("--spec-file", required=True, type=click.Path(exists=True), help="JSON file with module specification")
@click.option("--output-dir", required=True, type=click.Path(), help="Directory to create module in")
@click.option("--no-context7", is_flag=True, default=False, help="Skip Context7 documentation hints")
@click.option("--fresh-context7", is_flag=True, default=False, help="Ignore Context7 cache, force re-query")
@click.option("--skip-validation", is_flag=True, default=False, help="Skip semantic validation after rendering")
@click.option("--resume", is_flag=True, default=False, help="Resume from last generation (skip completed stages)")
@click.option("--force", is_flag=True, default=False, help="Full regeneration, ignore existing spec stash")
@click.option("--dry-run", "dry_run", is_flag=True, default=False, help="Show what would change without writing files")
def render_module_cmd(spec_file: str, output_dir: str, no_context7: bool, fresh_context7: bool, skip_validation: bool, resume: bool, force: bool, dry_run: bool) -> None:
    """Render a complete Odoo module from a JSON specification file."""
    from pydantic import ValidationError as PydanticValidationError

    from amil_utils.renderer import get_template_dir, render_module
    from amil_utils.spec_schema import format_validation_errors
    from amil_utils.verifier import build_verifier_from_env

    try:
        spec = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        click.echo(f"Error reading spec file: {exc}", err=True)
        sys.exit(1)

    # Validate required spec fields
    required_fields = ["module_name"]
    missing = [f for f in required_fields if f not in spec]
    if missing:
        click.echo(f"Missing required fields in spec: {', '.join(missing)}", err=True)
        sys.exit(1)

    template_dir = get_template_dir()
    output_path = Path(output_dir)

    # Phase 54: Load manifest for resume and instantiate hooks
    resume_manifest = None
    if resume:
        from amil_utils.manifest import load_manifest

        module_name = spec["module_name"]
        resume_manifest = load_manifest(output_path / module_name)
        if resume_manifest is None:
            click.echo("No previous manifest found. Running full generation.", err=True)

    try:
        from amil_utils.hooks import LoggingHook, ManifestHook

        module_name = spec["module_name"]
        render_hooks = [
            LoggingHook(),
            ManifestHook(module_path=output_path / module_name),
        ]

        verifier = build_verifier_from_env()
        files, warnings = render_module(
            spec, template_dir, output_path, verifier=verifier,
            no_context7=no_context7, fresh_context7=fresh_context7,
            hooks=render_hooks, resume_from=resume_manifest,
            force=force, dry_run=dry_run,
        )
        for f in files:
            click.echo(str(f))
        for w in warnings:
            click.echo(f"WARN [{w.check_type}] {w.subject}: {w.message}", err=True)
            if w.suggestion:
                click.echo(f"  Suggestion: {w.suggestion}", err=True)

        # Phase 60: Show pending conflicts summary
        pending_dir = output_path / module_name / ".amil-pending"
        if pending_dir.exists():
            pending_files = [
                str(f.relative_to(pending_dir))
                for f in pending_dir.rglob("*") if f.is_file()
            ]
            if pending_files:
                click.echo(f"\nPending conflicts ({len(pending_files)} files):", err=True)
                for pf in pending_files:
                    click.echo(f"  {pf}", err=True)
                click.echo("Use 'amil resolve' to manage pending files.", err=True)

        # Logic Writer: generate stub report
        try:
            from amil_utils.logic_writer import generate_stub_report
            from amil_utils.registry import ModelRegistry as _StubRegistry

            module_name = spec["module_name"]
            stub_reg: _StubRegistry | None = None
            try:
                stub_reg_path = _find_registry_path()
                stub_reg = _StubRegistry(stub_reg_path)
                stub_reg.load()
                stub_reg.load_known_models()
            except Exception:
                stub_reg = None

            stub_report = generate_stub_report(
                module_dir=output_path / module_name,
                spec=spec,
                registry=stub_reg,
            )
            if stub_report.total_stubs > 0:
                click.echo(
                    f"Stub report: {stub_report.total_stubs} stubs "
                    f"({stub_report.budget_count} budget, "
                    f"{stub_report.quality_count} quality) "
                    f"-> {stub_report.report_path}"
                )
            else:
                click.echo("Stub report: 0 stubs (no TODO methods found)")
        except Exception as exc:
            click.echo(f"WARN: Stub report generation failed: {exc}", err=True)

        # Post-render semantic validation
        if not skip_validation:
            from amil_utils.validation.semantic import (
                print_validation_report,
                semantic_validate,
            )

            module_name = spec["module_name"]
            validation = semantic_validate(output_path / module_name)
            print_validation_report(validation)
            if validation.has_errors:
                click.echo(
                    "Semantic validation failed. Module NOT registered.",
                    err=True,
                )
                sys.exit(1)

        # Post-render registry update
        try:
            from amil_utils.registry import ModelRegistry

            reg_path = _find_registry_path()
            reg = ModelRegistry(reg_path)
            reg.load()
            reg.load_known_models()

            vr = reg.validate_comodels(spec)
            for vw in vr.warnings:
                click.echo(f"WARNING: {vw}")
            for ve in vr.errors:
                click.echo(f"ERROR: {ve}")

            inferred = reg.infer_depends(spec)
            if inferred:
                click.echo(f"Inferred depends not in spec: {', '.join(inferred)}")

            reg.register_module(spec["module_name"], spec)
            reg.save()
            model_count = len(spec.get("models", []))
            click.echo(f"Registry updated: +{model_count} models ({spec['module_name']})")

            # Auto-generate mermaid diagrams (best-effort)
            if not skip_validation:
                try:
                    from amil_utils.mermaid import generate_module_diagrams

                    module_name = spec["module_name"]
                    docs_dir = output_path / module_name / "docs"
                    docs_dir.mkdir(parents=True, exist_ok=True)
                    generate_module_diagrams(
                        module_name=module_name,
                        spec=spec,
                        registry=reg,
                        output_dir=docs_dir,
                    )
                    click.echo(
                        f"Mermaid diagrams: {docs_dir}/dependencies.mmd, "
                        f"{docs_dir}/er_diagram.mmd"
                    )
                except Exception:
                    _logger.debug("Mermaid diagram generation failed", exc_info=True)
        except Exception:
            _logger.debug("Registry update failed (non-blocking)", exc_info=True)
    except PydanticValidationError as exc:
        formatted = format_validation_errors(exc, spec.get("module_name", "unknown"))
        click.echo(formatted, err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Error rendering module: {exc}", err=True)
        sys.exit(1)


@main.command("export-schema")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output file path (default: stdout)")
def export_schema(output: str | None) -> None:
    """Export the module spec JSON Schema for IDE autocomplete."""
    import json as json_mod

    from amil_utils.spec_schema import ModuleSpec

    schema = ModuleSpec.model_json_schema()
    schema_json = json_mod.dumps(schema, indent=2)

    if output:
        Path(output).write_text(schema_json, encoding="utf-8")
        click.echo(f"Schema written to {output}")
    else:
        click.echo(schema_json)


def _resolve_kb_path() -> Path:
    """Resolve the knowledge base directory path.

    Checks the installed location first (``~/.claude/amil/knowledge/``),
    then falls back to a development location (``./knowledge/``).

    Returns:
        Path to the knowledge base directory.

    Raises:
        click.ClickException: If no knowledge base directory is found.
    """
    installed = Path.home() / ".claude" / "amil" / "knowledge"
    if installed.is_dir():
        return installed

    dev = Path.cwd() / "knowledge"
    if dev.is_dir():
        return dev

    raise click.ClickException(
        "Knowledge base not found. Checked:\n"
        f"  - {installed}\n"
        f"  - {dev}\n"
        "Run install.sh or cd to the amil project directory."
    )


def _print_file_result(filename: str, result: dict) -> None:
    """Print validation results for a single file."""
    status = "VALID" if result["valid"] else "INVALID"
    icon = "+" if result["valid"] else "x"
    click.echo(f"  [{icon}] {filename}: {status}")
    for error in result["errors"]:
        click.echo(f"      ERROR: {error}")
    for warning in result["warnings"]:
        click.echo(f"      WARN:  {warning}")


@main.command("validate-kb")
@click.option("--custom", "scope", flag_value="custom", default=True, help="Validate only custom/ directory (default)")
@click.option("--all", "scope", flag_value="all", help="Validate all knowledge base files (shipped + custom)")
def validate_kb(scope: str) -> None:
    """Validate knowledge base rule files for correct markdown structure.

    By default, validates the custom/ subdirectory. Use --all to validate
    all shipped and custom knowledge base files.

    Checks format only: headings, code blocks, line count. Does not validate
    the semantic correctness of rule content.
    """
    from amil_utils.kb_validator import validate_kb_directory

    kb_path = _resolve_kb_path()

    has_errors = False

    if scope == "all":
        # Validate shipped (root) files
        click.echo(f"Validating shipped rules: {kb_path}/")
        shipped_result = validate_kb_directory(kb_path)
        if shipped_result["files"]:
            for filename, result in shipped_result["files"].items():
                _print_file_result(filename, result)
            summary = shipped_result["summary"]
            click.echo(
                f"  Shipped: {summary['valid']} valid, "
                f"{summary['invalid']} invalid, "
                f"{summary['warnings']} with warnings"
            )
            if not shipped_result["valid"]:
                has_errors = True
        else:
            click.echo("  No shipped .md files found.")
        click.echo()

    # Always validate custom/ directory
    custom_path = kb_path / "custom"
    click.echo(f"Validating custom rules: {custom_path}/")

    if not custom_path.is_dir():
        click.echo("  No custom/ directory found. Nothing to validate.")
    else:
        custom_result = validate_kb_directory(custom_path)
        if custom_result["files"]:
            for filename, result in custom_result["files"].items():
                _print_file_result(filename, result)
            summary = custom_result["summary"]
            click.echo(
                f"  Custom: {summary['valid']} valid, "
                f"{summary['invalid']} invalid, "
                f"{summary['warnings']} with warnings"
            )
            if not custom_result["valid"]:
                has_errors = True
        else:
            click.echo("  No custom .md rule files found (README.md is skipped).")

    if has_errors:
        raise SystemExit(1)


@main.command("extract-i18n")
@click.argument("module_path", type=click.Path(exists=True))
def extract_i18n(module_path: str) -> None:
    """Extract translatable strings and generate i18n .pot file.

    Scans Python files for _() calls and XML files for string= attributes.
    Writes MODULE_NAME.pot to MODULE_PATH/i18n/.
    """
    from amil_utils.i18n_extractor import extract_translatable_strings, generate_pot

    mod_path = Path(module_path).resolve()
    module_name = mod_path.name

    try:
        strings = extract_translatable_strings(mod_path)
        pot_content = generate_pot(module_name, strings)

        i18n_dir = mod_path / "i18n"
        i18n_dir.mkdir(parents=True, exist_ok=True)
        pot_path = i18n_dir / f"{module_name}.pot"
        pot_path.write_text(pot_content, encoding="utf-8")

        click.echo(f"Extracted {len(strings)} translatable strings to {pot_path}")
    except Exception as exc:
        click.echo(f"Error extracting i18n strings: {exc}", err=True)
        sys.exit(1)


@main.command("check-edition")
@click.argument("spec_file", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def check_edition(spec_file: str, json_output: bool) -> None:
    """Check a module spec for Enterprise-only dependencies.

    Reads the depends list from a spec JSON file and reports any
    Enterprise-only modules with Community alternatives.

    Exit code is always 0 -- warnings are informational (Decision B).
    """
    from amil_utils.edition import check_enterprise_dependencies

    try:
        spec = json.loads(Path(spec_file).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        click.echo(f"Error reading spec file: {exc}", err=True)
        sys.exit(1)

    depends = spec.get("depends", ["base"])
    warnings = check_enterprise_dependencies(depends)

    if not warnings:
        click.echo("All dependencies are Community-compatible.")
        return

    if json_output:
        click.echo(json.dumps(warnings, indent=2))
        return

    click.echo(f"Found {len(warnings)} Enterprise-only dependency(ies):\n")
    for w in warnings:
        click.echo(f"  * {w['module']} ({w['display_name']}) [{w['category']}]")
        if w.get("alternative"):
            click.echo(f"    Community alternative: {w['alternative']} ({w['alternative_repo']})")
            if w.get("notes"):
                click.echo(f"    Notes: {w['notes']}")
        else:
            click.echo("    No known Community alternative.")
        click.echo()


@main.command()
@click.argument("module_path", type=click.Path(exists=True))
@click.option("--pylint-only", is_flag=True, help="Run only pylint-odoo (skip Docker)")
@click.option("--auto-fix", is_flag=True, help="Attempt to auto-fix pylint violations (max 5 cycles)")
@click.option("--json", "json_output", is_flag=True, help="Output JSON report (machine-readable)")
@click.option("--pylintrc", type=click.Path(exists=True), help="Path to .pylintrc-odoo config file")
def validate(
    module_path: str,
    pylint_only: bool,
    auto_fix: bool,
    json_output: bool,
    pylintrc: str | None,
) -> None:
    """Validate an Odoo module against OCA quality standards.

    Runs pylint-odoo static analysis and optionally Docker-based installation
    and test execution. Produces a structured report with violations, install
    result, test results, and actionable error diagnosis.

    With --auto-fix, attempts to mechanically fix known pylint violations
    (up to 5 cycles) before reporting remaining issues.
    """
    from amil_utils.auto_fix import format_escalation, run_docker_fix_loop, run_pylint_fix_loop
    from amil_utils.validation import (
        ValidationReport,
        check_docker_available,
        diagnose_errors,
        docker_install_module,
        docker_run_tests,
        format_report_json,
        format_report_markdown,
        run_pylint_odoo,
    )

    mod_path = Path(module_path).resolve()

    # Validate manifest exists
    manifest = mod_path / "__manifest__.py"
    if not manifest.exists():
        click.echo(f"Error: No __manifest__.py found in {mod_path}", err=True)
        sys.exit(1)

    module_name = mod_path.name

    # Auto-detect .pylintrc-odoo in module directory if not provided
    pylintrc_path = Path(pylintrc) if pylintrc else None
    if pylintrc_path is None:
        candidate = mod_path / ".pylintrc-odoo"
        if candidate.exists():
            pylintrc_path = candidate

    # Step 1: Run pylint-odoo (with optional auto-fix loop)
    if auto_fix:
        fix_result = run_pylint_fix_loop(mod_path, pylintrc_path=pylintrc_path)
        if fix_result.success:
            total_fixed, violations = fix_result.data
        else:
            click.echo(f"Auto-fix error: {'; '.join(fix_result.errors)}", err=True)
            total_fixed, violations = 0, ()
        if total_fixed > 0:
            click.echo(f"Auto-fix: fixed {total_fixed} pylint violations")
        if violations:
            click.echo(format_escalation(violations))
    else:
        pylint_result = run_pylint_odoo(mod_path, pylintrc_path=pylintrc_path)
        if pylint_result.success:
            violations = pylint_result.data or ()
        else:
            click.echo(f"Pylint error: {'; '.join(pylint_result.errors)}", err=True)
            violations = ()

    install_result = None
    test_results: tuple = ()
    docker_available = True
    diagnosis: tuple[str, ...] = ()
    error_logs: list[str] = []

    if not pylint_only:
        # Step 2: Check Docker and run install
        docker_available = check_docker_available()
        if docker_available:
            docker_result = docker_install_module(mod_path)
            if not docker_result.success:
                click.echo(f"Docker error: {'; '.join(docker_result.errors)}", err=True)
                install_result = None
            else:
                install_result = docker_result.data
            if install_result and install_result.log_output:
                error_logs.append(install_result.log_output)

            # Step 2b: Auto-fix Docker errors if --auto-fix enabled
            if auto_fix and install_result and not install_result.success and install_result.log_output:
                docker_fix_result = run_docker_fix_loop(
                    mod_path,
                    install_result.log_output,
                    revalidate_fn=lambda: docker_install_module(mod_path),
                )
                if docker_fix_result.success:
                    any_docker_fixed, remaining_errors = docker_fix_result.data
                else:
                    any_docker_fixed, remaining_errors = False, ""
                if any_docker_fixed:
                    click.echo("Auto-fix: applied Docker error fix(es), retrying validation...")
                    retry_result = docker_install_module(mod_path)
                    if retry_result.success:
                        install_result = retry_result.data
                    else:
                        click.echo(f"Docker retry error: {'; '.join(retry_result.errors)}", err=True)
                        install_result = None
                    if install_result and install_result.log_output:
                        error_logs.append(install_result.log_output)
                    if remaining_errors and "iteration cap" in remaining_errors.lower():
                        click.echo(remaining_errors)

            # Step 3: Run tests if install succeeded
            if install_result and install_result.success:
                test_run_result = docker_run_tests(mod_path)
                if test_run_result.success:
                    test_results = test_run_result.data or ()
                else:
                    click.echo(f"Test run error: {'; '.join(test_run_result.errors)}", err=True)
                    test_results = ()

            # Step 4: Diagnose any error logs
            combined_logs = "\n".join(error_logs)
            if combined_logs.strip():
                diagnosis = diagnose_errors(combined_logs)

    # Build report
    report = ValidationReport(
        module_name=module_name,
        pylint_violations=violations,
        install_result=install_result,
        test_results=test_results,
        diagnosis=diagnosis,
        docker_available=docker_available,
    )

    # Output
    if json_output:
        click.echo(json.dumps(format_report_json(report), indent=2))
    else:
        click.echo(format_report_markdown(report))

    # Exit code: 0 if clean, 1 if any issues
    has_issues = bool(violations) or (
        install_result is not None and not install_result.success
    ) or any(not tr.passed for tr in test_results)

    if has_issues:
        sys.exit(1)


def _handle_auth_failure(no_wizard: bool) -> None:
    """Handle GitHub auth failure with optional wizard guidance."""
    if no_wizard:
        click.echo(
            "GitHub authentication required.\n"
            "Run: gh auth login\n"
            "Or set: export GITHUB_TOKEN=your_token",
            err=True,
        )
    else:
        from amil_utils.search.wizard import check_github_auth, format_auth_guidance

        status = check_github_auth()
        click.echo(format_auth_guidance(status), err=True)
    sys.exit(1)


@main.command("build-index")
@click.option("--token", envvar="GITHUB_TOKEN", default=None, help="GitHub personal access token")
@click.option("--db-path", default=None, help="ChromaDB storage path (default: ~/.local/share/amil/chromadb/)")
@click.option("--update", is_flag=True, help="Only re-index repos pushed since last build")
@click.option("--no-wizard", is_flag=True, help="Skip interactive setup guidance on auth failure")
def build_index(token: str | None, db_path: str | None, update: bool, no_wizard: bool) -> None:
    """Build or update the local ChromaDB index of OCA Odoo modules.

    Crawls all OCA GitHub repositories with a 19.0 branch, extracts module
    metadata from __manifest__.py files, and stores embeddings in a local
    ChromaDB database for semantic search.
    """
    from amil_utils.search import build_oca_index, get_github_token
    from amil_utils.search.index import DEFAULT_DB_PATH

    if token is None:
        token = get_github_token()

    if not token:
        _handle_auth_failure(no_wizard)

    resolved_path = db_path or str(DEFAULT_DB_PATH)

    def _progress(done: int, total: int) -> None:
        click.echo(f"Indexing OCA repos... {done}/{total}", nl=False)
        click.echo("\r", nl=False)

    click.echo("Building OCA module index...")
    count = build_oca_index(
        token=token,
        db_path=resolved_path,
        incremental=update,
        progress_callback=_progress,
    )
    click.echo(f"Indexed {count} modules from OCA")


@main.command("index-status")
@click.option("--db-path", default=None, help="ChromaDB storage path")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def index_status(db_path: str | None, json_output: bool) -> None:
    """Show the status of the local OCA module search index.

    Reports whether the index exists, how many modules are indexed,
    when it was last built, and the storage location.
    """
    from amil_utils.search import get_index_status

    status = get_index_status(db_path)

    if json_output:
        import dataclasses

        click.echo(json.dumps(dataclasses.asdict(status), indent=2))
    else:
        if status.exists:
            click.echo(f"Index exists: yes")
            click.echo(f"Modules indexed: {status.module_count}")
            click.echo(f"Last built: {status.last_built or 'unknown'}")
            click.echo(f"Storage path: {status.db_path}")
            click.echo(f"Size: {status.size_bytes} bytes")
        else:
            click.echo("Index exists: no")
            click.echo(f"Storage path: {status.db_path}")
            click.echo("Run 'amil-utils build-index' to create the index.")


@main.command("search-modules")
@click.argument("query")
@click.option("--limit", default=5, help="Number of results (default: 5)")
@click.option("--db-path", default=None, help="ChromaDB storage path")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option(
    "--github",
    "github_fallback",
    is_flag=True,
    help="Fall back to GitHub search if no OCA results found",
)
@click.option("--no-wizard", is_flag=True, help="Skip interactive setup guidance on auth failure")
def search_modules_cmd(
    query: str,
    limit: int,
    db_path: str | None,
    json_output: bool,
    github_fallback: bool,
    no_wizard: bool,
) -> None:
    """Semantically search for Odoo modules matching a natural language query.

    Searches the local ChromaDB index for OCA modules, sorted by relevance.
    With --github, falls back to live GitHub search when no OCA results found.
    Auto-builds the index on first use if it does not exist.
    """
    from amil_utils.search import build_oca_index, get_github_token, get_index_status
    from amil_utils.search.index import DEFAULT_DB_PATH
    from amil_utils.search.query import (
        format_results_json,
        format_results_text,
        search_modules,
    )

    resolved_path = db_path or str(DEFAULT_DB_PATH)

    # Auto-build index on first use (Decision B)
    status = get_index_status(resolved_path)
    if not status.exists or status.module_count == 0:
        token = get_github_token()
        if not token:
            _handle_auth_failure(no_wizard)

        click.echo("No index found. Building index first (this takes ~3-5 minutes)...")

        def _progress(done: int, total: int) -> None:
            click.echo(f"Indexing OCA repos... {done}/{total}", nl=False)
            click.echo("\r", nl=False)

        build_oca_index(
            token=token,
            db_path=resolved_path,
            progress_callback=_progress,
        )
        click.echo("Index built successfully.\n")

    # Run search
    try:
        results = search_modules(
            query,
            db_path=resolved_path,
            n_results=limit,
            github_fallback=github_fallback,
        )
    except ValueError as exc:
        click.echo(f"Search error: {exc}", err=True)
        sys.exit(1)

    # Auto-fallback: if OCA returned 0 results and --github not set, retry with fallback
    if not results and not github_fallback:
        results = search_modules(
            query,
            db_path=resolved_path,
            n_results=limit,
            github_fallback=True,
        )

    if not results:
        click.echo("No results found.")
        sys.exit(1)

    if json_output:
        click.echo(format_results_json(results))
    else:
        click.echo(format_results_text(results))


@main.command("extend-module")
@click.argument("module_name")
@click.option("--repo", required=True, help="OCA repo name (e.g., sale-workflow)")
@click.option(
    "--output-dir",
    default=".",
    type=click.Path(),
    help="Output directory for cloned + companion modules",
)
@click.option(
    "--spec-file",
    type=click.Path(exists=True),
    help="Refined spec JSON for the extension module",
)
@click.option("--branch", default="19.0", help="Git branch to clone (default: 19.0)")
@click.option("--json", "json_output", is_flag=True, help="Output analysis as JSON")
@click.option("--no-wizard", is_flag=True, help="Skip interactive setup guidance on auth failure")
def extend_module_cmd(
    module_name: str,
    repo: str,
    output_dir: str,
    spec_file: str | None,
    branch: str,
    json_output: bool,
    no_wizard: bool,
) -> None:
    """Clone an OCA module and set up a companion extension module.

    Performs git sparse checkout to clone only the target module from an OCA
    repository, analyzes its structure (models, fields, views, security),
    and creates a companion {module}_ext directory for delta code.

    If --spec-file is provided, copies the refined spec to both
    {module}_ext/spec.json and overwrites the original spec.json path
    (REFN-03: refined spec is the new source of truth).
    """
    from amil_utils.search import get_github_token
    from amil_utils.search.analyzer import analyze_module, format_analysis_text
    from amil_utils.search.fork import clone_oca_module, setup_companion_dir

    out_path = Path(output_dir).resolve()

    # Auth check for extend-module (requires GitHub for cloning)
    token = get_github_token()
    if not token:
        _handle_auth_failure(no_wizard)

    # Step 1: Clone the module via sparse checkout
    click.echo(f"Cloning {repo}/{module_name} (branch {branch})...")
    try:
        cloned_path = clone_oca_module(repo, module_name, out_path, branch=branch)
    except Exception as exc:
        click.echo(f"Error cloning module: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Cloned to: {cloned_path}")

    # Step 2: Analyze the module structure
    click.echo("Analyzing module structure...")
    try:
        analysis = analyze_module(cloned_path)
    except FileNotFoundError as exc:
        click.echo(f"Error analyzing module: {exc}", err=True)
        sys.exit(1)

    # Step 3: Set up companion directory
    companion_path = setup_companion_dir(cloned_path)
    click.echo(f"Companion module: {companion_path}")

    # Step 4: Handle spec file (REFN-03)
    if spec_file:
        spec_path = Path(spec_file).resolve()
        spec_content = spec_path.read_text(encoding="utf-8")

        # Save to companion module
        ext_spec = companion_path / "spec.json"
        ext_spec.write_text(spec_content, encoding="utf-8")
        click.echo(f"Spec saved to: {ext_spec}")

        # Overwrite original spec.json (REFN-03: refined spec is source of truth)
        spec_path.write_text(spec_content, encoding="utf-8")
        click.echo(f"Original spec overwritten: {spec_path}")

    # Step 5: Print analysis
    if json_output:
        import dataclasses

        analysis_dict = dataclasses.asdict(analysis)
        # Convert tuples to lists for JSON serialization
        analysis_dict["model_names"] = list(analysis.model_names)
        for model, field_names in analysis_dict["model_fields"].items():
            analysis_dict["model_fields"][model] = list(field_names)
        analysis_dict["security_groups"] = list(analysis.security_groups)
        analysis_dict["data_files"] = list(analysis.data_files)
        for model, types in analysis_dict["view_types"].items():
            analysis_dict["view_types"][model] = list(types)
        click.echo(json.dumps(analysis_dict, indent=2))
    else:
        click.echo("")
        click.echo(format_analysis_text(analysis))

    # Step 6: Print output paths
    click.echo("")
    click.echo("Output:")
    click.echo(f"  Original module: {cloned_path}")
    click.echo(f"  Companion module: {companion_path}")


@main.command("show-state")
@click.argument("module_path", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def show_state(module_path: str, json_output: bool) -> None:
    """Show artifact generation state for a module."""
    mod_path = Path(module_path).resolve()

    # Phase 54: Try new manifest format first
    from amil_utils.manifest import MANIFEST_FILENAME, load_manifest

    manifest = load_manifest(mod_path)

    if manifest is not None:
        if json_output:
            data = manifest.model_dump(exclude_none=True)
            click.echo(json.dumps(data, indent=2))
            return
        # Human-readable summary
        click.echo(f"Module: {manifest.module}")
        click.echo(f"Generated: {manifest.generated_at}")
        click.echo(f"Odoo version: {manifest.odoo_version}")
        click.echo(f"Spec SHA256: {manifest.spec_sha256[:12]}...")
        click.echo(f"Files: {manifest.artifacts.total_files} ({manifest.artifacts.total_lines} lines)")
        click.echo("")
        click.echo("Stages:")
        for name, stage in manifest.stages.items():
            icon = {"complete": "[OK]", "skipped": "[--]", "failed": "[!!]", "pending": "[..]"}.get(stage.status, "[??]")
            duration = f" ({stage.duration_ms}ms)" if stage.duration_ms else ""
            click.echo(f"  {icon} {name}{duration}")
            if stage.error:
                click.echo(f"       ERROR: {stage.error}")
        if manifest.preprocessing.preprocessors_run:
            click.echo(f"\nPreprocessors: {len(manifest.preprocessing.preprocessors_run)} ran ({manifest.preprocessing.duration_ms}ms)")
        if manifest.models_registered:
            click.echo(f"Models: {', '.join(manifest.models_registered)}")
        return

    # Legacy .amil-state.json is no longer supported.
    legacy_state = mod_path / ".amil-state.json"
    if legacy_state.exists():
        click.echo(
            "Legacy state file found (.amil-state.json). "
            "Re-generate the module with the current version for manifest tracking."
        )
        return

    click.echo("No manifest found. Module has not been tracked.")


@main.command("context7-status")
def context7_status() -> None:
    """Check Context7 API configuration status."""
    from amil_utils.context7 import build_context7_from_env

    client = build_context7_from_env()

    if not client.is_configured:
        click.echo("Context7 not configured. Set CONTEXT7_API_KEY to enable live Odoo docs.")
        return

    click.echo("Context7 configured.")
    library_id = client.resolve_odoo_library()
    if library_id is not None:
        click.echo(f"Odoo library resolved: {library_id}")
    else:
        click.echo("Odoo library resolution failed (docs may be unavailable).")


@main.command("diff-spec")
@click.argument("old_spec", type=click.Path(exists=True))
@click.argument("new_spec", type=click.Path(exists=True))
@click.option("--json", "json_output", is_flag=True, help="Output JSON only (no human summary)")
def diff_spec(old_spec: str, new_spec: str, json_output: bool) -> None:
    """Compare two spec versions and output structural differences.

    Reads two JSON spec files, computes a hierarchical diff with
    destructiveness classification, and outputs the results.

    Default: human-readable summary followed by JSON.
    With --json: JSON only, no human summary.
    """
    from amil_utils.spec_differ import diff_specs, format_human_summary

    try:
        old_data = json.loads(Path(old_spec).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        click.echo(f"Error reading old spec: {exc}", err=True)
        sys.exit(1)

    try:
        new_data = json.loads(Path(new_spec).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        click.echo(f"Error reading new spec: {exc}", err=True)
        sys.exit(1)

    result = diff_specs(old_data, new_data)

    if json_output:
        click.echo(json.dumps(result, indent=2))
    else:
        summary = format_human_summary(result)
        click.echo(summary)
        click.echo("")
        click.echo(json.dumps(result, indent=2))

    # Print destructive warnings to stderr
    if result.get("destructive_count", 0) > 0:
        click.echo(
            f"\nWARNING: {result['destructive_count']} destructive change(s) detected. "
            "Review migration script carefully.",
            err=True,
        )


@main.command("gen-migration")
@click.argument("old_spec", type=click.Path(exists=True))
@click.argument("new_spec", type=click.Path(exists=True))
@click.option("--version", "migration_version", required=True, help="Migration version (e.g., 19.0.1.1.0)")
@click.option("--output-dir", default=".", type=click.Path(), help="Output directory for migration folder")
def gen_migration(old_spec: str, new_spec: str, migration_version: str, output_dir: str) -> None:
    """Generate Odoo migration scripts from spec differences.

    Reads two JSON spec files, computes the diff, and generates
    pre-migrate.py and post-migrate.py scripts with per-change helper
    functions using raw SQL (cr.execute).

    Creates {output-dir}/migrations/{version}/ directory with the scripts.
    """
    from amil_utils.migration_generator import generate_migration
    from amil_utils.spec_differ import diff_specs

    try:
        old_data = json.loads(Path(old_spec).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        click.echo(f"Error reading old spec: {exc}", err=True)
        sys.exit(1)

    try:
        new_data = json.loads(Path(new_spec).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        click.echo(f"Error reading new spec: {exc}", err=True)
        sys.exit(1)

    diff = diff_specs(old_data, new_data)

    if not diff["migration_required"]:
        click.echo("No migration required.")
        return

    result = generate_migration(diff, migration_version, output_dir=output_dir)

    migration_dir = Path(output_dir) / "migrations" / migration_version
    click.echo(f"Created migration scripts in: {migration_dir}")
    click.echo(f"  {migration_dir / 'pre-migrate.py'}")
    click.echo(f"  {migration_dir / 'post-migrate.py'}")

    destructive_count = diff.get("destructive_count", 0)
    if destructive_count > 0:
        click.echo(
            f"\nWARNING: {destructive_count} destructive change(s) detected. "
            "Review migration scripts carefully.",
            err=True,
        )


@main.command("mermaid")
@click.option("--module", default=None, help="Module name")
@click.option(
    "--project", "is_project", is_flag=True, default=False,
    help="Generate project-level diagrams",
)
@click.option(
    "--type", "diagram_type",
    type=click.Choice(["deps", "er", "all"]),
    default="all",
    help="Diagram type (default: all)",
)
@click.option(
    "--stdout", "use_stdout", is_flag=True, default=False,
    help="Print to stdout instead of writing files",
)
def mermaid_cmd(
    module: str | None,
    is_project: bool,
    diagram_type: str,
    use_stdout: bool,
) -> None:
    """Generate Mermaid dependency DAG and ER diagrams.

    Either --module or --project must be specified, but not both.

    With --module, generates diagrams for a single module and writes them
    to <cwd>/<module>/docs/.

    With --project, generates combined project-level diagrams and writes
    them to .planning/diagrams/.

    Use --stdout to print diagram content to the console instead of writing files.
    """
    from amil_utils.mermaid import (
        generate_dependency_dag,
        generate_er_diagram,
        generate_module_diagrams,
        generate_project_diagrams,
    )
    from amil_utils.registry import ModelRegistry

    # Validate: exactly one of --module or --project must be specified
    if module and is_project:
        click.echo("Error: specify either --module or --project, not both.", err=True)
        sys.exit(1)
    if not module and not is_project:
        click.echo("Error: specify either --module or --project.", err=True)
        sys.exit(1)

    # Load registry
    reg_path = _find_registry_path()
    reg = ModelRegistry(reg_path)
    reg.load()
    reg.load_known_models()

    if is_project:
        if use_stdout:
            project_modules = set(reg._dependency_graph.keys())
            if diagram_type in ("deps", "all"):
                # Build combined DAG inline
                lines: list[str] = ["graph TD"]
                all_nodes: set[str] = set()
                all_edges: list[str] = []
                from amil_utils.mermaid import _mermaid_id, _is_external_module, _EXTERNAL_CLASSDEF
                for mod, deps in reg._dependency_graph.items():
                    mod_id = _mermaid_id(mod)
                    if mod_id not in all_nodes:
                        all_nodes.add(mod_id)
                        lines.append(f'    {mod_id}["{mod}"]')
                    for dep in deps:
                        dep_id = _mermaid_id(dep)
                        if dep_id not in all_nodes:
                            all_nodes.add(dep_id)
                            if _is_external_module(dep, project_modules):
                                lines.append(f'    {dep_id}["{dep}"]:::external')
                            else:
                                lines.append(f'    {dep_id}["{dep}"]')
                        all_edges.append(f"    {mod_id} --> {dep_id}")
                lines.extend(all_edges)
                lines.append(f"    {_EXTERNAL_CLASSDEF}")
                click.echo("\n".join(lines))
            if diagram_type in ("er", "all"):
                from amil_utils.mermaid import generate_er_diagram as _gen_er
                # Generate combined ER for all modules
                all_models = dict(reg._models)
                # Use first module as context -- pass all as a single "module"
                er_content = _gen_er("__project__", all_models, reg)
                click.echo(er_content)
        else:
            output_dir = Path.cwd() / ".planning" / "diagrams"
            if diagram_type == "deps":
                generate_project_diagrams(reg, output_dir)
                click.echo(str(output_dir / "project_dependencies.mmd"))
            elif diagram_type == "er":
                generate_project_diagrams(reg, output_dir)
                click.echo(str(output_dir / "project_er.mmd"))
            else:
                generate_project_diagrams(reg, output_dir)
                click.echo(str(output_dir / "project_dependencies.mmd"))
                click.echo(str(output_dir / "project_er.mmd"))
    else:
        # Module-level diagrams
        assert module is not None

        # Build spec from registry data
        module_models = {
            name: entry
            for name, entry in reg._models.items()
            if entry.module == module
        }
        deps = reg._dependency_graph.get(module, [])
        project_modules = set(reg._dependency_graph.keys())
        project_modules.add(module)

        if use_stdout:
            if diagram_type in ("deps", "all"):
                dep_graph = dict(reg._dependency_graph)
                dep_graph.setdefault(module, deps)
                dag_content = generate_dependency_dag(module, dep_graph, project_modules)
                click.echo(dag_content)
            if diagram_type in ("er", "all"):
                er_content = generate_er_diagram(module, module_models, reg)
                click.echo(er_content)
        else:
            # Build a spec dict for generate_module_diagrams
            models_list = []
            for model_name, entry in module_models.items():
                models_list.append({
                    "_name": model_name,
                    "fields": entry.fields,
                    "_inherit": list(entry.inherits),
                    "description": entry.description,
                })
            spec = {
                "module_name": module,
                "models": models_list,
                "depends": deps,
            }
            output_dir = Path.cwd() / module / "docs"
            if diagram_type == "deps":
                generate_module_diagrams(module, spec, reg, output_dir)
                click.echo(str(output_dir / "dependencies.mmd"))
            elif diagram_type == "er":
                generate_module_diagrams(module, spec, reg, output_dir)
                click.echo(str(output_dir / "er_diagram.mmd"))
            else:
                generate_module_diagrams(module, spec, reg, output_dir)
                click.echo(str(output_dir / "dependencies.mmd"))
                click.echo(str(output_dir / "er_diagram.mmd"))


# ---------------------------------------------------------------------------
# Phase 60: Resolve command group for managing pending conflict files
# ---------------------------------------------------------------------------


@main.group("resolve")
def resolve_group() -> None:
    """Manage pending conflict files from iterative generation."""


@resolve_group.command("status")
@click.option("--module-dir", required=True, type=click.Path(exists=True), help="Module directory")
def resolve_status_cmd(module_dir: str) -> None:
    """Show pending conflict files."""
    from amil_utils.iterative.resolve import resolve_status

    pending = resolve_status(Path(module_dir))
    if not pending:
        click.echo("No pending conflicts.")
        return

    click.echo(f"Pending conflicts ({len(pending)} files):")
    for rel_path in pending:
        click.echo(f"  {rel_path}")


@resolve_group.command("accept-all")
@click.option("--module-dir", required=True, type=click.Path(exists=True), help="Module directory")
def resolve_accept_all_cmd(module_dir: str) -> None:
    """Accept all pending conflict files (overwrite current with new)."""
    from amil_utils.iterative.resolve import resolve_accept_all

    count = resolve_accept_all(Path(module_dir))
    if count == 0:
        click.echo("No pending conflicts to resolve.")
    else:
        click.echo(f"Resolved {count} file(s).")


@resolve_group.command("accept-new")
@click.option("--module-dir", required=True, type=click.Path(exists=True), help="Module directory")
@click.argument("file_path")
def resolve_accept_new_cmd(module_dir: str, file_path: str) -> None:
    """Accept the new version of a specific pending file."""
    from amil_utils.iterative.resolve import resolve_accept_new

    result = resolve_accept_new(Path(module_dir), file_path)
    if result:
        click.echo(f"Accepted: {file_path}")
    else:
        click.echo(f"Not found in pending: {file_path}", err=True)
        sys.exit(1)


@resolve_group.command("keep-mine")
@click.option("--module-dir", required=True, type=click.Path(exists=True), help="Module directory")
@click.argument("file_path")
def resolve_keep_mine_cmd(module_dir: str, file_path: str) -> None:
    """Keep the current version of a specific file, discard pending."""
    from amil_utils.iterative.resolve import resolve_keep_mine

    result = resolve_keep_mine(Path(module_dir), file_path)
    if result:
        click.echo(f"Kept current: {file_path}")
    else:
        click.echo(f"Not found in pending: {file_path}", err=True)
        sys.exit(1)


@main.command("factory-docker")
@click.option("--action", type=click.Choice(["start", "stop", "reset", "status"]),
              help="Lifecycle action for the persistent Docker instance")
@click.option("--install", type=click.Path(exists=True),
              help="Module path to install into the running instance")
@click.option("--test", type=click.Path(exists=True),
              help="Module path to run tests for")
@click.option("--cross-test", multiple=True,
              help="Module names for cross-module testing (repeatable)")
@click.option("--url", is_flag=True, help="Print the Odoo web URL")
@click.option("--history", is_flag=True, help="Print install history as JSON")
@click.option("--state-dir", type=click.Path(), default=".planning",
              help="Directory for state persistence (default: .planning)")
def factory_docker(
    action: str | None,
    install: str | None,
    test: str | None,
    cross_test: tuple[str, ...],
    url: bool,
    history: bool,
    state_dir: str,
) -> None:
    """Manage the persistent Docker factory instance for 90+ module generation."""
    from amil_utils.validation.persistent_docker import PersistentDockerManager

    manager = PersistentDockerManager()
    sd = Path(state_dir)

    if url:
        click.echo(manager.get_web_url())
        return

    if history:
        manager._state_dir = sd
        manager._load_state()
        click.echo(json.dumps(manager.get_install_history(), indent=2))
        return

    if action == "status":
        manager._state_dir = sd
        manager._load_state()
        running = manager._running and manager._health_check()
        click.echo(json.dumps({
            "running": running,
            "installed_count": len(manager.installed_modules),
            "installed_modules": manager.installed_modules,
            "url": manager.get_web_url() if running else None,
        }, indent=2))
        return

    if action == "start":
        ok = manager.ensure_running(state_dir=sd)
        if ok:
            click.echo("Persistent Docker instance is running.")
            click.echo(f"Access Odoo at {manager.get_web_url()}")
        else:
            click.echo("Failed to start persistent Docker instance.", err=True)
            sys.exit(1)
        return

    if action == "stop":
        manager._state_dir = sd
        manager._load_state()
        manager.stop()
        click.echo("Persistent Docker instance stopped (data preserved).")
        return

    if action == "reset":
        manager._state_dir = sd
        manager._load_state()
        manager.reset()
        click.echo("Persistent Docker instance destroyed (all data removed).")
        return

    if install:
        manager._state_dir = sd
        manager._load_state()
        if not manager._running:
            click.echo("Docker not running. Start with: factory-docker --action start", err=True)
            sys.exit(1)
        result = manager.install_module(Path(install))
        if result.success and result.data and result.data.success:
            click.echo(f"Installed {Path(install).name} successfully.")
            click.echo(f"Total modules: {len(manager.installed_modules)}")
        else:
            msg = result.data.error_message if result.success and result.data else "; ".join(result.errors)
            click.echo(f"Install failed: {msg}", err=True)
            sys.exit(1)
        return

    if test:
        manager._state_dir = sd
        manager._load_state()
        result = manager.run_module_tests(Path(test))
        if result.success:
            click.echo(f"Tests completed for {Path(test).name}.")
        else:
            click.echo(f"Test run failed: {'; '.join(result.errors)}", err=True)
            sys.exit(1)
        return

    if cross_test:
        manager._state_dir = sd
        manager._load_state()
        result = manager.run_cross_module_test(list(cross_test))
        if result.success:
            click.echo(f"Cross-module tests completed for: {', '.join(cross_test)}")
        else:
            click.echo(f"Cross-module test failed: {'; '.join(result.errors)}", err=True)
            sys.exit(1)
        return

    click.echo("Specify --action, --install, --test, --cross-test, --url, or --history.", err=True)
    sys.exit(1)
