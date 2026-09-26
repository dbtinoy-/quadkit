/* MFA console logic: identity, status, enroll, disable, logout. */

async function loadProfile() {
  const me = await api("/api/me");
  if (!me.ok) {
    window.location.href = "login"; // relative: resolves under any mount prefix
    return;
  }
  document.getElementById("identity").innerHTML =
    `<div class="row"><span>${me.body.name}</span>` +
    `<span class="muted">${me.body.email}</span></div>`;

  const status = await api("/api/mfa/status");
  if (!status.ok) throw new Error(status.body.error || status.body.detail || "Could not load MFA status");

  const enabled = status.body.enabled;
  document.getElementById("mfa-state").textContent = enabled ? "enabled" : "disabled";
  document.getElementById("enroll-box").style.display = enabled ? "none" : "";
  document.getElementById("enrolled-box").style.display = enabled ? "" : "none";
  if (enabled) {
    document.getElementById("codes-left").textContent = status.body.backup_codes_left;
  }
}

document.getElementById("enroll-btn")?.addEventListener("click", async () => {
  showError("");
  const button = document.getElementById("enroll-btn");
  button.disabled = true;
  button.textContent = "Enrolling…";
  try {
    const result = await api("/api/mfa/enroll", { method: "POST" });
    if (!result.ok) throw new Error(result.body.error || result.body.detail || "Enrollment failed");
    const out = document.getElementById("enroll-output");
    out.textContent =
      `SECRET: ${result.body.secret}\n` +
      `URI: ${result.body.provisioning_uri}\n` +
      `BACKUP CODES (shown once): ${result.body.backup_codes.join(", ")}`;
    await loadProfile();
  } catch (error) {
    showError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "Enroll MFA";
  }
});

document.getElementById("disable-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  const submit = event.target.querySelector("button[type=submit]");
  submit.disabled = true;
  const form = new FormData(event.target);
  try {
    const result = await api("/api/mfa/disable", {
      method: "POST",
      body: JSON.stringify({ password: form.get("password") }),
    });
    if (!result.ok) throw new Error(result.body.error || result.body.detail || "Disable failed");
    event.target.reset();
    await loadProfile();
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

loadProfile().catch((error) => showError(error.message));
