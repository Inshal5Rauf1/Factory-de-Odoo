"""Archival and partitioning strategy preprocessor.

FLAW-16: Extends production.py's basic archival with:
- Date-based partitioning metadata
- Retention tiers (hot/warm/cold)
- Auto-purge after retention period
- Archive destination configuration

Registered at order=52 (after production_patterns@50).

Pure function -- never mutates input spec.
"""

from __future__ import annotations

import logging
from typing import Any

from odoo_gen_utils.preprocessors._registry import register_preprocessor
from odoo_gen_utils.utils.copy import deep_copy_model

logger = logging.getLogger(__name__)

# Default retention tier configuration
_DEFAULT_RETENTION_TIERS = {
    "hot": {"days": 90, "description": "Active records (< 90 days)"},
    "warm": {"days": 365, "description": "Recent records (90-365 days)"},
    "cold": {"days": 365 * 7, "description": "Archived records (> 1 year)"},
}


def _build_archival_cron(
    model: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Build a cron job spec for automatic archival."""
    model_name = model["name"]
    description = model.get("description", model_name)
    return {
        "name": f"Auto-Archive Old {description} Records",
        "model_name": model_name,
        "method": "_cron_archive_old_records",
        "interval_number": policy.get("cron_interval_days", 1),
        "interval_type": "days",
        "doall": False,
    }


def _build_purge_cron(
    model: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Build a cron job spec for purging expired archived records."""
    model_name = model["name"]
    description = model.get("description", model_name)
    return {
        "name": f"Purge Expired {description} Records",
        "model_name": model_name,
        "method": "_cron_purge_expired_records",
        "interval_number": policy.get("purge_interval_days", 7),
        "interval_type": "days",
        "doall": False,
    }


@register_preprocessor(order=52, name="archival_strategy")
def _process_archival_strategy(spec: dict[str, Any]) -> dict[str, Any]:
    """Enrich models with archival/partitioning strategy metadata.

    For each model with an ``archival_policy`` block:
    1. Configures retention tiers (hot/warm/cold)
    2. Sets partition field (date field for partitioning hints)
    3. Configures archive destination (active=False vs separate table)
    4. Generates archival + purge cron jobs
    5. Injects ``archived_date`` field if archive destination is active-based

    Returns a new spec dict. Pure function.
    """
    models = spec.get("models", [])
    has_archival_policy = any(m.get("archival_policy") for m in models)
    if not has_archival_policy:
        return spec

    new_models = []
    new_cron_jobs = list(spec.get("cron_jobs", []))

    for model in models:
        policy = model.get("archival_policy")
        if not policy:
            new_models.append(model)
            continue

        new_model = deep_copy_model(model)

        # Retention tiers
        tiers = policy.get("retention_tiers", _DEFAULT_RETENTION_TIERS)
        new_model["archival_retention_tiers"] = tiers

        # Partition field (which date field to partition by)
        partition_field = policy.get("partition_field", "create_date")
        new_model["archival_partition_field"] = partition_field

        # Archive destination: "active" (set active=False) or "table" (separate model)
        destination = policy.get("destination", "active")
        new_model["archival_destination"] = destination

        # Retention days before archive
        archive_after_days = policy.get("archive_after_days", 365)
        new_model["archival_archive_after_days"] = archive_after_days

        # Purge days (delete archived records after this many days)
        purge_after_days = policy.get("purge_after_days")
        if purge_after_days:
            new_model["archival_purge_after_days"] = purge_after_days

        # Batch size for archival operations
        new_model["archival_batch_size"] = policy.get("batch_size", 500)

        # Inject archived_date field for tracking when record was archived
        field_names = {f["name"] for f in new_model.get("fields", [])}
        if "archived_date" not in field_names:
            new_model["fields"] = [
                *new_model["fields"],
                {
                    "name": "archived_date",
                    "type": "Datetime",
                    "string": "Archived Date",
                    "readonly": True,
                    "index": True,
                },
            ]

        # Inject active field if destination is "active" and not present
        if destination == "active" and "active" not in field_names:
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

        new_model["has_archival_policy"] = True

        # Generate cron jobs
        new_cron_jobs.append(_build_archival_cron(model, policy))
        if purge_after_days:
            new_cron_jobs.append(_build_purge_cron(model, policy))

        new_models.append(new_model)

    return {
        **spec,
        "models": new_models,
        "cron_jobs": new_cron_jobs,
    }
