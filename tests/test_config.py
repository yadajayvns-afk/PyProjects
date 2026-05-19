"""Tests for config loading and validation."""

from __future__ import annotations

import pytest

from bill_organizer.config import (
    ConfigError,
    load_categories_config,
    load_fields_config,
)


def test_real_config_loads():
    """The shipped config/ files load and validate."""
    fields = load_fields_config()
    cats = load_categories_config()
    assert {f.name for f in fields.fields} >= {"bill_number", "bill_date", "amount", "vendor"}
    assert any(c.name == "Food" for c in cats.categories)
    assert cats.default_category == "Uncategorized"


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_fields_config(config_dir=tmp_path)


def test_malformed_yaml_raises(tmp_path):
    (tmp_path / "fields.yaml").write_text("fields: [: not valid", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_fields_config(config_dir=tmp_path)


def test_empty_fields_list_raises(tmp_path):
    (tmp_path / "fields.yaml").write_text("fields: []", encoding="utf-8")
    with pytest.raises(ConfigError, match="at least one field"):
        load_fields_config(config_dir=tmp_path)


def test_bad_field_type_raises(tmp_path):
    (tmp_path / "fields.yaml").write_text(
        "fields:\n  - name: x\n    label: X\n    type: banana\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="Invalid fields.yaml"):
        load_fields_config(config_dir=tmp_path)
