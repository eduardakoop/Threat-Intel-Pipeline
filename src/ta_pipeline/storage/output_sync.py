from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ta_pipeline.app_config import AppConfig


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runs_root(base_root: Path) -> Path:
    return base_root / "runs"


def _write_latest_marker(
    base_root: Path,
    run_root: Path,
) -> Path:
    payload = {
        "updated_at": _timestamp(),
        "run_name": run_root.name,
        "run_root": str(run_root),
    }

    latest_file = _runs_root(base_root) / "latest_run.json"
    latest_file.parent.mkdir(parents=True, exist_ok=True)
    with open(latest_file, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
    return latest_file


def finalize_outputs(config: AppConfig, run_root: Path) -> dict:
    local_marker = _write_latest_marker(config.storage_root, run_root)

    return {
        "local_run_root": run_root,
        "local_latest_marker": local_marker,
    }
