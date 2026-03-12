"""Model registry for cross-module model awareness.

Tracks all generated models across modules in a JSON registry,
enabling comodel validation and ``depends`` inference without
requiring a running Odoo instance.

Registry operations live in the CLI layer -- ``render_module()``
has no knowledge of the registry.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any

logger = logging.getLogger("odoo-gen.registry")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelEntry:
    """A single model stored in the registry."""

    module: str
    fields: dict[str, Any]
    inherits: list[str] = field(default_factory=list)
    mixins: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ValidationResult:
    """Aggregated validation output with three severity tiers."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


@dataclass
class ModelDiff:
    """Result of registering or comparing module models."""

    added_models: list[str] = field(default_factory=list)
    removed_models: list[str] = field(default_factory=list)
    added_fields: dict[str, list[str]] = field(default_factory=dict)
    removed_fields: dict[str, list[str]] = field(default_factory=dict)
    info: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Mixin Detection
# ---------------------------------------------------------------------------

_KNOWN_MIXIN_MODELS: frozenset[str] = frozenset({
    "mail.thread",
    "mail.activity.mixin",
    "portal.mixin",
    "utm.mixin",
    "image.mixin",
    "avatar.mixin",
    "mail.alias.mixin",
    "rating.mixin",
    "website.published.mixin",
    "website.seo.metadata",
    "website.multi.mixin",
})


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_RELATIONAL_TYPES = frozenset({"Many2one", "One2many", "Many2many"})


