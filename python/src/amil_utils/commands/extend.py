"""Business logic for the ``extend-module`` CLI command.

Pure Python -- no Click dependency.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any


def execute_extend_module(
    module_name: str,
    repo: str,
    output_dir: str,
    *,
    spec_file: str | None = None,
    branch: str = "19.0",
) -> dict[str, Any]:
    """Clone an OCA module and set up a companion extension module.

    Returns a result dict with keys:
        - cloned_path: str
        - companion_path: str
        - analysis: object -- ModuleAnalysis dataclass
        - analysis_dict: dict -- serialisable analysis
        - analysis_text: str -- formatted text
        - spec_saved: bool
        - needs_auth: bool
        - error: str | None
    """
    from amil_utils.search import get_github_token
    from amil_utils.search.analyzer import analyze_module, format_analysis_text
    from amil_utils.search.fork import clone_oca_module, setup_companion_dir

    result: dict[str, Any] = {
        "cloned_path": "",
        "companion_path": "",
        "analysis": None,
        "analysis_dict": {},
        "analysis_text": "",
        "spec_saved": False,
        "needs_auth": False,
        "error": None,
    }

    token = get_github_token()
    if not token:
        result["needs_auth"] = True
        return result

    out_path = Path(output_dir).resolve()

    try:
        cloned_path = clone_oca_module(repo, module_name, out_path, branch=branch)
    except Exception as exc:
        result["error"] = f"Error cloning module: {exc}"
        return result

    result["cloned_path"] = str(cloned_path)

    try:
        analysis = analyze_module(cloned_path)
    except FileNotFoundError as exc:
        result["error"] = f"Error analyzing module: {exc}"
        return result

    result["analysis"] = analysis
    result["analysis_text"] = format_analysis_text(analysis)

    # Build serialisable dict
    d = dataclasses.asdict(analysis)
    for k in ("model_names", "security_groups", "data_files"):
        d[k] = list(getattr(analysis, k))
    for m, v in d["model_fields"].items():
        d["model_fields"][m] = list(v)
    for m, v in d["view_types"].items():
        d["view_types"][m] = list(v)
    result["analysis_dict"] = d

    companion_path = setup_companion_dir(cloned_path)
    result["companion_path"] = str(companion_path)

    if spec_file:
        sp = Path(spec_file).resolve()
        content = sp.read_text(encoding="utf-8")
        (companion_path / "spec.json").write_text(content, encoding="utf-8")
        sp.write_text(content, encoding="utf-8")
        result["spec_saved"] = True

    return result
