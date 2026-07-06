# TAsAutomation

Local-first threat advisory automation for collecting cybersecurity reporting, clustering related stories, scoring them with a local OpenAI-compatible model, and generating executive summaries plus Threat Advisory briefs.

Everything runs on the host machine. Model access, run artifacts, logs, and the team web console are local by default.

## What It Does

- Pulls recent cybersecurity articles from configured RSS feeds.
- Optionally expands stories with Serper web search when enabled.
- Embeds and clusters related reporting.
- Scores every cluster with the configured local model.
- Selects the top TA-eligible clusters.
- Generates executive summaries and TA prep briefs.
- Serves a local web console for manual runs, logs, results, brief copy, and ZIP downloads.
- Installs an optional weekly cron run for Sunday at 10:00 PM Eastern time.

## Project Layout

```text
.
|-- .env.example
|-- .github/workflows/ci.yml
|-- CONTRIBUTING.md
|-- SECURITY.md
|-- docs/
|-- pyproject.toml
|-- requirements.txt
|-- requirements-dev.txt
|-- scripts/
|-- src/
|   |-- content_pipeline/
|   `-- ta_pipeline/
`-- tests/
```

## Setup

Create the local environment file:

```bash
cp .env.example .env.local
```

Edit `.env.local` for this machine:

- `TA_STORAGE_ROOT`: local output folder, usually `./storage`
- `TA_BASE_URL`: OpenAI-compatible model server URL, ending in `/v1`
- `TA_MODEL_ID`: local model identifier or model path
- `TA_MODEL_API_KEY`: key expected by the local model server
- `SERPER_API_KEY`: only required when `TA_EXPAND_FEED_TOPICS_WITH_SERPER=true`
- `TA_WEB_USERNAME` and `TA_WEB_PASSWORD`: optional browser Basic Auth

Install dependencies:

```bash
./scripts/setup_local_env.sh
```

## Running

Start the team web console:

```bash
./scripts/run_web_ui.sh
```

The console binds to `0.0.0.0:8765` by default so teammates on the same network can open:

```text
http://<this-machine-ip>:8765
```

Run the full pipeline from the terminal:

```bash
./scripts/run_full_pipeline.sh
```

Check model health only:

```bash
.venv/bin/python -m ta_pipeline --mode health --print-config
```

Manual execution currently supports only the full pipeline and health check:

```bash
PYTHONPATH=src .venv/bin/python -m ta_pipeline --mode full --print-config
```

## Weekly Schedule

Install or refresh the managed cron entry:

```bash
./scripts/install_weekly_cron.sh
```

The cron job runs every Sunday at `10:00 PM America/New_York` and writes logs under `logs/`. A lock file prevents overlapping scheduled and manual runs.

## Outputs

Each run is written locally under:

```text
${TA_STORAGE_ROOT}/runs/<timestamp>/
```

The web console shows readable run names, cluster labels, live logs, selected outputs, cluster details, generated summaries, TA briefs, and per-run ZIP downloads. All outputs stay on this machine.

## Development

Run tests:

```bash
make test
```

Run CI-equivalent tests locally:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests
```

## Publishing To GitHub

Before pushing or making the repository public:

- Confirm that `.env.local`, `.venv/`, `storage/`, `logs/`, `.pipeline.lock`, and `vllm_models/` are not staged.
- Keep generated run output and model files out of commits.
- Run `make test`.
- Choose and add a license if this repository will be open source. Without a license, the code is visible but not explicitly reusable.
- Review `SECURITY.md` for how sensitive issues should be reported.

## Team Demo Doc

A full teammate-facing design and demo guide is available at:

```text
docs/team_demo_design_doc.md
```
