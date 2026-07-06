from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ta_pipeline.security.models import IntegrityCheckResult, IntegrityFinding


_INTEGRITY_CACHE: dict[str, IntegrityCheckResult] = {}


def _package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_manifest_path() -> Path:
    return _package_root() / "security" / "integrity_manifest.json"


def _monitored_files(package_root: Path) -> list[Path]:
    explicit_files = [
        package_root / "app_config.py",
        package_root / "llm" / "executor.py",
        package_root / "llm" / "client.py",
        package_root / "llm" / "parser.py",
    ]

    recursive_files: list[Path] = []
    for folder_name in ("tasks", "agents"):
        recursive_files.extend(sorted((package_root / folder_name).rglob("*.py")))

    deduped: dict[str, Path] = {}
    for path in explicit_files + recursive_files:
        deduped[str(path.resolve())] = path

    return sorted(deduped.values(), key=lambda path: path.as_posix())


def calculate_sha256(file_path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_integrity_manifest() -> dict:
    package_root = _package_root()
    files = _monitored_files(package_root)

    return {
        "manifest_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "package_root": "ta_pipeline",
        "files": {
            path.relative_to(package_root).as_posix(): calculate_sha256(path)
            for path in files
            if path.exists()
        },
    }


def write_integrity_manifest(manifest_path: str | Path | None = None) -> Path:
    path = Path(manifest_path) if manifest_path else _default_manifest_path()
    payload = build_integrity_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)

    clear_integrity_cache()
    return path


def clear_integrity_cache() -> None:
    _INTEGRITY_CACHE.clear()


def verify_integrity(
    manifest_path: str | Path | None = None,
    use_cache: bool = True,
) -> IntegrityCheckResult:
    path = Path(manifest_path) if manifest_path else _default_manifest_path()
    resolved_path = path.resolve()
    cache_key = str(resolved_path)

    if use_cache and cache_key in _INTEGRITY_CACHE:
        return _INTEGRITY_CACHE[cache_key]

    checked_at = datetime.now(timezone.utc).isoformat()
    package_root = _package_root()
    current_files = {
        file_path.relative_to(package_root).as_posix(): calculate_sha256(file_path)
        for file_path in _monitored_files(package_root)
        if file_path.exists()
    }

    if not resolved_path.exists():
        result = IntegrityCheckResult(
            checked_at=checked_at,
            manifest_path=str(resolved_path),
            status="missing_manifest",
            recommendation="review",
            reasons=["Integrity baseline manifest was not found."],
            findings=[
                IntegrityFinding(
                    path=str(resolved_path),
                    status="missing_manifest",
                    reason="Integrity baseline manifest does not exist.",
                )
            ],
            checked_files=len(current_files),
        )
        _INTEGRITY_CACHE[cache_key] = result
        return result

    try:
        with open(resolved_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except Exception as exc:
        result = IntegrityCheckResult(
            checked_at=checked_at,
            manifest_path=str(resolved_path),
            status="invalid_manifest",
            recommendation="review",
            reasons=[f"Integrity manifest could not be parsed: {exc}"],
            findings=[
                IntegrityFinding(
                    path=str(resolved_path),
                    status="invalid_manifest",
                    reason=f"Integrity manifest could not be parsed: {exc}",
                )
            ],
            checked_files=len(current_files),
        )
        _INTEGRITY_CACHE[cache_key] = result
        return result

    manifest_files = manifest.get("files", {})
    findings: list[IntegrityFinding] = []

    for relative_path, expected_hash in sorted(manifest_files.items()):
        actual_hash = current_files.get(relative_path)
        if actual_hash is None:
            findings.append(
                IntegrityFinding(
                    path=relative_path,
                    status="missing_file",
                    reason="File tracked in the manifest is missing from disk.",
                    expected_sha256=expected_hash,
                    actual_sha256=None,
                )
            )
            continue

        if actual_hash != expected_hash:
            findings.append(
                IntegrityFinding(
                    path=relative_path,
                    status="hash_mismatch",
                    reason="Current file hash differs from the baseline manifest.",
                    expected_sha256=expected_hash,
                    actual_sha256=actual_hash,
                )
            )

    for relative_path, actual_hash in sorted(current_files.items()):
        if relative_path in manifest_files:
            continue
        findings.append(
            IntegrityFinding(
                path=relative_path,
                status="untracked_file",
                reason="File is monitored by policy but missing from the baseline manifest.",
                expected_sha256=None,
                actual_sha256=actual_hash,
            )
        )

    if findings:
        result = IntegrityCheckResult(
            checked_at=checked_at,
            manifest_path=str(resolved_path),
            status="mismatch",
            recommendation="review",
            reasons=["Integrity verification found baseline differences."],
            findings=findings,
            checked_files=len(current_files),
        )
    else:
        result = IntegrityCheckResult(
            checked_at=checked_at,
            manifest_path=str(resolved_path),
            status="ok",
            recommendation="allow",
            reasons=["Integrity verification matched the baseline manifest."],
            findings=[],
            checked_files=len(current_files),
        )

    _INTEGRITY_CACHE[cache_key] = result
    return result
