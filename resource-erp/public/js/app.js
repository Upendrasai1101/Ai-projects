/* ==========================================================================
   Universal AI-Powered Resource & Budget ERP — Frontend logic
   Vanilla JS, no framework/build step — fetch() against the Java backend.
   ========================================================================== */

const state = {
  sessionId: null,
  profileName: null,
  profiles: [],
  resources: [],
};

const PROFILE_META = {
  "Retail / IT Hardware Store": { icon: "💻", desc: "Electronics, hardware & accessories" },
  "Pharmacy & Healthcare": { icon: "💊", desc: "Medicines & healthcare supplies" },
  "Construction Engineering": { icon: "🏗️", desc: "Cement, steel & site materials" },
  "Restaurant & Cloud Kitchen": { icon: "🍳", desc: "Raw ingredients & kitchen supplies" },
};

// ============================================================== API HELPER

async function api(path, { method = "GET", body, auth = true } = {}) {
  let url = path;
  if (auth) {
    url += (path.includes("?") ? "&" : "?") + "sessionId=" + encodeURIComponent(state.sessionId || "");
  }
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

// =================================================================== TOAST

function toast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = "toast" + (type === "error" ? " error" : "");
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 300);
  }, 3200);
}

// ============================================================= SCREEN SHOW

function showScreen(id) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

function openModal(id) {
  document.getElementById(id).classList.add("active");
}
function closeModal(id) {
  document.getElementById(id).classList.remove("active");
}
document.querySelectorAll("[data-close]").forEach((btn) => {
  btn.addEventListener("click", () => closeModal(btn.dataset.close));
});
document.querySelectorAll(".modal-overlay").forEach((overlay) => {
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.classList.remove("active");
  });
});

// ======================================================== PROFILE SELECTION

let pendingProfileId = null;

function renderProfileCards(containerId, onClick) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  state.profiles.forEach((p) => {
    const meta = PROFILE_META[p.name] || { icon: "📦", desc: "" };
    const card = document.createElement("div");
    card.className = "profile-card";
    card.innerHTML = `
      <span class="icon">${meta.icon}</span>
      <div class="name">${p.name}</div>
      <div class="desc">${meta.desc}</div>
    `;
    card.addEventListener("click", () => onClick(p));
    container.appendChild(card);
  });
}

async function loadProfiles() {
  state.profiles = await api("/api/profiles", { auth: false });
  renderProfileCards("profile-cards", (p) => {
    pendingProfileId = p.id;
    document.getElementById("budget-profile-label").textContent =
      `Profile selected: ${p.name}`;
    showScreen("screen-budget");
  });
}

document.getElementById("budget-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const budgetCap = parseFloat(document.getElementById("input-budget-cap").value);
  const budgetDays = parseInt(document.getElementById("input-budget-days").value, 10);
  try {
    const res = await api("/api/session", {
      method: "POST",
      auth: false,
      body: { profileId: pendingProfileId, budgetCap, budgetDays },
    });
    state.sessionId = res.sessionId;
    applyState(res.state);
    showScreen("screen-dashboard");
    toast(`Session started for ${res.state.profile}!`);
  } catch (err) {
    toast(err.message, "error");
  }
});

document.getElementById("btn-switch-profile").addEventListener("click", () => {
  renderProfileCards("switch-profile-cards", async (p) => {
    try {
      const res = await api("/api/profile/switch", { method: "POST", body: { profileId: p.id } });
      applyState(res);
      closeModal("modal-switch-profile");
      toast(`Switched to ${res.profile}. Inventory & budget unchanged.`);
    } catch (err) {
      toast(err.message, "error");
    }
  });
  openModal("modal-switch-profile");
});

// ================================================================== STATE

function applyState(s) {
  state.profileName = s.profile;
  state.resources = s.resources;
  document.getElementById("topbar-profile").textContent = s.profile;
  renderResourcesTable();
  renderLowStock();
  renderBudget(s.budget);
}

function updateBudgetPill(budget) {
  const pct = Math.min(100, Math.max(0, budget.utilizationPercent));
  const fill = document.getElementById("budget-pill-fill");
  fill.style.width = pct + "%";
  fill.classList.toggle("warn", budget.variance < 0 || pct > 85);
  document.getElementById("budget-pill-text").textContent =
    `Rs.${budget.remaining.toFixed(2)} remaining of Rs.${budget.budgetCap.toFixed(2)}`;
}

