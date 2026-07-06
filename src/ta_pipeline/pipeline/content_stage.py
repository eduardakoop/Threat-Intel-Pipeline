from pathlib import Path

from content_pipeline import config as content_config
from content_pipeline.runner import run_content_discovery

from ta_pipeline.app_config import AppConfig


def _apply_content_pipeline_config(config: AppConfig) -> None:
    content_config.MIN_CLUSTER_ARTICLES = config.min_cluster_articles
    content_config.MAX_WEB_RESULTS = config.max_web_results
    content_config.SEARCHES_PER_SOURCE = config.searches_per_source
    content_config.MAX_ARTICLES_PER_FEED = config.max_articles_per_feed
    content_config.LOOKBACK_DAYS = config.lookback_days
    content_config.EXPAND_FEED_TOPICS_WITH_SERPER = config.expand_feed_topics_with_serper
    content_config.VERBOSE = config.verbose
    content_config.SIMILARITY_THRESHOLD = config.similarity_threshold
    content_config.SERPER_API_KEY = config.serper_api_key


def run_content_pipeline(config: AppConfig) -> Path:
    print("=== STAGE 1: Content Pipeline ===")
    _apply_content_pipeline_config(config)
    run_root = run_content_discovery(storage_root=str(config.storage_root))
    print(f"✅ Content pipeline finished → {run_root}")
    return run_root
