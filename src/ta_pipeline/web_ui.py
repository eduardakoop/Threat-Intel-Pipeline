from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hmac import compare_digest
from io import BytesIO
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Lock, Thread
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from flask import Flask, Response, jsonify, render_template, request, send_file

from ta_pipeline.app_config import AppConfig, build_config
from ta_pipeline.llm.health import check_model_server


RUN_ID_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z")
CLUSTER_ID_RE = re.compile(r"cluster_\d+")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_local_env(project_root: Path) -> None:
    env_file = project_root / ".env.local"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _safe_run_id(run_id: str) -> str:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("Invalid run id.")
    return run_id


def _safe_cluster_id(cluster_id: str) -> str:
    if not CLUSTER_ID_RE.fullmatch(cluster_id):
        raise ValueError("Invalid cluster id.")
    return cluster_id


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return default


def _tail_file(path: Path | None, max_lines: int = 200) -> str:
    if path is None or not path.exists():
        return ""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    return "\n".join(lines[-max_lines:])


def _cluster_number(cluster_id: str) -> int:
    try:
        return int(cluster_id.rsplit("_", 1)[1])
    except Exception:
        return -1


def _cluster_label(cluster_id: str) -> str:
    number = _cluster_number(cluster_id)
    return f"Cluster {number}" if number >= 0 else cluster_id


