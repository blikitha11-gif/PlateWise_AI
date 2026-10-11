// Dashboard View Logic & Plotly Visualizations

window.loadDashboard = async function() {
  await Promise.all([
    updateDashboardKPIs(),
    renderWasteTrendsChart(),
    renderWastefulItemsChart(),
    renderActualVsPredictedChart()
  ]);
};

async function updateDashboardKPIs() {
  try {
    const res = await fetch(`${window.API_BASE}/dashboard/summary`);
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("kpi-prepared").textContent = (data.total_meals_prepared || 0).toLocaleString();
    document.getElementById("kpi-sold").textContent = (data.total_meals_sold || 0).toLocaleString();
    document.getElementById("kpi-unsold").textContent = (data.total_unsold_meals || 0).toLocaleString();
    
    const surplusRate = data.total_meals_prepared > 0
      ? ((data.total_unsold_meals / data.total_meals_prepared) * 100).toFixed(1)
      : 0;
    document.getElementById("kpi-unsold-pct").textContent = `${surplusRate}% surplus rate`;

    document.getElementById("kpi-discarded").textContent = `${(data.total_discarded_kg || 0).toLocaleString()} kg`;
    document.getElementById("kpi-waste-cost").textContent = `Est. Cost: ₹${(data.total_waste_cost || 0).toLocaleString()}`;

    // Target banner
    document.getElementById("banner-target-date").textContent = `Target: ${data.next_day_target}`;
    document.getElementById("banner-pred-demand").textContent = `${Math.round(data.next_day_predicted_demand)} meals`;
    document.getElementById("banner-rec-prep").textContent = `${data.next_day_recommended_prepared} meals`;

    // Demo badge
    const badge = document.getElementById("data-status-badge");
    if (data.is_demo_data) {
      badge.textContent = "Demonstration Data (Synthetic)";
      badge.className = "badge badge-demo";
    } else {
      badge.textContent = data.record_count > 0 ? `Live Records (${data.record_count})` : "Empty Database";
      badge.className = "badge badge-success";
    }
  } catch (err) {
    console.error("Failed to load KPIs:", err);
  }
}

async function renderWasteTrendsChart() {
  const container = document.getElementById("chart-waste-trends");
  if (!container) return;

  try {
    const res = await fetch(`${window.API_BASE}/analytics/trends`);
    const data = await res.json();

    if (!data.dates || data.dates.length === 0) {
      container.innerHTML = `<div style="text-align:center; padding: 100px 0; color: #6b7280;">No data recorded yet. Load sample data or log daily entries.</div>`;
      return;
    }

    const tracePrepared = {
      x: data.dates,
      y: data.prepared,
      type: "scatter",
      mode: "lines",
      name: "Meals Prepared",
      line: { color: "#2d6a4f", width: 2 }
    };

    const traceSold = {
      x: data.dates,
      y: data.sold,
      type: "scatter",
      mode: "lines",
      name: "Meals Sold",
      line: { color: "#52b788", width: 2 }
    };

    const traceDiscarded = {
      x: data.dates,
      y: data.discarded_kg,
      type: "scatter",
      mode: "lines",
      name: "Discarded Waste (kg)",
      yaxis: "y2",
      line: { color: "#dc2626", dash: "dot", width: 2.5 }
    };

    const layout = {
      margin: { t: 30, r: 50, l: 50, b: 40 },
      legend: { orientation: "h", y: 1.15, x: 0 },
      xaxis: { title: "Date", showgrid: false },
      yaxis: { title: "Portions (Meals)", showgrid: true, gridcolor: "#f3f4f6" },
      yaxis2: {
        title: "Waste (kg)",
        overlaying: "y",
        side: "right",
        showgrid: false,
        titlefont: { color: "#dc2626" },
        tickfont: { color: "#dc2626" }
      },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent"
    };

    Plotly.newPlot(container, [tracePrepared, traceSold, traceDiscarded], layout, { responsive: true, displayModeBar: false });
  } catch (err) {
    console.error("Trends chart error:", err);
  }
}

async function renderWastefulItemsChart() {
  const container = document.getElementById("chart-wasteful-items");
  if (!container) return;

  try {
    const res = await fetch(`${window.API_BASE}/analytics/menu-items`);
    const items = await res.json();

    if (!items || items.length === 0) {
      container.innerHTML = `<div style="text-align:center; padding: 100px 0; color: #6b7280;">No menu items recorded.</div>`;
      return;
    }

    const labels = items.map(i => i.menu_item);
    const wasteKgs = items.map(i => i.total_discarded_kg);
    const costs = items.map(i => i.total_waste_cost);

    const trace = {
      x: labels,
      y: wasteKgs,
      type: "bar",
      marker: {
        color: ["#dc2626", "#ea580c", "#d97706", "#40916c", "#2d6a4f"],
        opacity: 0.85
      },
      text: wasteKgs.map((kg, idx) => `${kg} kg (₹${costs[idx]})`),
      textposition: "auto"
    };

    const layout = {
      margin: { t: 20, r: 20, l: 40, b: 60 },
      xaxis: { tickangle: -15 },
      yaxis: { title: "Discarded Food (kg)", gridcolor: "#f3f4f6" },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent"
    };

    Plotly.newPlot(container, [trace], layout, { responsive: true, displayModeBar: false });
  } catch (err) {
    console.error("Wasteful items chart error:", err);
  }
}

async function renderActualVsPredictedChart() {
  const container = document.getElementById("chart-actual-vs-predicted");
  if (!container) return;

  try {
    const res = await fetch(`${window.API_BASE}/ml/actual-vs-predicted?limit=25`);
    const data = await res.json();

    if (!data || data.length === 0) {
      container.innerHTML = `<div style="text-align:center; padding: 80px 0; color: #6b7280;">Train the model and run predictions to view actual vs forecast demand tracking.</div>`;
      return;
    }

    const labels = data.map(d => `${d.date.slice(5)} ${d.menu_item.split(" ")[0]}`);
    const actuals = data.map(d => d.actual_sold);
    const predicteds = data.map(d => d.predicted_demand !== null ? d.predicted_demand : null);

    const traceActual = {
      x: labels,
      y: actuals,
      type: "scatter",
      mode: "lines+markers",
      name: "Actual Demand (Sold)",
      line: { color: "#1b4332", width: 2.5 }
    };

    const tracePred = {
      x: labels,
      y: predicteds,
      type: "scatter",
      mode: "lines+markers",
      name: "Predicted Demand",
      line: { color: "#2563eb", dash: "dash", width: 2 }
    };

    const layout = {
      margin: { t: 20, r: 20, l: 50, b: 60 },
      legend: { orientation: "h", y: 1.15, x: 0 },
      xaxis: { tickangle: -25, showgrid: false },
      yaxis: { title: "Meals", gridcolor: "#f3f4f6" },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent"
    };

    Plotly.newPlot(container, [traceActual, tracePred], layout, { responsive: true, displayModeBar: false });
  } catch (err) {
    console.error("Actual vs Predicted chart error:", err);
  }
}
