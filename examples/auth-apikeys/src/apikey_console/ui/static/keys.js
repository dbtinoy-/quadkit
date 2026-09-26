/* Keys page: list, create, revoke. */

async function loadKeys() {
  const listing = await api("/api/keys");
  if (listing.status === 401) {
    window.location.href = "login"; // relative: resolves under any mount prefix
    return;
  }
  if (!listing.ok) {
    showError(listing.body.error || listing.body.detail || "Could not load keys");
    return;
  }
  showError("");
  const rows = document.getElementById("key-rows");
  rows.innerHTML = "";
  for (const key of listing.body.keys || []) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${key.name}</td><td><code>${key.prefix}…</code></td>` +
      `<td>${key.scopes.join(", ") || "—"}</td>` +
      `<td class="muted">${key.expires_at ?? "never"}</td>` +
      `<td><button type="button" class="secondary" data-key="${key.key_id}">Revoke</button></td>`;
    rows.appendChild(tr);
  }
  for (const button of document.querySelectorAll("button[data-key]")) {
    button.addEventListener("click", async () => {
      button.disabled = true;
      const result = await api(`/api/keys/${button.dataset.key}/revoke`, { method: "POST" });
      if (!result.ok) {
        button.disabled = false;
        showError(result.body.error || result.body.detail || "Could not revoke key");
        return;
      }
      loadKeys();
    });
  }
}

document.getElementById("create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = event.target.querySelector("button[type=submit]");
  submit.disabled = true;
  showError("");
  const form = new FormData(event.target);
  const scopes = [];
  if (form.get("scope-read")) scopes.push("read");
  if (form.get("scope-write")) scopes.push("write");
  try {
    const created = await api("/api/keys/create", {
      method: "POST",
      body: JSON.stringify({ name: form.get("name"), scopes }),
    });
    if (!created.ok) {
      showError(created.body.error || created.body.detail || "Could not create key");
      return;
    }
    const box = document.getElementById("raw-key-box");
    box.style.display = "";
    document.getElementById("raw-key").textContent = created.body.raw_key;
    loadKeys();
  } catch (error) {
    showError(error.message);
  } finally {
    submit.disabled = false;
  }
});

document.getElementById("logout").addEventListener("click", async (event) => {
  event.preventDefault();
  const button = event.currentTarget;
  button.disabled = true;
  try {
    await api("/api/logout", { method: "POST" });
    window.location.href = "login"; // relative: resolves under any mount prefix
  } catch (error) {
    showError(error.message);
    button.disabled = false;
  }
});

loadKeys().catch((error) => showError(error.message));
