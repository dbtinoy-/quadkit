/* Vanilla-JS client for the monitor stack console (no build step). */
"use strict";

const $ = (id) => document.getElementById(id);

function showError(message) {
  const error = $("error");
  error.textContent = message;
  error.classList.toggle("hidden", !message);
}

function ts() { return new Date().toLocaleTimeString(); }
function log(msg, cls) {
  const el = document.createElement("div");
  el.className = "log-entry " + (cls || "");
  el.textContent = `${ts()} ${msg}`;
  const logEl = $("log");
  logEl.prepend(el);
  if (logEl.children.length > 50) logEl.lastChild.remove();
}

function escapeHtml(text) {
  const element = document.createElement("div");
  element.textContent = String(text);
  return element.innerHTML;
}

async function readResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.error) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

async function refreshHealth() {
  try {
    const data = await readResponse(await fetch("/api/monitor/health"));
    const checks = data.checks || [];
    $("health-grid").innerHTML =
      `<div class="health-summary"><strong>${escapeHtml(data.status || "unknown")}</strong>` +
      `<span>${checks.length} check${checks.length === 1 ? "" : "s"}</span></div>` +
      checks.map((check) =>
        `<div class="health-check"><span>${escapeHtml(check.component)}</span>` +
        `<span class="status-${escapeHtml(check.status)}">${escapeHtml(check.status)}</span></div>`
      ).join("");
  } catch (e) {
    $("health-grid").innerHTML = "<p class='muted'>Health check unavailable — start the demo to see checks.</p>";
    log(`health check failed: ${e.message}`, "log-error");
  }
}

function metricRows(metrics, kind) {
  return Object.entries(metrics || {}).map(([name, value]) => {
    const display = kind === "histograms" && value && typeof value === "object"
      ? `count=${value.count} · avg=${Number(value.avg).toFixed(2)}`
      : value;
    return `<div class="metric-row"><code>${escapeHtml(name)}</code><strong>${escapeHtml(display)}</strong></div>`;
  }).join("");
}

async function refreshMetrics() {
  try {
    const data = await readResponse(await fetch("/api/monitor/metrics"));
    const html = [
      metricRows(data.counters, "counters"),
      metricRows(data.gauges, "gauges"),
      metricRows(data.histograms, "histograms"),
    ].join("");
    $("metrics-grid").innerHTML = html || "<p class=\"muted\">No metrics recorded yet.</p>";
  } catch (e) {
    $("metrics-grid").innerHTML = "<p class='muted'>Metrics unavailable — start the demo to see metrics.</p>";
    log(`metrics refresh failed: ${e.message}`, "log-error");
  }
}

async function createTrace(event) {
  event.preventDefault();
  const name = $("trace-name").value.trim();
  if (!name) return;
  const btn = $("trace-btn");
  btn.disabled = true;
  try {
    const res = await fetch("/api/monitor/trace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await readResponse(res);
    const span = data.span || {};
    $("trace-output").textContent = `${span.name}: ${Number(span.duration_ms).toFixed(2)} ms`;
    log(`recorded trace: ${span.name}`, "log-hit");
    await refreshMetrics();
  } catch (e) {
    showError(e.message);
    log(`trace failed: ${e.message}`, "log-error");
  } finally {
    btn.disabled = false;
  }
}

$("trace-form").addEventListener("submit", createTrace);
refreshHealth();
refreshMetrics();
setInterval(refreshHealth, 5000);
setInterval(refreshMetrics, 3000);
