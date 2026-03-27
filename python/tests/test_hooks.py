"""Unit tests for amil_utils.hooks module.

Tests cover: RenderHook Protocol, LoggingHook, ManifestHook, CheckpointPause,
notify_hooks helper, and zero-overhead when hooks list is empty.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# TestRenderHookProtocol
# ---------------------------------------------------------------------------


class TestRenderHookProtocol:
    """RenderHook Protocol structural typing tests."""

    def test_class_with_all_methods_is_instance(self):
        """A class implementing all three methods is isinstance(RenderHook)."""
        from amil_utils.hooks import RenderHook

        class GoodHook:
            def on_preprocess_complete(self, module_name, models, preprocessors_run):
                pass

            def on_stage_complete(self, module_name, stage_name, result, artifacts):
                pass

            def on_render_complete(self, module_name, manifest):
                pass

        assert isinstance(GoodHook(), RenderHook)

    def test_class_missing_method_is_not_instance(self):
        """A class missing a method is NOT isinstance(RenderHook)."""
        from amil_utils.hooks import RenderHook

        class BadHook:
            def on_preprocess_complete(self, module_name, models, preprocessors_run):
                pass

            def on_stage_complete(self, module_name, stage_name, result, artifacts):
                pass

            # Missing on_render_complete

        assert not isinstance(BadHook(), RenderHook)

    def test_runtime_checkable(self):
        """RenderHook is runtime_checkable."""
        from amil_utils.hooks import RenderHook

        # runtime_checkable protocols allow isinstance() checks
        assert hasattr(RenderHook, "__protocol_attrs__") or hasattr(
            RenderHook, "_is_runtime_protocol"
        )


# ---------------------------------------------------------------------------
# TestLoggingHook
# ---------------------------------------------------------------------------


class TestLoggingHook:
    """LoggingHook output tests."""

    def test_on_stage_complete_outputs_icon_and_name(self, capsys):
        """on_stage_complete with status='complete' outputs icon + stage name + duration."""
        from amil_utils.hooks import LoggingHook
        from amil_utils.manifest import StageResult

        hook = LoggingHook()
        result = StageResult(status="complete", duration_ms=42)
        hook.on_stage_complete("my_module", "models", result, ["models/foo.py"])

        captured = capsys.readouterr()
        assert "[OK]" in captured.out
        assert "models" in captured.out
        assert "42" in captured.out

    def test_on_stage_complete_failed_icon(self, capsys):
        """on_stage_complete with status='failed' uses [!!] icon."""
        from amil_utils.hooks import LoggingHook
        from amil_utils.manifest import StageResult

        hook = LoggingHook()
        result = StageResult(status="failed", error="Crash")
        hook.on_stage_complete("my_module", "views", result, [])

        captured = capsys.readouterr()
        assert "[!!]" in captured.out

    def test_on_stage_complete_skipped_icon(self, capsys):
        """on_stage_complete with status='skipped' uses [--] icon."""
        from amil_utils.hooks import LoggingHook
        from amil_utils.manifest import StageResult

        hook = LoggingHook()
        result = StageResult(status="skipped")
        hook.on_stage_complete("my_module", "views", result, [])

        captured = capsys.readouterr()
        assert "[--]" in captured.out

    def test_on_stage_complete_pending_icon(self, capsys):
        """on_stage_complete with status='pending' uses [..] icon."""
        from amil_utils.hooks import LoggingHook
        from amil_utils.manifest import StageResult

        hook = LoggingHook()
        result = StageResult(status="pending")
        hook.on_stage_complete("my_module", "views", result, [])

        captured = capsys.readouterr()
        assert "[..]" in captured.out

    def test_on_preprocess_complete_outputs_count(self, capsys):
        """on_preprocess_complete outputs preprocessor count."""
        from amil_utils.hooks import LoggingHook

        hook = LoggingHook()
        hook.on_preprocess_complete(
            "my_module", [{"name": "m1"}], ["normalize:10", "validate:20"]
        )

        captured = capsys.readouterr()
        assert "2" in captured.out
        assert "preprocessor" in captured.out.lower()

    def test_on_render_complete_outputs_summary(self, capsys):
        """on_render_complete outputs summary with file/line counts."""
        from amil_utils.hooks import LoggingHook
        from amil_utils.manifest import ArtifactInfo, GenerationManifest

        hook = LoggingHook()
        manifest = GenerationManifest(
            module="my_module",
            spec_sha256="abc",
            generated_at="2026-01-01T00:00:00Z",
            generator_version="0.1.0",
            artifacts=ArtifactInfo(total_files=10, total_lines=500),
        )
        hook.on_render_complete("my_module", manifest)

        captured = capsys.readouterr()
        assert "10" in captured.out
        assert "500" in captured.out

    def test_logging_hook_is_render_hook(self):
        """LoggingHook satisfies the RenderHook Protocol."""
        from amil_utils.hooks import LoggingHook, RenderHook

        assert isinstance(LoggingHook(), RenderHook)


# ---------------------------------------------------------------------------
# TestManifestHook
# ---------------------------------------------------------------------------


class TestManifestHook:
    """ManifestHook save_manifest tests."""

    def test_on_render_complete_calls_save_manifest(self, tmp_path: Path):
        """on_render_complete calls save_manifest with manifest and module_path."""
        from amil_utils.hooks import ManifestHook
        from amil_utils.manifest import GenerationManifest, MANIFEST_FILENAME

        hook = ManifestHook(module_path=tmp_path)
        manifest = GenerationManifest(
            module="test",
            spec_sha256="abc",
            generated_at="2026-01-01T00:00:00Z",
            generator_version="0.1.0",
        )
        hook.on_render_complete("test", manifest)

        # Verify manifest file was written
        assert (tmp_path / MANIFEST_FILENAME).exists()

    def test_on_preprocess_complete_is_noop(self):
        """on_preprocess_complete is a no-op (doesn't raise)."""
        from amil_utils.hooks import ManifestHook

        hook = ManifestHook(module_path=Path("/tmp"))
        # Should not raise
        hook.on_preprocess_complete("test", [{"name": "m1"}], ["normalize:10"])

    def test_on_stage_complete_is_noop(self):
        """on_stage_complete is a no-op (doesn't raise)."""
        from amil_utils.hooks import ManifestHook
        from amil_utils.manifest import StageResult

        hook = ManifestHook(module_path=Path("/tmp"))
        result = StageResult(status="complete")
        # Should not raise
        hook.on_stage_complete("test", "models", result, [])

    def test_manifest_hook_is_render_hook(self):
        """ManifestHook satisfies the RenderHook Protocol."""
        from amil_utils.hooks import ManifestHook, RenderHook

        assert isinstance(ManifestHook(module_path=Path("/tmp")), RenderHook)

    def test_on_render_complete_raises_on_error(self, tmp_path: Path):
        """PIPE-06: on_render_complete now propagates errors (critical hook)."""
        from amil_utils.hooks import ManifestHook
        from amil_utils.manifest import GenerationManifest

        # Use a non-existent deeply nested path that can't be created
        hook = ManifestHook(module_path=tmp_path / "no" / "such" / "dir")
        manifest = GenerationManifest(
            module="test",
            spec_sha256="abc",
            generated_at="2026-01-01T00:00:00Z",
            generator_version="0.1.0",
        )
        # PIPE-06: Critical hooks must raise, not swallow
        with pytest.raises(Exception):
            hook.on_render_complete("test", manifest)


# ---------------------------------------------------------------------------
# TestCheckpointPause
# ---------------------------------------------------------------------------


class TestCheckpointPause:
    """CheckpointPause exception tests."""

    def test_is_exception_subclass(self):
        """CheckpointPause is a subclass of Exception."""
        from amil_utils.hooks import CheckpointPause

        assert issubclass(CheckpointPause, Exception)

    def test_stores_attributes(self):
        """CheckpointPause stores stage_name, module_name, message."""
        from amil_utils.hooks import CheckpointPause

        exc = CheckpointPause(
            module_name="my_module",
            stage_name="models",
            message="Review the models",
        )
        assert exc.module_name == "my_module"
        assert exc.stage_name == "models"
        assert exc.message == "Review the models"

    def test_default_message(self):
        """CheckpointPause generates a default message if none provided."""
        from amil_utils.hooks import CheckpointPause

        exc = CheckpointPause(module_name="my_module", stage_name="security")
        assert "security" in exc.message
        assert "my_module" in exc.message

    def test_can_be_raised_and_caught(self):
        """CheckpointPause can be raised and caught."""
        from amil_utils.hooks import CheckpointPause

        with pytest.raises(CheckpointPause) as exc_info:
            raise CheckpointPause(
                module_name="test", stage_name="models", message="pause!"
            )

        assert exc_info.value.stage_name == "models"


# ---------------------------------------------------------------------------
# TestZeroOverhead
# ---------------------------------------------------------------------------


class TestZeroOverhead:
    """When hooks is None/empty, no hook methods are called."""

    def test_notify_hooks_none_is_noop(self):
        """notify_hooks with None hooks is a no-op."""
        from amil_utils.hooks import notify_hooks

        # Should not raise
        notify_hooks(None, "on_stage_complete", "mod", "stage", MagicMock(), [])

    def test_notify_hooks_empty_list_is_noop(self):
        """notify_hooks with empty list is a no-op."""
        from amil_utils.hooks import notify_hooks

        notify_hooks([], "on_stage_complete", "mod", "stage", MagicMock(), [])

    def test_notify_hooks_calls_all_hooks(self):
        """notify_hooks calls the method on all hooks."""
        from amil_utils.hooks import notify_hooks

        hook1 = MagicMock()
        hook2 = MagicMock()
        notify_hooks([hook1, hook2], "on_stage_complete", "mod", "stage")

        hook1.on_stage_complete.assert_called_once_with("mod", "stage")
        hook2.on_stage_complete.assert_called_once_with("mod", "stage")

    def test_notify_hooks_isolates_non_critical_exceptions(self):
        """notify_hooks isolates exceptions from non-critical hooks."""
        from amil_utils.hooks import notify_hooks

        hook1 = MagicMock()
        hook1.on_preprocess_complete.side_effect = RuntimeError("boom")
        hook2 = MagicMock()

        # Non-critical method: should not raise; hook2 still gets called
        notify_hooks([hook1, hook2], "on_preprocess_complete", "mod", [], [])
        hook2.on_preprocess_complete.assert_called_once()

    def test_notify_hooks_escalates_critical_exceptions(self):
        """PIPE-06: notify_hooks re-raises exceptions from critical hooks."""
        from amil_utils.hooks import notify_hooks

        hook = MagicMock()
        hook.on_stage_complete.side_effect = RuntimeError("critical failure")

        # Critical method: must propagate
        with pytest.raises(RuntimeError, match="critical failure"):
            notify_hooks([hook], "on_stage_complete", "mod", "stage")

    def test_notify_hooks_escalates_on_render_complete(self):
        """PIPE-06: notify_hooks re-raises on_render_complete failures."""
        from amil_utils.hooks import notify_hooks

        hook = MagicMock()
        hook.on_render_complete.side_effect = OSError("disk full")

        with pytest.raises(OSError, match="disk full"):
            notify_hooks([hook], "on_render_complete", "mod")

    def test_notify_hooks_propagates_checkpoint_pause(self):
        """notify_hooks propagates CheckpointPause (intentional pause)."""
        from amil_utils.hooks import CheckpointPause, notify_hooks

        hook = MagicMock()
        hook.on_stage_complete.side_effect = CheckpointPause(
            module_name="test", stage_name="models"
        )

        with pytest.raises(CheckpointPause):
            notify_hooks([hook], "on_stage_complete", "mod", "stage")


# ---------------------------------------------------------------------------
# TestHookExceptionIsolation (Integration)
# ---------------------------------------------------------------------------


class TestHookExceptionIsolation:
    """Non-critical hook exceptions do NOT kill the pipeline; critical ones DO."""

    def test_value_error_in_non_critical_hook_does_not_kill_pipeline(self, tmp_path, monkeypatch):
        """A hook raising ValueError in on_preprocess_complete does NOT crash render_module."""
        from unittest.mock import MagicMock

        from amil_utils.hooks import RenderHook
        from amil_utils.renderer import STAGE_NAMES, render_module
        from amil_utils.validation.types import Result

        module_name = "test_mod"
        spec = {"module_name": module_name, "models": [], "odoo_version": "17.0"}
        module_dir = tmp_path / module_name
        module_dir.mkdir(parents=True)

        # Mock all stage renderers
        for stage in STAGE_NAMES:
            fn_name = f"render_{stage}"
            mock_fn = MagicMock(return_value=Result(success=True, data=[]))
            monkeypatch.setattr(f"amil_utils.renderer.{fn_name}", mock_fn)

        monkeypatch.setattr("amil_utils.renderer.validate_spec", lambda s: MagicMock(model_dump=lambda **kw: spec))
        monkeypatch.setattr("amil_utils.renderer._validate_no_cycles", lambda s: None)
        monkeypatch.setattr("amil_utils.renderer.run_preprocessors", lambda s: s)
        monkeypatch.setattr("amil_utils.renderer.build_context7_from_env", lambda: MagicMock())
        monkeypatch.setattr("amil_utils.renderer.context7_enrich", lambda *a, **kw: {})

        # PIPE-06: Only non-critical hooks are isolated. Critical hooks propagate.
        class NonCriticalBadHook:
            def on_preprocess_complete(self, module_name, models, preprocessors_run):
                raise ValueError("I am broken!")

            def on_stage_complete(self, module_name, stage_name, result, artifacts):
                pass  # Critical — must not raise

            def on_render_complete(self, module_name, manifest):
                pass  # Critical — must not raise

        files, warnings = render_module(
            spec, tmp_path / "templates", tmp_path,
            no_context7=True,
            hooks=[NonCriticalBadHook()],
        )
        # Pipeline should complete without error
        assert isinstance(files, list)

    def test_checkpoint_pause_propagates_through_pipeline(self, tmp_path, monkeypatch):
        """CheckpointPause from a hook DOES propagate through render_module."""
        from unittest.mock import MagicMock

        from amil_utils.hooks import CheckpointPause
        from amil_utils.renderer import STAGE_NAMES, render_module
        from amil_utils.validation.types import Result

        module_name = "test_mod"
        spec = {"module_name": module_name, "models": [], "odoo_version": "17.0"}
        module_dir = tmp_path / module_name
        module_dir.mkdir(parents=True)

        # Mock all stage renderers
        for stage in STAGE_NAMES:
            fn_name = f"render_{stage}"
            mock_fn = MagicMock(return_value=Result(success=True, data=[]))
            monkeypatch.setattr(f"amil_utils.renderer.{fn_name}", mock_fn)

        monkeypatch.setattr("amil_utils.renderer.validate_spec", lambda s: MagicMock(model_dump=lambda **kw: spec))
        monkeypatch.setattr("amil_utils.renderer._validate_no_cycles", lambda s: None)
        monkeypatch.setattr("amil_utils.renderer.run_preprocessors", lambda s: s)
        monkeypatch.setattr("amil_utils.renderer.build_context7_from_env", lambda: MagicMock())
        monkeypatch.setattr("amil_utils.renderer.context7_enrich", lambda *a, **kw: {})

        # Create a hook that raises CheckpointPause on first stage
        class PauseHook:
            def on_preprocess_complete(self, module_name, models, preprocessors_run):
                pass

            def on_stage_complete(self, module_name, stage_name, result, artifacts):
                raise CheckpointPause(module_name=module_name, stage_name=stage_name, message="Pause!")

            def on_render_complete(self, module_name, manifest):
                pass

        with pytest.raises(CheckpointPause):
            render_module(
                spec, tmp_path / "templates", tmp_path,
                no_context7=True,
                hooks=[PauseHook()],
            )


# ---------------------------------------------------------------------------
# TestZeroOverheadIntegration
# ---------------------------------------------------------------------------


class TestZeroOverheadIntegration:
    """render_module() with hooks=None calls no hook methods."""

    def test_render_module_hooks_none_no_notify_hooks_calls(self, tmp_path, monkeypatch):
        """render_module() with hooks=None never calls notify_hooks with non-None hooks."""
        from unittest.mock import MagicMock

        from amil_utils.renderer import STAGE_NAMES, render_module
        from amil_utils.validation.types import Result

        module_name = "test_mod"
        spec = {"module_name": module_name, "models": [], "odoo_version": "17.0"}
        module_dir = tmp_path / module_name
        module_dir.mkdir(parents=True)

        for stage in STAGE_NAMES:
            fn_name = f"render_{stage}"
            mock_fn = MagicMock(return_value=Result(success=True, data=[]))
            monkeypatch.setattr(f"amil_utils.renderer.{fn_name}", mock_fn)

        monkeypatch.setattr("amil_utils.renderer.validate_spec", lambda s: MagicMock(model_dump=lambda **kw: spec))
        monkeypatch.setattr("amil_utils.renderer._validate_no_cycles", lambda s: None)
        monkeypatch.setattr("amil_utils.renderer.run_preprocessors", lambda s: s)
        monkeypatch.setattr("amil_utils.renderer.build_context7_from_env", lambda: MagicMock())
        monkeypatch.setattr("amil_utils.renderer.context7_enrich", lambda *a, **kw: {})

        # Patch notify_hooks to track calls
        original_calls = []

        def spy_notify_hooks(hooks, method, *args, **kwargs):
            original_calls.append((hooks, method))
            # Original behavior: if hooks is None, return immediately
            if not hooks:
                return

        monkeypatch.setattr("amil_utils.renderer.notify_hooks", spy_notify_hooks)

        files, warnings = render_module(
            spec, tmp_path / "templates", tmp_path,
            no_context7=True,
            hooks=None,
        )

        # All calls to notify_hooks should have hooks=None
        for hooks_arg, method in original_calls:
            assert hooks_arg is None, f"notify_hooks called with non-None hooks for method {method}"
