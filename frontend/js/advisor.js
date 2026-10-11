// AI Food-Waste Advisor View Logic

window.loadAdvisorView = async function() {
  const modeBadge = document.getElementById("advisor-mode-badge");
  const summaryEl = document.getElementById("advisor-executive-summary");
  const actionsContainer = document.getElementById("advisor-action-items");
  const surplusTbody = document.querySelector("#table-surplus-targets tbody");
  const redistribEl = document.getElementById("advisor-redistribution-content");

  try {
    const res = await fetch(`${window.API_BASE}/advisor/insights`);
    const data = await res.json();

    modeBadge.textContent = data.advisor_mode || "Local Expert Rule Engine";
    modeBadge.className = data.advisor_mode.includes("AWS") ? "badge badge-success" : "badge badge-info";
    summaryEl.textContent = data.executive_summary || "No active advisory insights available.";

    // Action items
    if (data.action_items && data.action_items.length > 0) {
      actionsContainer.innerHTML = data.action_items.map(item => `
        <div style="margin-bottom: 14px; padding: 14px; border-radius: var(--radius-sm); background: #ffffff; border: 1px solid var(--border-light); border-left: 4px solid ${item.priority === 'HIGH' ? 'var(--danger)' : 'var(--primary-accent)'};">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <strong style="color:var(--primary-dark); font-size:14px;">${item.title}</strong>
            <span class="badge ${item.priority === 'HIGH' ? 'badge-danger' : 'badge-info'}">${item.priority}</span>
          </div>
          <p style="font-size:13px; color:var(--text-secondary); line-height:1.5;">${item.detail}</p>
        </div>
      `).join("");
    } else {
      actionsContainer.innerHTML = `<div style="color:var(--text-muted); padding:20px; text-align:center;">No high priority items flagged. Kitchen batch sizes are well balanced.</div>`;
    }

    // Surplus reduction targets
    if (data.surplus_reduction_targets && data.surplus_reduction_targets.length > 0) {
      surplusTbody.innerHTML = data.surplus_reduction_targets.map(t => `
        <tr>
          <td><strong>${t.menu_item}</strong></td>
          <td><span class="badge badge-warning">${t.current_surplus_rate}</span></td>
          <td style="font-size:12px;">${t.recommended_reduction}</td>
          <td><strong style="color:var(--success);">${t.estimated_annual_saving_kg} kg</strong></td>
        </tr>
      `).join("");
    } else {
      surplusTbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No persistent surplus items identified.</td></tr>`;
    }

    // Redistribution Protocol
    if (data.redistribution_protocol && data.redistribution_protocol.guidelines) {
      redistribEl.innerHTML = `
        <p style="margin-bottom: 10px; font-weight: 600; color: var(--primary-dark);">Standard Operating Protocol for Safe Food Recovery:</p>
        <ul style="padding-left: 20px;">
          ${data.redistribution_protocol.guidelines.map(g => `<li style="margin-bottom: 6px;">${g}</li>`).join("")}
        </ul>
      `;
    }
  } catch (err) {
    console.error("Advisor view error:", err);
  }
};

document.addEventListener("DOMContentLoaded", () => {
  const btnRefresh = document.getElementById("btn-refresh-advisor");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      window.showToast("Re-analyzing canteen waste records...", "info");
      window.loadAdvisorView();
    });
  }
});
