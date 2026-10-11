// Daily Data Entry Logic

document.addEventListener("DOMContentLoaded", () => {
  const dateInput = document.getElementById("entry-date");
  const dowInput = document.getElementById("entry-day-of-week");
  const form = document.getElementById("entry-form");

  // Set default date to today
  if (dateInput) {
    const today = new Date().toISOString().split("T")[0];
    dateInput.value = today;
    updateDayOfWeek(today);

    dateInput.addEventListener("change", (e) => {
      updateDayOfWeek(e.target.value);
    });
  }

  function updateDayOfWeek(dateStr) {
    if (!dateStr || !dowInput) return;
    const dateObj = new Date(dateStr + "T00:00:00");
    const dayName = dateObj.toLocaleDateString("en-US", { weekday: "long" });
    dowInput.value = dayName;
  }

  // Handle Form Submission
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      const date = dateInput.value;
      const menuItem = document.getElementById("entry-menu-item").value;
      const mealCategory = document.getElementById("entry-meal-category").value;
      const prep = parseInt(document.getElementById("entry-prepared").value, 10);
      const sold = parseInt(document.getElementById("entry-sold").value, 10);
      const leftover = parseInt(document.getElementById("entry-leftover").value || "0", 10);
      const discardedKg = parseFloat(document.getElementById("entry-discarded-kg").value || "0.0");
      const cost = parseFloat(document.getElementById("entry-cost").value);
      const event = document.getElementById("entry-special-event").value;
      const isHoliday = document.getElementById("entry-is-holiday").checked ? 1 : 0;
      const notes = document.getElementById("entry-notes").value;

      // Client-side validations
      if (sold > prep) {
        window.showToast(`Validation Error: Meals sold (${sold}) cannot exceed meals prepared (${prep})!`, "error");
        return;
      }

      if (leftover > (prep - sold)) {
        window.showToast(`Notice: Edible leftovers (${leftover}) adjusted to match unsold balance (${prep - sold}).`, "warning");
      }

      const payload = {
        date: date,
        menu_item: menuItem,
        meal_category: mealCategory,
        meals_prepared: prep,
        meals_sold: sold,
        leftover_meals: Math.min(leftover, prep - sold),
        food_discarded_kg: discardedKg,
        cost_per_meal: cost,
        special_event: event,
        is_holiday: isHoliday,
        notes: notes
      };

      try {
        const res = await fetch(`${window.API_BASE}/records`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok) {
          window.showToast(`Record for '${menuItem}' on ${date} saved successfully!`, "success");
          form.reset();
          dateInput.value = date;
          updateDayOfWeek(date);
          loadRecentSubmissions();
        } else {
          window.showToast(data.detail || "Error saving record", "error");
        }
      } catch (err) {
        window.showToast("Failed to connect to backend", "error");
      }
    });
  }

  // Load initial recent submissions
  loadRecentSubmissions();
});

async function loadRecentSubmissions() {
  const tbody = document.querySelector("#table-recent-entries tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${window.API_BASE}/records?limit=6`);
    const data = await res.json();

    if (!data.records || data.records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">No entries recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.records.map(r => `
      <tr>
        <td><strong>${r.date}</strong></td>
        <td>${r.menu_item}</td>
        <td>${r.meals_prepared}</td>
        <td>${r.meals_sold}</td>
        <td><span class="badge ${r.food_discarded_kg > 5 ? 'badge-danger' : 'badge-success'}">${r.food_discarded_kg} kg</span></td>
      </tr>
    `).join("");
  } catch (err) {
    console.error("Recent submissions error:", err);
  }
}
