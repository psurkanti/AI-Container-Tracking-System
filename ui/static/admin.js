const statusBar = document.getElementById("statusBar");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const fileInput = document.getElementById("fileInput");
const customersList = document.getElementById("customersList");
const custUsername = document.getElementById("custUsername");
const custPassword = document.getElementById("custPassword");
const custParts = document.getElementById("custParts");
const custPins = document.getElementById("custPins");
const uploadPanel = document.getElementById("uploadPanel");
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
  fd.append("password", passwordInput.value.trim());
  const res = await fetch("/auth/login", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Login failed");
  authToken = data.payload.access_token;
  uploadPanel.style.display = "block";
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
    } catch (err) {
      setStatus("error", err.message);
    }
  });
});
