"""Pydantic models for AngeVoice admin APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, create_model

from ..admin_config_schema import ADMIN_CONFIG_FIELDS


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdminModelAction(StrictModel):
    include_current: bool = True
    force: bool = False


class AdminSingleModelAction(StrictModel):
    force: bool = False


class AdminSwitchModelAction(StrictModel):
    model: str
    unload_previous: bool | None = None
    load: bool = True


class AdminApiKeyAction(StrictModel):
    rotate: bool = True


class AdminProfileAction(StrictModel):
    profile: str


# Keep the admin editable field list single-sourced in admin_config_schema.
# Pydantic still rejects unknown fields here; value ranges/types are enforced by
# validate_admin_config_values() so adding a new editable field only touches one
# schema table.
AdminConfigPatch = create_model(
    "AdminConfigPatch",
    __base__=StrictModel,
    **{key: (Any | None, None) for key in ADMIN_CONFIG_FIELDS.keys()},
)
