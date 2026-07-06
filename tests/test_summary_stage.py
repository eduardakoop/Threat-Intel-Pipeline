import json
from types import SimpleNamespace

from ta_pipeline.models.agent import AgentSpec
from ta_pipeline.pipeline.summary_stage import run_executive_summary_and_ta_prep


def _cluster(cluster_id: str) -> dict:
    return {
        "cluster_id": cluster_id,
        "score": {
            "cluster_id": cluster_id,
            "overall_importance_score": 9,
            "most_recent_incident": "2026-04-16T00:00:00+00:00",
        },
        "articles": [
            {
                "title": f"Article for {cluster_id}",
                "source": "Feed",
                "published": "Apr 16, 2026",
                "summary": f"Summary for {cluster_id}",
                "full_text": f"Full text for {cluster_id}",
                "cves": ["CVE-2026-9999"],
                "url": f"https://example.test/{cluster_id}",
            }
        ],
    }


def test_run_executive_summary_and_ta_prep_generates_outputs_for_top_three_clusters(
    tmp_path,
    monkeypatch,
):
    run_root = tmp_path / "run"
    requested_cluster_ids = []

    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.get_top_clusters",
        lambda run_root, require_ta_eligible, limit: [
            _cluster("cluster_1"),
            _cluster("cluster_2"),
            _cluster("cluster_3"),
        ],
    )
    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.build_executive_writer_agent",
        lambda: AgentSpec("writer", "goal", "backstory"),
    )
    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.build_ta_prep_agent",
        lambda: AgentSpec("prep", "goal", "backstory"),
    )

    def fake_execute_json_task(client, config, task):
        cluster_id = task.user_prompt.split("ID: ", 1)[1].split(".", 1)[0]
        requested_cluster_ids.append((task.task_name, cluster_id))
        if task.task_name == "executive_summary":
            return {
                "cluster_id": cluster_id,
                "headline": f"Headline {cluster_id}",
                "executive_summary": f"Summary {cluster_id}",
                "why_it_matters": f"Why {cluster_id}",
                "key_takeaways": [f"Takeaway {cluster_id}"],
                "priority": "high",
            }

        return {
            "cluster_id": cluster_id,
            "title": f"TA {cluster_id}",
            "subtitle": f"Subtitle {cluster_id}",
            "introduction": f"Intro {cluster_id}",
            "threat_landscape_targets": f"Targets {cluster_id}",
            "ttps": [f"TTP {cluster_id}"],
            "iocs": [f"IOC {cluster_id}"],
            "defensive_strategies_best_practices": [f"Defense {cluster_id}"],
            "references": [f"Reference {cluster_id} - https://example.test/{cluster_id}"],
        }

    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.execute_json_task",
        fake_execute_json_task,
    )
    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.format_ta_brief",
        lambda payload: f"formatted {payload['cluster_id']}",
    )

    results = run_executive_summary_and_ta_prep(
        client=object(),
        config=SimpleNamespace(),
        run_root=run_root,
    )

    assert results == {
        "cluster_results": [
            {
                "cluster_id": "cluster_1",
                "executive_summary": {
                    "cluster_id": "cluster_1",
                    "headline": "Headline cluster_1",
                    "executive_summary": "Summary cluster_1",
                    "why_it_matters": "Why cluster_1",
                    "key_takeaways": ["Takeaway cluster_1"],
                    "priority": "high",
                },
                "ta_brief": "formatted cluster_1",
            },
            {
                "cluster_id": "cluster_2",
                "executive_summary": {
                    "cluster_id": "cluster_2",
                    "headline": "Headline cluster_2",
                    "executive_summary": "Summary cluster_2",
                    "why_it_matters": "Why cluster_2",
                    "key_takeaways": ["Takeaway cluster_2"],
                    "priority": "high",
                },
                "ta_brief": "formatted cluster_2",
            },
            {
                "cluster_id": "cluster_3",
                "executive_summary": {
                    "cluster_id": "cluster_3",
                    "headline": "Headline cluster_3",
                    "executive_summary": "Summary cluster_3",
                    "why_it_matters": "Why cluster_3",
                    "key_takeaways": ["Takeaway cluster_3"],
                    "priority": "high",
                },
                "ta_brief": "formatted cluster_3",
            },
        ]
    }
    assert requested_cluster_ids == [
        ("executive_summary", "cluster_1"),
        ("ta_prep", "cluster_1"),
        ("executive_summary", "cluster_2"),
        ("ta_prep", "cluster_2"),
        ("executive_summary", "cluster_3"),
        ("ta_prep", "cluster_3"),
    ]

    for cluster_id in ("cluster_1", "cluster_2", "cluster_3"):
        summary_file = run_root / "executive-summaries" / f"summary_{cluster_id}.json"
        ta_file = run_root / "TA-briefs" / f"TA-brief_{cluster_id}.txt"
        assert summary_file.exists()
        assert ta_file.exists()
        assert json.loads(summary_file.read_text(encoding="utf-8"))["cluster_id"] == cluster_id
        assert ta_file.read_text(encoding="utf-8") == f"formatted {cluster_id}"


def test_run_executive_summary_and_ta_prep_handles_fewer_than_three_clusters(
    tmp_path,
    monkeypatch,
):
    run_root = tmp_path / "run"

    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.get_top_clusters",
        lambda run_root, require_ta_eligible, limit: [
            _cluster("cluster_5"),
            _cluster("cluster_6"),
        ],
    )
    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.build_executive_writer_agent",
        lambda: AgentSpec("writer", "goal", "backstory"),
    )
    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.build_ta_prep_agent",
        lambda: AgentSpec("prep", "goal", "backstory"),
    )
    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.execute_json_task",
        lambda client, config, task: (
            {
                "cluster_id": task.user_prompt.split("ID: ", 1)[1].split(".", 1)[0],
                "headline": "Headline",
                "executive_summary": "Summary",
                "why_it_matters": "Why",
                "key_takeaways": ["Takeaway"],
                "priority": "high",
            }
            if task.task_name == "executive_summary"
            else {
                "cluster_id": task.user_prompt.split("ID: ", 1)[1].split(".", 1)[0],
                "title": "TA",
                "subtitle": "Subtitle",
                "introduction": "Intro",
                "threat_landscape_targets": "Targets",
                "ttps": ["TTP"],
                "iocs": ["IOC"],
                "defensive_strategies_best_practices": ["Defense"],
                "references": ["Reference - https://example.test"],
            }
        ),
    )
    monkeypatch.setattr(
        "ta_pipeline.pipeline.summary_stage.format_ta_brief",
        lambda payload: f"formatted {payload['cluster_id']}",
    )

    results = run_executive_summary_and_ta_prep(
        client=object(),
        config=SimpleNamespace(),
        run_root=run_root,
    )

    assert [item["cluster_id"] for item in results["cluster_results"]] == [
        "cluster_5",
        "cluster_6",
    ]
    assert not (run_root / "executive-summaries" / "summary_cluster_7.json").exists()
    assert not (run_root / "TA-briefs" / "TA-brief_cluster_7.txt").exists()
