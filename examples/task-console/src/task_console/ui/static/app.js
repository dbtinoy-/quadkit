"use strict";
const $ = (id) => document.getElementById(id);
function esc(value) { const el = document.createElement("span"); el.textContent = String(value ?? ""); return el.innerHTML; }
async function read(response) { const data = await response.json().catch(() => ({})); if (!response.ok || data.error || data.detail) throw new Error(data.detail || (data.error && data.error.message) || data.error || `HTTP ${response.status}`); return data; }

async function enqueue(event) {
  event.preventDefault();
  const task = $("task-select").value;
  const raw = $("task-kwargs").value.trim();
  let kwargs = {};
  if (raw) {
    try { kwargs = JSON.parse(raw); } catch (error) { $("enqueue-result").textContent = `Invalid kwargs JSON: ${error.message}`; return; }
  }
  const priority = parseInt($("task-priority").value, 10) || 5;
  try {
    const entry = await read(await fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task, kwargs, priority }),
    }));
    $("enqueue-result").textContent = `Enqueued ${entry.name} — job id ${entry.id}`;
    await loadSubmitted();
    await loadHealth();
  } catch (error) { $("enqueue-result").textContent = error.message; }
}

async function loadHealth() {
  try {
    const data = await read(await fetch("/api/tasks/health", { cache: "no-store" }));
    $("health").innerHTML = `<span class="status ${data.status === "healthy" ? "ok" : "warning"}">${esc(data.status)}</span> <span class="pill">submitted: ${esc(data.details?.submitted_count)}</span> <span class="pill">dlq: ${esc(data.details?.dlq_count)}</span>`;
  } catch (error) { $("health").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

async function loadWorkers() {
  try {
    const s = await read(await fetch("/api/tasks/workers", { cache: "no-store" }));
    $("workers").innerHTML = `<span class="pill">pool size: ${esc(s.pool_size)}</span> <span class="pill">active: ${esc(s.active_workers)}</span> <span class="pill">processed: ${esc(s.total_jobs_processed)}</span> <span class="pill">succeeded: ${esc(s.total_jobs_succeeded)}</span> <span class="pill">failed: ${esc(s.total_jobs_failed)}</span> <span class="pill">avg: ${esc(Math.round((s.average_processing_time || 0) * 1000))}ms</span>`;
  } catch (error) { $("workers").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

function renderSubmitted(jobs) {
  $("submitted-list").innerHTML = jobs.length ? jobs.map((j) => `<article class="hit-row">
      <span><strong>${esc(j.name)}</strong><br><small class="mono">${esc(j.id)}</small></span>
      <span class="hit-meta"><button type="button" class="poll-btn" data-job-id="${esc(j.id)}">Poll result</button></span>
    </article>`).join("") : `<p class="muted">No jobs submitted yet.</p>`;
  $("submitted-list").querySelectorAll(".poll-btn").forEach((btn) => {
    btn.addEventListener("click", () => pollJob(btn.getAttribute("data-job-id")));
  });
}

async function loadSubmitted() {
  try {
    const data = await read(await fetch("/api/tasks/submitted", { cache: "no-store" }));
    renderSubmitted(data.jobs);
  } catch (error) { $("submitted-list").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

async function pollJob(jobId) {
  try {
    const result = await read(await fetch(`/api/tasks/jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" }));
    $("enqueue-result").textContent = `${result.name}: ${result.success ? "succeeded" : "failed"} (${result.duration_ms}ms)${result.error ? " — " + result.error : ""}`;
  } catch (error) {
    $("enqueue-result").textContent = `Not finished yet — try again shortly (${error.message})`;
  }
  await loadResults();
  await loadDlq();
  await loadWorkers();
}

function renderResults(completed, failed) {
  const rows = [
    ...completed.map((r) => ({ ...r, tone: "ok", label: "completed" })),
    ...failed.map((r) => ({ ...r, tone: "danger", label: "failed" })),
  ];
  $("results-list").innerHTML = rows.length ? rows.map((r) => `<article class="hit-row">
      <span><strong>${esc(r.name)}</strong><br><small>${esc(r.error || JSON.stringify(r.data))}</small></span>
      <span class="hit-meta"><span class="status ${r.tone}">${r.label}</span><span class="pill">${esc(r.duration_ms)}ms</span></span>
    </article>`).join("") : `<p class="muted">No results yet.</p>`;
}

async function loadResults() {
  try {
    const data = await read(await fetch("/api/tasks/results", { cache: "no-store" }));
    renderResults(data.completed, data.failed);
  } catch (error) { $("results-list").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

async function loadScheduled() {
  try {
    const data = await read(await fetch("/api/tasks/scheduled", { cache: "no-store" }));
    const jobs = data.scheduled_jobs || [];
    $("scheduled-list").innerHTML = jobs.length ? jobs.map((j) => `<article class="hit-row">
        <span><strong>${esc(j.name)}</strong><br><small class="mono">${esc(j.cron)}</small></span>
        <span class="hit-meta"><span class="status ${j.enabled ? "ok" : "warning"}">${j.enabled ? "enabled" : "disabled"}</span></span>
      </article>`).join("") : `<p class="muted">No scheduled jobs.</p>`;
  } catch (error) { $("scheduled-list").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

function renderDlq(entries) {
  $("dlq-list").innerHTML = entries.length ? entries.map((e) => `<article class="hit-row">
      <span><strong>${esc(e.job_name)}</strong><br><small>${esc(e.error)}</small></span>
      <span class="hit-meta"><span class="pill">attempts: ${esc(e.attempt_count)}</span>
      <button type="button" class="retry-btn" data-job-id="${esc(e.job_id)}">Retry</button></span>
    </article>`).join("") : `<p class="muted">Dead letter queue is empty.</p>`;
  $("dlq-list").querySelectorAll(".retry-btn").forEach((btn) => {
    btn.addEventListener("click", () => retryDlqJob(btn.getAttribute("data-job-id")));
  });
}

async function loadDlq() {
  try {
    const data = await read(await fetch("/api/tasks/dlq", { cache: "no-store" }));
    renderDlq(data.entries);
  } catch (error) { $("dlq-list").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

async function retryDlqJob(jobId) {
  try {
    await read(await fetch(`/api/tasks/dlq/${encodeURIComponent(jobId)}/retry`, { method: "POST" }));
    await loadDlq();
    await loadSubmitted();
  } catch (error) { $("dlq-list").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

async function purgeDlq() {
  try {
    await read(await fetch("/api/tasks/dlq/purge", { method: "POST" }));
    await loadDlq();
    await loadHealth();
  } catch (error) { $("dlq-list").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

$("enqueue-form").addEventListener("submit", enqueue);
$("refresh-health").addEventListener("click", loadHealth);
$("refresh-workers").addEventListener("click", loadWorkers);
$("refresh-submitted").addEventListener("click", loadSubmitted);
$("refresh-results").addEventListener("click", loadResults);
$("refresh-scheduled").addEventListener("click", loadScheduled);
$("purge-dlq").addEventListener("click", purgeDlq);

loadHealth();
loadWorkers();
loadSubmitted();
loadResults();
loadScheduled();
loadDlq();
