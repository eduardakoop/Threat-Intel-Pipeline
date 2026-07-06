from __future__ import annotations

import re


def _normalize_text(value: object, fallback: str) -> str:
    if value is None:
        return fallback

    text = str(value).strip()
    if not text:
        return fallback

    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines) if lines else fallback


def _normalize_list(value: object, fallback: str) -> list[str]:
    if isinstance(value, list):
        items = [_normalize_text(item, "") for item in value]
        items = [item for item in items if item]
        return items or [fallback]

    if value is None:
        return [fallback]

    item = _normalize_text(value, "")
    return [item] if item else [fallback]


def _append_list_section(lines: list[str], heading: str, items: list[str]) -> None:
    lines.append(heading)
    if len(items) == 1 and items[0].lower().startswith("not reported"):
        lines.append(items[0])
    else:
        lines.extend(f"- {item}" for item in items)
    lines.append("")


def format_ta_brief(payload: dict) -> str:
    lines: list[str] = []

    lines.extend(
        [
            "1. Title",
            _normalize_text(payload.get("title"), "Not reported"),
            "",
            "2. Subtitle",
            _normalize_text(payload.get("subtitle"), "Not reported."),
            "",
            "3. Introduction",
            _normalize_text(payload.get("introduction"), "Not reported."),
            "",
            "4. Threat Landscape & Targets",
            _normalize_text(payload.get("threat_landscape_targets"), "Not reported."),
            "",
        ]
    )

    _append_list_section(
        lines,
        "5. Tactics, Techniques, and Procedures (TTPs)",
        _normalize_list(payload.get("ttps"), "Not reported."),
    )
    _append_list_section(
        lines,
        "6. Indicators of Compromise (IOCs)",
        _normalize_list(payload.get("iocs"), "Not reported."),
    )
    _append_list_section(
        lines,
        "7. Defensive Strategies & Best Practices",
        _normalize_list(
            payload.get("defensive_strategies_best_practices"),
            "Not reported.",
        ),
    )
    _append_list_section(
        lines,
        "8. References",
        _normalize_list(payload.get("references"), "Not reported."),
    )

    return "\n".join(lines).strip()
