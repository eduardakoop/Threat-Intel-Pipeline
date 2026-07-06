import json
from pathlib import Path

from openai import OpenAI

from ta_pipeline.app_config import AppConfig
from ta_pipeline.agents.scorer import build_scorer_agent
from ta_pipeline.llm.executor import execute_json_task
from ta_pipeline.pipeline.cluster_analysis import enrich_cluster_score
from ta_pipeline.tasks.scoring import build_scoring_task


def score_all_clusters(
    client: OpenAI,
    config: AppConfig,
    run_root: Path,
) -> None:
    print("\n=== STAGE 2: Scoring Clusters ===")

    sources_dir = run_root / "sources"
    if not sources_dir.exists():
        raise FileNotFoundError(f"Sources folder not found: {sources_dir}")

    cluster_dirs = sorted(
        [p for p in sources_dir.iterdir() if p.is_dir() and p.name.startswith("cluster_")]
    )

    if not cluster_dirs:
        print("⚠️ No cluster folders found.")
        return

    scorer_agent = build_scorer_agent()

    for cluster_dir in cluster_dirs:
        cluster_id = cluster_dir.name
        articles_file = cluster_dir / "articles.json"

        if not articles_file.exists():
            print(f"Skipping {cluster_id} (no articles.json)")
            continue

        with open(articles_file, "r", encoding="utf-8") as f:
            cluster_articles = json.load(f)

        print(f"\n🔎 Scoring {cluster_id}...")

        task = build_scoring_task(
            cluster_id=cluster_id,
            cluster_articles=cluster_articles,
            agent=scorer_agent,
        )

        try:
            score_data = execute_json_task(client, config, task)
        except Exception as e:
            print(f"❌ Failed scoring {cluster_id}: {e}")
            continue

        score_data = enrich_cluster_score(score_data, cluster_articles)

        output_file = cluster_dir / "cluster-score.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(score_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Saved → {output_file}")
