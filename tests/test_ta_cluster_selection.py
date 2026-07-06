import json
from datetime import datetime, timedelta, timezone

from ta_pipeline.pipeline.cluster_analysis import evaluate_ta_article_eligibility
from ta_pipeline.pipeline.selection import get_top_cluster, get_top_clusters


def _published(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%b %d, %Y")


def _article(
    *,
    title: str,
    published: str,
    summary: str,
    cves: list[str] | None = None,
    full_text: str = "",
) -> dict:
    return {
        "source": "Test Feed",
        "title": title,
        "published": published,
        "summary": summary,
        "full_text": full_text or summary,
        "cves": cves or [],
        "url": "https://example.test/article",
    }


def _write_cluster(run_root, cluster_id: str, score: dict, articles: list[dict]) -> None:
    cluster_dir = run_root / "sources" / cluster_id
    cluster_dir.mkdir(parents=True)
    (cluster_dir / "cluster-score.json").write_text(
        json.dumps(score, indent=2),
        encoding="utf-8",
    )
    (cluster_dir / "articles.json").write_text(
        json.dumps(articles, indent=2),
        encoding="utf-8",
    )


def test_get_top_cluster_prioritizes_importance_before_recency(tmp_path):
    run_root = tmp_path / "run"

    _write_cluster(
        run_root,
        "cluster_0",
        {
            "cluster_id": "cluster_0",
            "overall_importance_score": 9,
            "severity_score": 8,
            "urgency_score": 8,
            "business_impact_score": 8,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="Active exploitation of CVE-2026-1111 in Acme Gateway",
                published=_published(5),
                summary="The vulnerability is actively exploited in the wild and a patch is available.",
                cves=["CVE-2026-1111"],
            )
        ],
    )

    _write_cluster(
        run_root,
        "cluster_1",
        {
            "cluster_id": "cluster_1",
            "overall_importance_score": 8,
            "severity_score": 9,
            "urgency_score": 9,
            "business_impact_score": 8,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="Active exploitation of CVE-2026-2222 in Beta VPN",
                published=_published(1),
                summary="CISA says the flaw is exploited in the wild and a fix is now available.",
                cves=["CVE-2026-2222"],
            )
        ],
    )

    selected = get_top_cluster(run_root, require_ta_eligible=True)

    assert selected["cluster_id"] == "cluster_0"


def test_get_top_cluster_uses_most_recent_incident_as_secondary_tiebreaker(tmp_path):
    run_root = tmp_path / "run"

    _write_cluster(
        run_root,
        "cluster_0",
        {
            "cluster_id": "cluster_0",
            "overall_importance_score": 9,
            "severity_score": 8,
            "urgency_score": 8,
            "business_impact_score": 8,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="Active exploitation of CVE-2026-3001 in Alpha Appliance",
                published=_published(6),
                summary="The zero-day is actively exploited and defenders should patch immediately.",
                cves=["CVE-2026-3001"],
            )
        ],
    )

    _write_cluster(
        run_root,
        "cluster_1",
        {
            "cluster_id": "cluster_1",
            "overall_importance_score": 9,
            "severity_score": 7,
            "urgency_score": 7,
            "business_impact_score": 8,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="Emergency patch released for CVE-2026-3002 in Bravo Portal",
                published=_published(1),
                summary="The issue was exploited in the wild before the emergency patch shipped.",
                cves=["CVE-2026-3002"],
            )
        ],
    )

    selected = get_top_cluster(run_root, require_ta_eligible=True)

    assert selected["cluster_id"] == "cluster_1"


