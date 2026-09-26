/* Vanilla-JS client for the SQL repository console (no build step). */
"use strict";

const $ = (id) => document.getElementById(id);
function ts() { return new Date().toLocaleTimeString(); }
function log(msg, cls) {
  const el = document.createElement("div");
  el.className = "log-entry " + (cls || "");
  el.textContent = `${ts()} ${msg}`;
  const logEl = $("log");
  logEl.prepend(el);
  if (logEl.children.length > 50) logEl.lastChild.remove();
}
function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value);
  return element.innerHTML;
}
async function readResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok || data.error) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
  return data;
}

async function loadTasks() {
  try {
    const [tasksResponse, statsResponse] = await Promise.all([
      fetch("/api/tasks/tasks"),
      fetch("/api/tasks/stats"),
    ]);
    const tasks = await readResponse(tasksResponse);
    const stats = await readResponse(statsResponse);
    $("tasks-list").innerHTML = tasks.map((task) =>
      `<article class="task-row">` +
      `<div><strong>${escapeHtml(task.title)}</strong>` +
      `<small>#${task.id} · priority ${task.priority} · ${escapeHtml(task.created_at)}</small></div>` +
      `<div class="task-actions">` +
      `<select data-task-id="${task.id}" aria-label="Status for ${escapeHtml(task.title)}">` +
      ["todo", "in_progress", "done"].map((status) =>
        `<option value="${status}" ${status === task.status ? "selected" : ""}>${status}</option>`
      ).join("") +
      `</select><button data-delete-id="${task.id}" type="button">Delete</button></div></article>`
    ).join("") || "<p class=\"muted\">No tasks in SQLite yet.</p>";
    $("task-stats").textContent = `${stats.total} task${stats.total === 1 ? "" : "s"} · ${stats.done} done`;
  } catch (e) {
    log(`load failed: ${e.message}`, "log-error");
  }
}

async function createTask(event) {
  event.preventDefault();
  const input = $("task-title");
  const title = input.value.trim();
  if (!title) return;
  try {
    await readResponse(await fetch("/api/tasks/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, priority: 0 }),
    }));
    input.value = "";
    log(`created ${title}`, "log-hit");
    await loadTasks();
  } catch (e) { log(`create failed: ${e.message}`, "log-error"); }
}

async function updateStatus(select) {
  try {
    await readResponse(await fetch(`/api/tasks/tasks/${select.dataset.taskId}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: select.value }),
    }));
    log(`updated task #${select.dataset.taskId} to ${select.value}`, "log-hit");
    await loadTasks();
  } catch (e) { log(`update failed: ${e.message}`, "log-error"); }
}

async function deleteTask(button) {
  try {
    await readResponse(await fetch(`/api/tasks/tasks/${button.dataset.deleteId}`, { method: "DELETE" }));
    log(`deleted task #${button.dataset.deleteId}`, "log-hit");
    await loadTasks();
  } catch (e) { log(`delete failed: ${e.message}`, "log-error"); }
}

$("task-form").addEventListener("submit", createTask);
$("tasks-list").addEventListener("change", (event) => {
  if (event.target.matches("select[data-task-id]")) updateStatus(event.target);
});
$("tasks-list").addEventListener("click", (event) => {
  if (event.target.matches("button[data-delete-id]")) deleteTask(event.target);
});
loadTasks();
