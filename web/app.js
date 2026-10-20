const state = { dashboard: null, latestResearch: null, evaluation: null };
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
const pct = (value) => value === null || value === undefined ? "—" : `${Number(value).toFixed(2)}%`;
const safeHttpUrl = (value) => {
  if (typeof value !== "string" || !value.trim()) return "";
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : "";
  } catch { return ""; }
};
const metricIcons = [
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h4l3-8 4 16 3-8h4"/></svg>',
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V11M10 20V5M16 20v-7M22 20H2"/></svg>',
  '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8 8 8 8m0-8-8 8"/></svg>',
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h12a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z"/><path d="M5 17a2 2 0 0 1 2-2h12"/></svg>',
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/></svg>'
];

function showView(id) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === id));
  document.querySelectorAll(".nav-link").forEach((link) => link.classList.toggle("active", link.hash === `#${id}`));
  if (id === "evaluation" && !state.evaluation) loadEvaluation();
  if (id === "sources") loadSources();
}

window.addEventListener("hashchange", () => showView(location.hash.slice(1) || "dashboard"));
document.querySelectorAll("a[href^='#']").forEach((link) => link.addEventListener("click", () => setTimeout(() => showView(location.hash.slice(1)), 0)));
async function getJson(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(url, { ...options, cache: "no-store", signal: controller.signal });
    let payload;
    try { payload = await response.json(); }
    catch { throw new Error("The local server returned an invalid response. Restart it and try again."); }
    if (!response.ok) throw new Error(payload.error || `The server returned HTTP ${response.status}.`);
    return payload;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The Python server did not respond within 10 seconds.");
    if (error instanceof TypeError) throw new Error("Cannot reach the Python backend. Run website.py from the project folder and open https://localhost:8443.");
    throw error;
  } finally { clearTimeout(timer); }
}

async function loadDashboard() {
  try {
    state.dashboard = await getJson("/api/dashboard");
    const data = state.dashboard;
    $("#research-status").textContent = data.research_status;
    const metrics = data.evaluation?.metrics || {};
    const evaluationLabel = data.evaluation?.label || "No saved evaluation records";
    const statusTitle = $("#research-status-title");
    if (statusTitle) statusTitle.textContent = `Research status: ${evaluationLabel}`;
    const cards = [
      ["VERIFICATION ON · HALLUCINATION RATE", pct(metrics.on?.hallucination_rate_percent), evaluationLabel],
      ["VERIFICATION OFF · HALLUCINATION RATE", pct(metrics.off?.hallucination_rate_percent), evaluationLabel],
      ["UNSUPPORTED CLAIMS BLOCKED", metrics.on?.blocked_claim_count ?? "—", "In saved ON condition"],
      ["REGISTERED SOURCE DOCUMENTS", data.source_count, "From sources.csv"],
      ["EVALUATION QUESTIONS", data.evaluation?.question_count ?? 0, "Same saved set in OFF and ON"]
    ];
    $("#dashboard-metrics").innerHTML = cards.map(([label, value, foot], i) => `<article class="metric-card"><span class="metric-icon">${metricIcons[i]}</span><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value)}</div><div class="metric-foot">${esc(foot)}</div></article>`).join("");
    const descriptions = [
      "Registers documents and provenance after successful import.",
      "Extracts paragraphs and retains source IDs and PDF pages.",
      "Deterministic Decimal calculations and evaluation metrics.",
      "Checks claim support, labels conflicts, and blocks when ON.",
      "Browser interface, saved evaluation, and report annexure."
    ];
    $("#layers").innerHTML = data.layers.map((name, i) => `<article class="layer-card"><div class="layer-no">L${i + 1} · ${["INGEST", "EXTRACT", "ENGINE", "COMMENTARY", "OUTPUT"][i]}</div><h3>${esc(name)}</h3><p>${descriptions[i]}</p></article>`).join("");
    const disclosure = $("#report-disclosure-text");
    if (disclosure) {
      disclosure.textContent = evaluationLabel.includes("SYNTHETIC")
        ? `This annexure includes synthetic controlled records (${data.evaluation?.question_count ?? 0} evaluation question); it is not empirical research or a real-company filing.`
        : `Saved evaluation label: ${evaluationLabel}. Review the report's source provenance and limitations before interpreting its results.`;
    }
  } catch (error) {
    $("#research-status").textContent = error.message;
    $("#dashboard-metrics").innerHTML = `<div class="result-banner warning" role="alert">Dashboard data unavailable. ${esc(error.message)}</div>`;
    $("#layers").innerHTML = '<div class="result-banner warning">Start the Python website server to load live project status and the five-layer overview.</div>';
    const disclosure = $("#report-disclosure-text");
    if (disclosure) disclosure.textContent = "Evaluation label unavailable because the Python dashboard could not be loaded.";
  }
}

