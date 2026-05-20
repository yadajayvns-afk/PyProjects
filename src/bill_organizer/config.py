"""Load and validate the YAML config files into typed Pydantic objects.

Malformed config fails fast here with a clear message rather than blowing up
deep inside the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

# Repo root = two levels up from this file (src/bill_organizer/config.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = _REPO_ROOT / "config"

FieldType = Literal["string", "date", "decimal"]


class FieldSpec(BaseModel):
    """One field the extraction agent should pull from a bill."""

    name: str
    label: str
    type: FieldType
    required: bool = False
    description: str = ""


class FieldSettings(BaseModel):
    date_output_format: str = "%Y-%m-%d"
    currency_symbol_strip: list[str] = Field(default_factory=list)


class FieldsConfig(BaseModel):
    fields: list[FieldSpec]
    settings: FieldSettings = Field(default_factory=FieldSettings)


class CategoryRule(BaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)


class MatchSettings(BaseModel):
    case_sensitive: bool = False
    fields_searched: list[str] = Field(default_factory=lambda: ["vendor", "raw_text"])


class CategoriesConfig(BaseModel):
    default_category: str = "Uncategorized"
    match: MatchSettings = Field(default_factory=MatchSettings)
    categories: list[CategoryRule] = Field(default_factory=list)


class ConfigError(RuntimeError):
    """Raised when a config file is missing or malformed."""


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Config file {path} must contain a YAML mapping at the top level.")
    return data


def load_fields_config(config_dir: Path = DEFAULT_CONFIG_DIR) -> FieldsConfig:
    """Load and validate config/fields.yaml."""
    data = _load_yaml(config_dir / "fields.yaml")
    try:
        cfg = FieldsConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid fields.yaml:\n{exc}") from exc
    if not cfg.fields:
        raise ConfigError("fields.yaml must define at least one field.")
    return cfg


def load_categories_config(config_dir: Path = DEFAULT_CONFIG_DIR) -> CategoriesConfig:
    """Load and validate config/categories.yaml."""
    data = _load_yaml(config_dir / "categories.yaml")
    try:
        return CategoriesConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid categories.yaml:\n{exc}") from exc


# Define what is explicitly public (Like public access modifiers in C#)
__all__ = ["FieldsConfig", "load_fields_config", "CategoriesConfig", "load_categories_config"]