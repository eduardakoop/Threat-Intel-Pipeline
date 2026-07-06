from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from openai import OpenAI

from ta_pipeline.app_config import AppConfig
from ta_pipeline.llm.parser import extract_json_object
from ta_pipeline.models.task import TaskPayload
from ta_pipeline.security.audit_logger import hash_prompt_payload, hash_text, write_audit_record
from ta_pipeline.security.integrity_checker import verify_integrity
from ta_pipeline.security.models import (
    AuditRecord,
    IntegrityCheckResult,
    ScanResult,
    SecurityViolationError,
)
from ta_pipeline.security.output_scanner import sanitize_model_output, scan_model_output
from ta_pipeline.security.prompt_scanner import scan_prompt_text


def _build_request_kwargs(config: AppConfig, task: TaskPayload) -> dict:
    request_kwargs = {
        "model": config.model_id,
        "temperature": config.temperature,
        "messages": [
            {"role": "system", "content": task.system_prompt},
            {"role": "user", "content": task.user_prompt},
        ],
    }

    if config.max_tokens is not None:
        request_kwargs["max_tokens"] = config.max_tokens

    if config.disable_model_thinking and "qwen" in config.model_id.lower():
        # Qwen models served by vLLM support a hard switch that disables
        # reasoning output, which keeps strict-format tasks from leaking
        # chain-of-thought text into the final response.
        request_kwargs["extra_body"] = {
            "chat_template_kwargs": {
                "enable_thinking": False,
            }
        }

    return request_kwargs


def _empty_scan(scanner_name: str, scanned_fields: list[str]) -> ScanResult:
    return ScanResult(
        scanner_name=scanner_name,
        risk_score=0,
        recommendation="allow",
        triggered_rules=[],
        reasons=[],
        detections=[],
        scanned_fields=scanned_fields,
    )


def _empty_prompt_scan() -> ScanResult:
    return _empty_scan("prompt_scanner", ["system_prompt", "user_prompt"])


def _empty_output_scan() -> ScanResult:
    return _empty_scan("output_scanner", ["raw_output", "sanitized_output"])


def _disabled_integrity_check(config: AppConfig) -> IntegrityCheckResult:
    return IntegrityCheckResult(
        checked_at=datetime.now(timezone.utc).isoformat(),
        manifest_path=str(config.integrity_manifest_path) if config.integrity_manifest_path else "",
        status="disabled",
        recommendation="allow",
        reasons=["Security checks disabled by configuration."],
        findings=[],
        checked_files=0,
    )


def execute_chat_completion(
    client: OpenAI,
    config: AppConfig,
    task: TaskPayload,
) -> str:
    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    prompt_hash = hash_prompt_payload(task.system_prompt, task.user_prompt)
    prompt_length = len(task.system_prompt or "") + len(task.user_prompt or "")

    if config.security_enabled:
        pre_scan = scan_prompt_text(task.system_prompt, task.user_prompt)
        integrity_result = verify_integrity(config.integrity_manifest_path, use_cache=True)
    else:
        pre_scan = _empty_prompt_scan()
        integrity_result = _disabled_integrity_check(config)

    post_scan: ScanResult | None = None
    output_hash: str | None = None
    output_length: int | None = None
    final_decision: str = "allow"
    exception_message: str | None = None
    returned_text = ""

    try:
        if config.security_block_on_integrity_mismatch and integrity_result.recommendation != "allow":
            final_decision = "block"
            raise SecurityViolationError(
                f"Integrity verification did not pass cleanly: {integrity_result.status}"
            )

        if config.security_block_on_prompt_scan and pre_scan.recommendation == "block":
            final_decision = "block"
            raise SecurityViolationError(
                f"Prompt scan blocked task '{task.task_name}' with risk score {pre_scan.risk_score}"
            )

        response = client.chat.completions.create(**_build_request_kwargs(config, task))
        raw_text = (response.choices[0].message.content or "").strip()
        returned_text = sanitize_model_output(raw_text)
        output_hash = hash_text(returned_text)
        output_length = len(returned_text)

        if config.security_enabled:
            post_scan = scan_model_output(task, raw_text)
        else:
            post_scan = _empty_output_scan()

        if config.security_block_on_output_scan and post_scan.recommendation == "block":
            final_decision = "block"
            raise SecurityViolationError(
                f"Output scan blocked task '{task.task_name}' with risk score {post_scan.risk_score}"
            )

        if returned_text != raw_text:
            final_decision = "redact"

        return returned_text
    except Exception as exc:
        exception_message = str(exc)
        if final_decision == "allow":
            final_decision = "failed"
        raise
    finally:
        if config.security_enabled:
            audit_record = AuditRecord(
                timestamp=started_at.isoformat(),
                task_name=task.task_name,
                output_type=task.output_type,
                model_id=config.model_id,
                base_url=config.base_url,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                prompt_hash=prompt_hash,
                output_hash=output_hash,
                prompt_length=prompt_length,
                output_length=output_length,
                pre_scan=pre_scan,
                post_scan=post_scan if post_scan is not None else _empty_output_scan(),
                integrity_check=integrity_result,
                final_decision=final_decision,
                latency_ms=int((perf_counter() - started) * 1000),
                exception_message=exception_message,
                run_root=str(config.active_run_root) if config.active_run_root else None,
            )
            write_audit_record(config, audit_record)


def execute_json_task(
    client: OpenAI,
    config: AppConfig,
    task: TaskPayload,
) -> dict:
    raw_text = execute_chat_completion(client, config, task)

    print("\n=== MODEL OUTPUT (JSON TASK) ===")
    print(raw_text)

    return extract_json_object(raw_text)
