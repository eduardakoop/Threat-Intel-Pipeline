# TAsAutomation Team Demo Guide

This guide is a short operator-facing walkthrough for demonstrating the local Threat Advisory workflow.

## Demo Goal

Show how the project collects recent cybersecurity reporting, groups related stories, scores clusters, and produces executive summaries plus Threat Advisory prep briefs without sending run artifacts to a hosted service.

## Prerequisites

- `.env.local` exists and points to a reachable OpenAI-compatible model server.
- `TA_STORAGE_ROOT` points to a local folder, usually `./storage`.
- Dependencies are installed with `./scripts/setup_local_env.sh`.
- Optional: `SERPER_API_KEY` is configured only if `TA_EXPAND_FEED_TOPICS_WITH_SERPER=true`.
- Optional: `TA_WEB_USERNAME` and `TA_WEB_PASSWORD` are set when sharing the console on a team network.

## Suggested Demo Flow

1. Start the web console:

   ```bash
   ./scripts/run_web_ui.sh
   ```

2. Open the local URL printed by the script.
3. Use **Check Model** to verify the configured model endpoint.
4. Start a full pipeline run.
5. Watch live logs from the console while the pipeline fetches articles, builds clusters, scores them, and writes outputs.
6. Open the newest run and review the overview metrics.
7. Inspect the cluster table, including scores, TA eligibility, article evidence, and CVEs.
8. Open the TA Briefs tab and review generated brief text.
9. Download the per-run ZIP if the team needs to archive or share that run internally.

## Files Created During a Demo

Each run writes to:

```text
${TA_STORAGE_ROOT}/runs/<timestamp>/
```

Important outputs:

- `sources/articles.json`: all collected source articles for the run.
- `sources/cluster_*/articles.json`: article evidence for each saved cluster.
- `sources/cluster_*/cluster-score.json`: model score plus TA eligibility enrichment.
- `executive-summaries/summary_cluster_*.json`: executive summary payloads.
- `TA-briefs/TA-brief_cluster_*.txt`: formatted Threat Advisory prep briefs.

## Privacy Notes

Generated runs, logs, local env files, and local model directories are intentionally ignored by git. Do not copy those artifacts into the repository unless they have been reviewed and approved for sharing.
