from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from heart_transplant.models import StructuralArtifact


def artifact_root() -> Path:
    configured = os.environ.get("HEART_TRANSPLANT_ARTIFACT_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[3] / ".heart-transplant" / "artifacts"


def persist_structural_artifact(artifact: StructuralArtifact) -> Path:
    target_dir = artifact_root() / f"{timestamp_slug()}__{artifact.artifact_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    write_json(target_dir / "structural-artifact.json", artifact.model_dump(mode="json"))
    return target_dir


def timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))
