const loginStatusBar = document.getElementById("loginStatusBar");
const trackStatusBar = document.getElementById("trackStatusBar");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const partSearchInput = document.getElementById("partSearchInput");
const resultsList = document.getElementById("resultsList");
const containersPanel = document.getElementById("containersPanel");
const destinationList = document.getElementById("destinationList");
const destinationClear = document.getElementById("destinationClear");
const shipmentMatchCount = document.getElementById("shipmentMatchCount");

let authToken = "";
/** @type {Array<Record<string, unknown>>} */
let allCustomerRecords = [];
/** Applied part-number search. Never written from a destination click. */
let appliedPartQuery = "";
/** @type {string | null} */
let selectedDestination = null;

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
  return ShipmentFilters.recordsForDestinationList(records, q);
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
  if (shipmentMatchCount) {
    const total = allCustomerRecords.length;
    shipmentMatchCount.textContent = `${records.length} of ${total} shipments match your filters`;
  }
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
  appliedPartQuery = "";
  selectedDestination = null;
  if (partSearchInput) partSearchInput.value = "";
  renderView();
}

function renderDestinationOptions(options) {
  if (!destinationList) return;
  destinationList.replaceChildren();
  if (!options.length) {
    const empty = document.createElement("p");
    empty.className = "panel-note";
    empty.textContent = "No destinations in the current results.";
    destinationList.appendChild(empty);
  } else {
    for (const option of options) {
      const active = selectedDestination && option.name.toLowerCase() === selectedDestination.toLowerCase();
      const button = document.createElement("button");
      button.type = "button";
      button.className = active ? "destination-chip active" : "destination-chip secondary";
      button.dataset.destination = option.name;
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.setAttribute(
        "aria-label",
        active ? `Clear ${option.name} filter` : `Show ${option.name} shipments`
      );
      const name = document.createElement("span");
      name.textContent = option.name;
      const count = document.createElement("span");
      count.className = "count";
      count.textContent = String(option.count);
      button.append(name, count);
      if (active) {
        const clearMark = document.createElement("span");
        clearMark.className = "chip-clear";
        clearMark.setAttribute("aria-hidden", "true");
        clearMark.textContent = "×";
        button.append(clearMark);
      }
      destinationList.appendChild(button);
    }
  }
  if (destinationClear) destinationClear.hidden = !selectedDestination;
}

function renderView(emptyMessage) {
  const base = ShipmentFilters.recordsForDestinationList(allCustomerRecords, appliedPartQuery);
  const options = ShipmentFilters.ensureSelectedListed(
    ShipmentFilters.destinationOptions(base),
    selectedDestination
  );
  renderDestinationOptions(options);
  const visible = ShipmentFilters.filterByDestination(base, selectedDestination);
  const message = emptyMessage || (selectedDestination
    ? "No shipments for that destination."
    : "No authorized parts found.");
  renderRecords(visible, message);
}

function selectDestination(name) {
  selectedDestination = ShipmentFilters.toggleDestination(selectedDestination, name);
  renderView();
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
  appliedPartQuery = q;
  const matches = filterRecordsByPartQuery(allCustomerRecords, q);
  renderView(matches.length ? undefined : "No matching parts for that search.");
  if (matches.length) {
    hideTrackStatus();
  } else {
    setStatus("warn", "No matching parts for that search.");
  }
}

function clearPartSearch() {
  appliedPartQuery = "";
  if (partSearchInput) partSearchInput.value = "";
  renderView();
  hideTrackStatus();
}

function clearDestinationFilter() {
  selectedDestination = null;
  renderView();
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
      if (action === "destination-clear") {
        clearDestinationFilter();
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

if (destinationList) {
  destinationList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-destination]");
    if (!button) return;
    selectDestination(button.dataset.destination || "");
  });
}

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
