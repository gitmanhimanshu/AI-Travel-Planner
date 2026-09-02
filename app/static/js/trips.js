/* =========================================================================
   trips.js - list, favourite and delete saved trips.
   ========================================================================= */
(function () {
  "use strict";

  const grid = document.getElementById("tripsGrid");
  if (!grid) return;

  const loading = document.getElementById("tripsLoading");
  const emptyState = document.getElementById("tripsEmpty");
  const filters = document.getElementById("tripFilters");
  const deleteModalEl = document.getElementById("deleteModal");
  const deleteModal = new bootstrap.Modal(deleteModalEl);

  const GRADIENTS = [
    ["#0f766e", "#22d3ee"],
    ["#f97316", "#fb7185"],
    ["#8e2de2", "#4a00e0"],
    ["#11998e", "#38ef7d"],
    ["#2193b0", "#6dd5ed"],
    ["#c31432", "#240b36"],
  ];

  let trips = [];
  let filter = "all";
  let pendingDeleteId = null;

  /* --- Load ------------------------------------------------------------- */
  async function load() {
    try {
      const data = await App.api("/api/trips");
      trips = data.trips || [];
      render();
    } catch (err) {
      loading.classList.add("d-none");
      if (err.status === 401) {
        window.location.href = "/login?next=/trips";
        return;
      }
      emptyState.classList.remove("d-none");
      emptyState.querySelector("h4").textContent = "We could not load your trips";
      emptyState.querySelector("p").textContent = err.message;
    }
  }

  /* --- Render ----------------------------------------------------------- */
  function render() {
    loading.classList.add("d-none");

    const visible = filter === "favorites" ? trips.filter((trip) => trip.is_favorite) : trips;

    if (!visible.length) {
      grid.classList.add("d-none");
      emptyState.classList.remove("d-none");
      if (filter === "favorites" && trips.length) {
        emptyState.querySelector("h4").textContent = "No favourites yet";
        emptyState.querySelector("p").textContent = "Tap the heart on a trip to keep it here.";
      }
      return;
    }

    emptyState.classList.add("d-none");
    grid.classList.remove("d-none");
    grid.innerHTML = visible.map(card).join("");
  }

  function card(trip, index) {
    const gradient = GRADIENTS[index % GRADIENTS.length];
    const dates = trip.start_date
      ? App.formatDate(trip.start_date) + (trip.end_date ? " → " + App.formatDate(trip.end_date) : "")
      : "Flexible dates";

    return (
      '<div class="col-sm-6 col-lg-4">' +
      '<article class="card-soft trip-card">' +
      '<div class="trip-card-top" style="background: linear-gradient(135deg,' + gradient[0] + "," + gradient[1] + ');">' +
      '<i class="bi bi-airplane-engines"></i>' +
      '<button class="trip-fav ' + (trip.is_favorite ? "is-fav" : "") + '" data-fav="' + trip.id + '" ' +
      'aria-label="Toggle favourite"><i class="bi ' + (trip.is_favorite ? "bi-heart-fill" : "bi-heart") + '"></i></button>' +
      "</div>" +
      '<div class="dest-body">' +
      "<h5>" + App.escapeHtml(trip.destination) + "</h5>" +
      '<div class="dest-country"><i class="bi bi-signpost"></i> from ' + App.escapeHtml(trip.start_location) + "</div>" +
      '<div class="trip-meta">' +
      '<span><i class="bi bi-calendar-range"></i> ' + App.escapeHtml(dates) + "</span>" +
      '<span><i class="bi bi-clock-history"></i> ' + trip.duration_days + " days</span>" +
      '<span><i class="bi bi-people"></i> ' + trip.travelers + "</span>" +
      (trip.budget_amount
        ? '<span><i class="bi bi-wallet2"></i> ' + App.money(trip.budget_amount) + "</span>"
        : '<span><i class="bi bi-wallet2"></i> ' + App.titleCase(trip.budget_level || "") + "</span>") +
      "</div>" +
      '<div class="d-flex flex-wrap gap-1">' +
      (trip.travel_style || []).slice(0, 3).map((style) => '<span class="tag-pill">' + App.escapeHtml(App.titleCase(style)) + "</span>").join("") +
      "</div>" +
      '<div class="d-flex gap-2 mt-auto pt-2">' +
      '<a class="btn btn-brand btn-sm flex-grow-1" href="/itinerary?trip=' + trip.id + '">View trip</a>' +
      '<button class="btn btn-ghost btn-sm text-danger" data-delete="' + trip.id + '" ' +
      'data-name="' + App.escapeHtml(trip.destination) + '" aria-label="Delete trip"><i class="bi bi-trash3"></i></button>' +
      "</div></div></article></div>"
    );
  }

  /* --- Actions ---------------------------------------------------------- */
  grid.addEventListener("click", async function (event) {
    const favButton = event.target.closest("[data-fav]");
    if (favButton) {
      const id = Number(favButton.dataset.fav);
      try {
        const data = await App.api("/api/trips/" + id + "/favorite", { method: "POST", body: {} });
        const trip = trips.find((item) => item.id === id);
        if (trip) trip.is_favorite = data.is_favorite;
        render();
        App.toast(data.is_favorite ? "Added to favourites." : "Removed from favourites.", "success");
      } catch (err) {
        App.toast(err.message, "error");
      }
      return;
    }

    const deleteButton = event.target.closest("[data-delete]");
    if (deleteButton) {
      pendingDeleteId = Number(deleteButton.dataset.delete);
      document.getElementById("deleteText").textContent =
        "Your " + deleteButton.dataset.name + " itinerary will be removed permanently.";
      deleteModal.show();
    }
  });

  document.getElementById("confirmDelete").addEventListener("click", async function (event) {
    if (!pendingDeleteId) return;
    const button = event.currentTarget;
    App.setLoading(button, true, "Deleting...");
    try {
      await App.api("/api/trips/" + pendingDeleteId, { method: "DELETE" });
      trips = trips.filter((trip) => trip.id !== pendingDeleteId);
      render();
      App.toast("Trip deleted.", "success");
    } catch (err) {
      App.toast(err.message, "error");
    } finally {
      App.setLoading(button, false);
      deleteModal.hide();
      pendingDeleteId = null;
    }
  });

  filters.addEventListener("click", function (event) {
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    filters.querySelectorAll("[data-filter]").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    filter = button.dataset.filter;
    render();
  });

  load();
})();
