/* Vanilla-JS client for the storefront demo (no build step). */
"use strict";

const $ = (id) => document.getElementById(id);
let PRODUCTS = [];

function ts() {
  return new Date().toLocaleTimeString();
}

function log(msg, cls) {
  const el = document.createElement("div");
  el.className = "log-entry " + (cls || "");
  el.innerHTML = '<span class="log-time">' + ts() + "</span>" + msg;
  const panel = $("log");
  panel.prepend(el);
  if (panel.children.length > 50) panel.lastChild.remove();
}

function renderProducts() {
  const container = $("product-cards");
  container.innerHTML = "";
  PRODUCTS.forEach((p) => {
    const card = document.createElement("div");
    card.className = "pair-card";
    card.innerHTML =
      '<div class="pair-name">' + p.name + " (" + p.sku + ")</div>" +
      '<div class="pair-rate">$' + p.unit_price + "</div>" +
      '<div class="pair-source">' + p.stock + " in stock</div>";
    container.appendChild(card);
  });
}

function renderOrderLines() {
  const container = $("order-lines");
  container.innerHTML = "";
  PRODUCTS.forEach((p) => {
    const row = document.createElement("label");
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.gap = ".5rem";
    row.style.margin = ".3rem 0";
    row.innerHTML =
      '<input type="checkbox" class="line-sku" value="' + p.sku + '" /> ' +
      p.name + " &mdash; $" + p.unit_price +
      ' <input type="number" class="line-qty" data-sku="' + p.sku +
      '" min="1" value="1" style="width:4rem;margin-left:.5rem" />';
    container.appendChild(row);
  });
}

async function loadCatalog() {
  try {
    const res = await fetch("/api/catalog/products");
    PRODUCTS = await res.json();
    renderProducts();
    renderOrderLines();
    log("catalog loaded &mdash; " + PRODUCTS.length + " product(s)");
  } catch (e) {
    log("catalog load failed: " + e.message, "log-error");
  }
}

function renderOrders(orders) {
  const container = $("orders-list");
  container.innerHTML = "";
  if (!orders.length) {
    container.innerHTML = '<p class="muted">No orders yet.</p>';
    return;
  }
  orders.slice().reverse().forEach((o) => {
    const div = document.createElement("div");
    div.className = "pair-card";
    const lines = o.lines
      .map((l) => l.qty + "x " + l.name + " = $" + l.line_total)
      .join(", ");
    div.innerHTML =
      '<div class="pair-name">' + o.order_id + " &mdash; " + o.customer + "</div>" +
      '<div class="pair-source">' + lines + "</div>" +
      '<div class="pair-rate">$' + o.total + "</div>";
    container.appendChild(div);
  });
}

async function loadOrders() {
  try {
    const res = await fetch("/api/orders");
    const orders = await res.json();
    renderOrders(orders);
  } catch (e) {
    log("orders load failed: " + e.message, "log-error");
  }
}

async function placeOrder(event) {
  event.preventDefault();
  const customer = $("customer").value.trim();
  const items = [...document.querySelectorAll(".line-sku:checked")].map((cb) => {
    const qtyInput = document.querySelector('.line-qty[data-sku="' + cb.value + '"]');
    return { sku: cb.value, qty: parseInt(qtyInput.value, 10) || 1 };
  });
  if (!customer || items.length === 0) {
    log("pick a customer and at least one product", "log-error");
    return;
  }
  try {
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer, items }),
    });
    const body = await res.json();
    if (!res.ok || body.error) {
      throw new Error(body.detail || body.error || "HTTP " + res.status);
    }
    log("order placed &mdash; " + body.order_id + " ($" + body.total + ")", "log-hit");
    await loadCatalog();
    await loadOrders();
  } catch (e) {
    log("order failed: " + e.message, "log-error");
  }
}

async function runDemo() {
  const btn = $("btn-demo");
  btn.disabled = true;
  btn.textContent = "Running...";
  try {
    const res = await fetch("/api/orders/demo/run", { method: "POST" });
    const body = await res.json();
    if (!res.ok || body.error) {
      throw new Error(body.detail || body.error || "HTTP " + res.status);
    }
    log("demo order placed &mdash; " + body.order_id + " ($" + body.total + ")", "log-hit");
    await loadCatalog();
    await loadOrders();
  } catch (e) {
    log("demo failed: " + e.message, "log-error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Demo Order";
  }
}

/* Wire up */
$("order-form").addEventListener("submit", placeOrder);
$("btn-demo").addEventListener("click", runDemo);

/* Initial load */
loadCatalog();
loadOrders();
