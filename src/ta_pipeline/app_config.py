from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass
class AppConfig:
    # Paths
    storage_root: Path
    runs_root: Path

    # Model config
    base_url: str
    model_id: str
    model_api_key: str
    max_tokens: int | None = None

    # Optional APIs
    serper_api_key: str | None = None

    # Pipeline settings
    min_cluster_articles: int = 5
    max_web_results: int = 10
    searches_per_source: int = 3
    max_articles_per_feed: int = 0
    lookback_days: int = 7
    expand_feed_topics_with_serper: bool = False
    verbose: bool = True
    similarity_threshold: float = 0.8
    temperature: float = 0.0

    # Security settings
    security_enabled: bool = True
    security_block_on_prompt_scan: bool = True
    security_block_on_output_scan: bool = True
    security_block_on_integrity_mismatch: bool = False
    security_audit_subdir: str = "security/audit"
    integrity_manifest_path: Path | None = None
    active_run_root: Path | None = None
    disable_model_thinking: bool = True


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path, *, base: Path | None = None) -> Path:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    path = Path(raw_value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    return path


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    return int(raw_value) if raw_value is not None else default


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    return float(raw_value) if raw_value is not None else default


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def build_config() -> AppConfig:
    project_root = _project_root()
    storage_root = _env_path("TA_STORAGE_ROOT", project_root / "storage", base=project_root)
    base_url = os.getenv("TA_BASE_URL", "http://127.0.0.1:8000/v1")
    model_id = os.getenv("TA_MODEL_ID", "/models/Qwen3.5-35B-A3B-AWQ")
    model_api_key = (
        os.getenv("TA_MODEL_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or "local-dev-key"
    )

    if not base_url.startswith(("http://", "https://")):
        raise ValueError("BASE_URL must start with http:// or https://")

    if not base_url.endswith("/v1"):
        raise ValueError("BASE_URL must end with /v1")

    package_root = Path(__file__).resolve().parent

    return AppConfig(
        storage_root=storage_root,
        runs_root=storage_root / "runs",
        base_url=base_url,
        model_id=model_id,
        model_api_key=model_api_key,
        max_tokens=_env_int("TA_MAX_TOKENS", 0) or None,
        serper_api_key=os.getenv("SERPER_API_KEY"),
        min_cluster_articles=_env_int("TA_MIN_CLUSTER_ARTICLES", 1),
        max_web_results=_env_int("TA_MAX_WEB_RESULTS", 10),
        searches_per_source=_env_int("TA_SEARCHES_PER_SOURCE", 3),
        max_articles_per_feed=_env_int("TA_MAX_ARTICLES_PER_FEED", 0),
        lookback_days=_env_int("TA_LOOKBACK_DAYS", 7),
        expand_feed_topics_with_serper=_env_bool("TA_EXPAND_FEED_TOPICS_WITH_SERPER", False),
        verbose=_env_bool("TA_VERBOSE", True),
        similarity_threshold=_env_float("TA_SIMILARITY_THRESHOLD", 0.8),
        temperature=_env_float("TA_TEMPERATURE", 0.0),
        security_enabled=_env_bool("TA_SECURITY_ENABLED", True),
        security_block_on_prompt_scan=_env_bool("TA_SECURITY_BLOCK_ON_PROMPT_SCAN", True),
        security_block_on_output_scan=_env_bool("TA_SECURITY_BLOCK_ON_OUTPUT_SCAN", True),
        security_block_on_integrity_mismatch=_env_bool(
            "TA_SECURITY_BLOCK_ON_INTEGRITY_MISMATCH",
            False,
        ),
        security_audit_subdir=os.getenv("TA_SECURITY_AUDIT_SUBDIR", "security/audit"),
        integrity_manifest_path=package_root / "security" / "integrity_manifest.json",
        disable_model_thinking=_env_bool("TA_DISABLE_MODEL_THINKING", True),
    )
