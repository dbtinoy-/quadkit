/* Vanilla-JS client for the support-agent console (no build step). */
"use strict";

let scenario = "happy";

const $ = (id) => document.getElementById(id);
const show = (id) => $(id).classList.remove("hidden");
const hide = (id) => $(id).classList.add("hidden");

function setActiveButton() {
  document.querySelectorAll("#scenarios button").forEach((b) => {
    b.classList.toggle("active", b.dataset.scenario === scenario);
  });
}

function showError(message) {
  $("error").textContent = message;
  show("error");
}

async function loadTools() {
  const res = await fetch("/api/tools");
  const tools = await res.json().catch(() => ({}));
  if (!res.ok || tools.error || tools.detail) throw new Error(tools.error || tools.detail || `HTTP ${res.status}`);
  $("tools").innerHTML = tools
    .map((t) => `<li title="${escapeHtml(t.description)}"><code>${escapeHtml(t.name)}</code></li>`)
    .join("");
}

function escapeHtml(text) {
  const element = document.createElement("div");
  element.textContent = String(text);
  return element.innerHTML;
}

function row(step, call) {
  const outcome = call
    ? `${escapeHtml(call.tool_name)} ${call.succeeded ? "ok" : `FAILED: ${escapeHtml(call.error ?? "")}`}`
    : "";
  return `<tr><td>${escapeHtml(step.step_number)}</td><td>${escapeHtml(step.thought ?? "")}</td>` +
         `<td>${escapeHtml(step.action ?? "")}</td><td>${outcome}</td></tr>`;
}

function render(body) {
  $("answer").textContent = body.answer;
  $("trace").querySelector("tbody").innerHTML =
    body.steps.map((s, i) => row(s, body.tool_calls[i])).join("");
  $("meta").textContent = `tokens=${body.total_tokens} · ${body.duration_ms} ms`;
  ["answer", "trace", "meta"].forEach(show);
}

async function ask(event) {
  event.preventDefault();
  ["answer", "trace", "meta", "error"].forEach(hide);
  const submit = $("ask-form").querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: $("question").value.trim(), scenario }),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok || body.error || body.detail) {
      throw new Error(body.error || body.detail || `HTTP ${res.status}`);
    }
    render(body);
  } catch (error) {
    $("error").textContent = error.message;
    show("error");
  } finally {
    submit.disabled = false;
  }
}

document.querySelectorAll("#scenarios button").forEach((b) =>
  b.addEventListener("click", () => {
    scenario = b.dataset.scenario;
    setActiveButton();
  }));
$("ask-form").addEventListener("submit", ask);
setActiveButton();
loadTools().catch((error) => {
  $("tools").innerHTML = "<li class='muted'>Tools unavailable — start the demo to see tools.</li>";
});
