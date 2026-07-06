import json
from pathlib import Path

from content_pipeline.utils import sort_articles_deterministically
from ta_pipeline.pipeline.cluster_analysis import enrich_cluster_score, get_most_recent_incident_at


def get_top_clusters(
    run_root: Path,
    *,
    require_ta_eligible: bool = False,
    limit: int = 1,
) -> list[dict]:
    sources_dir = run_root / "sources"
    clusters = []

    for cluster_dir in sorted(sources_dir.iterdir()):
        if not cluster_dir.is_dir() or not cluster_dir.name.startswith("cluster_"):
            continue

        score_file = cluster_dir / "cluster-score.json"
        articles_file = cluster_dir / "articles.json"

        if not score_file.exists() or not articles_file.exists():
            continue

        with open(score_file, "r", encoding="utf-8") as f:
            score = json.load(f)

        with open(articles_file, "r", encoding="utf-8") as f:
            articles = json.load(f)

        enriched_score = enrich_cluster_score(score, articles)
        most_recent_incident_at, _ = get_most_recent_incident_at(enriched_score, articles)

        clusters.append({
            "cluster_id": cluster_dir.name,
            "score": enriched_score,
            "articles": articles,
            "most_recent_incident_at": most_recent_incident_at,
        })

    if not clusters:
        raise Exception("No valid clusters found")

    if require_ta_eligible:
        clusters = [cluster for cluster in clusters if cluster["score"].get("is_ta_eligible", False)]

    if not clusters:
        raise ValueError("No TA-eligible clusters found")

    clusters.sort(
        key=lambda x: (
            x["score"].get("overall_importance_score", 0),
            x["most_recent_incident_at"].timestamp() if x["most_recent_incident_at"] else float("-inf"),
            x["score"].get("severity_score", 0),
            x["score"].get("urgency_score", 0),
            x["cluster_id"],
        ),
        reverse=True,
    )

    return clusters[:limit]


def get_top_cluster(run_root: Path, *, require_ta_eligible: bool = False) -> dict:
    return get_top_clusters(
        run_root,
        require_ta_eligible=require_ta_eligible,
        limit=1,
    )[0]


def select_top_articles(articles: list, max_articles: int = 2) -> list:
    selected = []

    for article in sort_articles_deterministically(articles):
        selected.append({
            "title": article.get("title", ""),
            "source": article.get("source", ""),
            "published": article.get("published", ""),
            "summary": (article.get("summary") or "")[:500],
            "full_text": (article.get("full_text") or "")[:4000],
            "cves": article.get("cves", []),
            "url": article.get("url") or article.get("link", ""),
        })

        if len(selected) >= max_articles:
            break

    return selected
