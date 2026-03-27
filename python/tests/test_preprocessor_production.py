"""Tests for the production_patterns preprocessor."""

from __future__ import annotations

from typing import Any

import pytest

from amil_utils.preprocessors.production import _process_production_patterns


def _make_spec(
    models: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal spec dict."""
    return {"module_name": "test_mod", "models": models or [], **kwargs}


def _make_model(
    name: str = "test.model",
    fields: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a minimal model dict."""
    return {"name": name, "fields": fields or [], **kwargs}


class TestProcessProductionPatterns:
    """Tests for _process_production_patterns."""

    # --- Bulk ---

    def test_bulk_enrichment(self):
        """bulk:true sets is_bulk and override_sources."""
        model = _make_model(bulk=True)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        assert result is not spec
        rm = result["models"][0]
        assert rm["is_bulk"] is True
        assert rm["has_create_override"] is True
        assert "bulk" in rm["override_sources"]["create"]

    # --- Cacheable ---

    def test_cacheable_enrichment(self):
        """cacheable:true sets is_cacheable, override_sources for create+write."""
        model = _make_model(cacheable=True)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert rm["is_cacheable"] is True
        assert rm["needs_tools"] is True
        assert rm["has_create_override"] is True
        assert rm["has_write_override"] is True
        assert "cache" in rm["override_sources"]["create"]
        assert "cache" in rm["override_sources"]["write"]

    def test_cacheable_explicit_cache_key(self):
        """cache_key sets cache_lookup_field."""
        model = _make_model(cacheable=True, cache_key="code")
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert rm["cache_lookup_field"] == "code"

    def test_cacheable_auto_lookup_unique_char(self):
        """Without cache_key, first unique Char field is used."""
        fields = [
            {"name": "ref", "type": "Char", "unique": True},
            {"name": "name", "type": "Char"},
        ]
        model = _make_model(cacheable=True, fields=fields)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert rm["cache_lookup_field"] == "ref"

    def test_cacheable_fallback_to_name(self):
        """Without cache_key and no unique Char, falls back to 'name'."""
        fields = [
            {"name": "title", "type": "Char"},
            {"name": "count", "type": "Integer"},
        ]
        model = _make_model(cacheable=True, fields=fields)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert rm["cache_lookup_field"] == "name"

    # --- Archival ---

    def test_archival_enrichment(self):
        """archival:true sets is_archival with default batch_size and days."""
        model = _make_model(archival=True)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert rm["is_archival"] is True
        assert rm["archival_batch_size"] == 100
        assert rm["archival_days"] == 365

    def test_archival_custom_values(self):
        """archival respects custom batch_size and days."""
        model = _make_model(
            archival=True,
            archival_batch_size=50,
            archival_days=180,
        )
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert rm["archival_batch_size"] == 50
        assert rm["archival_days"] == 180

    def test_archival_injects_active_field(self):
        """archival injects an 'active' Boolean field if not present."""
        fields = [{"name": "name", "type": "Char"}]
        model = _make_model(archival=True, fields=fields)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rf = result["models"][0]["fields"]
        active_fields = [f for f in rf if f["name"] == "active"]
        assert len(active_fields) == 1
        af = active_fields[0]
        assert af["type"] == "Boolean"
        assert af["default"] is True
        assert af["index"] is True

    def test_archival_does_not_duplicate_active_field(self):
        """archival does not inject 'active' if already present."""
        fields = [
            {"name": "name", "type": "Char"},
            {"name": "active", "type": "Boolean", "default": True},
        ]
        model = _make_model(archival=True, fields=fields)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rf = result["models"][0]["fields"]
        active_fields = [f for f in rf if f["name"] == "active"]
        assert len(active_fields) == 1

    def test_archival_wizard_injected(self):
        """archival adds an archive wizard to spec wizards."""
        model = _make_model(name="test.item", archival=True)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        wizards = result["wizards"]
        assert len(wizards) == 1
        wiz = wizards[0]
        assert wiz["name"] == "test.item.archive.wizard"
        assert wiz["target_model"] == "test.item"
        assert wiz["template"] == "archival_wizard.py.j2"
        assert len(wiz["fields"]) == 1
        assert wiz["fields"][0]["name"] == "days_threshold"

    def test_archival_cron_job_injected(self):
        """archival adds a cron job to spec cron_jobs."""
        model = _make_model(name="test.item", archival=True)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        crons = result["cron_jobs"]
        assert len(crons) == 1
        cron = crons[0]
        assert cron["model_name"] == "test.item"
        assert cron["method"] == "_cron_archive_old_records"
        assert cron["interval_number"] == 1
        assert cron["interval_type"] == "days"

    def test_archival_cron_uses_description(self):
        """archival cron name uses model description when available."""
        model = _make_model(
            name="test.item",
            description="Test Item",
            archival=True,
        )
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        cron = result["cron_jobs"][0]
        assert cron["name"] == "Archive Old Test Item Records"

    # --- Combined patterns ---

    def test_bulk_and_cacheable_combined(self):
        """bulk + cacheable both enrich the same model."""
        model = _make_model(bulk=True, cacheable=True, cache_key="code")
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert rm["is_bulk"] is True
        assert rm["is_cacheable"] is True
        assert "bulk" in rm["override_sources"]["create"]
        assert "cache" in rm["override_sources"]["create"]
        assert "cache" in rm["override_sources"]["write"]

    def test_all_three_patterns_combined(self):
        """bulk + cacheable + archival all work together."""
        model = _make_model(bulk=True, cacheable=True, archival=True, cache_key="code")
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert rm["is_bulk"] is True
        assert rm["is_cacheable"] is True
        assert rm["is_archival"] is True
        assert len(result["wizards"]) == 1
        assert len(result["cron_jobs"]) == 1

    # --- Edge cases ---

    def test_empty_spec_no_models(self):
        """Empty models list returns spec unchanged."""
        spec = _make_spec(models=[])

        result = _process_production_patterns(spec)

        assert result is spec

    def test_model_without_patterns(self):
        """Model with no production patterns passes through."""
        model = _make_model()
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert "is_bulk" not in rm
        assert "is_cacheable" not in rm
        assert "is_archival" not in rm

    def test_preserves_existing_override_sources(self):
        """Existing override_sources from Phase 29 are preserved (unioned)."""
        model = _make_model(
            bulk=True,
            has_create_override=True,
            override_sources={"create": {"constraints"}},
        )
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        sources = rm["override_sources"]["create"]
        assert "constraints" in sources
        assert "bulk" in sources

    def test_preserves_existing_write_override(self):
        """Existing has_write_override is preserved."""
        model = _make_model(cacheable=True, has_write_override=True)
        spec = _make_spec(models=[model])

        result = _process_production_patterns(spec)

        rm = result["models"][0]
        assert rm["has_write_override"] is True

    def test_immutability_input_not_mutated(self):
        """Input spec and model dicts are not mutated."""
        fields = [{"name": "name", "type": "Char"}]
        model = _make_model(bulk=True, fields=fields)
        spec = _make_spec(models=[model])
        original_keys = set(model.keys())

        _process_production_patterns(spec)

        # Original model should not gain new keys
        assert set(model.keys()) == original_keys
        assert "is_bulk" not in model

    def test_existing_wizards_preserved(self):
        """Existing wizards in spec are preserved alongside new ones."""
        existing_wizard = {"name": "existing.wizard", "target_model": "test.other"}
        model = _make_model(name="test.item", archival=True)
        spec = _make_spec(models=[model], wizards=[existing_wizard])

        result = _process_production_patterns(spec)

        assert len(result["wizards"]) == 2
        names = [w["name"] for w in result["wizards"]]
        assert "existing.wizard" in names
        assert "test.item.archive.wizard" in names

    def test_existing_cron_jobs_preserved(self):
        """Existing cron_jobs in spec are preserved alongside new ones."""
        existing_cron = {"name": "Existing Cron", "model_name": "test.other"}
        model = _make_model(name="test.item", archival=True)
        spec = _make_spec(models=[model], cron_jobs=[existing_cron])

        result = _process_production_patterns(spec)

        assert len(result["cron_jobs"]) == 2
        names = [c["name"] for c in result["cron_jobs"]]
        assert "Existing Cron" in names

    def test_multiple_models_independent_enrichment(self):
        """Multiple models with different patterns are enriched independently."""
        m1 = _make_model(name="test.a", bulk=True)
        m2 = _make_model(name="test.b", archival=True)
        m3 = _make_model(name="test.c")
        spec = _make_spec(models=[m1, m2, m3])

        result = _process_production_patterns(spec)

        assert result["models"][0]["is_bulk"] is True
        assert "is_archival" not in result["models"][0]
        assert result["models"][1]["is_archival"] is True
        assert "is_bulk" not in result["models"][1]
        assert "is_bulk" not in result["models"][2]
        assert "is_archival" not in result["models"][2]
