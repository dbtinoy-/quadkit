/* Vanilla-JS client for the event-driven orders console (no build step). */
"use strict";

const $ = (id) => document.getElementById(id);
const show = (id) => $(id).classList.remove("hidden");
const hide = (id) => $(id).classList.add("hidden");

function ts() {
  return new Date().toLocaleTimeString();
}

function log(msg, cls) {
  const el = document.createElement("div");
  el.className = "log-entry " + (cls || "");
  el.innerHTML = '<span class="log-time">' + ts() + "</span>" + msg;
  const logEl = $("log");
  logEl.prepend(el);
  if (logEl.children.length > 60) logEl.lastChild.remove();
}

function badge(status) {
  return '<span class="badge badge-' + status + '">' + status + "</span>";
}

/* ── Orders ─────────────────────────────────────────────── */

async function loadOrders() {
  try {
    const res = await fetch("/orders");
  const rows = await res.json();
  const tbody = $("orders-table").querySelector("tbody");
  tbody.innerHTML = "";
  if (rows.length === 0) {
    show("orders-empty");
    return;
  }
  hide("orders-empty");
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    const shortId = r.order_id.substring(0, 8);
    let actions = "";
    if (r.status === "placed") {
      actions = '<button type="button" class="action-btn pay" data-id="' + r.order_id + '" data-total="' + r.total + '">Pay</button>';
    } else if (r.status === "paid") {
      actions = '<button type="button" class="action-btn ship" data-id="' + r.order_id + '">Ship</button>';
    }
    tr.innerHTML =
      "<td><code>" + shortId + "</code></td>" +
      "<td>" + r.customer + "</td>" +
      "<td>" + r.total + "</td>" +
      "<td>" + badge(r.status) + "</td>" +
      "<td>" + actions + "</td>";
    tbody.appendChild(tr);
  });

  /* wire action buttons */
    tbody.querySelectorAll(".action-btn.pay").forEach((btn) =>
      btn.addEventListener("click", () => payOrder(btn.dataset.id, btn.dataset.total, btn))
    );
    tbody.querySelectorAll(".action-btn.ship").forEach((btn) =>
      btn.addEventListener("click", () => shipOrder(btn.dataset.id, btn))
    );
  } catch (error) {
    $("orders-error").textContent = "Orders unavailable — start the demo to place orders.";
    show("orders-error");
    log("load orders failed: " + error.message, "log-err");
  }
}

/* ── Place order ────────────────────────────────────────── */

function buildItemRows() {
  return Array.from($("items-fieldset").querySelectorAll(".item-row")).map((row) => ({
    sku: row.querySelector(".item-sku").value.trim(),
    qty: parseInt(row.querySelector(".item-qty").value, 10) || 1,
    unit_price: row.querySelector(".item-price").value.trim(),
  }));
}

function addItemRow() {
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML =
    '<input class="item-sku" type="text" placeholder="SKU" required>' +
    '<input class="item-qty" type="number" value="1" min="1" required>' +
    '<input class="item-price" type="text" placeholder="0.00" required>' +
    '<button type="button" class="remove-item">&times;</button>';
  row.querySelector(".remove-item").addEventListener("click", () => {
    row.remove();
    updateRemoveButtons();
  });
  $("items-fieldset").appendChild(row);
  updateRemoveButtons();
}

function updateRemoveButtons() {
  const rows = $("items-fieldset").querySelectorAll(".item-row");
  rows.forEach((r, i) => {
    r.querySelector(".remove-item").disabled = rows.length <= 1;
  });
}

async function placeOrder(event) {
  event.preventDefault();
  hide("place-error");
  const items = buildItemRows().filter((i) => i.sku && i.unit_price);
  if (items.length === 0) {
    $("place-error").textContent = "Add at least one item";
    show("place-error");
    return;
  }
  const body = { customer: $("customer").value.trim(), items };
  const submit = event.target.querySelector("button[type=submit]");
  submit.disabled = true;
  submit.textContent = "Placing…";
  try {
    const res = await fetch("/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      $("place-error").textContent = data.detail || data.error || "HTTP " + res.status;
      show("place-error");
      log("place failed: " + ($("place-error").textContent), "log-err");
      return;
    }
    log("order placed: " + data.order_id.substring(0, 8), "log-ok");
    $("customer").value = "";
    $("items-fieldset").innerHTML = "";
    addItemRow();
    await loadOrders();
  } catch (e) {
    $("place-error").textContent = e.message;
    show("place-error");
  } finally {
    submit.disabled = false;
    submit.textContent = "Place Order";
  }
}

