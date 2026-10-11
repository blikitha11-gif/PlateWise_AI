// Global Application Controller & State
window.API_BASE = "/api";

window.showToast = function(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
};

window.openModal = function(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.add("open");
};

window.closeModal = function(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.remove("open");
};

window.navigateTo = function(viewName) {
  document.querySelectorAll(".nav-link").forEach(link => {
    link.classList.toggle("active", link.dataset.view === viewName);
  });

  document.querySelectorAll(".view-section").forEach(sec => {
    sec.classList.toggle("active-view", sec.id === `view-${viewName}`);
  });

  const titles = {
    dashboard: { title: "Executive Dashboard", sub: "Real-time canteen meal demand & food waste metrics" },
    entry: { title: "Daily Data Entry", sub: "Log cooking, consumption, and discarded food amounts" },
    prediction: { title: "Demand Prediction", sub: "Machine learning demand forecasting with chronological validation" },
    planner: { title: "Smart Prep Planner", sub: "Calibrated kitchen preparation recommendations with configurable buffers" },
    advisor: { title: "AI Food-Waste Advisor", sub: "Actionable surplus prevention & safe redistribution guidance" },
    analytics: { title: "Impact & Analytics", sub: "Longitudinal audit comparing baseline waste against optimized outcomes" },
    data: { title: "Data Management", sub: "Inspect historical records, edit, filter, or import/export CSV files" }
  };

  const info = titles[viewName] || titles.dashboard;
  document.getElementById("page-title").textContent = info.title;
  document.getElementById("page-subtitle").textContent = info.sub;

  // View-specific initializers
  if (viewName === "dashboard" && window.loadDashboard) window.loadDashboard();
  if (viewName === "prediction" && window.loadPredictionView) window.loadPredictionView();
  if (viewName === "planner" && window.loadPlannerView) window.loadPlannerView();
  if (viewName === "advisor" && window.loadAdvisorView) window.loadAdvisorView();
  if (viewName === "analytics" && window.loadAnalyticsView) window.loadAnalyticsView();
  if (viewName === "data" && window.loadDataManagementView) window.loadDataManagementView();
};

document.addEventListener("DOMContentLoaded", () => {
  // Navigation Links
  document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const view = link.dataset.view;
      window.navigateTo(view);
    });
  });

  // Seed Demo Data Button
  const btnSeed = document.getElementById("btn-seed-data");
  if (btnSeed) {
    btnSeed.addEventListener("click", async () => {
      if (!confirm("Load realistic synthetic demonstration data (120 days across 5 menu items)?")) return;
      btnSeed.disabled = true;
      btnSeed.textContent = "⏳ Seeding Data...";
      try {
        const res = await fetch(`${window.API_BASE}/seed-sample-data`, { method: "POST" });
        const data = await res.json();
        if (res.ok) {
          window.showToast(`Loaded ${data.records_inserted} demonstration meal records and trained ML model!`, "success");
          window.loadDashboard();
        } else {
          window.showToast(data.detail || "Error loading seed data", "error");
        }
      } catch (err) {
        window.showToast("Connection failed", "error");
      } finally {
        btnSeed.disabled = false;
        btnSeed.textContent = "⚡ Load Sample Data";
      }
    });
  }

  // Clear Data Button
  const btnClear = document.getElementById("btn-clear-data");
  if (btnClear) {
    btnClear.addEventListener("click", async () => {
      if (!confirm("Are you sure you want to clear all data? This resets the SQLite database.")) return;
      try {
        const res = await fetch(`${window.API_BASE}/clear-data`, { method: "POST" });
        const data = await res.json();
        window.showToast(data.message, "info");
        window.loadDashboard();
      } catch (err) {
        window.showToast("Failed to clear data", "error");
      }
    });
  }

  // Initial Load
  window.loadDashboard();
});