// ============================================================== RESOURCES

function renderResourcesTable() {
  const tbody = document.getElementById("resources-tbody");
  tbody.innerHTML = "";
  state.resources.forEach((r) => {
    const tr = document.createElement("tr");
    const badge = r.outOfStock
      ? '<span class="badge badge-out">OUT</span>'
      : r.lowStock
      ? '<span class="badge badge-low">LOW</span>'
      : '<span class="badge badge-ok">OK</span>';
    tr.innerHTML = `
      <td>#${r.id}</td>
      <td>${r.name} ${badge}</td>
      <td>${r.category}</td>
      <td>${r.quantity}</td>
      <td>${r.unit}</td>
      <td>Rs.${r.buyPrice.toFixed(2)}</td>
      <td>Rs.${r.sellPrice.toFixed(2)}</td>
      <td>${r.reorderLevel}</td>
      <td class="row-actions"></td>
    `;
    const actionsCell = tr.querySelector(".row-actions");

    const inBtn = mkBtn("+ In", async () => {
      const qty = promptNumber(`Add stock to "${r.name}" — quantity:`);
      if (qty === null) return;
      try {
        await api(`/api/resources/${r.id}/stock-in`, { method: "POST", body: { quantity: qty } });
        toast(`Stocked in ${qty} ${r.unit} of ${r.name}.`);
        await refreshResourcesAndStats();
      } catch (err) {
        toast(err.message, "error");
      }
    });
    const outBtn = mkBtn("- Out", async () => {
      const qty = promptNumber(`Remove stock from "${r.name}" — quantity:`);
      if (qty === null) return;
      try {
        await api(`/api/resources/${r.id}/stock-out`, { method: "POST", body: { quantity: qty } });
        toast(`Removed ${qty} ${r.unit} of ${r.name}.`);
        await refreshResourcesAndStats();
      } catch (err) {
        toast(err.message, "error");
      }
    });
    const emailBtn = mkBtn("✉", () => openAiReorderEmail(r));
    const delBtn = mkBtn("🗑", async () => {
      if (!confirm(`Delete "${r.name}"? This cannot be undone.`)) return;
      try {
        await api(`/api/resources/${r.id}`, { method: "DELETE" });
        toast(`Deleted ${r.name}.`);
        await refreshResourcesAndStats();
      } catch (err) {
        toast(err.message, "error");
      }
    });
    [inBtn, outBtn, emailBtn, delBtn].forEach((b) => actionsCell.appendChild(b));
    tbody.appendChild(tr);
  });
}

function mkBtn(label, onClick) {
  const b = document.createElement("button");
  b.className = "btn btn-ghost btn-small";
  b.style.marginRight = "6px";
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

function promptNumber(message) {
  const raw = prompt(message, "10");
  if (raw === null) return null;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : null;
}

async function refreshResourcesAndStats() {
  const resources = await api("/api/resources");
  state.resources = resources;
  renderResourcesTable();
  renderLowStock();
  const budget = await api("/api/budget");
  renderBudget(budget);
}

function renderLowStock() {
  const container = document.getElementById("lowstock-list");
  const lows = state.resources.filter((r) => r.lowStock);
  container.innerHTML = "";
  if (lows.length === 0) {
    container.innerHTML = `<p class="app-subtitle">All resources have sufficient stock! 🎉</p>`;
    return;
  }
  lows.forEach((r) => {
    const div = document.createElement("div");
    div.className = "stock-alert-card" + (r.outOfStock ? " out" : "");
    div.innerHTML = `
      <div class="name">${r.name}</div>
      <div class="meta">${r.category} · ${r.quantity} ${r.unit} left (reorder at ${r.reorderLevel})</div>
    `;
    container.appendChild(div);
  });
}

document.getElementById("btn-open-add").addEventListener("click", () => openModal("modal-add-resource"));

document.getElementById("add-resource-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    name: document.getElementById("ar-name").value,
    category: document.getElementById("ar-category").value,
    unit: document.getElementById("ar-unit").value,
    description: document.getElementById("ar-desc").value,
    quantity: parseInt(document.getElementById("ar-qty").value, 10),
    reorderLevel: parseInt(document.getElementById("ar-reorder").value, 10),
    buyPrice: parseFloat(document.getElementById("ar-buy").value),
    sellPrice: parseFloat(document.getElementById("ar-sell").value),
  };
  try {
    await api("/api/resources", { method: "POST", body });
    toast(`Added ${body.name} to inventory.`);
    e.target.reset();
    closeModal("modal-add-resource");
    await refreshResourcesAndStats();
  } catch (err) {
    toast(err.message, "error");
  }
});

