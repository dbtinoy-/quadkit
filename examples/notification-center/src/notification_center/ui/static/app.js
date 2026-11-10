"use strict";
const $ = (id) => document.getElementById(id);
function esc(value) { const el = document.createElement("span"); el.textContent = String(value ?? ""); return el.innerHTML; }
async function read(response) { const data = await response.json().catch(() => ({})); if (!response.ok || data.error || data.detail) throw new Error(data.detail || (data.error && data.error.message) || data.error || `HTTP ${response.status}`); return data; }

function currentUser() { return $("inbox-user").value.trim() || "demo-user"; }

async function sendEmail(event) {
  event.preventDefault();
  const to = $("email-to").value.trim();
  const body = {
    to: to ? [to] : [],
    subject: $("email-subject").value.trim(),
    body: $("email-body").value.trim(),
  };
  try {
    const receipt = await read(await fetch("/api/notifications", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }));
    $("email-result").textContent = `Sent via ${receipt.backend} — message id ${receipt.message_id}`;
    $("email-to").value = ""; $("email-subject").value = ""; $("email-body").value = "";
    await loadSentLog();
    await loadHealth();
  } catch (error) { $("email-result").textContent = error.message; }
}

async function loadHealth() {
  try {
    const data = await read(await fetch("/api/notifications/health", { cache: "no-store" }));
    $("health").innerHTML = `<span class="status ${data.status === "healthy" ? "ok" : "warning"}">${esc(data.status)}</span> <span class="pill">mailer: ${esc(data.details?.mailer)}</span> <span class="pill">sent: ${esc(data.details?.sent_count)}</span>`;
  } catch (error) { $("health").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

function renderSentLog(sent) {
  $("sent-log").innerHTML = sent.length ? sent.slice().reverse().map((entry) => `<article class="hit-row">
      <span><strong>${esc(entry.subject || "(no subject)")}</strong><br><small>to ${esc((entry.to || []).join(", "))}</small></span>
      <span class="hit-meta"><span class="pill">${esc(entry.backend)}</span><span class="status ok">${esc(entry.status)}</span></span>
    </article>`).join("") : `<p class="muted">No emails sent yet.</p>`;
}

async function loadSentLog() {
  try {
    const data = await read(await fetch("/api/notifications/sent", { cache: "no-store" }));
    renderSentLog(data.sent);
  } catch (error) { $("sent-log").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

async function sendInboxMessage(event) {
  event.preventDefault();
  const body = {
    user_id: currentUser(),
    title: $("inbox-title").value.trim(),
    body: $("inbox-body").value.trim(),
  };
  try {
    await read(await fetch("/api/notifications/inbox", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }));
    $("inbox-title").value = ""; $("inbox-body").value = "";
    await loadInbox();
  } catch (error) { $("inbox-summary").textContent = error.message; }
}

function renderInbox(messages) {
  $("inbox-list").innerHTML = messages.length ? messages.map((m) => `<article class="hit-row">
      <span><strong>${esc(m.title)}</strong><br><small>${esc(m.body)}</small></span>
      <span class="hit-meta"><span class="status ${m.read ? "ok" : "warning"}">${m.read ? "read" : "unread"}</span>
      <button type="button" data-msg-id="${esc(m.id)}" class="mark-read-btn" ${m.read ? "disabled" : ""}>Mark read</button>
      <button type="button" data-msg-id="${esc(m.id)}" class="delete-msg-btn">Delete</button></span>
    </article>`).join("") : `<p class="muted">No messages for this user.</p>`;
  $("inbox-list").querySelectorAll(".mark-read-btn").forEach((btn) => {
    btn.addEventListener("click", () => markRead(btn.getAttribute("data-msg-id")));
  });
  $("inbox-list").querySelectorAll(".delete-msg-btn").forEach((btn) => {
    btn.addEventListener("click", () => deleteMessage(btn.getAttribute("data-msg-id")));
  });
}

async function loadInbox() {
  const user = currentUser();
  try {
    const [inbox, unread] = await Promise.all([
      read(await fetch(`/api/notifications/inbox?user_id=${encodeURIComponent(user)}`, { cache: "no-store" })),
      read(await fetch(`/api/notifications/inbox/unread-count?user_id=${encodeURIComponent(user)}`, { cache: "no-store" })),
    ]);
    $("inbox-summary").textContent = `${inbox.count} message${inbox.count === 1 ? "" : "s"} · ${unread.unread_count} unread for ${user}`;
    renderInbox(inbox.messages);
  } catch (error) { $("inbox-list").innerHTML = `<p class="error">${esc(error.message)}</p>`; }
}

async function markRead(messageId) {
  try {
    await read(await fetch(`/api/notifications/inbox/message/${encodeURIComponent(messageId)}/read?user_id=${encodeURIComponent(currentUser())}`, { method: "POST" }));
    await loadInbox();
  } catch (error) { $("inbox-summary").textContent = error.message; }
}

async function deleteMessage(messageId) {
  try {
    await read(await fetch(`/api/notifications/inbox/message/${encodeURIComponent(messageId)}?user_id=${encodeURIComponent(currentUser())}`, { method: "DELETE" }));
    await loadInbox();
  } catch (error) { $("inbox-summary").textContent = error.message; }
}

async function markAllRead() {
  try {
    await read(await fetch(`/api/notifications/inbox/read-all?user_id=${encodeURIComponent(currentUser())}`, { method: "POST" }));
    await loadInbox();
  } catch (error) { $("inbox-summary").textContent = error.message; }
}

async function clearInbox() {
  try {
    await read(await fetch(`/api/notifications/inbox?user_id=${encodeURIComponent(currentUser())}`, { method: "DELETE" }));
    await loadInbox();
  } catch (error) { $("inbox-summary").textContent = error.message; }
}

$("email-form").addEventListener("submit", sendEmail);
$("inbox-form").addEventListener("submit", sendInboxMessage);
$("user-form").addEventListener("submit", (event) => { event.preventDefault(); loadInbox(); });
$("mark-all-read").addEventListener("click", markAllRead);
$("clear-inbox").addEventListener("click", clearInbox);
$("refresh-inbox").addEventListener("click", loadInbox);
$("refresh-sent").addEventListener("click", loadSentLog);
$("refresh-health").addEventListener("click", loadHealth);

loadHealth();
loadSentLog();
loadInbox();
