from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ta_pipeline.app_config import AppConfig
from ta_pipeline.security.models import AuditRecord


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_prompt_payload(system_prompt: str, user_prompt: str) -> str:
    prompt_payload = json.dumps(
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hash_text(prompt_payload)


def _audit_root(config: AppConfig) -> Path:
    if config.active_run_root is not None:
        return config.active_run_root / Path(config.security_audit_subdir)
    return config.runs_root / "_security" / "audit"


def write_audit_record(config: AppConfig, record: AuditRecord) -> Path:
    audit_root = _audit_root(config)
    audit_root.mkdir(parents=True, exist_ok=True)

    safe_task_name = re.sub(r"[^A-Za-z0-9_-]+", "_", record.task_name).strip("_") or "task"
    timestamp_prefix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    file_name = f"{timestamp_prefix}_{safe_task_name}_{record.prompt_hash[:12]}.json"
    file_path = audit_root / file_name

    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(record.to_dict(), handle, indent=2, ensure_ascii=False, sort_keys=True)

    return file_path
