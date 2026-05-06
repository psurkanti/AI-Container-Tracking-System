const statusBar = document.getElementById("statusBar");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const fileInput = document.getElementById("fileInput");
const customersList = document.getElementById("customersList");
const custUsername = document.getElementById("custUsername");
const custPassword = document.getElementById("custPassword");
const custParts = document.getElementById("custParts");
const custPins = document.getElementById("custPins");
const mContainerNumber = document.getElementById("mContainerNumber");
const mPoNumber = document.getElementById("mPoNumber");
const mPartNumber = document.getElementById("mPartNumber");
const mSupplierName = document.getElementById("mSupplierName");
const mQtyOrdered = document.getElementById("mQtyOrdered");
const mQtyLoaded = document.getElementById("mQtyLoaded");
const mQtyReceived = document.getElementById("mQtyReceived");
const mContainerStatus = document.getElementById("mContainerStatus");
const mEtaDate = document.getElementById("mEtaDate");
const mArrivalDate = document.getElementById("mArrivalDate");
const mEstimatedArrivalDate = document.getElementById("mEstimatedArrivalDate");
const mDestination = document.getElementById("mDestination");
const mTrackingPin = document.getElementById("mTrackingPin");
const mQcStatus = document.getElementById("mQcStatus");
const uploadPanel = document.getElementById("uploadPanel");
const manualPanel = document.getElementById("manualPanel");
const customerAccessPanel = document.getElementById("customerAccessPanel");

let authToken = "";

function setStatus(kind, text) {
  statusBar.style.display = "block";
  statusBar.className = `status ${kind}`;
  statusBar.textContent = text;
}

async function login() {
  const fd = new FormData();
  fd.append("username", usernameInput.value.trim());
  fd.append("password", passwordInput.value);
  const res = await fetch("/auth/login", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Login failed");
  authToken = data.payload.access_token;
  uploadPanel.style.display = "block";
  manualPanel.style.display = "block";
  customerAccessPanel.style.display = "block";
}

async function upload() {
  const fd = new FormData();
  fd.append("auth_token", authToken);
  fd.append("file", fileInput.files[0]);
  const res = await fetch("/upload-data", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
}

function renderCustomers(customers = []) {
  if (!customers.length) {
    customersList.innerHTML = "<article class='issue-card medium'><div>No customers found.</div></article>";
    return;
  }
  customersList.innerHTML = customers.map((c) => `
    <article class="issue-card medium">
      <div class="issue-title">${c.username}</div>
      <div><strong>Parts:</strong> ${(c.allowed_part_numbers || []).join(", ")}</div>
      <div><strong>Pins:</strong> ${(c.allowed_tracking_pins || []).join(", ")}</div>
    </article>
  `).join("");
}

async function customersListApi() {
  const fd = new FormData();
  fd.append("auth_token", authToken);
  const res = await fetch("/admin/customers/list", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to list customers");
  renderCustomers(data.payload.customers || []);
}

async function customersUpsertApi() {
  const fd = new FormData();
  fd.append("auth_token", authToken);
  fd.append("username", custUsername.value.trim());
  fd.append("password", custPassword.value);
  fd.append("allowed_part_numbers", custParts.value.trim());
  fd.append("allowed_tracking_pins", custPins.value.trim());
  const res = await fetch("/admin/customers/upsert", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to save customer");
}

async function customersDeleteApi() {
  const fd = new FormData();
  fd.append("auth_token", authToken);
  fd.append("username", custUsername.value.trim());
  const res = await fetch("/admin/customers/delete", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to delete customer");
}

async function manualSaveApi() {
  const fd = new FormData();
  fd.append("auth_token", authToken);
  fd.append("container_number", mContainerNumber.value.trim());
  fd.append("po_number", mPoNumber.value.trim());
  fd.append("part_number", mPartNumber.value.trim());
  fd.append("supplier_name", mSupplierName.value.trim());
  fd.append("qty_ordered", mQtyOrdered.value || "0");
  fd.append("qty_loaded", mQtyLoaded.value || "0");
  fd.append("qty_received", mQtyReceived.value || "0");
  fd.append("container_status", mContainerStatus.value.trim());
  fd.append("eta_date", mEtaDate.value);
  fd.append("arrival_date", mArrivalDate.value);
  fd.append("estimated_arrival_date", mEstimatedArrivalDate.value);
  fd.append("destination", mDestination.value.trim());
  fd.append("tracking_pin", mTrackingPin.value.trim());
  fd.append("qc_status", mQcStatus.value.trim() || "Pending");
  const res = await fetch("/admin/manual-entry", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to save manual entry");
}

document.querySelectorAll("button[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      const action = button.dataset.action;
      if (action === "login") {
        setStatus("progress", "Logging in...");
        await login();
        setStatus("success", "Admin login successful.");
        return;
      }
      if (!authToken) throw new Error("Please login first");
      if (action === "upload") {
        if (!fileInput.files[0]) throw new Error("Select CSV file");
        setStatus("progress", "Uploading...");
        await upload();
        setStatus("success", "Upload successful.");
        return;
      }
      if (action === "customers-list") {
        setStatus("progress", "Loading customers...");
        await customersListApi();
        setStatus("success", "Customer access loaded.");
        return;
      }
      if (action === "customers-upsert") {
        setStatus("progress", "Saving customer access...");
        await customersUpsertApi();
        await customersListApi();
        setStatus("success", "Customer access saved.");
        return;
      }
      if (action === "customers-delete") {
        setStatus("progress", "Deleting customer...");
        await customersDeleteApi();
        await customersListApi();
        setStatus("success", "Customer deleted.");
        return;
      }
      if (action === "manual-save") {
        setStatus("progress", "Saving manual entry...");
        await manualSaveApi();
        setStatus("success", "Manual entry saved.");
      }
    } catch (err) {
      setStatus("error", err.message);
    }
  });
});
