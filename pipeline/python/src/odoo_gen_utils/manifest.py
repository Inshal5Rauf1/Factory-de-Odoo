"""Generation manifest models and persistence for the Odoo module pipeline.

Provides Pydantic v2 models (GenerationManifest, StageResult, ArtifactEntry,
PreprocessingInfo, ArtifactInfo, ValidationInfo), the GenerationSession
dataclass for tracking stage results during a render, and save/load helpers.

These are **leaf modules** -- no imports from renderer.py to prevent circular
dependencies.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from odoo_gen_utils import __version__

logger = logging.getLogger("odoo-gen.manifest")

MANIFEST_FILENAME = ".odoo-gen-manifest.json"


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class StageResult(BaseModel):
    """Result of a single generation stage."""

    model_config = ConfigDict(protected_namespaces=())

    status: Literal["complete", "skipped", "failed", "pending"] = "pending"
    duration_ms: int = 0
    reason: str | None = None
    error: str | None = None
    artifacts: list[str] = []


class ArtifactEntry(BaseModel):
    """A generated file with its SHA256 checksum."""

    model_config = ConfigDict(protected_namespaces=())

    path: str
    sha256: str


class PreprocessingInfo(BaseModel):
    """Info about the preprocessing stage."""

    model_config = ConfigDict(protected_namespaces=())

    preprocessors_run: list[str] = []
    duration_ms: int = 0


class ArtifactInfo(BaseModel):
    """Aggregate artifact information."""

    model_config = ConfigDict(protected_namespaces=())

    files: list[ArtifactEntry] = []
    total_files: int = 0
    total_lines: int = 0


class ValidationInfo(BaseModel):
    """Results of semantic validation."""

    model_config = ConfigDict(protected_namespaces=())

    semantic_errors: int = 0
    semantic_warnings: int = 0
    duration_ms: int = 0


class GenerationManifest(BaseModel):
    """Full manifest describing a module generation run."""

    model_config = ConfigDict(protected_namespaces=())

    module: str
    spec_version: str = "1.0"
    spec_sha256: str
    generated_at: str
    odoo_version: str = "19.0"
    generator_version: str
    preprocessing: PreprocessingInfo = PreprocessingInfo()
    stages: dict[str, StageResult] = {}
    artifacts: ArtifactInfo = ArtifactInfo()
    validation: ValidationInfo | None = None
    models_registered: list[str] = []


# ---------------------------------------------------------------------------
# SHA256 Helpers
# ---------------------------------------------------------------------------


def compute_file_sha256(file_path: Path) -> str:
    """Return the SHA256 hex digest of a file's contents."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def compute_spec_sha256(spec: dict) -> str:
    """Return the SHA256 hex digest of a spec dict using canonical JSON.

    Key order and whitespace are normalized via ``sort_keys=True`` and
    compact separators so that logically identical specs produce the
    same hash.
    """
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_manifest(manifest: GenerationManifest, module_path: Path) -> Path:
    """Write *manifest* as JSON to ``module_path / .odoo-gen-manifest.json``.

    Uses ``exclude_none=True`` so that optional None fields are omitted.
    Returns the path to the written file.
    """
    manifest_file = module_path / MANIFEST_FILENAME
    data = manifest.model_dump(exclude_none=True)
    manifest_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    logger.info("Saved manifest for module '%s' to %s", manifest.module, manifest_file)
    return manifest_file


def load_manifest(module_path: Path) -> GenerationManifest | None:
    """Load a ``GenerationManifest`` from the JSON sidecar file.

    Returns ``None`` when the file is missing, empty, or contains invalid
    JSON -- a warning is logged but no exception is raised.
    """
    manifest_file = module_path / MANIFEST_FILENAME

    if not manifest_file.exists():
        return None

    raw = manifest_file.read_text(encoding="utf-8").strip()
    if not raw:
        logger.warning("Manifest file is empty: %s", manifest_file)
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse manifest file %s: %s", manifest_file, exc)
        return None

    try:
        manifest = GenerationManifest.model_validate(data)
        logger.info("Loaded manifest for module '%s' (generated %s)", manifest.module, manifest.generated_at)
        return manifest
    except Exception as exc:
        logger.warning("Invalid manifest structure in %s: %s", manifest_file, exc)
        return None


# ---------------------------------------------------------------------------
# GenerationSession
# ---------------------------------------------------------------------------


@dataclass
class GenerationSession:
    """Mutable session tracking stage results during a render.

    NOT frozen -- mutated as stages complete. Convert to an immutable
    ``GenerationManifest`` via ``to_manifest()`` when the render is done.
    """

    module_name: str
    spec_sha256: str
    odoo_version: str = "19.0"
    generator_version: str = __version__
    _stages: dict[str, StageResult] = field(default_factory=dict)
    _start_time_ns: int = field(default_factory=lambda: time.perf_counter_ns())

    def record_stage(self, name: str, result: StageResult) -> None:
        """Store a stage result (overwrites any previous result for the same stage)."""
        self._stages[name] = result
        logger.debug("Recorded stage '%s' with status '%s' for module '%s'", name, result.status, self.module_name)

    def is_stage_complete(self, name: str) -> bool:
        """Return True only if the named stage has status 'complete'."""
        stage = self._stages.get(name)
        if stage is None:
            return False
        return stage.status == "complete"

    def to_manifest(self, **kwargs) -> GenerationManifest:
        """Build a ``GenerationManifest`` from session state.

        Accepts override kwargs for ``preprocessing``, ``artifacts``,
        ``validation``, ``models_registered``, ``generated_at``.
        """
        generated_at = kwargs.pop(
            "generated_at",
            datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        logger.info("Building manifest for module '%s' with %d stage(s)", self.module_name, len(self._stages))
        return GenerationManifest(
            module=self.module_name,
            spec_sha256=self.spec_sha256,
            odoo_version=self.odoo_version,
            generator_version=self.generator_version,
            generated_at=generated_at,
            stages=dict(self._stages),
            **kwargs,
        )
