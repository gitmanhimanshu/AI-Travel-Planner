/* =========================================================================
   explore.js - search / tag filtering and "Plan Trip" prefill.
   ========================================================================= */
(function () {
  "use strict";

  const grid = document.getElementById("destGrid");
  if (!grid) return;

  const items = Array.prototype.slice.call(grid.querySelectorAll(".dest-item"));
  const search = document.getElementById("destSearch");
  const filters = document.getElementById("tagFilters");
  const noResults = document.getElementById("noResults");

  let activeTag = "all";

  function apply() {
    const query = search.value.trim().toLowerCase();
    let visible = 0;

    items.forEach(function (item) {
      const matchesText = !query || item.dataset.name.indexOf(query) !== -1;
      const matchesTag =
        activeTag === "all" || item.dataset.tags.split("|").indexOf(activeTag) !== -1;
      const show = matchesText && matchesTag;
      item.classList.toggle("d-none", !show);
      if (show) visible += 1;
    });

    noResults.classList.toggle("d-none", visible > 0);
  }

  search.addEventListener("input", apply);

  filters.addEventListener("click", function (event) {
    const button = event.target.closest("[data-tag]");
    if (!button) return;
    filters.querySelectorAll("[data-tag]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    activeTag = button.dataset.tag;
    apply();
  });

  grid.addEventListener("click", function (event) {
    const button = event.target.closest("[data-plan-trip]");
    if (!button) return;
    App.savePrefill({
      destination: button.dataset.planTrip,
      budget_amount: button.dataset.budget,
      interests: (button.dataset.interests || "").split(",").filter(Boolean),
    });
    window.location.href = "/planner";
  });
})();