def _run_id_to_iso(run_id: str) -> str:
    try:
        parsed = datetime.strptime(run_id, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except Exception:
        return ""


def _run_label(run_id: str) -> str:
    try:
        parsed = datetime.strptime(run_id, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return run_id

    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year} · {parsed.strftime('%H:%M')} UTC"


def _run_root(config: AppConfig, run_id: str) -> Path:
    safe_id = _safe_run_id(run_id)
    run_root = (config.runs_root / safe_id).resolve()
    runs_root = config.runs_root.resolve()
    if runs_root not in run_root.parents or not run_root.is_dir():
        raise FileNotFoundError(f"Run not found: {safe_id}")
    return run_root


def _latest_run_name(config: AppConfig) -> str | None:
    latest = _read_json(config.runs_root / "latest_run.json", default={})
    run_name = latest.get("run_name") if isinstance(latest, dict) else None
    return run_name if isinstance(run_name, str) else None


def _list_run_dirs(config: AppConfig) -> list[Path]:
    if not config.runs_root.exists():
        return []
    return sorted(
        [
            path
            for path in config.runs_root.iterdir()
            if path.is_dir() and RUN_ID_RE.fullmatch(path.name)
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _summary_for_file(run_root: Path, cluster_id: str) -> dict:
    return _read_json(
        run_root / "executive-summaries" / f"summary_{cluster_id}.json",
        default={},
    ) or {}


def _brief_path(run_root: Path, cluster_id: str) -> Path:
    return run_root / "TA-briefs" / f"TA-brief_{cluster_id}.txt"


def _collect_cluster_summaries(run_root: Path) -> list[dict]:
    sources_dir = run_root / "sources"
    if not sources_dir.exists():
        return []

    clusters: list[dict] = []
    for cluster_dir in sorted(sources_dir.iterdir(), key=lambda path: _cluster_number(path.name)):
        if not cluster_dir.is_dir() or not CLUSTER_ID_RE.fullmatch(cluster_dir.name):
            continue

        articles = _read_json(cluster_dir / "articles.json", default=[]) or []
        score = _read_json(cluster_dir / "cluster-score.json", default={}) or {}
        summary = _summary_for_file(run_root, cluster_dir.name)
        cves = sorted(
            {
                str(cve).upper()
                for article in articles
                for cve in (article.get("cves") or [])
                if cve
            }
        )
        top_article = articles[0] if articles else {}

        clusters.append(
            {
                "cluster_id": cluster_dir.name,
                "cluster_label": _cluster_label(cluster_dir.name),
                "article_count": len(articles),
                "overall_importance_score": score.get("overall_importance_score"),
                "severity_score": score.get("severity_score"),
                "urgency_score": score.get("urgency_score"),
                "business_impact_score": score.get("business_impact_score"),
                "is_ta_eligible": bool(score.get("is_ta_eligible")),
                "ta_eligibility_reason": score.get("ta_eligibility_reason", ""),
                "most_recent_incident": score.get("most_recent_incident")
                or score.get("most_recent_incident_date")
                or "",
                "recommended_for_executive_summary": bool(
                    score.get("recommended_for_executive_summary")
                ),
                "recommended_for_ta_brief": bool(score.get("recommended_for_ta_brief")),
                "headline": summary.get("headline", ""),
                "priority": summary.get("priority", ""),
                "has_summary": bool(summary),
                "has_ta_brief": _brief_path(run_root, cluster_dir.name).exists(),
                "top_title": top_article.get("title", ""),
                "top_source": top_article.get("source", ""),
                "cves": cves,
            }
        )

    return sorted(
        clusters,
        key=lambda item: (
            item["overall_importance_score"] or 0,
            item["severity_score"] or 0,
            item["urgency_score"] or 0,
            -_cluster_number(item["cluster_id"]),
        ),
        reverse=True,
    )


def _run_summary(config: AppConfig, run_root: Path, latest_name: str | None = None) -> dict:
    articles = _read_json(run_root / "sources" / "articles.json", default=[]) or []
    clusters = _collect_cluster_summaries(run_root)
    summary_count = len(list((run_root / "executive-summaries").glob("summary_cluster_*.json")))
    brief_count = len(list((run_root / "TA-briefs").glob("TA-brief_cluster_*.txt")))
    scored_count = len([cluster for cluster in clusters if cluster["overall_importance_score"] is not None])
    eligible_count = len([cluster for cluster in clusters if cluster["is_ta_eligible"]])
    top_cluster = clusters[0] if clusters else {}

    return {
        "run_id": run_root.name,
        "run_label": _run_label(run_root.name),
        "path": str(run_root),
        "started_at": _run_id_to_iso(run_root.name),
        "modified_at": datetime.fromtimestamp(
            run_root.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat(),
        "is_latest": run_root.name == latest_name,
        "article_count": len(articles),
        "cluster_count": len(clusters),
        "scored_count": scored_count,
        "ta_eligible_count": eligible_count,
        "summary_count": summary_count,
        "brief_count": brief_count,
        "top_score": top_cluster.get("overall_importance_score"),
        "top_cluster_id": top_cluster.get("cluster_id", ""),
        "top_cluster_label": top_cluster.get("cluster_label", ""),
        "top_headline": top_cluster.get("headline") or top_cluster.get("top_title", ""),
    }


def _brief_summaries(run_root: Path) -> list[dict]:
    briefs = []
    for path in sorted((run_root / "TA-briefs").glob("TA-brief_cluster_*.txt")):
        cluster_id = path.stem.replace("TA-brief_", "")
        summary = _summary_for_file(run_root, cluster_id)
        text = _read_text(path)
        title = ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if "1. Title" in lines:
            title_index = lines.index("1. Title")
            if len(lines) > title_index + 1:
                title = lines[title_index + 1]
        briefs.append(
            {
                "cluster_id": cluster_id,
                "cluster_label": _cluster_label(cluster_id),
                "title": title or summary.get("headline", cluster_id),
                "priority": summary.get("priority", ""),
                "headline": summary.get("headline", ""),
                "preview": text[:700],
                "path": str(path),
            }
        )
    return briefs


def _config_snapshot(config: AppConfig) -> dict:
    return {
        "storage_root": str(config.storage_root),
        "runs_root": str(config.runs_root),
        "base_url": config.base_url,
        "model_id": config.model_id,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "min_cluster_articles": config.min_cluster_articles,
        "max_articles_per_feed": config.max_articles_per_feed,
        "lookback_days": config.lookback_days,
        "expand_feed_topics_with_serper": config.expand_feed_topics_with_serper,
        "disable_model_thinking": config.disable_model_thinking,
        "security_enabled": config.security_enabled,
        "serper_api_key_present": bool(config.serper_api_key),
        "web_auth_enabled": bool(os.getenv("TA_WEB_USERNAME") and os.getenv("TA_WEB_PASSWORD")),
    }


@dataclass
class PipelineJob:
    job_id: str
    mode: str
    command: list[str]
    log_file: Path
    started_at: str
    process: subprocess.Popen | None = None
    status: str = "starting"
    finished_at: str | None = None
    returncode: int | None = None
    pid: int | None = None
    run_root: str | None = None
    error: str | None = None
    options: dict = field(default_factory=dict)

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "mode": self.mode,
            "command": self.command,
            "log_file": str(self.log_file),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "returncode": self.returncode,
            "pid": self.pid,
            "run_root": self.run_root,
            "error": self.error,
            "options": self.options,
            "running": self.is_running(),
        }


class PipelineRunner:
    def __init__(self, project_root: Path, config: AppConfig):
        self.project_root = project_root
        self.config = config
        self._lock = Lock()
        self._job: PipelineJob | None = None
        self._log_handle = None

    def current_job(self) -> PipelineJob | None:
        with self._lock:
            return self._job

    def start(self, *, skip_health_check: bool) -> PipelineJob:
        with self._lock:
            if self._job is not None and self._job.is_running():
                raise RuntimeError("A pipeline run is already active.")

            log_root = self.project_root / "logs"
            log_root.mkdir(parents=True, exist_ok=True)
            job_id = _utc_now().strftime("web_%Y%m%dT%H%M%S_%fZ")
            log_file = log_root / f"{job_id}.log"

            command = [
                sys.executable,
                "-m",
                "ta_pipeline",
                "--mode",
                "full",
                "--print-config",
            ]
            if skip_health_check:
                command.append("--skip-health-check")

            env = os.environ.copy()
            src_root = str(self.project_root / "src")
            env["PYTHONPATH"] = (
                src_root
                if not env.get("PYTHONPATH")
                else f"{src_root}{os.pathsep}{env['PYTHONPATH']}"
            )

            job = PipelineJob(
                job_id=job_id,
                mode="full",
                command=command,
                log_file=log_file,
                started_at=_iso_now(),
                status="running",
                options={
                    "skip_health_check": skip_health_check,
                },
            )

            try:
                self._log_handle = open(log_file, "w", encoding="utf-8")
                self._log_handle.write(f"Started at {job.started_at}\n")
                self._log_handle.write(f"Command: {' '.join(command)}\n\n")
                self._log_handle.flush()
                process = subprocess.Popen(
                    command,
                    cwd=self.project_root,
                    stdout=self._log_handle,
                    stderr=subprocess.STDOUT,
                    env=env,
                    text=True,
                )
            except Exception as exc:
                if self._log_handle is not None:
                    self._log_handle.close()
                    self._log_handle = None
                job.status = "failed"
                job.finished_at = _iso_now()
                job.error = str(exc)
                self._job = job
                raise

            job.process = process
            job.pid = process.pid
            self._job = job

            monitor = Thread(target=self._monitor_job, args=(job,), daemon=True)
            monitor.start()
            return job

    def stop(self) -> PipelineJob:
        with self._lock:
            if self._job is None or not self._job.is_running() or self._job.process is None:
                raise RuntimeError("No active pipeline run to stop.")
            self._job.status = "stopping"
            self._job.process.terminate()
            return self._job

    def _monitor_job(self, job: PipelineJob) -> None:
        assert job.process is not None
        returncode = job.process.wait()
        run_root = self._infer_run_root(job.log_file)

        with self._lock:
            job.returncode = returncode
            job.finished_at = _iso_now()
            job.run_root = str(run_root) if run_root is not None else None
            if job.status == "stopping":
                job.status = "stopped"
            elif returncode == 0:
                job.status = "completed"
            else:
                job.status = "failed"

            if self._log_handle is not None:
                self._log_handle.write(f"\nFinished at {job.finished_at} with code {returncode}\n")
                if job.run_root:
                    self._log_handle.write(f"Resolved run root: {job.run_root}\n")
                self._log_handle.flush()
                self._log_handle.close()
                self._log_handle = None

    def _infer_run_root(self, log_file: Path) -> Path | None:
        log_text = _read_text(log_file)
        matches = re.findall(r"(?:Output|RUN_ROOT):\s*(.+)", log_text)
        for raw_path in reversed(matches):
            path = Path(raw_path.strip())
            if path.exists() and path.is_dir():
                return path

        latest_name = _latest_run_name(self.config)
        if latest_name:
            candidate = self.config.runs_root / latest_name
            if candidate.exists():
                return candidate

        run_dirs = _list_run_dirs(self.config)
        return run_dirs[0] if run_dirs else None


def create_app(config: AppConfig | None = None) -> Flask:
    project_root = _project_root()
    _load_local_env(project_root)
    app_config = config or build_config()
    runner = PipelineRunner(project_root, app_config)

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent / "web_templates"),
        static_folder=str(Path(__file__).resolve().parent / "web_static"),
        static_url_path="/static",
    )

    @app.before_request
    def require_basic_auth():
        username = os.getenv("TA_WEB_USERNAME")
        password = os.getenv("TA_WEB_PASSWORD")
        if not username or not password:
            return None

        auth = request.authorization
        if auth and compare_digest(auth.username or "", username) and compare_digest(
            auth.password or "",
            password,
        ):
            return None

        return Response(
            "Authentication required.",
            401,
            {"WWW-Authenticate": 'Basic realm="TAsAutomation"'},
        )

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/config")
    def config_api():
        return jsonify(_config_snapshot(app_config))

    @app.get("/api/status")
    def status_api():
        job = runner.current_job()
        latest_name = _latest_run_name(app_config)
        payload = {
            "job": None if job is None else job.to_dict(),
            "log_tail": "" if job is None else _tail_file(job.log_file),
            "latest_run_id": latest_name,
        }
        return jsonify(payload)

    @app.post("/api/run")
    def run_api():
        body = request.get_json(silent=True) or {}
        try:
            job = runner.start(
                skip_health_check=bool(body.get("skip_health_check", False)),
            )
            return jsonify({"job": job.to_dict()}), 202
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 409
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/run/stop")
    def stop_api():
        try:
            job = runner.stop()
            return jsonify({"job": job.to_dict()})
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 409

    @app.post("/api/health-check")
    def health_api():
        try:
            health = check_model_server(app_config, timeout=15)
            return jsonify({"ok": True, "health": health})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 502

    @app.get("/api/runs")
    def runs_api():
        latest_name = _latest_run_name(app_config)
        runs = [_run_summary(app_config, run_root, latest_name) for run_root in _list_run_dirs(app_config)]
        return jsonify({"runs": runs, "latest_run_id": latest_name})

    @app.get("/api/runs/<run_id>")
    def run_detail_api(run_id: str):
        try:
            run_root = _run_root(app_config, run_id)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404

        latest_name = _latest_run_name(app_config)
        return jsonify(
            {
                "run": _run_summary(app_config, run_root, latest_name),
                "clusters": _collect_cluster_summaries(run_root),
                "briefs": _brief_summaries(run_root),
            }
        )

    @app.get("/api/runs/<run_id>/clusters/<cluster_id>")
    def cluster_detail_api(run_id: str, cluster_id: str):
        try:
            run_root = _run_root(app_config, run_id)
            safe_cluster_id = _safe_cluster_id(cluster_id)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404

        cluster_dir = run_root / "sources" / safe_cluster_id
        if not cluster_dir.is_dir():
            return jsonify({"error": "Cluster not found."}), 404

        articles = _read_json(cluster_dir / "articles.json", default=[]) or []
        for article in articles:
            full_text = article.get("full_text") or ""
            article["full_text_excerpt"] = full_text[:6000]
            if "full_text" in article:
                del article["full_text"]

        score = _read_json(cluster_dir / "cluster-score.json", default={}) or {}
        summary = _summary_for_file(run_root, safe_cluster_id)
        brief_text = _read_text(_brief_path(run_root, safe_cluster_id))

        return jsonify(
            {
                "cluster_id": safe_cluster_id,
                "cluster_label": _cluster_label(safe_cluster_id),
                "score": score,
                "articles": articles,
                "summary": summary,
                "ta_brief": brief_text,
            }
        )

    @app.get("/api/runs/<run_id>/briefs/<cluster_id>")
    def brief_api(run_id: str, cluster_id: str):
        try:
            run_root = _run_root(app_config, run_id)
            safe_cluster_id = _safe_cluster_id(cluster_id)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404

        path = _brief_path(run_root, safe_cluster_id)
        if not path.exists():
            return jsonify({"error": "Brief not found."}), 404
        return jsonify({"cluster_id": safe_cluster_id, "text": _read_text(path), "path": str(path)})

    @app.get("/api/runs/<run_id>/download")
    def download_run_api(run_id: str):
        try:
            run_root = _run_root(app_config, run_id)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 404

        buffer = BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            for path in sorted(run_root.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(run_root.parent))
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{run_id}.zip",
        )

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local TAsAutomation web console.")
    parser.add_argument("--host", default=os.getenv("TA_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("TA_WEB_PORT", "8765")))
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    app = create_app()
    print(f"TAsAutomation web console: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
