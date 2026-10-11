// Smart Preparation Planner View Logic

window.loadPlannerView = async function() {
  loadPlanHistory();

  const planDate = document.getElementById("plan-date");
  if (planDate && !planDate.value) {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    planDate.value = tomorrow.toISOString().split("T")[0];
  }
};

async function loadPlanHistory() {
  const tbody = document.querySelector("#table-plan-history tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${window.API_BASE}/planner/history?limit=10`);
    const plans = await res.json();

    if (!plans || plans.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No preparation plans generated yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = plans.map(p => `
      <tr>
        <td><strong>${p.target_date}</strong></td>
        <td>${p.menu_item}</td>
        <td>${Math.round(p.predicted_demand)}</td>
        <td>+${p.buffer_meals} (${p.buffer_percent}%)</td>
        <td><strong style="color:var(--primary-dark); font-size:14px;">${p.recommended_prepared}</strong></td>
        <td style="font-size:12px; color:var(--text-secondary); max-width:280px;">${p.rationale}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Plan history error:", err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const slider = document.getElementById("plan-buffer-slider");
  const display = document.getElementById("plan-buffer-display");

  if (slider && display) {
    slider.addEventListener("input", (e) => {
      display.textContent = `${e.target.value}%`;
    });
  }

  const plannerForm = document.getElementById("planner-form");
  if (plannerForm) {
    plannerForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const overrideVal = document.getElementById("plan-predicted-override").value;

      const payload = {
        target_date: document.getElementById("plan-date").value,
        menu_item: document.getElementById("plan-item").value,
        buffer_percent: parseFloat(slider.value),
        stockout_penalty_weight: parseFloat(document.getElementById("plan-stockout-weight").value),
        waste_penalty_weight: parseFloat(document.getElementById("plan-waste-weight").value),
        predicted_demand: overrideVal ? parseFloat(overrideVal) : null
      };

      try {
        const res = await fetch(`${window.API_BASE}/planner/recommend`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok) {
          renderPlanResult(data);
          loadPlanHistory();
          window.showToast(`Preparation plan computed: ${data.recommended_prepared} meals for ${data.menu_item}`, "success");
        } else {
          window.showToast(data.detail || "Planning calculation failed", "error");
        }
      } catch (err) {
        window.showToast("Failed to connect to planner service", "error");
      }
    });
  }
});

function renderPlanResult(plan) {
  const container = document.getElementById("plan-result-container");
  if (!container) return;

  const cost = plan.cost_estimation;

  container.innerHTML = `
    <div style="background: var(--mint-subtle); border-radius: var(--radius-md); padding: 20px; border-left: 4px solid var(--primary-accent);">
      <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px;">
        <span class="stat-label">Recommended Preparation</span>
        <span class="badge badge-success">${plan.model_source}</span>
      </div>

      <div style="font-size: 38px; font-weight: 800; color: var(--primary-dark); line-height: 1;">
        ${plan.recommended_prepared} <span style="font-size: 18px; font-weight: 500; color: var(--text-muted);">portions</span>
      </div>

      <div style="display: flex; gap: 20px; margin: 16px 0; padding: 12px 0; border-top: 1px solid rgba(0,0,0,0.06); border-bottom: 1px solid rgba(0,0,0,0.06); font-size: 13px;">
        <div>
          <span style="color: var(--text-muted);">Base Forecast:</span>
          <strong>${Math.round(plan.predicted_demand)} meals</strong>
        </div>
        <div>
          <span style="color: var(--text-muted);">Safety Margin:</span>
          <strong style="color: var(--warning);">+${plan.buffer_meals} meals (${plan.buffer_percent}%)</strong>
        </div>
      </div>

      <div style="margin-bottom: 16px;">
        <h4 style="font-size: 13px; font-weight: 700; color: var(--primary-dark); margin-bottom: 6px;">Transparent Kitchen Rationale:</h4>
        <p style="font-size: 12px; color: var(--text-secondary); line-height: 1.6; background: #ffffff; padding: 10px; border-radius: 4px; border: 1px solid var(--border-light);">
          ${plan.rationale}
        </p>
      </div>

      <div>
        <h4 style="font-size: 13px; font-weight: 700; color: var(--primary-dark); margin-bottom: 8px;">Economic Risk Assessment:</h4>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
          <div style="background: #ffffff; padding: 8px 12px; border-radius: 4px; border: 1px solid var(--border-light);">
            <div style="color: var(--text-muted);">Total Cooking Cost:</div>
            <strong>₹${cost.raw_cost_to_prepare.toLocaleString()}</strong>
          </div>
          <div style="background: #ffffff; padding: 8px 12px; border-radius: 4px; border: 1px solid var(--border-light);">
            <div style="color: var(--text-muted);">Surplus Risk Exposure:</div>
            <strong style="color: var(--warning);">₹${cost.maximum_surplus_cost_risk.toLocaleString()}</strong>
          </div>
        </div>
      </div>
    </div>
  `;
}
