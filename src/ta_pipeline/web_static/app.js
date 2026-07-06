const state = {
  config: null,
  status: null,
  runs: [],
  latestRunId: null,
  selectedRunId: null,
  runDetail: null,
  selectedClusterId: null,
  clusterDetail: null,
  activeTab: "overview",
  wasRunning: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fileName(path) {
  if (!path) return "";
  return String(path).split("/").filter(Boolean).pop() || path;
}

function formatDate(value) {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRunName(run) {
  if (!run) return "No run selected";
  if (run.run_label) return run.run_label;
  return formatDate(run.started_at || run.modified_at || run.run_id);
}

function formatClusterName(value) {
  if (!value) return "Cluster";
  if (typeof value === "object") {
    if (value.cluster_label) return value.cluster_label;
    value = value.cluster_id;
  }
  const match = String(value).match(/cluster_(\d+)/);
  return match ? `Cluster ${match[1]}` : String(value);
}

function scoreClass(score) {
  const numeric = Number(score || 0);
  if (numeric >= 8) return "high";
  if (numeric >= 5) return "mid";
  return "low";
}

function setNotice(message, tone = "info") {
  const notice = $("#notice");
  if (!message) {
    notice.hidden = true;
    notice.textContent = "";
    return;
  }
  notice.hidden = false;
  notice.textContent = message;
  notice.dataset.tone = tone;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function loadConfig() {
  state.config = await api("/api/config");
  renderConfig();
}

async function loadStatus() {
  state.status = await api("/api/status");
  renderStatus();
}

async function loadRuns(preferredRunId = null) {
  const payload = await api("/api/runs");
  state.runs = payload.runs || [];
  state.latestRunId = payload.latest_run_id || null;

  const nextRunId =
    preferredRunId ||
    state.selectedRunId ||
    state.latestRunId ||
    (state.runs[0] ? state.runs[0].run_id : null);

  renderRunList();

  if (nextRunId) {
    await selectRun(nextRunId);
  } else {
    state.selectedRunId = null;
    state.runDetail = null;
    state.clusterDetail = null;
    renderAll();
  }
}

async function selectRun(runId) {
  state.selectedRunId = runId;
  state.clusterDetail = null;
  const detail = await api(`/api/runs/${encodeURIComponent(runId)}`);
  state.runDetail = detail;

  const clusters = detail.clusters || [];
  const selected =
    clusters.find((cluster) => cluster.has_ta_brief) ||
    clusters.find((cluster) => cluster.is_ta_eligible) ||
    clusters[0];
  state.selectedClusterId = selected ? selected.cluster_id : null;

  renderAll();
  if (state.selectedClusterId) {
    await selectCluster(state.selectedClusterId, { keepTab: true });
  }
}

async function selectCluster(clusterId, options = {}) {
  if (!state.selectedRunId || !clusterId) return;
  state.selectedClusterId = clusterId;
  state.clusterDetail = await api(
    `/api/runs/${encodeURIComponent(state.selectedRunId)}/clusters/${encodeURIComponent(clusterId)}`
  );
  renderClusters();
  renderClusterDetail();
  if (!options.keepTab) switchTab("clusters");
}

async function pollStatus() {
  const previousRunning = state.wasRunning;
  try {
    await loadStatus();
    const running = Boolean(state.status?.job?.running);
    if (previousRunning && !running) {
      await loadRuns(state.status.latest_run_id || state.latestRunId);
    }
    state.wasRunning = running;
  } catch (error) {
    setNotice(error.message, "error");
  }
}

function renderStatus() {
  const job = state.status?.job;
  const running = Boolean(job?.running);
  const status = job?.status || "idle";

  const jobPill = $("#job-pill");
  jobPill.textContent = status[0].toUpperCase() + status.slice(1);
  jobPill.className = "status-pill muted";
  if (status === "completed") jobPill.className = "status-pill ok";
  if (status === "failed" || status === "stopped") jobPill.className = "status-pill bad";
  if (running) jobPill.className = "status-pill";

  $("#start-run-button").disabled = running;
  $("#stop-run-button").disabled = !running;
  $("#job-started").textContent = job?.started_at ? formatDate(job.started_at) : "Not running";
  $("#job-output").textContent = job?.run_root || state.status?.latest_run_id || "No active output";
  $("#log-view").textContent = state.status?.log_tail || "No active run.";
  $("#log-file-label").textContent = job?.log_file ? fileName(job.log_file) : "No active log";
}

function renderConfig() {
  if (!state.config) return;
  const rows = [
    ["Model", state.config.model_id],
    ["Endpoint", state.config.base_url],
    ["Storage", state.config.storage_root],
    ["Lookback", `${state.config.lookback_days} days`],
    ["Security", state.config.security_enabled ? "Enabled" : "Disabled"],
    ["Serper", state.config.serper_api_key_present ? "Configured" : "Disabled"],
    ["Feed limit", state.config.max_articles_per_feed || "All recent"],
  ];

  $("#config-list").innerHTML = rows
    .map(
      ([label, value]) => `
        <div>
          <dt>${escapeHTML(label)}</dt>
          <dd>${escapeHTML(value)}</dd>
        </div>
      `
    )
    .join("");
}

function renderRunList() {
  const container = $("#run-list");
  if (!state.runs.length) {
    container.innerHTML = `<div class="empty-state">No runs found.</div>`;
    return;
  }

  container.innerHTML = state.runs
    .map((run) => {
      const active = run.run_id === state.selectedRunId ? "active" : "";
      const latest = run.is_latest ? " · Latest" : "";
      return `
        <button class="run-item ${active}" data-run-id="${escapeHTML(run.run_id)}" type="button">
          <strong>${escapeHTML(formatRunName(run))}${latest}</strong>
          <span>${run.cluster_count} clusters · ${run.brief_count} briefs</span>
        </button>
      `;
    })
    .join("");

  $$(".run-item").forEach((button) => {
    button.addEventListener("click", () => selectRun(button.dataset.runId));
  });
}

function renderMetrics() {
  const run = state.runDetail?.run;
  $("#metric-articles").textContent = run?.article_count ?? 0;
  $("#metric-clusters").textContent = run?.cluster_count ?? 0;
  $("#metric-eligible").textContent = run?.ta_eligible_count ?? 0;
  $("#metric-briefs").textContent = run?.brief_count ?? 0;
}

function renderOverview() {
  const run = state.runDetail?.run;
  $("#overview-run-title").textContent = run
    ? `${formatRunName(run)}${run.is_latest ? " · Latest" : ""}`
    : "No run selected";
  $("#overview-run-path").textContent = run?.path || "Select a run.";
  $("#overview-top-cluster").textContent = run?.top_cluster_id
    ? `${formatClusterName(run.top_cluster_label || run.top_cluster_id)}: ${run.top_headline || "No headline"}`
    : "No scored clusters yet.";
  $("#overview-modified").textContent = formatDate(run?.modified_at);

  const download = $("#download-run-link");
  if (run?.run_id) {
    download.href = `/api/runs/${encodeURIComponent(run.run_id)}/download`;
    download.setAttribute("aria-disabled", "false");
  } else {
    download.href = "#";
    download.setAttribute("aria-disabled", "true");
  }

  renderSelectedOutputs();
}

function renderSelectedOutputs() {
  const container = $("#selected-output-grid");
  const briefs = state.runDetail?.briefs || [];
  if (!briefs.length) {
    container.innerHTML = `<div class="empty-state">No TA briefs were generated for this run.</div>`;
    return;
  }

  container.innerHTML = briefs
    .map(
      (brief) => `
        <article class="output-item">
          <h3>${escapeHTML(brief.title)}</h3>
          <p>${escapeHTML(formatClusterName(brief))}${brief.priority ? ` · ${escapeHTML(brief.priority)}` : ""}</p>
          <div class="button-row" style="margin-top: 12px;">
            <button class="button secondary" data-open-cluster="${escapeHTML(brief.cluster_id)}" type="button">Open Cluster</button>
            <button class="button ghost" data-copy-brief="${escapeHTML(brief.cluster_id)}" type="button">Copy Brief</button>
          </div>
        </article>
      `
    )
    .join("");

  bindBriefActions();
}

function filteredClusters() {
  const clusters = state.runDetail?.clusters || [];
  const query = $("#cluster-search")?.value.trim().toLowerCase() || "";
  const eligibleOnly = Boolean($("#eligible-only")?.checked);

  return clusters.filter((cluster) => {
    if (eligibleOnly && !cluster.is_ta_eligible) return false;
    if (!query) return true;
    const haystack = [
      cluster.cluster_id,
      cluster.cluster_label,
      cluster.headline,
      cluster.top_title,
      cluster.top_source,
      cluster.priority,
      cluster.ta_eligibility_reason,
      ...(cluster.cves || []),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function renderClusters() {
  const body = $("#cluster-table-body");
  const clusters = filteredClusters();

  if (!clusters.length) {
    body.innerHTML = `
      <tr>
        <td colspan="5">
          <div class="empty-state">No clusters match the current view.</div>
        </td>
      </tr>
    `;
    return;
  }

  body.innerHTML = clusters
    .map((cluster) => {
      const score = cluster.overall_importance_score ?? "-";
      const active = cluster.cluster_id === state.selectedClusterId ? "active" : "";
      const title = cluster.headline || cluster.top_title || "Untitled cluster";
      const eligibility = cluster.is_ta_eligible ? "Eligible" : "Not eligible";
      return `
        <tr class="${active}" data-cluster-id="${escapeHTML(cluster.cluster_id)}">
          <td>
            <span class="cluster-title">${escapeHTML(formatClusterName(cluster))}</span>
            <span class="cluster-subtitle">${escapeHTML(cluster.most_recent_incident || "No incident date")}</span>
          </td>
          <td><span class="score-badge ${scoreClass(score)}">${escapeHTML(score)}</span></td>
          <td>${escapeHTML(eligibility)}</td>
          <td>${cluster.article_count}</td>
          <td>
            <span class="cluster-title">${escapeHTML(title)}</span>
            <span class="cluster-subtitle">${escapeHTML((cluster.cves || []).slice(0, 4).join(", ") || cluster.top_source || "No CVEs listed")}</span>
          </td>
        </tr>
      `;
    })
    .join("");

  $$("#cluster-table-body tr[data-cluster-id]").forEach((row) => {
    row.addEventListener("click", () => selectCluster(row.dataset.clusterId));
  });
}

function scoreMeter(label, value) {
  const numeric = Math.max(0, Math.min(10, Number(value || 0)));
  return `
    <div class="score-row">
      <span><b>${escapeHTML(label)}</b><b>${numeric || "-"}/10</b></span>
      <div class="meter"><div style="width: ${numeric * 10}%"></div></div>
    </div>
  `;
}

function renderClusterDetail() {
  const container = $("#cluster-detail");
  const detail = state.clusterDetail;
  if (!detail) {
    container.innerHTML = `<div class="empty-state">Select a cluster to inspect scores, evidence, summary, and TA brief.</div>`;
    return;
  }

  const score = detail.score || {};
  const summary = detail.summary || {};
  const articles = detail.articles || [];
  const title = summary.headline || articles[0]?.title || detail.cluster_id;
  const detailLabel = formatClusterName(detail);
  const signals = score.key_signals || [];
  const takeaways = summary.key_takeaways || [];

  container.innerHTML = `
    <h2 class="detail-title">${escapeHTML(title)}</h2>
    <p class="detail-subtitle">${escapeHTML(detailLabel)} · ${escapeHTML(summary.priority || "No priority")} · ${articles.length} articles</p>

    <div class="score-grid">
      ${scoreMeter("Overall", score.overall_importance_score)}
      ${scoreMeter("Severity", score.severity_score)}
      ${scoreMeter("Urgency", score.urgency_score)}
      ${scoreMeter("Business", score.business_impact_score)}
    </div>

    <h3 class="section-title">TA Eligibility</h3>
    <p>${score.is_ta_eligible ? "Eligible" : "Not eligible"}: ${escapeHTML(score.ta_eligibility_reason || "No reason recorded.")}</p>

    <h3 class="section-title">Rationale</h3>
    <p>${escapeHTML(score.rationale || "No rationale recorded.")}</p>

    <h3 class="section-title">Key Signals</h3>
    ${signals.length ? `<ul class="plain-list">${signals.map((item) => `<li>${escapeHTML(item)}</li>`).join("")}</ul>` : "<p>No key signals recorded.</p>"}

    <h3 class="section-title">Executive Summary</h3>
    ${
      Object.keys(summary).length
        ? `
          <p>${escapeHTML(summary.executive_summary || "")}</p>
          <p><b>Why it matters:</b> ${escapeHTML(summary.why_it_matters || "")}</p>
          ${takeaways.length ? `<ul class="plain-list">${takeaways.map((item) => `<li>${escapeHTML(item)}</li>`).join("")}</ul>` : ""}
        `
        : "<p>No executive summary was generated for this cluster.</p>"
    }

    <h3 class="section-title">TA Brief</h3>
    ${
      detail.ta_brief
        ? `<pre class="brief-preview">${escapeHTML(detail.ta_brief)}</pre>
           <button class="button ghost" data-copy-current-brief type="button">Copy Brief</button>`
        : "<p>No TA brief was generated for this cluster.</p>"
    }

    <h3 class="section-title">Articles</h3>
    <div class="article-list">
      ${articles
        .map(
          (article) => `
            <article class="article-item">
              <a href="${escapeHTML(article.url || article.link || "#")}" target="_blank" rel="noreferrer">${escapeHTML(article.title || "Untitled article")}</a>
              <div class="cluster-subtitle">${escapeHTML(article.source || "Unknown source")} · ${escapeHTML(article.published || "No date")}</div>
              <p>${escapeHTML(article.summary || article.full_text_excerpt || "No summary available.")}</p>
              ${
                article.cves?.length
                  ? `<div class="tag-row">${article.cves.map((cve) => `<span class="tag">${escapeHTML(cve)}</span>`).join("")}</div>`
                  : ""
              }
            </article>
          `
        )
        .join("")}
    </div>
  `;

  const copyButton = container.querySelector("[data-copy-current-brief]");
  if (copyButton) {
    copyButton.addEventListener("click", () => copyText(detail.ta_brief, "TA brief copied."));
  }
}

function renderBriefs() {
  const container = $("#brief-grid");
  const briefs = state.runDetail?.briefs || [];

  if (!briefs.length) {
    container.innerHTML = `<div class="empty-state">No TA briefs are available for this run.</div>`;
    return;
  }

  container.innerHTML = briefs
    .map(
      (brief) => `
        <article class="brief-card">
          <h3>${escapeHTML(brief.title)}</h3>
          <p>${escapeHTML(formatClusterName(brief))}${brief.priority ? ` · ${escapeHTML(brief.priority)}` : ""}</p>
          <pre>${escapeHTML(brief.preview)}${brief.preview.length >= 700 ? "\n..." : ""}</pre>
          <div class="button-row">
            <button class="button secondary" data-open-cluster="${escapeHTML(brief.cluster_id)}" type="button">Open Cluster</button>
            <button class="button ghost" data-copy-brief="${escapeHTML(brief.cluster_id)}" type="button">Copy Brief</button>
          </div>
        </article>
      `
    )
    .join("");

  bindBriefActions();
}

function bindBriefActions() {
  $$("[data-open-cluster]").forEach((button) => {
    button.addEventListener("click", () => selectCluster(button.dataset.openCluster));
  });
  $$("[data-copy-brief]").forEach((button) => {
    button.addEventListener("click", () => copyBrief(button.dataset.copyBrief));
  });
}

async function copyBrief(clusterId) {
  if (!state.selectedRunId) return;
  const payload = await api(
    `/api/runs/${encodeURIComponent(state.selectedRunId)}/briefs/${encodeURIComponent(clusterId)}`
  );
  await copyText(payload.text || "", "TA brief copied.");
}

async function copyText(text, successMessage) {
  try {
    await navigator.clipboard.writeText(text);
    setNotice(successMessage);
  } catch {
    setNotice("The browser blocked clipboard access.", "error");
  }
}

function renderAll() {
  renderRunList();
  renderMetrics();
  renderOverview();
  renderClusters();
  renderBriefs();
  renderClusterDetail();
}

function switchTab(tabName) {
  state.activeTab = tabName;
  $$(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === tabName);
  });
  $$(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${tabName}`);
  });
}

async function startRun() {
  setNotice("");
  const skipHealth = $("#skip-health").checked;

  try {
    const payload = await api("/api/run", {
      method: "POST",
      body: JSON.stringify({
        skip_health_check: skipHealth,
      }),
    });
    state.status = { job: payload.job, log_tail: "", latest_run_id: state.latestRunId };
    state.wasRunning = true;
    renderStatus();
    switchTab("logs");
  } catch (error) {
    setNotice(error.message, "error");
  }
}

async function stopRun() {
  try {
    const payload = await api("/api/run/stop", { method: "POST" });
    state.status = { ...state.status, job: payload.job };
    renderStatus();
  } catch (error) {
    setNotice(error.message, "error");
  }
}

async function checkHealth() {
  const button = $("#health-button");
  const pill = $("#model-pill");
  button.disabled = true;
  pill.textContent = "Checking model";
  pill.className = "status-pill";

  try {
    await api("/api/health-check", { method: "POST" });
    pill.textContent = "Model reachable";
    pill.className = "status-pill ok";
  } catch (error) {
    pill.textContent = "Model offline";
    pill.className = "status-pill bad";
    setNotice(error.message, "error");
  } finally {
    button.disabled = false;
  }
}

function bindEvents() {
  $("#start-run-button").addEventListener("click", startRun);
  $("#stop-run-button").addEventListener("click", stopRun);
  $("#health-button").addEventListener("click", checkHealth);
  $("#refresh-button").addEventListener("click", () => loadRuns(state.selectedRunId));
  $("#cluster-search").addEventListener("input", renderClusters);
  $("#eligible-only").addEventListener("change", renderClusters);
  $$(".tab").forEach((tab) => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  });
}

async function boot() {
  bindEvents();
  try {
    await Promise.all([loadConfig(), loadStatus()]);
    await loadRuns();
  } catch (error) {
    setNotice(error.message, "error");
  }
  setInterval(pollStatus, 3000);
}

document.addEventListener("DOMContentLoaded", boot);
