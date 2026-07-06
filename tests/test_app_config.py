import inspect
from pathlib import Path

from ta_pipeline.app_config import build_config


def test_build_config_defaults(monkeypatch):
    monkeypatch.delenv("TA_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("TA_BASE_URL", raising=False)
    monkeypatch.delenv("TA_MODEL_ID", raising=False)
    monkeypatch.delenv("TA_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = build_config()
    project_root = Path(inspect.getfile(build_config)).resolve().parents[2]

    assert config.storage_root == project_root / "storage"
    assert config.runs_root == project_root / "storage" / "runs"
    assert config.base_url == "http://127.0.0.1:8000/v1"
    assert config.model_id == "/models/Qwen3.5-35B-A3B-AWQ"
    assert config.model_api_key == "local-dev-key"
    assert config.min_cluster_articles == 1
    assert config.max_articles_per_feed == 0
    assert config.lookback_days == 7
    assert config.expand_feed_topics_with_serper is False
    assert config.disable_model_thinking is True


def test_build_config_env_overrides(monkeypatch, tmp_path):
    storage_root = tmp_path / "storage"

    monkeypatch.setenv("TA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("TA_BASE_URL", "http://localhost:9000/v1")
    monkeypatch.setenv("TA_MODEL_ID", "model-x")
    monkeypatch.setenv("TA_MODEL_API_KEY", "secret")
    monkeypatch.setenv("TA_MIN_CLUSTER_ARTICLES", "4")
    monkeypatch.setenv("TA_MAX_ARTICLES_PER_FEED", "12")
    monkeypatch.setenv("TA_LOOKBACK_DAYS", "14")
    monkeypatch.setenv("TA_EXPAND_FEED_TOPICS_WITH_SERPER", "true")
    monkeypatch.setenv("TA_DISABLE_MODEL_THINKING", "false")

    config = build_config()

    assert config.storage_root == storage_root
    assert config.runs_root == storage_root / "runs"
    assert config.base_url == "http://localhost:9000/v1"
    assert config.model_id == "model-x"
    assert config.model_api_key == "secret"
    assert config.min_cluster_articles == 4
    assert config.max_articles_per_feed == 12
    assert config.lookback_days == 14
    assert config.expand_feed_topics_with_serper is True
    assert config.disable_model_thinking is False


def test_build_config_resolves_relative_storage_root(monkeypatch):
    monkeypatch.setenv("TA_STORAGE_ROOT", "./storage")

    config = build_config()
    project_root = Path(inspect.getfile(build_config)).resolve().parents[2]

    assert config.storage_root == project_root / "storage"
    assert config.runs_root == project_root / "storage" / "runs"
