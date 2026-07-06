from __future__ import annotations

import re

from ta_pipeline.security.models import DetectionFinding, ScanResult


_PROMPT_RULES = (
    {
        "name": "role_override_attempt",
        "score": 70,
        "reason": "Prompt contains language that attempts to override higher-priority instructions.",
        "patterns": (
            r"\bignore(?: all| any| the)? previous instructions\b",
            r"\bdisregard(?: all| any| the)? (?:previous|above) instructions\b",
            r"\bforget(?: about)? (?:your|the) system prompt\b",
            r"\byou are no longer\b",
            r"\boverride(?: the)? system prompt\b",
            r"\bnew system prompt\b",
        ),
    },
    {
        "name": "prompt_injection_attempt",
        "score": 65,
        "reason": "Prompt contains prompt-injection style control language.",
        "patterns": (
            r"\b(begin|end) (?:system|developer|assistant) prompt\b",
            r"</?(?:system|assistant|developer|tool)>",
            r"\b###\s*(?:system|assistant|developer)\b",
            r"\bfrom now on[,:\s]+(?:only )?follow these instructions\b",
            r"\bthis message has higher priority\b",
        ),
    },
    {
        "name": "system_prompt_exfiltration",
        "score": 75,
        "reason": "Prompt asks the model to reveal hidden instructions or system content.",
        "patterns": (
            r"\b(reveal|show|print|repeat|display)\b.{0,40}\b(system prompt|hidden instructions|developer message|secret prompt)\b",
            r"\bwhat (?:is|was) your system prompt\b",
            r"\bquote the instructions above\b",
            r"\bleak\b.{0,20}\bprompt\b",
        ),
    },
    {
        "name": "tool_call_abuse_language",
        "score": 55,
        "reason": "Prompt attempts to coerce tool execution or unauthorized command behavior.",
        "patterns": (
            r"\b(run|execute|invoke|call)\b.{0,30}\b(tool|function|plugin|shell|powershell|bash|terminal|browser)\b",
            r"\buse the tool\b",
            r"\bfunction call\b",
            r"\bopen a shell\b",
        ),
    },
    {
        "name": "instruction_override_phrasing",
        "score": 45,
        "reason": "Prompt contains suspicious instruction-reprioritization language.",
        "patterns": (
            r"\binstead[, ]+follow\b",
            r"\bdo not follow\b.{0,20}\b(previous|above|system)\b",
            r"\bpriority instructions\b",
            r"\bonly obey\b",
            r"\byour real instructions are\b",
        ),
    },
)


def _truncate(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _compile_patterns(patterns: tuple[str, ...]) -> list[re.Pattern[str]]:
    return [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in patterns]


def _rule_match(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in _compile_patterns(patterns):
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


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


def _scan_delimiter_flooding(text: str) -> DetectionFinding | None:
    repeated_delimiters = re.findall(r"([<>{}\[\]`#=*_\-])\1{7,}", text)
    code_fence_count = len(re.findall(r"```", text))
    xml_boundary_count = len(
        re.findall(r"</?(?:system|assistant|developer|tool|function)>", text, flags=re.IGNORECASE)
    )

    if len(repeated_delimiters) < 2 and code_fence_count < 6 and xml_boundary_count < 3:
        return None

    evidence = (
        f"repeated_delimiters={len(repeated_delimiters)}, "
        f"code_fences={code_fence_count}, xml_boundaries={xml_boundary_count}"
    )

    return DetectionFinding(
        rule_name="delimiter_flooding",
        score=35,
        reason="Prompt contains excessive delimiter or boundary markers that can increase prompt confusion risk.",
        evidence=evidence,
    )


def scan_prompt_text(system_prompt: str, user_prompt: str) -> ScanResult:
    fields = {
        "system_prompt": system_prompt or "",
        "user_prompt": user_prompt or "",
    }
    combined_prompt = "\n\n".join(part for part in fields.values() if part)

    detections: list[DetectionFinding] = []
    triggered_rules: list[str] = []
    reasons: list[str] = []

    for rule in _PROMPT_RULES:
        for field_name, text in fields.items():
            if not text:
                continue

            match_text = _rule_match(text, rule["patterns"])
            if not match_text:
                continue

            detection = DetectionFinding(
                rule_name=rule["name"],
                score=rule["score"],
                reason=f"{rule['reason']} Detected in {field_name}.",
                evidence=_truncate(match_text),
            )
            detections.append(detection)
            triggered_rules.append(rule["name"])
            reasons.append(detection.reason)
            break

    delimiter_detection = _scan_delimiter_flooding(combined_prompt)
    if delimiter_detection:
        detections.append(delimiter_detection)
        triggered_rules.append(delimiter_detection.rule_name)
        reasons.append(delimiter_detection.reason)

    risk_score = _calculate_risk_score(detections)

    return ScanResult(
        scanner_name="prompt_scanner",
        risk_score=risk_score,
        recommendation=_recommendation_for_score(risk_score),
        triggered_rules=triggered_rules,
        reasons=reasons,
        detections=detections,
        scanned_fields=["system_prompt", "user_prompt", "combined_prompt"],
    )
