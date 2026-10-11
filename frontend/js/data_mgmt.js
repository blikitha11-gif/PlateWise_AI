// Data Management View Logic (CRUD, Filter, Pagination, CSV Upload)

let currentSkip = 0;
const pageLimit = 25;

window.loadDataManagementView = function() {
  currentSkip = 0;
  fetchRecords();
};

async function fetchRecords() {
  const itemFilter = document.getElementById("filter-menu-item").value;
  const fromFilter = document.getElementById("filter-date-from").value;
  const toFilter = document.getElementById("filter-date-to").value;

  let url = `${window.API_BASE}/records?skip=${currentSkip}&limit=${pageLimit}`;
  if (itemFilter) url += `&menu_item=${encodeURIComponent(itemFilter)}`;
  if (fromFilter) url += `&date_from=${encodeURIComponent(fromFilter)}`;
  if (toFilter) url += `&date_to=${encodeURIComponent(toFilter)}`;

  try {
    const res = await fetch(url);
    const data = await res.json();

    document.getElementById("data-records-count").textContent = `Historical Records (${data.total})`;
    
    const pageNum = Math.floor(currentSkip / pageLimit) + 1;
    const totalPages = Math.ceil(data.total / pageLimit) || 1;
    document.getElementById("data-page-indicator").textContent = `Page ${pageNum} of ${totalPages}`;

    document.getElementById("btn-prev-page").disabled = currentSkip === 0;
    document.getElementById("btn-next-page").disabled = (currentSkip + pageLimit) >= data.total;

    renderRecordsTable(data.records);
  } catch (err) {
    console.error("Fetch records error:", err);
  }
}

