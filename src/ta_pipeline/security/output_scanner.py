from __future__ import annotations

import json
import re

from ta_pipeline.llm.parser import extract_json_object
from ta_pipeline.models.task import TaskPayload
from ta_pipeline.security.models import DetectionFinding, ScanResult


_SPECIAL_TOKEN_PATTERN = re.compile(r"<\|[^>]+?\|>|</?think>", re.IGNORECASE)
_REASONING_MARKER_PATTERN = re.compile(
    r"\b(thinking process|chain of thought|internal reasoning|let'?s think step by step)\b",
    re.IGNORECASE,
)
_UNSAFE_CYBER_PATTERN = re.compile(
    r"\b(step[- ]by[- ]step|follow these steps|execute the following command|run this command)\b"
    r".{0,120}\b(mimikatz|metasploit|payload|reverse shell|credential dump|shellcode|ransomware)\b",
    re.IGNORECASE | re.DOTALL,
)


def _truncate(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _calculate_risk_score(detections: list[DetectionFinding]) -> int:
    if not detections:
        return 0

    scores = sorted((detection.score for detection in detections), reverse=True)
    highest = scores[0]
    additive = sum(scores[1:]) // 3
    return min(100, highest + additive)


def _recommendation_for_score(score: int) -> str:
    if score >= 75:
        return "block"
    if score >= 40:
        return "review"
    return "allow"


def sanitize_model_output(raw_output: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", raw_output, flags=re.IGNORECASE | re.DOTALL)
    cleaned = _SPECIAL_TOKEN_PATTERN.sub("", cleaned)
    return cleaned.strip()


def _detect_prompt_echo(task: TaskPayload, raw_output: str) -> DetectionFinding | None:
    normalized_output = " ".join(raw_output.split())
    matched_lines: list[str] = []

    for prompt_text in (task.system_prompt, task.user_prompt):
        for line in prompt_text.splitlines():
            candidate = " ".join(line.split())
            if len(candidate) < 40:
                continue
            if candidate in normalized_output:
                matched_lines.append(candidate)
            if len(matched_lines) >= 2:
                break
        if len(matched_lines) >= 2:
            break

    if not matched_lines:
        return None

    return DetectionFinding(
        rule_name="prompt_template_leakage",
        score=65,
        reason="Model output echoed internal prompt or template content.",
        evidence=_truncate(matched_lines[0]),
    )


def _detect_json_format_issues(output_text: str) -> list[DetectionFinding]:
    findings: list[DetectionFinding] = []

    try:
        extract_json_object(output_text)
    except Exception:
        findings.append(
            DetectionFinding(
                rule_name="malformed_json_output",
                score=90,
                reason="Expected JSON output could not be recovered from the model response.",
                evidence=None,
            )
        )
        return findings

    try:
        json.loads(output_text)
    except Exception:
        findings.append(
            DetectionFinding(
                rule_name="json_wrapper_noise",
                score=35,
                reason="JSON response included extra wrapper text or formatting noise around the structured payload.",
                evidence=None,
            )
        )

    return findings


def scan_model_output(task: TaskPayload, raw_output: str) -> ScanResult:
    detections: list[DetectionFinding] = []
    triggered_rules: list[str] = []
    reasons: list[str] = []
    sanitized_output = sanitize_model_output(raw_output)

    special_token_match = _SPECIAL_TOKEN_PATTERN.search(raw_output)
    if special_token_match:
        detections.append(
            DetectionFinding(
                rule_name="special_token_leakage",
                score=55,
                reason="Model output contained internal control tokens or think markers.",
                evidence=_truncate(special_token_match.group(0)),
            )
        )

    reasoning_match = _REASONING_MARKER_PATTERN.search(raw_output)
    if reasoning_match:
        detections.append(
            DetectionFinding(
                rule_name="reasoning_marker_exposure",
                score=50,
                reason="Model output exposed internal reasoning markers or chain-of-thought phrasing.",
                evidence=_truncate(reasoning_match.group(0)),
            )
        )

    prompt_echo_detection = _detect_prompt_echo(task, raw_output)
    if prompt_echo_detection:
        detections.append(prompt_echo_detection)

    unsafe_cyber_match = _UNSAFE_CYBER_PATTERN.search(raw_output)
    if unsafe_cyber_match:
        detections.append(
            DetectionFinding(
                rule_name="unsafe_cyber_instructions",
                score=50,
                reason="Model output contained step-oriented offensive cyber instructions.",
                evidence=_truncate(unsafe_cyber_match.group(0)),
            )
        )

    if task.output_type == "json":
        detections.extend(_detect_json_format_issues(sanitized_output))

    for detection in detections:
        triggered_rules.append(detection.rule_name)
        reasons.append(detection.reason)

    risk_score = _calculate_risk_score(detections)

    return ScanResult(
        scanner_name="output_scanner",
        risk_score=risk_score,
        recommendation=_recommendation_for_score(risk_score),
        triggered_rules=triggered_rules,
        reasons=reasons,
        detections=detections,
        scanned_fields=["raw_output", "sanitized_output"],
    )
