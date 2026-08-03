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

    // 4. Display the result on the page
    displayRFQResult(data);
  } catch (error) {
    console.error("Failed to load sample RFQ:", error);
    displayError(error.message);
  }
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