function renderResearch(result) {
  state.latestResearch = result;
  const modeLabel = result.passages?.some((passage) => passage.source_id === "synthetic-demo" || passage.synthetic === "true") ? "SYNTHETIC DEMONSTRATION" : "REGISTERED CORPUS";
  const bannerClass = modeLabel.startsWith("SYNTHETIC") ? "result-banner warning" : "result-banner";
  const banner = `<div class="result-question"><span>RESEARCH QUESTION</span><p>${esc(result.question)}</p></div><div class="${bannerClass}"><b>${modeLabel}</b> · Verification ${result.condition.toUpperCase()} · ${result.blocked_claim_count} claim(s) blocked. ${esc(result.answer)}</div>`;
  const claims = (result.claims || []).map((claim) => {
    const status = claim.evidence_status || "unsupported";
    const citations = (claim.citations || []).map((citation) => {
      const passage = (result.passages || []).find((item) => item.source_id === citation.source_id && (item.text || "").includes(citation.quote || ""));
      return `<div class="citation"><small>CITATION · SOURCE ${esc(citation.source_id)}${passage?.page ? ` · PAGE ${esc(passage.page)}` : ""}${passage?.publisher ? ` · ${esc(passage.publisher)}` : ""}</small><p>${esc(citation.quote)}</p></div>`;
    }).join("");
    return `<article class="claim-card"><div class="claim-top"><span class="pill pill-${esc(status)}">${esc(status)}</span>${claim.blocked ? '<span class="pill pill-blocked">BLOCKED</span>' : ""}</div><div class="claim-text">${esc(claim.text)}</div><div class="claim-reason">Verifier reason: ${esc(claim.reason)}</div>${citations || '<div class="claim-reason">No citation attached to this claim.</div>'}</article>`;
  }).join("");
  const passages = (result.passages || []).map((passage) => { const sourceUrl = safeHttpUrl(passage.source_url); return `<article class="passage-card"><header><span>${esc(passage.title)} · ${esc(passage.source_id)}</span><span>${passage.page ? `PAGE ${esc(passage.page)}` : "PAGE N/A"}</span></header><div class="passage-meta">${esc(passage.publisher || "Publisher not recorded")}${passage.published_on ? ` · Published ${esc(passage.published_on)}` : ""}${passage.retrieved_at_utc ? ` · Retrieved ${esc(passage.retrieved_at_utc)}` : ""}${sourceUrl ? ` · <a href="${esc(sourceUrl)}" target="_blank" rel="noreferrer">Source URL</a>` : ""}</div><p>${esc(passage.text)}</p>${(passage.source_id === "synthetic-demo" || passage.synthetic === "true") ? '<small class="pill pill-unsupported">SYNTHETIC — NOT A REAL FILING</small>' : ""}</article>`; }).join("");
  const html = `${banner}<div class="result-heading"><h2>Claim review</h2><span class="subtle">${(result.claims || []).length} proposed claims</span></div>${claims || '<div class="empty-state compact"><strong>No claims were produced.</strong><span>The current workflow may have found no registered passages for this question.</span></div>'}<div class="result-heading"><h2>Retrieved evidence</h2><span class="subtle">${(result.passages || []).length} passage(s)</span></div>${passages || '<div class="empty-state compact"><strong>No evidence passages retrieved</strong><span>Register and extract a source document, then ask a question using its content.</span></div>'}`;
  $("#research-result").className = "result-area";
  $("#research-result").innerHTML = html;
  $("#evidence-result").className = "result-area";
  $("#evidence-result").innerHTML = html;
}

