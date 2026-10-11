// Impact & Analytics View Logic

window.loadAnalyticsView = async function() {
  await Promise.all([
    loadImpactComparison(),
    loadMenuItemBreakdownTable()
  ]);
};

async function loadImpactComparison() {
  try {
    const res = await fetch(`${window.API_BASE}/analytics/impact`);
    const data = await res.json();

    if (!data.has_data) {
      document.getElementById("impact-avoided-kg").textContent = "--";
      document.getElementById("impact-cost-saved").textContent = "₹--";
      document.getElementById("impact-reduction-pct").textContent = "--";
      document.getElementById("impact-surplus-drop").textContent = "--";
      document.getElementById("impact-baseline-stats").textContent = data.message || "Insufficient longitudinal data.";
      document.getElementById("impact-optimized-stats").textContent = "Log more daily entries to track longitudinal impact.";
      return;
    }

    const imp = data.impact_metrics;
    const b = data.baseline_period;
    const o = data.optimized_period;

    document.getElementById("impact-avoided-kg").textContent = `${imp.estimated_avoided_waste_kg} kg`;
    document.getElementById("impact-cost-saved").textContent = `₹${imp.estimated_cost_saved.toLocaleString()}`;
    document.getElementById("impact-reduction-pct").textContent = `${imp.relative_reduction_pct}%`;
    
    const surplusDrop = (b.avg_surplus_rate_pct - o.avg_surplus_rate_pct).toFixed(1);
    document.getElementById("impact-surplus-drop").textContent = `-${surplusDrop}%`;

    document.getElementById("impact-baseline-title").textContent = b.name;
    document.getElementById("impact-baseline-stats").innerHTML = `
      <strong>${b.days_recorded} days logged:</strong> Cooked ${b.meals_prepared.toLocaleString()} meals, 
      Served ${b.meals_sold.toLocaleString()} meals. 
      Recorded <strong>${b.discarded_kg_measured} kg</strong> of discarded food (${b.waste_per_1000_meals_kg} kg / 1k meals). 
      Average kitchen surplus rate: <strong>${b.avg_surplus_rate_pct}%</strong>.
    `;

    document.getElementById("impact-optimized-title").textContent = o.name;
    document.getElementById("impact-optimized-stats").innerHTML = `
      <strong>${o.days_recorded} days logged:</strong> Cooked ${o.meals_prepared.toLocaleString()} meals, 
      Served ${o.meals_sold.toLocaleString()} meals. 
      Recorded <strong>${o.discarded_kg_measured} kg</strong> of discarded food (${o.waste_per_1000_meals_kg} kg / 1k meals). 
      Average kitchen surplus rate: <strong>${o.avg_surplus_rate_pct}%</strong>.
    `;
  } catch (err) {
    console.error("Impact comparison error:", err);
  }
}

async function loadMenuItemBreakdownTable() {
  const tbody = document.querySelector("#table-menu-item-breakdown tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${window.API_BASE}/analytics/menu-items`);
    const items = await res.json();

    if (!items || items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No records available.</td></tr>`;
      return;
    }

    tbody.innerHTML = items.map(i => `
      <tr>
        <td><strong>${i.menu_item}</strong></td>
        <td><span class="badge badge-info">${i.meal_category}</span></td>
        <td>${i.total_prepared.toLocaleString()}</td>
        <td>${i.total_sold.toLocaleString()}</td>
        <td>${i.total_unsold.toLocaleString()}</td>
        <td><span class="badge ${i.waste_rate_pct > 15 ? 'badge-warning' : 'badge-success'}">${i.waste_rate_pct}%</span></td>
        <td><strong style="color:var(--danger);">${i.total_discarded_kg} kg</strong></td>
        <td>₹${i.total_waste_cost.toLocaleString()}</td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Menu breakdown table error:", err);
  }
}
