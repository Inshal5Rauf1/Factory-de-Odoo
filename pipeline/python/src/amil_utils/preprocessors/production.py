"""Production pattern enrichment (bulk, cache, archival)."""

from __future__ import annotations

from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.utils.copy import deep_copy_model, merge_override_source


@register_preprocessor(order=50, name="production_patterns")
def _process_production_patterns(spec: dict[str, Any]) -> dict[str, Any]:
    """Enrich models with bulk create, ORM cache, and archival production patterns.

    Analyzes:
    1. bulk:true -> is_bulk=True, override_sources["create"].add("bulk")
    2. cacheable:true -> is_cacheable=True, needs_tools=True,
       override_sources["create"].add("cache"), override_sources["write"].add("cache"),
       cache_lookup_field (from cache_key or first unique Char or "name")
    3. archival:true -> is_archival=True, active field injection,
       archival wizard in spec["wizards"], archival cron in spec["cron_jobs"]

    Preserves existing override_sources from Phase 29 constraints (union, don't replace).

    Pure function -- does NOT mutate the input spec.
    """
    models = spec.get("models", [])
    if not models:
        return spec

    new_models = []
    new_wizards = list(spec.get("wizards", []))
    new_cron_jobs = list(spec.get("cron_jobs", []))

    for model in models:
        new_model = deep_copy_model(model)

        is_bulk = bool(model.get("bulk"))
        is_cacheable = bool(model.get("cacheable"))
        is_archival = bool(model.get("archival"))

        if not is_bulk and not is_cacheable and not is_archival:
            new_models.append(new_model)
            continue

        if is_bulk:
            new_model["is_bulk"] = True
            new_model["has_create_override"] = True
            merge_override_source(new_model, "create", "bulk")

        if is_cacheable:
            new_model["is_cacheable"] = True
            new_model["needs_tools"] = True
            new_model["has_create_override"] = True
            new_model["has_write_override"] = True
            merge_override_source(new_model, "create", "cache")
            merge_override_source(new_model, "write", "cache")

            # Determine cache lookup field
            cache_key = model.get("cache_key")
            if cache_key:
                new_model["cache_lookup_field"] = cache_key
            else:
                # Find first unique Char field
                fields = model.get("fields", [])
                unique_char = next(
                    (f["name"] for f in fields
                     if f.get("type") == "Char" and f.get("unique")),
                    None,
                )
                new_model["cache_lookup_field"] = unique_char or "name"

        if is_archival:
            new_model["is_archival"] = True
            new_model["archival_batch_size"] = model.get("archival_batch_size", 100)
            new_model["archival_days"] = model.get("archival_days", 365)

            # Inject active field if not already present
            existing_field_names = {f["name"] for f in new_model["fields"]}
            if "active" not in existing_field_names:
                new_model["fields"] = [
                    *new_model["fields"],
                    {
                        "name": "active",
                        "type": "Boolean",
                        "default": True,
                        "index": True,
                        "string": "Active",
                    },
                ]

            # Inject archival wizard into spec wizards
            wizard_name = f"{model['name']}.archive.wizard"
            new_wizards.append({
                "name": wizard_name,
                "target_model": model["name"],
                "template": "archival_wizard.py.j2",
                "form_template": "archival_wizard_form.xml.j2",
                "fields": [
                    {
                        "name": "days_threshold",
                        "type": "Integer",
                        "string": "Archive records older than (days)",
                        "default": 365,
                        "required": True,
                    },
                ],
                "transient_max_hours": 1.0,
            })

            # Inject archival cron into spec cron_jobs
            new_cron_jobs.append({
                "name": f"Archive Old {model.get('description', model['name'])} Records",
                "model_name": model["name"],
                "method": "_cron_archive_old_records",
                "interval_number": 1,
                "interval_type": "days",
                "doall": False,
            })

        # Preserve existing override flags from Phase 29 (OR, don't replace)
        if model.get("has_create_override"):
            new_model["has_create_override"] = True
        if model.get("has_write_override"):
            new_model["has_write_override"] = True

        # Preserve existing override_sources from Phase 29 (union via merge)
        existing_sources = model.get("override_sources")
        if existing_sources:
            for key, sources in existing_sources.items():
                for source in sources:
                    merge_override_source(new_model, key, source)

        new_models.append(new_model)

    return {**spec, "models": new_models, "wizards": new_wizards, "cron_jobs": new_cron_jobs}