def test_get_top_cluster_skips_clusters_that_fail_ta_eligibility(tmp_path):
    run_root = tmp_path / "run"

    _write_cluster(
        run_root,
        "cluster_0",
        {
            "cluster_id": "cluster_0",
            "overall_importance_score": 10,
            "severity_score": 10,
            "urgency_score": 10,
            "business_impact_score": 9,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="ThreatsDay Bulletin: Defender 0-Day, Excel RCE and 15 More Stories",
                published=_published(1),
                summary="This weekly bulletin covers multiple vendors, patch news, campaigns, and more stories.",
                cves=[
                    "CVE-2026-1001",
                    "CVE-2026-1002",
                    "CVE-2026-1003",
                    "CVE-2026-1004",
                    "CVE-2026-1005",
                ],
            )
        ],
    )

    _write_cluster(
        run_root,
        "cluster_1",
        {
            "cluster_id": "cluster_1",
            "overall_importance_score": 8,
            "severity_score": 8,
            "urgency_score": 8,
            "business_impact_score": 8,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="CISA warns of active exploitation of CVE-2026-4001 in Delta Gateway",
                published=_published(2),
                summary="The vulnerability is actively exploited in the wild and customers should apply the patch immediately.",
                cves=["CVE-2026-4001"],
            )
        ],
    )

    selected = get_top_cluster(run_root, require_ta_eligible=True)

    assert selected["cluster_id"] == "cluster_1"


def test_get_top_clusters_returns_top_three_in_rank_order(tmp_path):
    run_root = tmp_path / "run"

    _write_cluster(
        run_root,
        "cluster_0",
        {
            "cluster_id": "cluster_0",
            "overall_importance_score": 7,
            "severity_score": 7,
            "urgency_score": 7,
            "business_impact_score": 7,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="Patch released for CVE-2026-7000",
                published=_published(3),
                summary="The issue was recently patched after active exploitation.",
                cves=["CVE-2026-7000"],
            )
        ],
    )
    _write_cluster(
        run_root,
        "cluster_1",
        {
            "cluster_id": "cluster_1",
            "overall_importance_score": 10,
            "severity_score": 9,
            "urgency_score": 9,
            "business_impact_score": 9,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="Active exploitation of CVE-2026-7001",
                published=_published(2),
                summary="The flaw is exploited in the wild and customers should patch immediately.",
                cves=["CVE-2026-7001"],
            )
        ],
    )
    _write_cluster(
        run_root,
        "cluster_2",
        {
            "cluster_id": "cluster_2",
            "overall_importance_score": 9,
            "severity_score": 8,
            "urgency_score": 8,
            "business_impact_score": 8,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="Campaign deploys FrostyRAT against healthcare",
                published=_published(1),
                summary="Researchers observed an active campaign delivering FrostyRAT.",
            )
        ],
    )
    _write_cluster(
        run_root,
        "cluster_3",
        {
            "cluster_id": "cluster_3",
            "overall_importance_score": 8,
            "severity_score": 8,
            "urgency_score": 7,
            "business_impact_score": 7,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="CISA adds CVE-2026-7003 to KEV",
                published=_published(4),
                summary="CISA says the vulnerability is exploited in the wild.",
                cves=["CVE-2026-7003"],
            )
        ],
    )

    selected = get_top_clusters(run_root, require_ta_eligible=True, limit=3)

    assert [cluster["cluster_id"] for cluster in selected] == [
        "cluster_1",
        "cluster_2",
        "cluster_3",
    ]


def test_get_top_clusters_returns_all_available_when_fewer_than_three_exist(tmp_path):
    run_root = tmp_path / "run"

    _write_cluster(
        run_root,
        "cluster_0",
        {
            "cluster_id": "cluster_0",
            "overall_importance_score": 9,
            "severity_score": 8,
            "urgency_score": 8,
            "business_impact_score": 8,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="Emergency patch for CVE-2026-7100",
                published=_published(1),
                summary="Emergency patch released after active exploitation in the wild.",
                cves=["CVE-2026-7100"],
            )
        ],
    )
    _write_cluster(
        run_root,
        "cluster_1",
        {
            "cluster_id": "cluster_1",
            "overall_importance_score": 8,
            "severity_score": 7,
            "urgency_score": 7,
            "business_impact_score": 7,
            "is_ta_eligible": True,
        },
        [
            _article(
                title="Active phishing campaign delivers WinterRAT",
                published=_published(2),
                summary="Researchers observed an active phishing campaign hitting finance teams.",
            )
        ],
    )

    selected = get_top_clusters(run_root, require_ta_eligible=True, limit=3)

    assert [cluster["cluster_id"] for cluster in selected] == [
        "cluster_0",
        "cluster_1",
    ]


