// Demand Prediction & Machine Learning View

window.loadPredictionView = async function() {
  await Promise.all([
    loadModelEvaluation(),
    loadActualVsPredictedTable()
  ]);

  const targetDateInput = document.getElementById("pred-target-date");
  if (targetDateInput && !targetDateInput.value) {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    targetDateInput.value = tomorrow.toISOString().split("T")[0];
  }
};

async function loadModelEvaluation() {
  try {
    const res = await fetch(`${window.API_BASE}/ml/evaluation`);
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("ml-model-name").textContent = data.model_name || "Random Forest";
    document.getElementById("ml-split-samples").textContent = `Train: ${data.train_samples || 0} | Test: ${data.test_samples || 0}`;
    document.getElementById("ml-mae").textContent = `${data.mae} meals`;
    document.getElementById("ml-baseline-mae").textContent = `Baseline MAE: ${data.baseline_mae} meals`;
    document.getElementById("ml-rmse").textContent = `${data.rmse} meals`;
    document.getElementById("ml-baseline-rmse").textContent = `Baseline RMSE: ${data.baseline_rmse} meals`;
    
    const impEl = document.getElementById("ml-improvement");
    impEl.textContent = `${data.improvement_pct > 0 ? '+' : ''}${data.improvement_pct}%`;
    impEl.style.color = data.improvement_pct > 0 ? "var(--success)" : "var(--warning)";
  } catch (err) {
    console.error("Evaluation load error:", err);
  }
}

async function loadActualVsPredictedTable() {
  const tbody = document.querySelector("#table-prediction-eval tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${window.API_BASE}/ml/actual-vs-predicted?limit=15`);
    const data = await res.json();

    if (!data || data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--text-muted);">No prediction matches found.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.map(r => {
      const predText = r.predicted_demand !== null ? `${r.predicted_demand}` : "<span style='color:#9ca3af;'>Unpredicted</span>";
      const errBadge = r.absolute_error !== null
        ? `<span class="badge ${r.absolute_error > 20 ? 'badge-warning' : 'badge-success'}">±${r.absolute_error}</span>`
        : "--";

      return `
        <tr>
          <td>${r.date}</td>
          <td>${r.menu_item}</td>
          <td><strong>${r.actual_sold}</strong></td>
          <td>${predText}</td>
          <td>${errBadge}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Actual vs Pred table error:", err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Retrain button
  const btnRetrain = document.getElementById("btn-retrain-ml");
  if (btnRetrain) {
    btnRetrain.addEventListener("click", async () => {
      btnRetrain.disabled = true;
      btnRetrain.textContent = "⏳ Training Models...";
      try {
        const res = await fetch(`${window.API_BASE}/ml/train`, { method: "POST" });
        const data = await res.json();
        if (data.status === "insufficient_data") {
          window.showToast(data.message, "warning");
        } else {
          window.showToast(`Random Forest Retrained! Held-out MAE: ${data.mae} meals (Improvement: ${data.mae_improvement_pct}%)`, "success");
          loadModelEvaluation();
          loadActualVsPredictedTable();
        }
      } catch (err) {
        window.showToast("Training failed", "error");
      } finally {
        btnRetrain.disabled = false;
        btnRetrain.textContent = "⚡ Retrain Random Forest Model";
      }
    });
  }

  // Interactive Predict Form
  const predictForm = document.getElementById("predict-form");
  if (predictForm) {
    predictForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const payload = {
        target_date: document.getElementById("pred-target-date").value,
        menu_item: document.getElementById("pred-menu-item").value,
        special_event: document.getElementById("pred-event").value,
        is_holiday: document.getElementById("pred-holiday").checked ? 1 : 0
      };

      try {
        const res = await fetch(`${window.API_BASE}/ml/predict`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok) {
          const outBox = document.getElementById("pred-output-box");
          outBox.style.display = "block";

          document.getElementById("pred-output-model").textContent = data.model_name;
          document.getElementById("pred-output-val").textContent = `${Math.round(data.predicted_demand)} meals`;
          document.getElementById("pred-output-range").textContent = 
            `Forecast Interval: ${Math.round(data.confidence_interval.lower)} to ${Math.round(data.confidence_interval.upper)} meals (${data.confidence_interval.confidence_level})`;

          const insightsList = data.feature_insights.map(i => `<li>${i}</li>`).join("");
          document.getElementById("pred-output-insights").innerHTML = `<ul style="padding-left:18px;">${insightsList}</ul>`;

          // Button to send to planner
          const btnSend = document.getElementById("pred-btn-send-planner");
          btnSend.onclick = () => {
            window.navigateTo("planner");
            setTimeout(() => {
              document.getElementById("plan-date").value = data.target_date;
              document.getElementById("plan-item").value = data.menu_item;
              document.getElementById("plan-predicted-override").value = Math.round(data.predicted_demand);
            }, 100);
          };

          window.showToast(`Forecast computed for ${data.menu_item}: ${Math.round(data.predicted_demand)} meals`, "success");
        } else {
          window.showToast(data.detail || "Prediction failed", "error");
        }
      } catch (err) {
        window.showToast("Forecast service error", "error");
      }
    });
  }
});
