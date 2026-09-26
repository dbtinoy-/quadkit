/* Vanilla JS client for the auth-web API — no build step. */

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = {};
  }
  return { status: response.status, ok: response.ok, body };
}

function showError(message) {
  const el = document.getElementById("error");
  if (el) {
    el.textContent = message || "";
    el.style.display = message ? "block" : "none";
  }
}

function showOk(message) {
  const el = document.getElementById("ok");
  if (el) {
    el.textContent = message || "";
    el.style.display = message ? "block" : "none";
  }
}
