"""Click sub-commands for the ``registry`` group.

Separated from cli.py to reduce its line count while keeping the Click
wiring together with the business logic for registry management.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from amil_utils.commands.registry_helpers import find_registry_path


def _rp() -> Path:
    return find_registry_path()


def register_registry_commands(registry_group: click.Group) -> None:
    """Register all registry sub-commands onto *registry_group*."""

    @registry_group.command("list")
    @click.option("--json", "json_output", is_flag=True)
    def registry_list(json_output: bool) -> None:
        """List all registered modules and their models."""
        from amil_utils.registry import ModelRegistry
        reg = ModelRegistry(_rp()); reg.load(); modules = reg.list_modules()
        if not modules: click.echo("No modules registered."); return
        if json_output: click.echo(json.dumps(modules, indent=2)); return
        for mn, names in sorted(modules.items()):
            click.echo(f"  {mn}: {len(names)} model(s)")
            for m in sorted(names): click.echo(f"    - {m}")

    @registry_group.command("show")
    @click.argument("model_name")
    def registry_show(model_name: str) -> None:
        """Display details for a specific model."""
        from amil_utils.registry import ModelRegistry
        reg = ModelRegistry(_rp()); reg.load(); reg.load_known_models()
        e = reg.show_model(model_name)
        if not e: click.echo(f"Model '{model_name}' not found."); return
        click.echo(f"Model: {model_name}\nModule: {e.module}")
        if e.description: click.echo(f"Description: {e.description}")
        if e.inherits: click.echo(f"Inherits: {', '.join(e.inherits)}")
        if e.mixins: click.echo(f"Mixins: {', '.join(e.mixins)}")
        if e.fields:
            click.echo("Fields:")
            for fn, fd in e.fields.items():
                cm = fd.get("comodel_name", "")
                click.echo(f"  {fn}: {fd.get('type','?')}{f' -> {cm}' if cm else ''}")

    @registry_group.command("remove")
    @click.argument("module_name")
    def registry_remove(module_name: str) -> None:
        """Remove a module from the registry."""
        from amil_utils.registry import ModelRegistry
        reg = ModelRegistry(_rp()); reg.load()
        if module_name not in reg.list_modules() and module_name not in reg._dependency_graph:
            click.echo(f"Module '{module_name}' not found."); return
        reg.remove_module(module_name); reg.save()
        click.echo(f"Removed '{module_name}'.")

    @registry_group.command("rebuild")
    @click.option("--scan-root", type=click.Path(exists=True), default=".")
    def registry_rebuild(scan_root: str) -> None:
        """Re-scan modules and rebuild registry."""
        import ast as ast_mod
        from amil_utils.commands.registry_helpers import parse_module_dir_to_spec
        from amil_utils.registry import ModelRegistry
        reg = ModelRegistry(_rp()); count = 0
        for mp in Path(scan_root).resolve().rglob("__manifest__.py"):
            try: data = ast_mod.literal_eval(mp.read_text(encoding="utf-8"))
            except (ValueError, SyntaxError): click.echo(f"  Skip {mp}"); continue
            reg.register_module(mp.parent.name, parse_module_dir_to_spec(mp.parent.name, data, mp.parent))
            count += 1
        reg.save(); click.echo(f"Rebuilt: {count} module(s).")

    @registry_group.command("validate")
    def registry_validate() -> None:
        """Check for broken comodel references and dependency cycles."""
        from amil_utils.registry import ModelRegistry
        reg = ModelRegistry(_rp()); reg.load(); reg.load_known_models()
        errs = False
        for mn, names in reg.list_modules().items():
            ml = []
            for n in names:
                e = reg.show_model(n)
                if e: ml.append({"_name": n, "fields": e.fields, "_inherit": e.inherits + e.mixins})
            vr = reg.validate_comodels({"module_name": mn, "models": ml, "depends": reg._dependency_graph.get(mn, [])})
            for w in vr.warnings: click.echo(f"  WARNING: {w}")
            for e in vr.errors: click.echo(f"  ERROR: {e}"); errs = True
        for c in reg.detect_cycles(): click.echo(f"  ERROR: {c}"); errs = True
        if not errs: click.echo("Registry validation passed.")
        if errs: sys.exit(1)

    @registry_group.command("import")
    @click.option("--from-manifest", "manifest_path", required=True, type=click.Path(exists=True))
    def registry_import(manifest_path: str) -> None:
        """Import a module from its manifest."""
        import ast as ast_mod
        from amil_utils.commands.registry_helpers import parse_module_dir_to_spec
        from amil_utils.registry import ModelRegistry
        mf = Path(manifest_path).resolve()
        try: data = ast_mod.literal_eval(mf.read_text(encoding="utf-8"))
        except (ValueError, SyntaxError) as exc: click.echo(f"Error: {exc}", err=True); sys.exit(1)
        spec = parse_module_dir_to_spec(mf.parent.name, data, mf.parent)
        reg = ModelRegistry(_rp()); reg.load(); reg.register_module(mf.parent.name, spec); reg.save()
        click.echo(f"Imported '{mf.parent.name}': {len(spec.get('models',[]))} model(s).")