$("#research-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "Running local verification…";
  $("#research-result").className = "result-area empty-state";
  $("#research-result").innerHTML = '<strong>Running existing Python workflow…</strong><span>Retrieval and claim verification are performed locally.</span>';
  try {
    const result = await getJsonPost({ question: $("#question").value, verify: $("#verification-mode").value === "on", mode: $("#source-mode").value });
    renderResearch(result);
  } catch (error) {
    $("#research-result").className = "result-area result-banner warning";
    $("#research-result").textContent = error.message;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Run verification <span>→</span>';
  }
});

async function getJsonPost(payload) {
  return getJson("/api/research", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
}

async function loadEvaluation() {
  try {
    const experiment = await getJson("/api/evaluation");
    state.evaluation = experiment;
    $("#eval-method-label").textContent = experiment.label || "Evaluation label unavailable";
    const syntheticLabel = String(experiment.label || "").includes("SYNTHETIC");
    $("#eval-method-detail").textContent = `${experiment.question_set.length} saved question(s); OFF and ON use the same evidence. ${syntheticLabel ? "Evidence is synthetic controlled data, not financial filings. " : "Evidence is from the saved local corpus. "}No live model is connected.`;
    const metrics = experiment.metrics;
    const labels = [["hallucination_rate_percent", "Hallucination rate"], ["citation_coverage_percent", "Citation coverage"], ["claim_support_rate_percent", "Claim support rate"], ["hallucinated_output_claims", "Hallucinated outputs (count)"], ["cited_claim_count", "Cited claims (count)"], ["supported_claim_count", "Supported claims (count)"], ["unsupported_claim_count", "Unsupported claims (count)"], ["contradicted_claim_count", "Contradicted claims (count)"], ["blocked_claim_count", "Blocked claims (count)"], ["total_evaluated_claims", "Evaluated claims (denominator)"]];
    $("#evaluation-cards").innerHTML = ["off", "on"].map((condition) => `<article class="evaluation-card ${condition}"><h2>Verification ${condition.toUpperCase()}</h2><p>Recalculated by engine · ${esc(experiment.label)}</p><div class="eval-metrics">${labels.map(([key, label]) => `<div class="eval-metric"><span>${label}</span><strong>${key.endsWith("percent") ? pct(metrics[condition][key]) : esc(metrics[condition][key])}</strong></div>`).join("")}</div></article>`).join("");
    const absolute = metrics.comparison.absolute_reduction_percentage_points;
    const relative = metrics.comparison.relative_reduction_percent;
    $("#comparison-summary").innerHTML = `<div><b>Calculated difference in the ${syntheticLabel ? "synthetic controlled demonstration" : "local-corpus rules evaluation"}</b><br><span>Not an estimate of empirical LLM or real-world performance.</span></div><div><strong>${absolute === null ? "—" : `${Number(absolute).toFixed(2)} pp`}</strong><br>absolute reduction</div><div><strong>${pct(relative)}</strong><br>relative reduction</div>`;
    const rateOff = metrics.off.hallucination_rate_percent;
    const rateOn = metrics.on.hallucination_rate_percent;
    $("#comparison-chart").innerHTML = [["OFF", rateOff, "off"], ["ON", rateOn, "on"]].map(([label, value, tone]) => {
      const width = value === null ? 0 : Math.max(0, Math.min(100, Number(value)));
      return `<div class="chart-row"><span>Verification ${label}</span><div class="chart-track"><div class="chart-bar ${tone}" style="width:${width}%"></div></div><b>${pct(value)}</b></div>`;
    }).join("");
    $("#evaluation-table tbody").innerHTML = labels.map(([key, label]) => `<tr><th scope="row">${esc(label)}</th><td>${key.endsWith("percent") ? pct(metrics.off[key]) : esc(metrics.off[key])}</td><td>${key.endsWith("percent") ? pct(metrics.on[key]) : esc(metrics.on[key])}</td></tr>`).join("");
    $("#evaluation-details").innerHTML = experiment.question_set.map((question) => {
      const runs = experiment.runs.filter((run) => run.question === question);
      const runCards = runs.map((run) => {
        const claims = run.claims.map((claim) => `<div class="eval-claim"><p class="${claim.blocked ? "blocked-text" : ""}"><span class="pill pill-${esc(claim.evidence_status)}">${esc(claim.evidence_status)}</span> ${claim.blocked ? "BLOCKED · " : ""}${esc(claim.text)}</p><div class="claim-reason">${esc(claim.reason)}</div>${(claim.citations || []).map((citation) => `<div class="citation"><small>CITATION · SOURCE ${esc(citation.source_id)}</small><p>${esc(citation.quote)}</p></div>`).join("") || '<div class="claim-reason">No citation attached to this proposal.</div>'}</div>`).join("");
        const evidence = (run.passages || []).map((passage) => {
          const synthetic = passage.source_id === "synthetic-demo" || passage.synthetic === "true";
          const sourceUrl = safeHttpUrl(passage.source_url);
          return `<div class="citation"><small>EVIDENCE · SOURCE ${esc(passage.source_id)}${passage.page ? ` · PAGE ${esc(passage.page)}` : ""}${synthetic ? " · SYNTHETIC — NOT A REAL FILING" : ""}</small><p>${esc(passage.text)}</p>${sourceUrl ? `<a href="${esc(sourceUrl)}" target="_blank" rel="noreferrer">Open source</a>` : ""}</div>`;
        }).join("") || '<div class="claim-reason">No evidence passages retrieved for this question.</div>';
        return `<article class="eval-run-card"><header><span>VERIFICATION ${run.condition.toUpperCase()}</span><span>${run.blocked_claim_count} BLOCKED</span></header><p>${esc(run.answer)}</p>${claims}<h4>Evidence passages</h4>${evidence}</article>`;
      }).join("");
      return `<div class="eval-question">${esc(question)}</div><div class="eval-run">${runCards}</div>`;
    }).join("");
  } catch (error) {
    $("#evaluation-cards").innerHTML = `<div class="result-banner warning">Evaluation could not be loaded: ${esc(error.message)}</div>`;
    $("#comparison-chart").innerHTML = `<div class="result-banner warning">Calculated chart unavailable: ${esc(error.message)}</div>`;
    $("#comparison-summary").textContent = "Evaluation comparison unavailable.";
    $("#evaluation-details").innerHTML = `<div class="result-banner warning">Question and evidence details unavailable: ${esc(error.message)}</div>`;
  }
}

async function loadSources() {
  try {
    const { sources } = await getJson("/api/sources");
    $("#source-count").textContent = sources.length;
    $("#source-list").innerHTML = sources.map((source) => { const sourceUrl = safeHttpUrl(source.source_url); return `<article class="source-card"><h3>${esc(source.title)} ${source.synthetic === "true" ? '<span class="pill pill-unsupported">SYNTHETIC</span>' : ""}</h3><div class="source-meta">${[["SOURCE ID", source.source_id], ["PUBLISHER", source.publisher], ["PUBLISHED ON", source.published_on], ["PERIOD", source.reporting_period], ["ORIGIN", source.origin], ["RETRIEVED UTC", source.retrieved_at_utc || "Not applicable / not recorded"], ["RECORDED UTC", source.recorded_at_utc], ["SHA-256", source.sha256]].map(([label, value]) => `<span>${label}<b>${esc(value || "Not recorded")}</b></span>`).join("")}</div>${sourceUrl ? `<p><a href="${esc(sourceUrl)}" target="_blank" rel="noreferrer">Open source URL ↗</a></p>` : ""}</article>`; }).join("");
    $("#source-empty").hidden = sources.length > 0;
  } catch (error) {
    $("#source-empty").hidden = true;
    $("#source-list").innerHTML = `<div class="result-banner warning">Source registry could not be loaded: ${esc(error.message)}</div>`;
  }
}

loadDashboard();
if (location.hash) showView(location.hash.slice(1));
