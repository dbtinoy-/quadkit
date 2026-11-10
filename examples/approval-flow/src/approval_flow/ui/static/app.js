"use strict";
const $ = (id) => document.getElementById(id);
function esc(v) { const el = document.createElement("span"); el.textContent = String(v ?? ""); return el.innerHTML; }
async function read(r) { const d = await r.json().catch(() => ({})); if (!r.ok || d.error) throw new Error(d.detail || d.error || `HTTP ${r.status}`); return d; }
async function load() {
  try {
    const d = await read(await fetch("/api/workflow", { cache: "no-store" }));
    $("state-pill").textContent = d.state.replaceAll("_", " "); $("version").textContent = `version ${d.version}`;
    $("steps").innerHTML = d.steps.map((step) => `<div class="step"><span class="step-dot ${esc(step.status)}"></span><div><strong>${esc(step.label)}</strong><small>${esc(step.status)}</small></div></div>`).join("");
    $("events").innerHTML = d.available_events.map((item) => `<button type="button" data-event="${esc(item.event)}" class="${item.event.includes("reject") ? "danger" : item.event === "rollback" ? "warning" : "accent"}">${esc(item.label)}</button>`).join("");
    $("history").innerHTML = d.history.length ? d.history.map((item) => `<div class="history-row"><span class="version-badge">v${item.version}</span><strong>${esc(item.from_state)} → ${esc(item.to_state)}</strong><span>${esc(item.event)}</span><span>${esc(item.actor)}</span><time>${esc(item.timestamp)}</time></div>`).join("") : `<p class="muted">No transitions yet. Submit the request to begin.</p>`;
  } catch (error) { $("flow-result").textContent = error.message; }
}
async function createRequest(event) {
  event.preventDefault();
  try { await read(await fetch("/api/workflow/request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: $("title").value, amount: Number($("amount").value), owner: $("owner").value }) })); $("flow-result").textContent = "New request created in draft"; await load(); } catch (error) { $("flow-result").textContent = error.message; }
}
async function transition(event) {
  const button = event.target.closest("button[data-event]"); if (!button) return;
  button.disabled = true;
  try { const d = await read(await fetch("/api/workflow/transition", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event: button.dataset.event, actor: button.dataset.event.includes("finance") ? "finance-reviewer" : "manager-reviewer" }) })); $("flow-result").textContent = `Transitioned to ${d.state}`; await load(); } catch (error) { $("flow-result").textContent = error.message; } finally { button.disabled = false; }
}
async function policy(event) {
  event.preventDefault();
  try { const d = await read(await fetch("/api/workflow/policy", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ manager_approved: $("manager-ok").checked, finance_approved: $("finance-ok").checked }) })); $("policy-result").textContent = JSON.stringify(d, null, 2); } catch (error) { $("policy-result").textContent = error.message; }
}
$("request-form").addEventListener("submit", createRequest); $("events").addEventListener("click", transition); $("policy-form").addEventListener("submit", policy); load();
setInterval(load, 8000);
