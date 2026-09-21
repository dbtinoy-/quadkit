/* Vanilla-JS hub console — intentionally no build step. */
"use strict";
const $ = (id) => document.getElementById(id);
let filter = "all";
let query = "";
const groupLabels = { starter: "Starter templates", standard: "Standard modules", "multi-module": "Multi-module apps" };
const groupDescriptions = { starter: "Canonical src/ layout starters — the recommended reading order for a first Quadkit project.", standard: "One domain module plus WebModule — learn a capability in isolation.", "multi-module": "Composed applications — see several Quadkit capabilities work together." };
function esc(value) { const el = document.createElement("span"); el.textContent = String(value ?? ""); return el.innerHTML; }
function matches(service) { const haystack = [service.name, service.blurb, ...(service.capabilities || [])].join(" ").toLowerCase(); return !query || haystack.includes(query); }
async function load() {
  const status = $("hub-status");
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    const body = await res.json().catch(() => ({}));
    if (!res.ok || body.error) throw new Error(body.error || `HTTP ${res.status}`);
    const services = body.services || [];
    $("total-count").textContent = services.length;
    $("up-count").textContent = services.filter((service) => service.status === "up").length;
    render(services);
    status.textContent = `${services.length} demos · ${$("up-count").textContent} ready · status refreshes automatically`;
    status.className = "hub-status";
  } catch (error) {
    status.textContent = `Unable to load demo status: ${error.message}`;
    status.className = "hub-status error";
    if (!$("cards").children.length) $("cards").innerHTML = "<p class=\"empty-state\">Try refreshing the hub.</p>";
  }
}
function card(service) {
  const errorTitle = service.error ? ` title="${esc(service.error)}"` : "";
  const tags = (service.capabilities || []).slice(0, 3).map((tag) => `<span>${esc(tag)}</span>`).join("");
  const featured = service.featured ? `<span class="featured">New</span>` : "";
  return `<article class="card-wrap"><a class="card" href="/examples/${encodeURIComponent(service.slug)}/"${errorTitle}><div class="card-top"><span class="live-state"><span class="dot ${service.status === "up" ? "up" : "down"}"></span>${service.status === "up" ? "Ready" : "Unavailable"}</span>${featured}</div><h3>${esc(service.name)}</h3><p>${esc(service.blurb)}</p><div class="tags">${tags}</div><div class="card-bottom"><code>standalone :${service.port}</code><span class="open-label">Open demo&nbsp; →</span></div></a><button type="button" class="info-btn" data-slug="${esc(service.slug)}" data-name="${esc(service.name)}" title="About this demo" aria-label="About ${esc(service.name)}">i</button></article>`;
}
function render(services) {
  const visible = services.filter((service) => (filter === "all" || service.group === filter) && matches(service));
  const groups = {};
  for (const service of visible) { const group = service.group || "standard"; if (!groups[group]) groups[group] = []; groups[group].push(service); }
  let html = "";
  for (const [key, items] of Object.entries(groups)) {
    html += `<section class="group-section"><div class="group-heading"><div><h2>${esc(groupLabels[key] || key)}</h2><p>${esc(groupDescriptions[key] || "")}</p></div><span class="group-count">${items.length}</span></div><div class="grid">${items.map(card).join("")}</div></section>`;
  }
  if (!html) html = `<div class="empty-state"><strong>No demos match “${esc(query || filter)}”.</strong><p>Try another search or choose All demos.</p></div>`;
  $("cards").innerHTML = html;
  document.querySelectorAll(".info-btn").forEach((button) => button.addEventListener("click", (event) => { event.preventDefault(); event.stopPropagation(); openModal(button.dataset.slug, button.dataset.name); }));
}
function openModal(slug, name) {
  $("modal-title").textContent = name; $("modal-body").innerHTML = `<p class="modal-loading">Loading the learning path…</p>`; $("modal-overlay").classList.remove("hidden"); document.body.style.overflow = "hidden";
  fetch(`/api/demo/${encodeURIComponent(slug)}/readme`, { cache: "no-store" }).then(async (response) => { const data = await response.json().catch(() => ({})); if (!response.ok || data.error) throw new Error(data.detail || data.error || `HTTP ${response.status}`); return data; }).then((data) => { $("modal-body").innerHTML = renderMarkdown(data.readme || "No README available."); }).catch((error) => { $("modal-body").innerHTML = `<p class="modal-error">Failed to load README: ${esc(error.message)}</p>`; });
}
function closeModal() { $("modal-overlay").classList.add("hidden"); document.body.style.overflow = ""; }
$("modal-close").addEventListener("click", closeModal); $("modal-overlay").addEventListener("click", (event) => { if (event.target === $("modal-overlay")) closeModal(); }); document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeModal(); });
function renderMarkdown(markdown) {
  const lines = markdown.split("\n"); let html = ""; let inCode = false; let inTable = false; let inList = false;
  for (const line of lines) {
    if (line.startsWith("```")) { if (inCode) { html += "</code></pre>"; inCode = false; } else { html += "<pre><code>"; inCode = true; } continue; }
    if (inCode) { html += esc(line) + "\n"; continue; }
    if (line.includes("|") && line.trim().startsWith("|")) { if (!inTable) { html += "<table>"; inTable = true; } const cells = line.split("|").slice(1, -1).map((cell) => cell.trim()); if (cells.every((cell) => /^[-:]+$/.test(cell))) continue; html += `<tr>${cells.map((cell) => `<td>${inlineMd(cell)}</td>`).join("")}</tr>`; continue; }
    if (inTable) { html += "</table>"; inTable = false; }
    if (/^\s*[-*]\s/.test(line)) { if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inlineMd(line.replace(/^\s*[-*]\s/, ""))}</li>`; continue; }
    if (inList) { html += "</ul>"; inList = false; }
    if (!line.trim()) { html += "\n"; continue; }
    const heading = line.match(/^(#{1,6})\s+(.*)/); if (heading) { html += `<h${heading[1].length}>${inlineMd(heading[2])}</h${heading[1].length}>`; continue; }
    html += `<p>${inlineMd(line)}</p>`;
  }
  if (inCode) html += "</code></pre>"; if (inTable) html += "</table>"; if (inList) html += "</ul>"; return html;
}
function inlineMd(text) { return esc(text).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\*([^*]+)\*/g, "<em>$1</em>").replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>'); }
$("search").addEventListener("input", (event) => { query = event.target.value.trim().toLowerCase(); load(); });
document.querySelectorAll("#filters button").forEach((button) => button.addEventListener("click", () => { filter = button.dataset.f; document.querySelectorAll("#filters button").forEach((item) => item.classList.toggle("active", item === button)); load(); }));
load(); setInterval(load, 5000);