// =========================================================== TRANSACTIONS

async function loadTransactions() {
  const tx = await api("/api/transactions");
  const tbody = document.getElementById("transactions-tbody");
  tbody.innerHTML = "";
  [...tx].reverse().forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${t.timestamp}</td>
      <td>${t.type}</td>
      <td>${t.resourceName} (#${t.resourceId})</td>
      <td>${t.quantityDelta > 0 ? "+" : ""}${t.quantityDelta}</td>
      <td>Rs.${t.amount.toFixed(2)}</td>
      <td>${t.note}</td>
    `;
    tbody.appendChild(tr);
  });
}

// =================================================================== BUDGET

function renderBudget(budget) {
  updateBudgetPill(budget);
  const grid = document.getElementById("budget-stats");
  const varianceClass = budget.variance < 0 ? "negative" : "positive";
  grid.innerHTML = `
    <div class="stat-card"><div class="label">Budget Cap</div><div class="value">Rs.${budget.budgetCap.toFixed(2)}</div></div>
    <div class="stat-card"><div class="label">Total Spent</div><div class="value">Rs.${budget.totalSpent.toFixed(2)}</div></div>
    <div class="stat-card"><div class="label">Remaining</div><div class="value">Rs.${budget.remaining.toFixed(2)}</div></div>
    <div class="stat-card"><div class="label">Utilization</div><div class="value">${budget.utilizationPercent.toFixed(1)}%</div></div>
    <div class="stat-card"><div class="label">Daily Burn Rate</div><div class="value">Rs.${budget.dailyBurnRate.toFixed(2)}</div></div>
    <div class="stat-card"><div class="label">Projected Spend</div><div class="value">Rs.${budget.projectedSpend.toFixed(2)}</div></div>
    <div class="stat-card"><div class="label">Cost Variance</div><div class="value ${varianceClass}">Rs.${budget.variance.toFixed(2)}</div></div>
  `;
}

document.getElementById("purchase-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const description = document.getElementById("purchase-desc").value;
  const cost = parseFloat(document.getElementById("purchase-cost").value);
  try {
    const res = await api("/api/budget/purchase", { method: "POST", body: { description, cost } });
    renderBudget(res.budget);
    if (res.blocked) {
      showAiModal("Smart Purchase Guard — Blocked");
      renderAiResult(res.aiAdvice, `This purchase of Rs.${cost.toFixed(2)} exceeds your remaining budget. AI-suggested reallocation strategies:`);
    } else {
      toast(`Purchase recorded: ${description} (Rs.${cost.toFixed(2)})`);
      e.target.reset();
    }
  } catch (err) {
    toast(err.message, "error");
  }
});

document.getElementById("eoq-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    name: document.getElementById("eoq-name").value,
    annualDemand: parseInt(document.getElementById("eoq-demand").value, 10),
    orderingCost: parseFloat(document.getElementById("eoq-order-cost").value),
    holdingCost: parseFloat(document.getElementById("eoq-holding-cost").value),
  };
  showAiModal("Cost Optimizer (EOQ)");
  renderAiLoading();
  try {
    const res = await api("/api/budget/eoq", { method: "POST", body });
    renderAiResult(res.aiAdvice, `Calculated EOQ: ~${res.eoq.toFixed(1)} units per order.`);
  } catch (err) {
    renderAiError(err.message);
  }
});

// ====================================================================== AI

function showAiModal(title) {
  document.getElementById("ai-modal-title").textContent = title;
  openModal("modal-ai");
}

function renderAiLoading() {
  document.getElementById("ai-modal-body").innerHTML = `
    <div class="spinner-wrap">
      <div class="spinner"></div>
      <div>Asking Groq AI...</div>
    </div>
  `;
}

function renderAiResult(text, preface) {
  document.getElementById("ai-modal-body").innerHTML = `
    ${preface ? `<p class="app-subtitle" style="text-align:left;margin-top:-4px;">${preface}</p>` : ""}
    <div class="ai-result"></div>
  `;
  document.querySelector("#ai-modal-body .ai-result").textContent = text;
}

function renderAiError(message) {
  document.getElementById("ai-modal-body").innerHTML = `<div class="ai-result">⚠ ${message}</div>`;
}

document.querySelectorAll(".ai-card").forEach((card) => {
  card.addEventListener("click", () => handleAiCard(card.dataset.ai));
});

async function handleAiCard(kind) {
  if (kind === "advisor") {
    showAiModal("AI Industry Business Advisor");
    renderAiLoading();
    try {
      const res = await api("/api/ai/advisor", { method: "POST" });
      renderAiResult(res.result);
    } catch (err) {
      renderAiError(err.message);
    }
    return;
  }

  if (kind === "fraud-audit") {
    showAiModal("AI Fraud & Stock Leakage Audit");
    renderAiLoading();
    try {
      const res = await api("/api/ai/fraud-audit", { method: "POST" });
      renderAiResult(res.result);
    } catch (err) {
      renderAiError(err.message);
    }
    return;
  }

  if (kind === "query") {
    showAiModal("AI Smart Natural Language Query");
    document.getElementById("ai-modal-body").innerHTML = `
      <form id="ai-query-form" class="form-card">
        <label>Ask a question about your inventory
          <input type="text" id="ai-query-input" placeholder="e.g. What is my most profitable item?" required />
        </label>
        <button type="submit" class="btn btn-primary btn-block">Ask AI</button>
      </form>
    `;
    document.getElementById("ai-query-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const question = document.getElementById("ai-query-input").value;
      renderAiLoading();
      try {
        const res = await api("/api/ai/query", { method: "POST", body: { question } });
        renderAiResult(res.result, `Q: ${question}`);
      } catch (err) {
        renderAiError(err.message);
      }
    });
    return;
  }

  if (kind === "categorize") {
    showAiModal("AI Auto-Categorizer & Description Writer");
    document.getElementById("ai-modal-body").innerHTML = `
      <form id="ai-cat-form" class="form-card">
        <label>New item name
          <input type="text" id="ai-cat-input" placeholder="e.g. Wireless Barcode Scanner" required />
        </label>
        <button type="submit" class="btn btn-primary btn-block">Generate</button>
      </form>
    `;
    document.getElementById("ai-cat-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("ai-cat-input").value;
      renderAiLoading();
      try {
        const res = await api("/api/ai/categorize", { method: "POST", body: { name } });
        renderAiResult(res.result, `Item: ${name}`);
      } catch (err) {
        renderAiError(err.message);
      }
    });
    return;
  }

  if (kind === "reorder-email") {
    if (state.resources.length === 0) {
      toast("Add a resource first.", "error");
      return;
    }
    openAiReorderEmail(state.resources[0]);
  }
}

function openAiReorderEmail(defaultResource) {
  showAiModal("AI Supplier Reorder Email Generator");
  const options = state.resources
    .map((r) => `<option value="${r.id}" ${r.id === defaultResource.id ? "selected" : ""}>#${r.id} — ${r.name}</option>`)
    .join("");
  document.getElementById("ai-modal-body").innerHTML = `
    <form id="ai-email-form" class="form-card">
      <label>Resource to reorder
        <select id="ai-email-resource">${options}</select>
      </label>
      <label>Supplier name (optional)
        <input type="text" id="ai-email-supplier" placeholder="e.g. MedPlus Distributors" />
      </label>
      <button type="submit" class="btn btn-primary btn-block">Generate Email</button>
    </form>
  `;
  document.getElementById("ai-email-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const resourceId = parseInt(document.getElementById("ai-email-resource").value, 10);
    const supplier = document.getElementById("ai-email-supplier").value;
    renderAiLoading();
    try {
      const res = await api("/api/ai/reorder-email", { method: "POST", body: { resourceId, supplier } });
      renderAiResult(res.result);
    } catch (err) {
      renderAiError(err.message);
    }
  });
}

// ==================================================================== TABS

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById("panel-" + tab.dataset.tab).classList.add("active");

    if (tab.dataset.tab === "transactions") loadTransactions();
    if (tab.dataset.tab === "budget") api("/api/budget").then(renderBudget);
  });
});

// ==================================================================== INIT

loadProfiles().catch((err) => toast(err.message, "error"));