def test_evaluate_ta_article_eligibility_rejects_broad_or_mixed_clusters():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    score = {"overall_importance_score": 9}
    articles = [
        _article(
            title="ThreatsDay Bulletin: Defender 0-Day, Excel RCE and 15 More Stories",
            published="Apr 16, 2026",
            summary="This roundup covers multiple vendors, several campaigns, and a broad patch bulletin.",
            cves=[
                "CVE-2026-1001",
                "CVE-2026-1002",
                "CVE-2026-1003",
                "CVE-2026-1004",
                "CVE-2026-1005",
            ],
        )
    ]

    is_eligible, reason = evaluate_ta_article_eligibility(score, articles, now=now)

    assert is_eligible is False
    assert (
        "broad" in reason.lower()
        or "mixes unrelated" in reason.lower()
        or "roundup" in reason.lower()
        or "bulletin" in reason.lower()
    )


def test_evaluate_ta_article_eligibility_accepts_related_multi_issue_clusters():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    score = {"overall_importance_score": 9}
    articles = [
        _article(
            title="Cisco Identity Services flaws CVE-2026-8101, CVE-2026-8102, CVE-2026-8103",
            published="Apr 16, 2026",
            summary=(
                "Cisco Identity Services Engine vulnerabilities are actively exploited in the wild "
                "and customers should patch immediately."
            ),
            cves=["CVE-2026-8101", "CVE-2026-8102", "CVE-2026-8103"],
        ),
        _article(
            title="More Cisco Identity Services vulnerabilities CVE-2026-8104 and CVE-2026-8105",
            published="Apr 15, 2026",
            summary=(
                "Additional Cisco Identity Services Engine flaws were recently patched after "
                "active exploitation."
            ),
            cves=["CVE-2026-8104", "CVE-2026-8105"],
        ),
    ]

    is_eligible, reason = evaluate_ta_article_eligibility(score, articles, now=now)

    assert is_eligible is True
    assert "focused" in reason.lower()


def test_evaluate_ta_article_eligibility_rejects_old_incidents():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    score = {"overall_importance_score": 9}
    articles = [
        _article(
            title="Active exploitation of CVE-2026-5001 in Legacy Gateway",
            published="Feb 10, 2026",
            summary="The vulnerability was actively exploited in the wild and a patch was released.",
            cves=["CVE-2026-5001"],
        )
    ]

    is_eligible, reason = evaluate_ta_article_eligibility(score, articles, now=now)

    assert is_eligible is False
    assert "too old" in reason.lower()


def test_evaluate_ta_article_eligibility_rejects_non_actionable_clusters():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    score = {"overall_importance_score": 8}
    articles = [
        _article(
            title="[Webinar] Find and Eliminate Orphaned Non-Human Identities",
            published="Apr 16, 2026",
            summary="Join our webinar for a practical playbook on managing non-human identities.",
        )
    ]

    is_eligible, reason = evaluate_ta_article_eligibility(score, articles, now=now)

    assert is_eligible is False
    assert "informational" in reason.lower() or "promotional" in reason.lower()


def test_evaluate_ta_article_eligibility_accepts_recent_focused_campaign():
    now = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    score = {"overall_importance_score": 8}
    articles = [
        _article(
            title="APT29 phishing campaign deploys FrostyRAT against finance teams",
            published="Apr 16, 2026",
            summary="Researchers observed an active phishing campaign delivering FrostyRAT to finance targets.",
        )
    ]

    is_eligible, reason = evaluate_ta_article_eligibility(score, articles, now=now)

    assert is_eligible is True
    assert "focused" in reason.lower()
