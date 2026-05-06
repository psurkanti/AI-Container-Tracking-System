const loginStatusBar = document.getElementById("loginStatusBar");
const trackStatusBar = document.getElementById("trackStatusBar");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const partSearchInput = document.getElementById("partSearchInput");
const resultsList = document.getElementById("resultsList");
const containersPanel = document.getElementById("containersPanel");

let authToken = "";
/** @type {Array<Record<string, unknown>>} */
let allCustomerRecords = [];

async function parseApiResponse(res) {
  const raw = await res.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch (_) {
    if (!res.ok) {
      throw new Error(raw || `Request failed (${res.status})`);
    }
  }
  return data;
}

function formatDate(value) {
  if (!value) return "-";
  if (typeof value === "string" && /^\d{1,2}\/\d{1,2}\/\d{4}$/.test(value.trim())) {
    return value.trim();
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  const mm = String(parsed.getMonth() + 1).padStart(2, "0");
  const dd = String(parsed.getDate()).padStart(2, "0");
  const yyyy = parsed.getFullYear();
  return `${mm}/${dd}/${yyyy}`;
}

function displayVal(v) {
  if (v === null || v === undefined || v === "") return "-";
  return String(v);
}

/** Filter already server-scoped rows from /my-parts-status (no second request — avoids 404 if API is outdated). */
function filterRecordsByPartQuery(records, query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return records.filter((r) => displayVal(r.part_number).toLowerCase().includes(q));
}

function setStatus(kind, text) {
  trackStatusBar.style.display = "block";
  trackStatusBar.className = `status ${kind}`;
  trackStatusBar.textContent = text;
}

function hideTrackStatus() {
  trackStatusBar.style.display = "none";
  trackStatusBar.textContent = "";
  trackStatusBar.className = "status idle";
}

function setLoginStatus(kind, text) {
  loginStatusBar.style.display = "block";
  loginStatusBar.className = `status ${kind}`;
  loginStatusBar.textContent = text;
}

/** Same fields for full list and search: container, part, qty arriving, dates, destination only. */
function partCardHtml(r) {
  return `<article class="issue-card medium"><div class="issue-title">${displayVal(r.part_number)}</div><div><strong>Quantity Arriving:</strong> ${displayVal(r.qty_loaded ?? r.quantity_arriving ?? r.qty_received)}</div><div><strong>Arrival Date:</strong> ${formatDate(r.arrival_date)}</div><div><strong>Estimated Arrival Date:</strong> ${formatDate(r.estimated_arrival_date ?? r.eta_date)}</div><div><strong>Destination:</strong> ${displayVal(r.destination)}</div></article>`;
}

function renderRecords(records, emptyMessage = "No authorized parts found.") {
  if (!records.length) {
    resultsList.innerHTML = `<article class='issue-card medium'><div>${emptyMessage}</div></article>`;
    return;
  }
  const byContainer = new Map();
  for (const r of records) {
    const key = r.container_number || "Unknown Container";
    if (!byContainer.has(key)) byContainer.set(key, []);
    byContainer.get(key).push(r);
  }

  resultsList.innerHTML = Array.from(byContainer.entries()).map(([container, parts]) => {
    const items = parts.map((r) => partCardHtml(r)).join("");
    return `<section class="panel"><h3 style="font-size:16px;margin-bottom:10px;">Container ${container}</h3><div class="issue-list">${items}</div></section>`;
  }).join("");
}

async function loadMyContainers() {
  const fd = new FormData();
  fd.append("auth_token", authToken);
  const res = await fetch("/my-parts-status", { method: "POST", body: fd });
  const data = await parseApiResponse(res);
  if (!res.ok) throw new Error(data.detail || "Failed to load containers");
  allCustomerRecords = data.payload?.records || [];
  if (partSearchInput) partSearchInput.value = "";
  renderRecords(allCustomerRecords);
}

async function login() {
  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  if (!username || !password) {
    throw new Error("Enter username and password");
  }

  const fd = new FormData();
  fd.append("username", username);
  fd.append("password", password);
  const res = await fetch("/auth/login", { method: "POST", body: fd });
  const data = await parseApiResponse(res);
  if (!res.ok) throw new Error(data.detail || "Login failed");
  authToken = data.payload.access_token;
  containersPanel.style.display = "block";
  resultsList.innerHTML = "";
  allCustomerRecords = [];
}

function runPartSearch() {
  if (!partSearchInput) return;
  const q = partSearchInput.value.trim();
  if (!q) {
    setStatus("error", "Enter a part number to search.");
    return;
  }
  const matches = filterRecordsByPartQuery(allCustomerRecords, q);
  renderRecords(matches, "No matching parts for that search.");
  if (matches.length) {
    hideTrackStatus();
  } else {
    setStatus("warn", "No matching parts for that search.");
  }
}

function clearPartSearch() {
  if (partSearchInput) partSearchInput.value = "";
  renderRecords(allCustomerRecords);
  hideTrackStatus();
}

document.querySelectorAll("button[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      const action = button.dataset.action;
      if (action === "login") {
        setLoginStatus("progress", "Logging in...");
        await login();
        setLoginStatus("success", "Login successful.");
        await loadMyContainers();
        hideTrackStatus();
        return;
      }
      if (action === "part-search") {
        runPartSearch();
        return;
      }
      if (action === "part-search-clear") {
        clearPartSearch();
        return;
      }
    } catch (err) {
      if (!authToken) {
        setLoginStatus("error", err.message);
      } else {
        setStatus("error", err.message);
      }
    }
  });
});

if (partSearchInput) {
  partSearchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      try {
        runPartSearch();
      } catch (err) {
        setStatus("error", err.message);
      }
    }
  });
}