function renderRecordsTable(records) {
  const tbody = document.querySelector("#table-all-records tbody");
  if (!tbody) return;

  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color:var(--text-muted); padding:30px;">No matching records found.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map(r => `
    <tr>
      <td>${r.id}</td>
      <td><strong>${r.date}</strong></td>
      <td>${r.menu_item}</td>
      <td>${r.meal_category}</td>
      <td>${r.meals_prepared}</td>
      <td>${r.meals_sold}</td>
      <td><span class="badge ${r.food_discarded_kg > 4 ? 'badge-danger' : 'badge-success'}">${r.food_discarded_kg} kg</span></td>
      <td>${r.special_event}</td>
      <td style="max-width:140px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${r.notes || ''}">${r.notes || '--'}</td>
      <td>
        <div style="display:flex; gap:6px;">
          <button class="btn btn-outline btn-sm" onclick="openEditRecordModal(${JSON.stringify(r).replace(/"/g, '&quot;')})">✏️</button>
          <button class="btn btn-danger btn-sm" onclick="deleteRecord(${r.id}, '${r.menu_item}', '${r.date}')">🗑️</button>
        </div>
      </td>
    </tr>
  `).join("");
}

window.openEditRecordModal = function(rec) {
  document.getElementById("edit-record-id").value = rec.id;
  document.getElementById("edit-record-date").value = rec.date;
  document.getElementById("edit-record-item").value = rec.menu_item;
  document.getElementById("edit-record-prepared").value = rec.meals_prepared;
  document.getElementById("edit-record-sold").value = rec.meals_sold;
  document.getElementById("edit-record-leftover").value = rec.leftover_meals;
  document.getElementById("edit-record-discarded").value = rec.food_discarded_kg;
  document.getElementById("edit-record-notes").value = rec.notes || "";

  window.openModal("modal-edit-record");
};

window.deleteRecord = async function(id, item, date) {
  if (!confirm(`Delete meal log for '${item}' on ${date}?`)) return;

  try {
    const res = await fetch(`${window.API_BASE}/records/${id}`, { method: "DELETE" });
    if (res.ok) {
      window.showToast("Record successfully deleted", "info");
      fetchRecords();
    } else {
      window.showToast("Failed to delete record", "error");
    }
  } catch (err) {
    window.showToast("Connection error", "error");
  }
};

document.addEventListener("DOMContentLoaded", () => {
  // Filter button
  const btnFilter = document.getElementById("btn-apply-filter");
  if (btnFilter) {
    btnFilter.addEventListener("click", () => {
      currentSkip = 0;
      fetchRecords();
    });
  }

  // Pagination buttons
  const btnPrev = document.getElementById("btn-prev-page");
  const btnNext = document.getElementById("btn-next-page");
  if (btnPrev) {
    btnPrev.addEventListener("click", () => {
      if (currentSkip >= pageLimit) {
        currentSkip -= pageLimit;
        fetchRecords();
      }
    });
  }
  if (btnNext) {
    btnNext.addEventListener("click", () => {
      currentSkip += pageLimit;
      fetchRecords();
    });
  }

  // Edit Form Submit
  const editForm = document.getElementById("form-edit-record");
  if (editForm) {
    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const id = document.getElementById("edit-record-id").value;
      const prep = parseInt(document.getElementById("edit-record-prepared").value, 10);
      const sold = parseInt(document.getElementById("edit-record-sold").value, 10);

      if (sold > prep) {
        window.showToast("Meals sold cannot exceed meals prepared!", "error");
        return;
      }

      const payload = {
        meals_prepared: prep,
        meals_sold: sold,
        leftover_meals: parseInt(document.getElementById("edit-record-leftover").value || "0", 10),
        food_discarded_kg: parseFloat(document.getElementById("edit-record-discarded").value || "0.0"),
        notes: document.getElementById("edit-record-notes").value
      };

      try {
        const res = await fetch(`${window.API_BASE}/records/${id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          window.showToast("Record updated successfully!", "success");
          window.closeModal("modal-edit-record");
          fetchRecords();
        } else {
          const data = await res.json();
          window.showToast(data.detail || "Update failed", "error");
        }
      } catch (err) {
        window.showToast("Connection failed", "error");
      }
    });
  }

  // Open CSV Upload Modal
  const btnOpenUpload = document.getElementById("btn-open-upload-modal");
  if (btnOpenUpload) {
    btnOpenUpload.addEventListener("click", () => {
      document.getElementById("csv-file-input").value = "";
      document.getElementById("upload-result-feedback").style.display = "none";
      window.openModal("modal-upload-csv");
    });
  }

  // CSV Upload Submit
  const uploadForm = document.getElementById("form-upload-csv");
  if (uploadForm) {
    uploadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fileInput = document.getElementById("csv-file-input");
      if (!fileInput.files || fileInput.files.length === 0) {
        window.showToast("Select a CSV file first", "warning");
        return;
      }

      const formData = new FormData();
      formData.append("file", fileInput.files[0]);

      const feedback = document.getElementById("upload-result-feedback");
      feedback.style.display = "block";
      feedback.innerHTML = `<span style="color:var(--text-muted);">Processing CSV upload...</span>`;

      try {
        const res = await fetch(`${window.API_BASE}/csv/upload`, {
          method: "POST",
          body: formData
        });

        const data = await res.json();
        if (res.ok && data.success) {
          feedback.innerHTML = `
            <div style="background:var(--mint-subtle); padding:10px; border-radius:4px; border:1px solid #bbf7d0;">
              <strong style="color:var(--success);">Upload Successful!</strong><br>
              Imported: <strong>${data.imported_count}</strong> rows.<br>
              Skipped: <strong>${data.skipped_count}</strong> rows.
              ${data.errors && data.errors.length > 0 ? `<br><small style="color:var(--text-muted);">${data.errors.slice(0, 3).join("<br>")}</small>` : ''}
            </div>
          `;
          window.showToast(`Imported ${data.imported_count} records from CSV!`, "success");
          fetchRecords();
        } else {
          feedback.innerHTML = `
            <div style="background:var(--danger-bg); padding:10px; border-radius:4px; color:var(--danger);">
              <strong>Upload Failed:</strong> ${data.error || data.detail || "Validation error"}
            </div>
          `;
        }
      } catch (err) {
        feedback.innerHTML = `<span style="color:var(--danger);">Upload connection error</span>`;
      }
    });
  }
});
