"""Inline environment verifier for Odoo module generation.

Checks model inheritance, relational field targets, field override type mismatches,
and view field references against the live Odoo instance via OdooClient. Non-blocking:
all errors return VerificationWarning objects, never raise.

Exports:
    EnvironmentVerifier  -- main verifier class
    VerificationWarning  -- immutable warning dataclass
    build_verifier_from_env  -- factory that reads ODOO_URL from environment
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from odoo_gen_utils.validation.types import Result

if TYPE_CHECKING:
    from odoo_gen_utils.mcp.odoo_client import OdooClient

logger = logging.getLogger("odoo-gen.verifier")

# Standard Odoo mixins always present when 'mail' module is installed.
# Skip inheritance checks for these to avoid spurious warnings on base-only instances.
_ALWAYS_PRESENT_MIXINS: frozenset[str] = frozenset({
    "mail.thread",
    "mail.activity.mixin",
})


@dataclass(frozen=True)
class VerificationWarning:
    """One mismatch found during inline environment verification.

    Attributes:
        check_type: Category of check. One of:
            'model_inherit'      -- _inherit base model not found in Odoo
            'field_comodel'      -- relational field comodel_name not found
            'field_override'     -- override field missing or wrong ttype in Odoo
            'view_field'         -- view references a field not on the model
            'view_inherit_target'-- inherited view target model has no views
        subject: The item being checked (model name, field name, "model.field").
        message: Human-readable description of the mismatch.
        suggestion: Optional correction hint.
    """

    check_type: str
    subject: str
    message: str
    suggestion: str = ""


class EnvironmentVerifier:
    """Verifies spec declarations against the live Odoo instance.

    Pass client=None or omit to get a no-op verifier (all methods return []).
    All exceptions from OdooClient are caught; never raises.

    Usage:
        verifier = EnvironmentVerifier(client)  # client may be None
        warnings = verifier.verify_model_spec(model_dict)
        warnings += verifier.verify_view_spec(model_name, field_names)
    """

    def __init__(self, client: "OdooClient | None" = None) -> None:
        self._client = client

    def verify_model_spec(self, model: dict) -> Result[list[VerificationWarning]]:
        """Verify _inherit base models, relational comodel targets, and field overrides.

        Args:
            model: Single model dict from spec['models'].

        Returns:
            Result.ok(warnings) on success, Result.fail(message) on MCP client error.
        """
        if self._client is None:
            return Result.ok([])
        try:
            warnings: list[VerificationWarning] = []
            warnings.extend(self._check_inherit(model))
            warnings.extend(self._check_relational_comodels(model))
            warnings.extend(self._check_field_overrides(model))
            return Result.ok(warnings)
        except Exception as exc:
            logger.warning("MCP-03 verification error: %s", exc)
            return Result.fail(f"MCP-03 verification error: {exc}")

    def verify_view_spec(
        self,
        model_name: str,
        field_names: list[str],
        inherited_view_target: str | None = None,
    ) -> Result[list[VerificationWarning]]:
        """Verify view field references against live model schema.

        Args:
            model_name: Technical model name the view is for.
            field_names: List of field names referenced in the view XML.
            inherited_view_target: Optional view model name to verify exists.

        Returns:
            Result.ok(warnings) on success, Result.fail(message) on MCP client error.
        """
        if self._client is None:
            return Result.ok([])
        try:
            warnings: list[VerificationWarning] = []
            warnings.extend(self._check_view_fields(model_name, field_names))
            if inherited_view_target:
                warnings.extend(self._check_view_target(inherited_view_target))
            return Result.ok(warnings)
        except Exception as exc:
            logger.warning("MCP-04 verification error: %s", exc)
            return Result.fail(f"MCP-04 verification error: {exc}")

    def _check_inherit(self, model: dict) -> list[VerificationWarning]:
        """Check that _inherit base models exist in the live Odoo instance."""
        inherit = model.get("inherit")
        if not inherit:
            return []
        # inherit can be a string or a list
        inherits = [inherit] if isinstance(inherit, str) else list(inherit)
        warnings: list[VerificationWarning] = []
        for base_model in inherits:
            if base_model in _ALWAYS_PRESENT_MIXINS:
                continue
            result = self._client.search_read(
                "ir.model",
                [["model", "=", base_model]],
                ["model"],
                limit=1,
            )
            if not result:
                warnings.append(VerificationWarning(
                    check_type="model_inherit",
                    subject=base_model,
                    message=(
                        f"Base model '{base_model}' not found in live Odoo instance. "
                        f"Ensure the module that defines '{base_model}' is installed."
                    ),
                    suggestion=(
                        f"Add the module that provides '{base_model}' to `depends` "
                        f"in __manifest__.py and install it in the dev instance."
                    ),
                ))
            else:
                logger.info("MCP-03 _inherit PASS: %s", base_model)
        return warnings

    def _check_relational_comodels(self, model: dict) -> list[VerificationWarning]:
        """Check that relational field comodel_name targets exist."""
        checked: set[str] = set()
        warnings: list[VerificationWarning] = []
        relational_types = frozenset({"Many2one", "One2many", "Many2many"})
        for f in model.get("fields", []):
            if f.get("type") not in relational_types:
                continue
            comodel = f.get("comodel_name")
            if not comodel or comodel in checked:
                continue
            checked.add(comodel)
            result = self._client.search_read(
                "ir.model",
                [["model", "=", comodel]],
                ["model"],
                limit=1,
            )
            if not result:
                warnings.append(VerificationWarning(
                    check_type="field_comodel",
                    subject=f"{model['name']}.{f['name']}",
                    message=(
                        f"Relational field '{f['name']}' targets '{comodel}' "
                        f"which was not found in the live Odoo instance."
                    ),
                    suggestion=(
                        f"Verify the module providing '{comodel}' is listed in "
                        f"`depends` and installed in the dev instance."
                    ),
                ))
            else:
                logger.info("MCP-03 comodel PASS: %s.%s -> %s", model["name"], f["name"], comodel)
        return warnings

    def _check_field_overrides(self, model: dict) -> list[VerificationWarning]:
        """Check that override fields exist in Odoo with matching ttype.

        MCP-03 criterion #3: For each field with `override: True`, query
        ir.model.fields. If the field is missing, emit a warning. If ttype
        does not match the spec type, emit a warning.
        """
        warnings: list[VerificationWarning] = []
        model_name = model.get("name", "")
        for f in model.get("fields", []):
            if not f.get("override"):
                continue
            field_name = f.get("name", "")
            spec_type = f.get("type", "").lower()
            result = self._client.search_read(
                "ir.model.fields",
                [["model", "=", model_name], ["name", "=", field_name]],
                ["name", "ttype"],
                limit=1,
            )
            if not result:
                warnings.append(VerificationWarning(
                    check_type="field_override",
                    subject=f"{model_name}.{field_name}",
                    message=(
                        f"Field '{field_name}' not found on '{model_name}' in Odoo. "
                        f"Cannot override a non-existent field."
                    ),
                    suggestion=(
                        f"Check that '{field_name}' is defined on '{model_name}' in Odoo. "
                        f"Ensure the required module is installed."
                    ),
                ))
            else:
                odoo_ttype = result[0]["ttype"].lower()
                if odoo_ttype != spec_type:
                    warnings.append(VerificationWarning(
                        check_type="field_override",
                        subject=f"{model_name}.{field_name}",
                        message=(
                            f"Field '{field_name}' type mismatch: "
                            f"Odoo has '{odoo_ttype}', spec has '{spec_type}'."
                        ),
                        suggestion=(
                            f"Change the spec type to '{odoo_ttype}' to match Odoo, "
                            f"or remove the `override` flag if this is a new field."
                        ),
                    ))
                else:
                    logger.info(
                        "MCP-03 field_override PASS: %s.%s ttype=%s",
                        model_name, field_name, odoo_ttype,
                    )
        return warnings

    def _check_view_fields(
        self,
        model_name: str,
        field_names: list[str],
    ) -> list[VerificationWarning]:
        """Check that field names referenced in views exist on the model."""
        if not field_names:
            return []
        real_data = self._client.search_read(
            "ir.model.fields",
            [["model", "=", model_name]],
            ["name"],
        )
        real_names = {r["name"] for r in real_data}
        if not real_names:
            # Model not yet in Odoo (new model being generated) -- skip silently.
            return []
        warnings: list[VerificationWarning] = []
        for name in field_names:
            if name not in real_names:
                warnings.append(VerificationWarning(
                    check_type="view_field",
                    subject=f"{model_name}.{name}",
                    message=(
                        f"View references field '{name}' on model '{model_name}' "
                        f"but that field was not found in the live Odoo instance."
                    ),
                    suggestion=(
                        f"Check that '{name}' is defined in the model spec "
                        f"and that the field exists in Odoo (correct spelling, correct model)."
                    ),
                ))
            else:
                logger.info("MCP-04 view field PASS: %s.%s", model_name, name)
        return warnings

    def _check_view_target(self, target_model: str) -> list[VerificationWarning]:
        """Check that an inherited view target model has views in ir.ui.view."""
        result = self._client.search_read(
            "ir.ui.view",
            [["model", "=", target_model]],
            ["name"],
            limit=1,
        )
        if not result:
            return [VerificationWarning(
                check_type="view_inherit_target",
                subject=target_model,
                message=(
                    f"Inherited view target '{target_model}' has no views "
                    f"in the live Odoo instance."
                ),
                suggestion=(
                    f"Ensure the module providing views for '{target_model}' is installed."
                ),
            )]
        return []


def build_verifier_from_env() -> EnvironmentVerifier:
    """Build an EnvironmentVerifier from environment variables.

    Returns an EnvironmentVerifier with a connected OdooClient when ODOO_URL
    is set, or an EnvironmentVerifier with no client (no-op) when ODOO_URL
    is absent or when client construction fails.

    Environment variables read:
        ODOO_URL      -- Odoo instance URL (required to enable verification)
        ODOO_DB       -- database name (default: 'odoo_dev')
        ODOO_USER     -- username (default: 'admin')
        ODOO_API_KEY  -- API key / password (default: 'admin')
    """
    url = os.environ.get("ODOO_URL")
    if not url:
        return EnvironmentVerifier(client=None)

    from odoo_gen_utils.mcp.odoo_client import OdooClient, OdooConfig

    config = OdooConfig(
        url=url,
        db=os.environ.get("ODOO_DB", "odoo_dev"),
        username=os.environ.get("ODOO_USER", ""),
        api_key=os.environ.get("ODOO_API_KEY", ""),
    )
    if not config.username or not config.api_key:
        logger.warning(
            "ODOO_USER and ODOO_API_KEY not set; environment verification disabled."
        )
        return EnvironmentVerifier(client=None)
    try:
        client = OdooClient(config)
        return EnvironmentVerifier(client=client)
    except Exception as exc:
        logger.warning("Failed to create OdooClient for verification (degrading): %s", exc)
        return EnvironmentVerifier(client=None)
