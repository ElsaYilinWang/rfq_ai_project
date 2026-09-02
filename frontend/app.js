// frontend/app.js

const API_BASE_URL = "http://127.0.0.1:8000";

const loadButton = document.getElementById("load-rfq-btn");

loadButton.addEventListener("click", loadSampleRFQ);

async function loadSampleRFQ() {
  try {
    // 1. Call the FastAPI backend endpoint
    const response = await fetch(`${API_BASE_URL}/rfqs/sample`);

    // 2. If the API response is not successful, show an error
    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }

    // 3. Convert JSON response into a JavaScript object
    const data = await response.json();

    // 4. Display the summary result on the page
    displayRFQResult(data);

    // 5. Also load and display the line-item detail for the same RFQ
    await loadSampleRFQItems();

    // 6. Also load and display supplier candidates for the same RFQ
    await loadSupplierCandidates();

  } catch (error) {
    console.error("Failed to load sample RFQ:", error);
    displayError(error.message);
  }
}

async function loadSampleRFQItems() {
  try {
    const response = await fetch(`${API_BASE_URL}/rfqs/sample/items`);

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }

    const data = await response.json();
    displayItemsTable(data.items);
  } catch (error) {
    console.error("Failed to load RFQ items:", error);
    displayItemsError(error.message);
  }
}

function displayItemsTable(items) {
  const tableBody = document.getElementById("items-table-body");
  tableBody.innerHTML = "";

  if (!items || items.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="8">No line items found.</td></tr>`;
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("tr");

    if (item.flags && item.flags.length > 0) {
      row.classList.add("flagged-row");
    }

    row.innerHTML = `
      <td>${item.line_item}</td>
      <td>${item.material_number}</td>
      <td>${item.description}</td>
      <td>${item.manufacturer ?? "N/A"}</td>
      <td>${item.part_number ?? "N/A"}</td>
      <td>${item.uom}</td>
      <td>${item.quantity}</td>
      <td>${item.flags && item.flags.length > 0 ? item.flags.join("; ") : "—"}</td>
    `;

    tableBody.appendChild(row);
  });
}

function displayItemsError(message) {
  const tableBody = document.getElementById("items-table-body");
  tableBody.innerHTML = `<tr><td colspan="8">Error: ${message}</td></tr>`;
}

async function loadSupplierCandidates() {
  try {
    const response = await fetch(`${API_BASE_URL}/rfqs/sample/supplier-candidates`);

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }

    const data = await response.json();
    displaySupplierCandidatesTable(data.supplier_candidates);
  } catch (error) {
    console.error("Failed to load supplier candidates:", error);
    displaySupplierCandidatesError(error.message);
  }
}

// Turns true/false/null into readable text instead of the raw JS value,
// per the "true/false values should be readable" requirement.
function formatBoolean(value) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return value ? "Yes" : "No";
}

function displaySupplierCandidatesTable(candidates) {
  const tableBody = document.getElementById("supplier-candidates-table-body");
  tableBody.innerHTML = "";

  if (!candidates || candidates.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="6">No supplier candidates found.</td></tr>`;
    return;
  }

  candidates.forEach((candidate) => {
    const row = document.createElement("tr");

    // Reuses the same flagged-row highlight as the items table — both
    // mean the same thing: this row needs a human to look at it.
    if (candidate.human_review_required) {
      row.classList.add("flagged-row");
    }

    row.innerHTML = `
      <td>${candidate.supplier_name}</td>
      <td>${candidate.manufacturer ?? "N/A"}</td>
      <td>${candidate.source}</td>
      <td>${formatBoolean(candidate.stale)}</td>
      <td>${formatBoolean(candidate.human_review_required)}</td>
      <td>${candidate.reason}</td>
    `;

    tableBody.appendChild(row);
  });
}

function displaySupplierCandidatesError(message) {
  const tableBody = document.getElementById("supplier-candidates-table-body");
  tableBody.innerHTML = `<tr><td colspan="6">Error: ${message}</td></tr>`;
}

function displayRFQResult(data) {
  document.getElementById("rfq-number").textContent = data.rfq_number;
  document.getElementById("status").textContent = data.status;
  document.getElementById("items-processed").textContent = data.items_processed;
  document.getElementById("next-action").textContent = data.next_action;
  document.getElementById("trace-id").textContent = data.trace_id || "N/A";

  displayWarnings(data.warnings);
}

function displayWarnings(warnings) {
  const warningsList = document.getElementById("warnings-list");

  // Clear the old warning list
  warningsList.innerHTML = "";

  if (!warnings || warnings.length === 0) {
    const listItem = document.createElement("li");
    listItem.textContent = "No validation warnings.";
    warningsList.appendChild(listItem);
    return;
  }

  warnings.forEach((warning) => {
    const listItem = document.createElement("li");

    listItem.textContent =
      `Line ${warning.line_item} / ${warning.field}: ${warning.message}`;

    warningsList.appendChild(listItem);
  });
}

function displayError(message) {
  document.getElementById("status").textContent = "error";
  document.getElementById("next-action").textContent = "check_api_or_logs";

  const warningsList = document.getElementById("warnings-list");
  warningsList.innerHTML = "";

  const listItem = document.createElement("li");
  listItem.textContent = `Error: ${message}`;
  warningsList.appendChild(listItem);
}