class ModelRegistry:
    """Central model registry for cross-module awareness.

    Persists to a JSON file with three top-level sections:
    ``_meta``, ``models``, and ``dependency_graph``.
    """

    def __init__(self, registry_path: Path) -> None:
        self._path = registry_path
        self._meta: dict[str, Any] = {
            "version": "1.0",
            "last_updated": "",
            "odoo_version": "19.0",
            "modules_registered": 0,
        }
        self._models: dict[str, ModelEntry] = {}
        self._dependency_graph: dict[str, list[str]] = {}
        self._known_models: dict[str, dict[str, Any]] = {}

    # -- Persistence --------------------------------------------------------

    def load(self) -> None:
        """Load registry from JSON file.  No-op if file does not exist."""
        if not self._path.exists():
            logger.debug("Registry file not found at %s, starting empty", self._path)
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._meta = data.get("_meta", self._meta)
        raw_models = data.get("models", {})
        self._models = {
            name: ModelEntry(
                module=entry["module"],
                fields=entry.get("fields", {}),
                inherits=entry.get("inherits", []),
                mixins=entry.get("mixins", []),
                description=entry.get("description", ""),
            )
            for name, entry in raw_models.items()
        }
        self._dependency_graph = data.get("dependency_graph", {})
        logger.info("Loaded registry: %d models, %d modules", len(self._models), len(self._dependency_graph))

    def save(self) -> None:
        """Persist current state to the JSON file atomically.

        Writes to a temporary file first, then renames to the target path.
        Keeps a .bak backup of the previous version.
        """
        self._meta["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._meta["modules_registered"] = len(self._dependency_graph)
        payload = {
            "_meta": self._meta,
            "models": {name: asdict(entry) for name, entry in self._models.items()},
            "dependency_graph": self._dependency_graph,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        if self._path.exists():
            bak_path = self._path.with_suffix(".bak")
            self._path.replace(bak_path)
        tmp_path.rename(self._path)

    # -- Known models -------------------------------------------------------

    def load_known_models(self) -> None:
        """Load the shipped ``known_odoo_models.json`` into memory."""
        data_path = Path(__file__).parent / "data" / "known_odoo_models.json"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        self._known_models = data.get("models", {})

    # -- Module operations --------------------------------------------------

    def register_module(self, module_name: str, spec: dict[str, Any]) -> ModelDiff:
        """Extract models from *spec* and store them.

        Returns a :class:`ModelDiff` with added/removed models and fields.
        Overwrites all existing entries for *module_name*.
        """
        diff = ModelDiff()

        # Snapshot previous entries for this module
        old_models = {
            name: entry for name, entry in self._models.items()
            if entry.module == module_name
        }
        if old_models:
            diff.info.append(
                f"INFO: Overwriting {len(old_models)} model(s) for module '{module_name}'"
            )
            logger.info("Overwriting %d model(s) for module '%s'", len(old_models), module_name)
            for name in old_models:
                del self._models[name]

        # Register each model from the spec
        new_model_names: set[str] = set()
        for model in spec.get("models", []):
            model_name: str = model["_name"]
            new_model_names.add(model_name)
            inherits = model.get("_inherit", [])
            if isinstance(inherits, str):
                inherits = [inherits]

            # Separate mixins from regular inherits (REG-4.2)
            mixins = [inh for inh in inherits if self._is_mixin(inh)]
            non_mixin_inherits = [inh for inh in inherits if inh not in mixins]

            new_fields = model.get("fields", {})
            self._models[model_name] = ModelEntry(
                module=module_name,
                fields=new_fields,
                inherits=non_mixin_inherits,
                mixins=mixins,
                description=model.get("description", ""),
            )

            # Compute field diff against previous registration (REG-4.3)
            if model_name in old_models:
                old_field_names = set(old_models[model_name].fields.keys())
                new_field_names = set(new_fields.keys())
                added = sorted(new_field_names - old_field_names)
                removed = sorted(old_field_names - new_field_names)
                if added:
                    diff.added_fields[model_name] = added
                if removed:
                    diff.removed_fields[model_name] = removed
            else:
                diff.added_models.append(model_name)

        # Detect removed models
        for old_name in old_models:
            if old_name not in new_model_names:
                diff.removed_models.append(old_name)

        # Update dependency graph
        self._dependency_graph[module_name] = list(spec.get("depends", []))
        logger.info(
            "Registered module '%s': +%d/-%d models, %d field additions, %d field removals",
            module_name,
            len(diff.added_models),
            len(diff.removed_models),
            sum(len(v) for v in diff.added_fields.values()),
            sum(len(v) for v in diff.removed_fields.values()),
        )
        return diff

    def remove_module(self, module_name: str) -> None:
        """Remove all models belonging to *module_name*.  No-op if absent."""
        models_to_remove = [
            name for name, entry in self._models.items() if entry.module == module_name
        ]
        for name in models_to_remove:
            del self._models[name]
        self._dependency_graph.pop(module_name, None)
        logger.info("Removed module '%s' (%d models)", module_name, len(models_to_remove))

    # -- Mixin detection (REG-4.2) -----------------------------------------

    def _is_mixin(self, model_name: str) -> bool:
        """Check if a model is a mixin.

        Checks (in order):
        1. Hardcoded known Odoo mixin models
        2. Name contains 'mixin' (case-insensitive)
        3. Known models JSON marked as ``is_mixin``
        """
        if model_name in _KNOWN_MIXIN_MODELS:
            return True
        if "mixin" in model_name.lower():
            return True
        return self._known_models.get(model_name, {}).get("is_mixin", False)

    # -- Breaking change detection (REG-4.1) --------------------------------

    def detect_breaking_changes(
        self, module_name: str, new_spec: dict[str, Any],
    ) -> list[str]:
        """Compare *new_spec* against registered models for *module_name*.

        Returns a list of breaking-change descriptions. Empty list means
        no breaking changes detected. Does NOT modify the registry.
        """
        warnings: list[str] = []
        old_models = {
            name: entry for name, entry in self._models.items()
            if entry.module == module_name
        }
        if not old_models:
            return warnings

        new_model_names = {m["_name"] for m in new_spec.get("models", [])}

        # Removed models
        for old_name in sorted(set(old_models.keys()) - new_model_names):
            warnings.append(
                f"BREAKING: Model '{old_name}' removed from module '{module_name}'"
            )

        # Removed fields in surviving models
        for model in new_spec.get("models", []):
            model_name: str = model["_name"]
            if model_name not in old_models:
                continue
            old_field_names = set(old_models[model_name].fields.keys())
            new_field_names = set(model.get("fields", {}).keys())
            for removed in sorted(old_field_names - new_field_names):
                warnings.append(
                    f"BREAKING: Field '{model_name}.{removed}' removed"
                )

        if warnings:
            logger.warning(
                "Detected %d breaking change(s) in module '%s'",
                len(warnings), module_name,
            )
        return warnings

    # -- Validation ---------------------------------------------------------

    def validate_comodels(self, spec: dict[str, Any]) -> ValidationResult:
        """Validate comodel references, inherits, and duplicates.

        Returns a :class:`ValidationResult` with errors, warnings, info.
        """
        result = ValidationResult()
        seen_names: list[str] = []

        for model in spec.get("models", []):
            model_name: str = model["_name"]

            # Duplicate _name check
            if model_name in seen_names:
                result.errors.append(
                    f"ERROR: Duplicate model _name '{model_name}' within module"
                )
            seen_names.append(model_name)

            # Self-inherit check
            inherits = model.get("_inherit", [])
            if isinstance(inherits, str):
                inherits = [inherits]
            if model_name in inherits:
                result.errors.append(
                    f"ERROR: Model '{model_name}' inherits from itself"
                )

            # Comodel validation for relational fields
            for field_name, field_def in model.get("fields", {}).items():
                ftype = field_def.get("type", "")
                comodel = field_def.get("comodel_name")
                if ftype in _RELATIONAL_TYPES and comodel:
                    if not self._is_known_model(comodel, spec):
                        result.warnings.append(
                            f"WARNING: comodel '{comodel}' (field '{model_name}.{field_name}') "
                            f"not in registry or known Odoo models"
                        )

        return result

    def _is_known_model(self, model_name: str, spec: dict[str, Any]) -> bool:
        """Check if *model_name* exists in known models, registry, or current spec."""
        if model_name in self._known_models:
            return True
        if model_name in self._models:
            return True
        # Check models being defined in the current spec
        for model in spec.get("models", []):
            if model["_name"] == model_name:
                return True
        return False

    # -- Depends inference --------------------------------------------------

    def infer_depends(self, spec: dict[str, Any]) -> list[str]:
        """Infer module dependencies from comodel/inherit references.

        Returns module names NOT already in ``spec['depends']``.
        """
        explicit = set(spec.get("depends", []))
        inferred: set[str] = set()

        for model in spec.get("models", []):
            # From inherits / mixins
            inherits = model.get("_inherit", [])
            if isinstance(inherits, str):
                inherits = [inherits]
            for inh in inherits:
                owner = self._find_owning_module(inh)
                if owner and owner not in explicit:
                    inferred.add(owner)

            # From relational field comodels
            for _field_name, field_def in model.get("fields", {}).items():
                ftype = field_def.get("type", "")
                comodel = field_def.get("comodel_name")
                if ftype in _RELATIONAL_TYPES and comodel:
                    owner = self._find_owning_module(comodel)
                    if owner and owner not in explicit:
                        inferred.add(owner)

        return sorted(inferred)

    def _find_owning_module(self, model_name: str) -> str | None:
        """Return the module that owns *model_name*, or ``None``."""
        known = self._known_models.get(model_name)
        if known:
            return known["module"]
        registered = self._models.get(model_name)
        if registered:
            return registered.module
        return None

    # -- Cycle detection ----------------------------------------------------

    def detect_cycles(self) -> list[str]:
        """Detect circular dependencies in the module dependency graph.

        Returns a list of error messages (empty if no cycles).
        Uses :class:`graphlib.TopologicalSorter`.
        """
        graph: dict[str, set[str]] = {
            mod: set(deps) for mod, deps in self._dependency_graph.items()
        }
        try:
            ts = TopologicalSorter(graph)
            list(ts.static_order())
        except CycleError as exc:
            cycle_nodes = exc.args[1]
            cycle_str = " -> ".join(str(n) for n in cycle_nodes)
            return [
                f"ERROR: Circular dependency detected: {cycle_str}. "
                f"Break the cycle by removing one dependency."
            ]
        return []

    # -- Query helpers ------------------------------------------------------

    def list_modules(self) -> dict[str, list[str]]:
        """Return ``{module_name: [model_names]}``."""
        result: dict[str, list[str]] = {}
        for model_name, entry in self._models.items():
            result.setdefault(entry.module, []).append(model_name)
        return result

    def show_model(self, model_name: str) -> ModelEntry | None:
        """Look up a model by name.  Returns ``None`` if not found."""
        return self._models.get(model_name)
