from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from ta_pipeline.app_config import AppConfig, build_config
from ta_pipeline.llm.health import check_model_server
from ta_pipeline.storage.output_sync import finalize_outputs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the TA automation pipeline on the local machine while allowing "
            "outputs to be written to a configurable storage root."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("full", "health"),
        default="full",
        help="Which pipeline mode to run.",
    )
    parser.add_argument("--storage-root", help="Override the storage root used for run outputs.")
    parser.add_argument("--base-url", help="Override the OpenAI-compatible model server base URL.")
    parser.add_argument("--model-id", help="Override the model identifier sent to the API.")
    parser.add_argument("--model-api-key", help="Override the API key used for the model server.")
    parser.add_argument("--serper-api-key", help="Override the SERPER API key.")
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip probing the model server before running the pipeline.",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print the effective runtime configuration before running.",
    )
    return parser


def _apply_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    if args.storage_root:
        config.storage_root = Path(args.storage_root).expanduser()
        config.runs_root = config.storage_root / "runs"
    if args.base_url:
        config.base_url = args.base_url
    if args.model_id:
        config.model_id = args.model_id
    if args.model_api_key:
        config.model_api_key = args.model_api_key
    if args.serper_api_key:
        config.serper_api_key = args.serper_api_key
        os.environ["SERPER_API_KEY"] = args.serper_api_key
    return config


def _config_snapshot(config: AppConfig) -> dict:
    return {
        "storage_root": str(config.storage_root),
        "runs_root": str(config.runs_root),
        "base_url": config.base_url,
        "model_id": config.model_id,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "min_cluster_articles": config.min_cluster_articles,
        "max_articles_per_feed": config.max_articles_per_feed,
        "lookback_days": config.lookback_days,
        "expand_feed_topics_with_serper": config.expand_feed_topics_with_serper,
        "disable_model_thinking": config.disable_model_thinking,
        "security_enabled": config.security_enabled,
        "security_block_on_prompt_scan": config.security_block_on_prompt_scan,
        "security_block_on_output_scan": config.security_block_on_output_scan,
        "security_block_on_integrity_mismatch": config.security_block_on_integrity_mismatch,
        "serper_api_key_present": bool(config.serper_api_key),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = _apply_overrides(build_config(), args)

    if args.print_config:
        print(json.dumps(_config_snapshot(config), indent=2))

    if (not args.skip_health_check and args.mode == "full") or args.mode == "health":
        health = check_model_server(config)
        print(json.dumps(health, indent=2))

    if args.mode == "health":
        return 0

    from ta_pipeline.llm.client import build_llm_client
    from ta_pipeline.main import run_full_pipeline

    client = build_llm_client(config)
    result = run_full_pipeline(client, config)
    output_summary = finalize_outputs(config, result["run_root"])
    print(
        json.dumps(
            {
                "mode": args.mode,
                "run_root": str(result["run_root"]),
                "has_results": result["results"] is not None,
                "local_latest_marker": str(output_summary["local_latest_marker"]),
            },
            indent=2,
        )
    )
    return 0
