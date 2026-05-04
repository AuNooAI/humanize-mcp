"""JSON-backed tone preset CRUD with atomic writes."""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional


PRESET_FIELDS = (
    "name",
    "tone",
    "paragraph_style",
    "length_mode",
    "formality",
    "instructions",
    "example_input",
    "example_output",
)


class PresetError(RuntimeError):
    """Raised on preset CRUD failures (not found, invalid input, IO errors)."""


def _resolve_path(path: str | Path) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


class PresetStore:
    def __init__(self, path: str | Path) -> None:
        self.path = _resolve_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"presets": []})

    def _read(self) -> dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {"presets": []}
        except json.JSONDecodeError as e:
            raise PresetError(f"presets file is not valid JSON: {self.path} ({e})") from e
        if not isinstance(data, dict) or not isinstance(data.get("presets"), list):
            raise PresetError(f"presets file is malformed (missing top-level 'presets' list): {self.path}")
        return data

    def _write(self, data: dict[str, Any]) -> None:
        # Atomic write: write to a temp file in the same dir, then rename.
        tmp_fd, tmp_path = tempfile.mkstemp(prefix=".presets-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=False)
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def list(self) -> list[dict[str, Any]]:
        return self._read()["presets"]

    def get(self, preset_id: str) -> dict[str, Any]:
        for p in self._read()["presets"]:
            if p.get("id") == preset_id:
                return p
        raise PresetError(f"preset not found: {preset_id!r}")

    def create(self, *, name: str, **fields: Any) -> dict[str, Any]:
        if not name or not name.strip():
            raise PresetError("preset name is required")
        data = self._read()
        preset: dict[str, Any] = {
            "id": uuid.uuid4().hex[:12],
            "name": name.strip(),
            "created_at": int(time.time()),
        }
        for key in PRESET_FIELDS:
            if key == "name":
                continue
            if key in fields and fields[key] is not None:
                preset[key] = fields[key]
        data["presets"].append(preset)
        self._write(data)
        return preset

    def update(self, preset_id: str, **fields: Any) -> dict[str, Any]:
        data = self._read()
        for p in data["presets"]:
            if p.get("id") == preset_id:
                for key in PRESET_FIELDS:
                    if key in fields and fields[key] is not None:
                        p[key] = fields[key]
                p["updated_at"] = int(time.time())
                self._write(data)
                return p
        raise PresetError(f"preset not found: {preset_id!r}")

    def delete(self, preset_id: str) -> None:
        data = self._read()
        new_presets = [p for p in data["presets"] if p.get("id") != preset_id]
        if len(new_presets) == len(data["presets"]):
            raise PresetError(f"preset not found: {preset_id!r}")
        data["presets"] = new_presets
        self._write(data)
