from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ScanRecommendation = Literal["allow", "review", "block"]
InferenceDecision = Literal["allow", "block", "redact", "failed"]


@dataclass(frozen=True)
class DetectionFinding:
    rule_name: str
    score: int
    reason: str
    evidence: str | None = None

    def to_dict(self) -> dict:
        return {
            "rule_name": self.rule_name,
            "score": self.score,
            "reason": self.reason,
            "evidence": self.evidence,
        }


@dataclass
class ScanResult:
    scanner_name: str
    risk_score: int
    recommendation: ScanRecommendation
    triggered_rules: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    detections: list[DetectionFinding] = field(default_factory=list)
    scanned_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scanner_name": self.scanner_name,
            "risk_score": self.risk_score,
            "recommendation": self.recommendation,
            "triggered_rules": list(self.triggered_rules),
            "reasons": list(self.reasons),
            "detections": [detection.to_dict() for detection in self.detections],
            "scanned_fields": list(self.scanned_fields),
        }


@dataclass(frozen=True)
class IntegrityFinding:
    path: str
    status: str
    reason: str
    expected_sha256: str | None = None
    actual_sha256: str | None = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "status": self.status,
            "reason": self.reason,
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
        }


@dataclass
class IntegrityCheckResult:
    checked_at: str
    manifest_path: str
    status: str
    recommendation: ScanRecommendation
    reasons: list[str] = field(default_factory=list)
    findings: list[IntegrityFinding] = field(default_factory=list)
    checked_files: int = 0

    def to_dict(self) -> dict:
        return {
            "checked_at": self.checked_at,
            "manifest_path": self.manifest_path,
            "status": self.status,
            "recommendation": self.recommendation,
            "reasons": list(self.reasons),
            "findings": [finding.to_dict() for finding in self.findings],
            "checked_files": self.checked_files,
        }


@dataclass
class AuditRecord:
    timestamp: str
    task_name: str
    output_type: str
    model_id: str
    base_url: str
    temperature: float
    max_tokens: int | None
    prompt_hash: str
    output_hash: str | None
    prompt_length: int
    output_length: int | None
    pre_scan: ScanResult
    post_scan: ScanResult
    integrity_check: IntegrityCheckResult
    final_decision: InferenceDecision
    latency_ms: int | None
    exception_message: str | None = None
    run_root: str | None = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "task_name": self.task_name,
            "output_type": self.output_type,
            "model_id": self.model_id,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "prompt_hash": self.prompt_hash,
            "output_hash": self.output_hash,
            "prompt_length": self.prompt_length,
            "output_length": self.output_length,
            "pre_scan": self.pre_scan.to_dict(),
            "post_scan": self.post_scan.to_dict(),
            "integrity_check": self.integrity_check.to_dict(),
            "final_decision": self.final_decision,
            "latency_ms": self.latency_ms,
            "exception_message": self.exception_message,
            "run_root": self.run_root,
        }


class SecurityViolationError(RuntimeError):
    """Raised when a configured security control blocks an inference."""
