from pathlib import Path

from ta_pipeline.app_config import AppConfig
from ta_pipeline.storage.output_sync import finalize_outputs


def _config(storage_root: Path) -> AppConfig:
    return AppConfig(
        storage_root=storage_root,
        runs_root=storage_root / "runs",
        base_url="http://127.0.0.1:8000/v1",
        model_id="model",
        model_api_key="key",
    )


def test_finalize_outputs_writes_local_marker(tmp_path):
    local_root = tmp_path / "local"
    run_root = local_root / "runs" / "2026-04-16T00-00-00Z"
    run_root.mkdir(parents=True)
    (run_root / "result.txt").write_text("ok", encoding="utf-8")

    summary = finalize_outputs(_config(local_root), run_root)
    latest_marker = local_root / "runs" / "latest_run.json"

    assert summary["local_run_root"] == run_root
    assert summary["local_latest_marker"] == latest_marker
    assert latest_marker.exists()
    assert str(run_root) in latest_marker.read_text(encoding="utf-8")