/* ── Pay / Ship ─────────────────────────────────────────── */

async function payOrder(orderId, total, button) {
  button.disabled = true;
  try {
    const res = await fetch("/orders/" + orderId + "/pay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount: total }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      log("pay failed: " + (data.detail || data.error || res.status), "log-err");
      return;
    }
    log("order paid: " + orderId.substring(0, 8), "log-ok");
    await loadOrders();
  } catch (e) {
    log("pay error: " + e.message, "log-err");
  } finally {
    button.disabled = false;
  }
}

async function shipOrder(orderId, button) {
  button.disabled = true;
  try {
    const res = await fetch("/orders/" + orderId + "/ship", { method: "POST" });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      log("ship failed: " + (data.detail || data.error || res.status), "log-err");
      return;
    }
    log("order shipped: " + orderId.substring(0, 8), "log-ok");
    await loadOrders();
  } catch (e) {
    log("ship error: " + e.message, "log-err");
  } finally {
    button.disabled = false;
  }
}

/* ── Outbox ─────────────────────────────────────────────── */

async function loadOutbox() {
  try {
    const res = await fetch("/outbox");
  const rows = await res.json();
  const tbody = $("outbox-table").querySelector("tbody");
  tbody.innerHTML = "";
  if (rows.length === 0) {
    show("outbox-empty");
    hide("outbox-table");
    return;
  }
  hide("outbox-empty");
  show("outbox-table");
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = "<td>" + r.event_type + "</td><td>" + r.status + "</td>";
      tbody.appendChild(tr);
    });
  } catch (error) {
    $("outbox-error").textContent = "Outbox unavailable — start the demo to see events.";
    show("outbox-error");
    log("load outbox failed: " + error.message, "log-err");
  }
}

async function flushOutbox() {
  const button = $("flush-btn");
  button.disabled = true;
  button.textContent = "Flushing…";
  try {
    const res = await fetch("/outbox/flush", { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      log("outbox flushed: " + data.flushed + " events", "log-info");
    } else {
      log("flush failed", "log-err");
    }
    await loadOutbox();
    await loadOrders();
  } catch (e) {
    log("flush error: " + e.message, "log-err");
  } finally {
    button.disabled = false;
    button.textContent = "Flush Outbox";
  }
}

/* ── Demo ─────────────────────────────────────────────── */

async function runDemo() {
  const btn = $("demo-btn");
  btn.disabled = true;
  btn.textContent = "Running\u2026";
  hide("demo-result");
  try {
    const res = await fetch("/api/demo", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      $("demo-result").textContent = "Demo failed: " + (data.detail || data.error || res.status);
      show("demo-result");
      $("demo-result").className = "error";
      log("demo failed: " + ($("demo-result").textContent), "log-err");
      return;
    }
    const shortId = (data.order_id || "").substring(0, 8);
    $("demo-result").textContent = "Order " + shortId + " \u2014 " + data.status + " (total: " + data.total + ")";
    show("demo-result");
    $("demo-result").className = "log-ok";
    log("demo complete: order " + shortId + " lifecycle finished", "log-ok");
    await loadOrders();
    await loadOutbox();
  } catch (e) {
    $("demo-result").textContent = "Demo error: " + e.message;
    show("demo-result");
    $("demo-result").className = "error";
    log("demo error: " + e.message, "log-err");
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Demo";
  }
}

/* ── Wire up ────────────────────────────────────────────── */

$("place-form").addEventListener("submit", placeOrder);
$("add-item").addEventListener("click", addItemRow);
$("flush-btn").addEventListener("click", flushOutbox);
$("refresh-btn").addEventListener("click", () => { loadOrders(); loadOutbox(); });
$("demo-btn").addEventListener("click", runDemo);

updateRemoveButtons();
loadOrders();
loadOutbox();
