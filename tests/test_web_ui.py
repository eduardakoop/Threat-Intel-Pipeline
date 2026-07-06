import json
from pathlib import Path
from zipfile import ZipFile

from ta_pipeline.app_config import AppConfig
from ta_pipeline.web_ui import create_app


def _config(storage_root: Path) -> AppConfig:
    return AppConfig(
        storage_root=storage_root,
        runs_root=storage_root / "runs",
        base_url="http://127.0.0.1:8000/v1",
        model_id="local-model",
        model_api_key="secret",
        security_enabled=False,
    )


def _write_run(storage_root: Path) -> str:
    run_id = "2026-04-17T18-11-55Z"
    run_root = storage_root / "runs" / run_id
    cluster_dir = run_root / "sources" / "cluster_7"
    cluster_dir.mkdir(parents=True)
    (run_root / "executive-summaries").mkdir()
    (run_root / "TA-briefs").mkdir()

    article = {
        "source": "Test Feed",
        "title": "Active exploitation of CVE-2026-1111 in Acme Gateway",
        "published": "Apr 17, 2026",
        "summary": "The flaw is exploited in the wild.",
        "url": "https://example.test/story",
        "cves": ["CVE-2026-1111"],
        "full_text": "Long source text",
    }
    (run_root / "sources" / "articles.json").write_text(
        json.dumps([article]),
        encoding="utf-8",
    )
    (cluster_dir / "articles.json").write_text(json.dumps([article]), encoding="utf-8")
    (cluster_dir / "cluster-score.json").write_text(
        json.dumps(
            {
                "cluster_id": "cluster_7",
                "overall_importance_score": 9,
                "severity_score": 9,
                "urgency_score": 8,
                "business_impact_score": 8,
                "is_ta_eligible": True,
                "ta_eligibility_reason": "Focused and actionable.",
            }
        ),
        encoding="utf-8",
    )
    (run_root / "executive-summaries" / "summary_cluster_7.json").write_text(
        json.dumps(
            {
                "cluster_id": "cluster_7",
                "headline": "Acme Gateway exploitation",
                "priority": "critical",
                "executive_summary": "Executive summary.",
                "why_it_matters": "Leadership impact.",
                "key_takeaways": ["Patch immediately."],
            }
        ),
        encoding="utf-8",
    )
    (run_root / "TA-briefs" / "TA-brief_cluster_7.txt").write_text(
        "1. Title\nAcme Gateway exploitation\n\n8. References\n- Test Feed - https://example.test/story",
        encoding="utf-8",
    )
    (storage_root / "runs" / "latest_run.json").write_text(
        json.dumps({"run_name": run_id, "run_root": str(run_root)}),
        encoding="utf-8",
    )
    return run_id


def test_web_ui_lists_runs_and_cluster_details(tmp_path):
    storage_root = tmp_path / "storage"
    run_id = _write_run(storage_root)
    app = create_app(_config(storage_root))

    client = app.test_client()
    runs_response = client.get("/api/runs")
    assert runs_response.status_code == 200
    runs_payload = runs_response.get_json()

    assert runs_payload["latest_run_id"] == run_id
    assert runs_payload["runs"][0]["run_label"] == "Apr 17, 2026 · 18:11 UTC"
    assert runs_payload["runs"][0]["cluster_count"] == 1
    assert runs_payload["runs"][0]["brief_count"] == 1

    detail_response = client.get(f"/api/runs/{run_id}")
    detail_payload = detail_response.get_json()
    assert detail_payload["clusters"][0]["cluster_id"] == "cluster_7"
    assert detail_payload["clusters"][0]["cluster_label"] == "Cluster 7"
    assert detail_payload["clusters"][0]["headline"] == "Acme Gateway exploitation"

    cluster_response = client.get(f"/api/runs/{run_id}/clusters/cluster_7")
    cluster_payload = cluster_response.get_json()
    assert cluster_payload["cluster_label"] == "Cluster 7"
    assert cluster_payload["score"]["overall_importance_score"] == 9
    assert cluster_payload["summary"]["priority"] == "critical"
    assert "Acme Gateway exploitation" in cluster_payload["ta_brief"]
    assert "full_text" not in cluster_payload["articles"][0]
    assert cluster_payload["articles"][0]["full_text_excerpt"] == "Long source text"


def test_web_ui_serves_cyberflorida_logo(tmp_path):
    app = create_app(_config(tmp_path / "storage"))

    response = app.test_client().get("/static/cyberfloridalogo.png")

    assert response.status_code == 200
    assert response.content_type == "image/png"
    assert response.data.startswith(b"\x89PNG")


def test_web_ui_downloads_run_zip(tmp_path):
    storage_root = tmp_path / "storage"
    run_id = _write_run(storage_root)
    app = create_app(_config(storage_root))

    response = app.test_client().get(f"/api/runs/{run_id}/download")

    assert response.status_code == 200
    zip_path = tmp_path / "run.zip"
    zip_path.write_bytes(response.data)
    with ZipFile(zip_path) as archive:
        assert f"{run_id}/TA-briefs/TA-brief_cluster_7.txt" in archive.namelist()
