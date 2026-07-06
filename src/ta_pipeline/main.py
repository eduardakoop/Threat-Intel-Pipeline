from openai import OpenAI

from ta_pipeline.app_config import AppConfig
from ta_pipeline.pipeline.content_stage import run_content_pipeline
from ta_pipeline.pipeline.scoring_stage import score_all_clusters
from ta_pipeline.pipeline.summary_stage import run_executive_summary_and_ta_prep


def run_full_pipeline(
    client: OpenAI,
    config: AppConfig,
) -> dict:
    run_root = run_content_pipeline(config)
    config.active_run_root = run_root
    score_all_clusters(client, config, run_root)
    results = run_executive_summary_and_ta_prep(client, config, run_root)

    print("\nFull pipeline COMPLETE")
    print(f"Output: {run_root}")

    return {
        "run_root": run_root,
        "results": results,
    }
