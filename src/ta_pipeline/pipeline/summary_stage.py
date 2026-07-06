import json
from pathlib import Path

from openai import OpenAI

from ta_pipeline.app_config import AppConfig
from ta_pipeline.agents.executive_writer import build_executive_writer_agent
from ta_pipeline.agents.ta_prep import build_ta_prep_agent
from ta_pipeline.llm.executor import execute_json_task
from ta_pipeline.pipeline.selection import get_top_clusters, select_top_articles
from ta_pipeline.pipeline.ta_brief_formatter import format_ta_brief
from ta_pipeline.tasks.executive_summary import build_executive_summary_task
from ta_pipeline.tasks.ta_prep import build_ta_prep_task

TOP_CLUSTER_COUNT = 3


def run_executive_summary_and_ta_prep(
    client: OpenAI,
    config: AppConfig,
    run_root: Path,
) -> dict | None:
    print("\n=== EXECUTIVE SUMMARY + TA PREP STAGE ===")

    try:
        top_clusters = get_top_clusters(
            run_root,
            require_ta_eligible=True,
            limit=TOP_CLUSTER_COUNT,
        )
    except ValueError as e:
        print(f"⚠️ {e}")
        return None

    executive_writer_agent = build_executive_writer_agent()
    ta_prep_agent = build_ta_prep_agent()
    exec_output_dir = run_root / "executive-summaries"
    exec_output_dir.mkdir(parents=True, exist_ok=True)
    ta_output_dir = run_root / "TA-briefs"
    ta_output_dir.mkdir(parents=True, exist_ok=True)
    cluster_results = []

    print(f"🏆 Selected {len(top_clusters)} TA-eligible clusters for executive summary + TA prep")

    for index, cluster in enumerate(top_clusters, start=1):
        cluster_id = cluster["cluster_id"]
        score_data = cluster["score"]
        articles = cluster["articles"]

        print(
            f"  {index}. {cluster_id} "
            f"(importance={score_data.get('overall_importance_score', 0)}, "
            f"most_recent_incident={score_data.get('most_recent_incident', 'unknown')})"
        )

        selected_articles = select_top_articles(articles, max_articles=2)
        exec_task = build_executive_summary_task(
            cluster_id=cluster_id,
            scored_cluster=score_data,
            cluster_articles=selected_articles,
            agent=executive_writer_agent,
        )

        try:
            summary = execute_json_task(client, config, exec_task)
        except Exception as e:
            print(f"❌ Failed to generate executive summary for {cluster_id}: {e}")
            cluster_results.append(
                {
                    "cluster_id": cluster_id,
                    "executive_summary": None,
                    "ta_brief": None,
                }
            )
            continue

        exec_output_file = exec_output_dir / f"summary_{cluster_id}.json"
        with open(exec_output_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"✅ Executive summary saved → {exec_output_file}")

        ta_task = build_ta_prep_task(
            cluster_id=cluster_id,
            scored_cluster=score_data,
            cluster_articles=selected_articles,
            executive_summary=summary,
            agent=ta_prep_agent,
        )

        try:
            ta_brief_payload = execute_json_task(client, config, ta_task)
            ta_brief = format_ta_brief(ta_brief_payload)
        except Exception as e:
            print(f"❌ Failed to generate TA brief for {cluster_id}: {e}")
            cluster_results.append(
                {
                    "cluster_id": cluster_id,
                    "executive_summary": summary,
                    "ta_brief": None,
                }
            )
            continue

        ta_output_file = ta_output_dir / f"TA-brief_{cluster_id}.txt"
        with open(ta_output_file, "w", encoding="utf-8") as f:
            f.write(str(ta_brief))

        print(f"✅ TA brief saved → {ta_output_file}")

        cluster_results.append(
            {
                "cluster_id": cluster_id,
                "executive_summary": summary,
                "ta_brief": ta_brief,
            }
        )

    return {
        "cluster_results": cluster_results,
    }
