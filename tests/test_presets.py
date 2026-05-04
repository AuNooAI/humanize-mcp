"""Round-trip CRUD for the JSON-backed PresetStore."""

import json

import pytest

from humanize_mcp.presets import PresetError, PresetStore


@pytest.fixture
def store(tmp_path):
    return PresetStore(tmp_path / "presets.json")


def test_create_and_list(store):
    p = store.create(name="Casual blog", tone="friendly", length_mode="concise")
    assert p["id"]
    assert p["name"] == "Casual blog"
    assert p["tone"] == "friendly"

    listed = store.list()
    assert len(listed) == 1
    assert listed[0]["id"] == p["id"]


def test_get_round_trip(store):
    p = store.create(name="Punchy", instructions="Cut all filler.")
    fetched = store.get(p["id"])
    assert fetched["instructions"] == "Cut all filler."


def test_get_missing_raises(store):
    with pytest.raises(PresetError):
        store.get("does-not-exist")


def test_update_changes_only_passed_fields(store):
    p = store.create(name="Punchy", tone="terse", length_mode="concise")
    updated = store.update(p["id"], tone="dry")
    assert updated["tone"] == "dry"
    assert updated["length_mode"] == "concise"  # unchanged
    assert "updated_at" in updated


def test_update_missing_raises(store):
    with pytest.raises(PresetError):
        store.update("missing", tone="x")


def test_delete_removes_entry(store):
    p = store.create(name="Temp")
    store.delete(p["id"])
    assert store.list() == []


def test_delete_missing_raises(store):
    with pytest.raises(PresetError):
        store.delete("missing")


def test_create_requires_name(store):
    with pytest.raises(PresetError):
        store.create(name="   ")


def test_atomic_write_leaves_valid_json(store, tmp_path):
    store.create(name="A")
    store.create(name="B")
    # File should be valid JSON with both presets.
    data = json.loads((tmp_path / "presets.json").read_text())
    assert {p["name"] for p in data["presets"]} == {"A", "B"}


def test_persists_across_instances(tmp_path):
    path = tmp_path / "presets.json"
    PresetStore(path).create(name="Persistent")
    fresh = PresetStore(path)
    assert any(p["name"] == "Persistent" for p in fresh.list())
