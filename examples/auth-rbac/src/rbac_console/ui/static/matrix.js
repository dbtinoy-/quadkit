/* Matrix page: grid, try-verdict form, articles list. */

const esc = (value) => {
  const element = document.createElement("span");
  element.textContent = String(value);
  return element.innerHTML;
};

async function loadMe() {
  const me = await api("/api/me");
  if (!me.ok) {
    window.location.href = "login"; // relative: resolves under any mount prefix
    return;
  }
  document.getElementById("who").textContent =
    `${me.body.email} — ${me.body.roles.join(", ")}`;
}

async function loadMatrix() {
  const matrix = await api("/api/matrix");
  if (!matrix.ok) throw new Error(matrix.body.error || matrix.body.detail || "Could not load matrix");
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  for (const check of matrix.body.checks) {
    const row = document.createElement("tr");
    row.innerHTML = `<td><code>${esc(check)}</code></td>`;
    for (const role of matrix.body.personas) {
      const granted = matrix.body.cells[role][check];
      row.innerHTML += `<td class="${granted ? "ok" : "error"}">${granted ? "✓" : "✗"}</td>`;
    }
    grid.appendChild(row);
  }
}

document.getElementById("try-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = event.target.querySelector("button[type=submit]");
  button.disabled = true;
  showError("");
  try {
    const result = await api("/api/try", {
      method: "POST",
      body: JSON.stringify({
        role: document.getElementById("try-role").value,
        action: document.getElementById("try-action").value.trim(),
        resource: document.getElementById("try-resource").value.trim(),
      }),
    });
    if (!result.ok) throw new Error(result.body.error || result.body.detail || "Authorization failed");
    document.getElementById("verdict").textContent = JSON.stringify(result.body);
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
  }
});

async function loadArticles() {
  const listing = await api("/api/articles");
  if (!listing.ok) throw new Error(listing.body.error || listing.body.detail || "Could not load articles");
  const list = document.getElementById("article-list");
  list.innerHTML = "";
  for (const article of listing.body.articles) {
    const item = document.createElement("li");
    item.innerHTML = `<strong>${esc(article.title)}</strong> <span class="muted">${esc(article.id)}</span>`;
    list.appendChild(item);
  }
}

document.getElementById("create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  const button = event.target.querySelector("button[type=submit]");
  button.disabled = true;
  const title = document.getElementById("new-title").value.trim();
  try {
    const created = await api("/api/articles", {
      method: "POST",
      body: JSON.stringify({ title, body: `Body for ${title}` }),
    });
    if (!created.ok) throw new Error(created.body.error || created.body.detail || "Create failed");
    event.target.reset();
    await loadArticles();
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
  }
});

document.getElementById("logout").addEventListener("click", async (event) => {
  event.preventDefault();
  const link = event.currentTarget;
  link.setAttribute("aria-busy", "true");
  try {
    await api("/api/logout", { method: "POST" });
    window.location.href = "login"; // relative: resolves under any mount prefix
  } catch (error) {
    showError(error.message);
    link.removeAttribute("aria-busy");
  }
});

Promise.all([loadMe(), loadMatrix(), loadArticles()]).catch((error) => showError(error.message));
