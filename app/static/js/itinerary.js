/* =========================================================================
   itinerary.js - renders a generated or saved itinerary.
   Data comes from /api/trips/<id> when signed in, otherwise from
   sessionStorage where the planner page left it.
   ========================================================================= */
(function () {
  "use strict";

  const root = document.getElementById("itineraryRoot");
  if (!root) return;

  const loading = document.getElementById("itineraryLoading");
  const empty = document.getElementById("itineraryEmpty");

  const BUDGET_COLORS = {
    transport: "#0f766e",
    accommodation: "#14b8a6",
    food: "#f97316",
    activities: "#6366f1",
    miscellaneous: "#94a3b8",
  };

  const PERIOD_META = {
    morning: { label: "Morning", icon: "bi-sunrise" },
    afternoon: { label: "Afternoon", icon: "bi-sun" },
    evening: { label: "Evening", icon: "bi-moon-stars" },
  };

  const state = { trip: null, itinerary: null, tripId: null, isFavorite: false };

  /* ---------------------------------------------------------------- load */
  async function load() {
    const tripId = window.ITINERARY_TRIP_ID;
    const cached = App.loadItinerary();

    if (tripId) {
      try {
        const data = await App.api("/api/trips/" + tripId);
        state.trip = data.trip;
        state.itinerary = data.trip.itinerary;
        state.tripId = data.trip.id;
        state.isFavorite = !!data.trip.is_favorite;
        return render();
      } catch (err) {
        if (cached && cached.itinerary) {
          App.toast("Showing the copy from this tab.", "info");
        } else {
          return showEmpty("We could not load that trip", err.message);
        }
      }
    }

    if (cached && cached.itinerary) {
      state.trip = cached.trip;
      state.itinerary = cached.itinerary;
      state.tripId = cached.trip_id || null;
      return render();
    }
    return showEmpty();
  }

  function showEmpty(title, message) {
    loading.classList.add("d-none");
    empty.classList.remove("d-none");
    if (title) document.getElementById("emptyTitle").textContent = title;
    if (message) document.getElementById("emptyMessage").textContent = message;
  }

  /* -------------------------------------------------------------- render */
  function render() {
    const itinerary = state.itinerary || {};
    const summary = itinerary.trip_summary || {};
    const trip = state.trip || {};

    loading.classList.add("d-none");
    root.classList.remove("d-none");
    document.getElementById("chatLauncher").classList.remove("d-none");

    // Header
    const destination = summary.destination || trip.destination || "Your trip";
    document.title = destination + " itinerary - AI Travel Planner";
    document.getElementById("tripTitle").textContent = destination;

    const dates = formatRange(trip.start_date || summary.start_date, trip.end_date || summary.end_date);
    document.getElementById("tripSubtitle").textContent =
      [summary.duration, dates, plural(trip.travelers || summary.travelers, "traveller")]
        .filter(Boolean)
        .join("  ·  ");

    const styles = (trip.travel_style || summary.travel_style || []).map(App.titleCase);
    const badge = document.getElementById("tripStyleBadge");
    if (styles.length) badge.textContent = styles.join(" · ");
    else badge.hidden = true;

    renderOverview(itinerary, trip);
    renderBudget(itinerary);
    renderDays(itinerary.days || []);
    renderRestaurants(itinerary.restaurants || []);
    renderPlaces(itinerary.places_to_visit || []);
    renderLogistics(itinerary);
    renderPacking(itinerary.packing_list || []);
    renderTips(itinerary.travel_tips || []);
    renderAlert(itinerary);
    renderFavorite();

    loadWeather(destination);
  }

  function renderOverview(itinerary, trip) {
    const summary = itinerary.trip_summary || {};
    const budget = itinerary.budget_status || {};
    const items = [
      ["Destination", summary.destination || trip.destination || "-", "bi-geo-alt"],
      ["Dates", formatRange(trip.start_date || summary.start_date, trip.end_date || summary.end_date) || "Flexible", "bi-calendar-range"],
      ["Duration", summary.duration || plural(trip.duration_days, "day"), "bi-clock-history"],
      ["Travellers", String(trip.travelers || summary.travelers || 1), "bi-people"],
      ["Estimated cost", App.money(budget.estimated || (itinerary.budget_breakdown || {}).total), "bi-wallet2"],
      ["Best time to visit", summary.best_time || "-", "bi-brightness-high"],
    ];

    document.getElementById("overviewStrip").innerHTML = items
      .map(function (item) {
        return (
          '<div class="col-6 col-md-4 col-xl-2"><div class="overview-item">' +
          '<div class="label"><i class="bi ' + item[2] + ' me-1"></i>' + App.escapeHtml(item[0]) + "</div>" +
          '<div class="value">' + App.escapeHtml(item[1]) + "</div>" +
          "</div></div>"
        );
      })
      .join("");
  }

  /* ---------------------------------------------------------------- days */
  function renderDays(days) {
    const container = document.getElementById("daysContainer");
    if (!days.length) {
      container.innerHTML = '<div class="empty-state"><p>No days were returned for this trip.</p></div>';
      return;
    }

    container.innerHTML = days.map(renderDay).join("");

    container.querySelectorAll(".day-head").forEach(function (head) {
      head.addEventListener("click", function () {
        const body = document.getElementById(head.dataset.target);
        const isOpen = head.getAttribute("aria-expanded") === "true";
        head.setAttribute("aria-expanded", String(!isOpen));
        body.classList.toggle("d-none", isOpen);
      });
    });

    const toggleAll = document.getElementById("toggleAllDays");
    toggleAll.addEventListener("click", function () {
      const heads = container.querySelectorAll(".day-head");
      const shouldOpen = toggleAll.dataset.state !== "open";
      heads.forEach(function (head) {
        head.setAttribute("aria-expanded", String(shouldOpen));
        document.getElementById(head.dataset.target).classList.toggle("d-none", !shouldOpen);
      });
      toggleAll.dataset.state = shouldOpen ? "open" : "closed";
      toggleAll.innerHTML = shouldOpen
        ? '<i class="bi bi-arrows-collapse me-1"></i> Collapse all'
        : '<i class="bi bi-arrows-expand me-1"></i> Expand all';
    });
  }

  function renderDay(day, index) {
    const bodyId = "day-body-" + day.day;
    const open = index === 0;

    const periods = ["morning", "afternoon", "evening"]
      .map(function (period) {
        const activities = (day[period] || []).length
          ? day[period]
          : (day.activities || []).filter((item) => item.period === period);
        if (!activities.length) return "";
        const meta = PERIOD_META[period];
        return (
          '<div class="period">' +
          '<div class="period-label"><i class="bi ' + meta.icon + '"></i>' + meta.label + "</div>" +
          activities.map(renderActivity).join("") +
          "</div>"
        );
      })
      .join("");

    const food = (day.food_recommendations || []).length
      ? '<div class="food-strip"><strong><i class="bi bi-cup-hot me-1"></i>Eat here:</strong> ' +
        day.food_recommendations
          .map(function (item) {
            const dish = item.dish ? " (" + App.escapeHtml(item.dish) + ")" : "";
            const cost = item.approx_cost ? " - " + App.money(item.approx_cost) : "";
            return App.escapeHtml(item.name) + dish + cost;
          })
          .join(" &nbsp;•&nbsp; ") +
        "</div>"
      : "";

    return (
      '<article class="card-soft day-card">' +
      '<button class="day-head" type="button" aria-expanded="' + open + '" data-target="' + bodyId + '">' +
      '<span class="day-num"><small>DAY</small>' + day.day + "</span>" +
      "<span><h5>" + App.escapeHtml(day.title || "Day " + day.day) + "</h5>" +
      '<span class="meta">' +
      [day.date_label, day.location].filter(Boolean).map(App.escapeHtml).join(" · ") +
      "</span></span>" +
      (day.estimated_cost ? '<span class="day-cost">' + App.money(day.estimated_cost) + "</span>" : "") +
      '<i class="bi bi-chevron-down chev"></i>' +
      "</button>" +
      '<div class="day-body' + (open ? "" : " d-none") + '" id="' + bodyId + '">' +
      (periods || '<p class="text-muted-soft mt-3 mb-0">No activities were listed for this day.</p>') +
      food +
      "</div></article>"
    );
  }

  function renderActivity(activity) {
    return (
      '<div class="activity">' +
      (activity.time ? '<div class="time">' + App.escapeHtml(activity.time) + "</div>" : "") +
      "<h6>" + App.escapeHtml(activity.activity) + "</h6>" +
      (activity.description ? "<p>" + App.escapeHtml(activity.description) + "</p>" : "") +
      (activity.estimated_cost
        ? '<span class="cost"><i class="bi bi-tag"></i> ' + App.money(activity.estimated_cost) + "</span>"
        : "") +
      "</div>"
    );
  }

  /* -------------------------------------------------------------- budget */
  function renderBudget(itinerary) {
    const breakdown = itinerary.budget_breakdown || {};
    const status = itinerary.budget_status || {};
    const keys = ["transport", "accommodation", "food", "activities", "miscellaneous"];
    const total = Number(breakdown.total) || keys.reduce((sum, key) => sum + (Number(breakdown[key]) || 0), 0);

    document.getElementById("budgetRows").innerHTML = keys
      .map(function (key) {
        const value = Number(breakdown[key]) || 0;
        const share = total ? Math.round((value / total) * 100) : 0;
        return (
          '<div class="budget-row">' +
          '<span class="swatch" style="background:' + BUDGET_COLORS[key] + '"></span>' +
          '<span class="name">' + App.titleCase(key) + ' <small class="text-muted-soft">' + share + "%</small></span>" +
          '<span class="amount">' + App.money(value) + "</span>" +
          "</div>"
        );
      })
      .join("");

    const summary = document.getElementById("budgetSummary");
    let html =
      '<div class="line total"><span>Estimated budget</span><strong>' + App.money(total) + "</strong></div>";

    if (status.has_budget) {
      const overClass = status.over_budget ? "text-over" : "text-under";
      html =
        '<div class="line"><span>Your budget</span><strong>' + App.money(status.user_budget) + "</strong></div>" +
        '<div class="line"><span>Estimated cost</span><strong>' + App.money(status.estimated) + "</strong></div>" +
        '<div class="line total"><span>' +
        (status.over_budget ? "Over by" : "Remaining") +
        '</span><strong class="' + overClass + '">' +
        App.money(Math.abs(status.remaining)) +
        "</strong></div>";

      const fill = document.getElementById("budgetFill");
      fill.style.width = Math.min(100, status.usage_percent || 0) + "%";
      if (status.over_budget) fill.style.background = "linear-gradient(90deg,#f97316,#dc2626)";
    } else {
      document.getElementById("budgetFill").style.width = "100%";
    }
    summary.innerHTML = html;
  }

  function renderAlert(itinerary) {
    const alert = itinerary.budget_alert || {};
    const box = document.getElementById("budgetAlert");
    if (!alert.over_budget && !(alert.cheaper_alternatives || []).length) return;

    box.className = "alert " + (alert.over_budget ? "alert-warning" : "alert-info");
    box.classList.remove("d-none");
    box.innerHTML =
      '<div class="d-flex gap-2"><i class="bi bi-exclamation-triangle-fill mt-1"></i><div>' +
      "<strong>" + (alert.over_budget ? "This plan is over your budget" : "Budget note") + "</strong>" +
      "<div>" + App.escapeHtml(alert.message || "") + "</div>" +
      ((alert.cheaper_alternatives || []).length
        ? "<ul class='mb-0 mt-2'>" +
          alert.cheaper_alternatives.map((item) => "<li>" + App.escapeHtml(item) + "</li>").join("") +
          "</ul>"
        : "") +
      "</div></div>";
  }

  /* -------------------------------------------------- restaurants/places */
  function renderRestaurants(restaurants) {
    if (!restaurants.length) return;
    document.getElementById("restaurantsCard").hidden = false;
    document.getElementById("restaurantsList").innerHTML = restaurants
      .map(function (item) {
        return (
          '<div class="col-md-6"><div class="p-3 h-100" style="border:1px solid var(--line);border-radius:14px;">' +
          '<div class="d-flex justify-content-between align-items-start gap-2">' +
          "<h6 class='mb-1'>" + App.escapeHtml(item.name) + "</h6>" +
          (item.price_range ? '<span class="tag-pill">' + App.escapeHtml(item.price_range) + "</span>" : "") +
          "</div>" +
          '<div class="small text-muted-soft">' +
          [item.cuisine, item.area].filter(Boolean).map(App.escapeHtml).join(" · ") +
          "</div>" +
          (item.must_try ? '<div class="small mt-2"><i class="bi bi-star-fill text-warning me-1"></i>' + App.escapeHtml(item.must_try) + "</div>" : "") +
          "</div></div>"
        );
      })
      .join("");
  }

  function renderPlaces(places) {
    if (!places.length) return;
    document.getElementById("placesCard").hidden = false;
    document.getElementById("placesList").innerHTML = places
      .map(function (item) {
        return (
          '<div class="place-row">' +
          '<span class="pin"><i class="bi bi-geo-alt-fill"></i></span>' +
          "<div class='flex-grow-1'>" +
          "<h6>" + App.escapeHtml(item.name) + "</h6>" +
          (item.description ? "<p>" + App.escapeHtml(item.description) + "</p>" : "") +
          '<div class="small text-muted-soft mt-1">' +
          [
            item.best_time_to_visit ? "Best: " + item.best_time_to_visit : "",
            item.entry_fee ? "Entry: " + item.entry_fee : "",
          ]
            .filter(Boolean)
            .map(App.escapeHtml)
            .join(" · ") +
          "</div></div>" +
          '<a class="btn btn-ghost btn-sm align-self-center print-hide" target="_blank" rel="noopener" href="' +
          App.escapeHtml(App.mapLink(item.map_query || item.name)) +
          '"><i class="bi bi-map"></i><span class="d-none d-sm-inline ms-1">View on map</span></a>' +
          "</div>"
        );
      })
      .join("");
  }

  function renderLogistics(itinerary) {
    const transport = itinerary.transportation || {};
    const stay = itinerary.accommodation || {};
    let html = "";

    if (transport.recommendation) {
      html +=
        '<div class="mb-3"><div class="fw-semibold mb-1"><i class="bi bi-airplane me-1 text-info"></i>Transport ' +
        '<span class="float-end">' + App.money(transport.estimated_cost) + "</span></div>" +
        '<p class="small text-muted-soft mb-1">' + App.escapeHtml(transport.recommendation) + "</p>" +
        ((transport.tips || []).length
          ? "<ul class='small text-muted-soft mb-0 ps-3'>" +
            transport.tips.map((tip) => "<li>" + App.escapeHtml(tip) + "</li>").join("") +
            "</ul>"
          : "") +
        "</div>";
    }

    if (stay.recommendation) {
      html +=
        '<div class="pt-3" style="border-top:1px solid var(--line)"><div class="fw-semibold mb-1">' +
        '<i class="bi bi-building me-1 text-info"></i>Stay <span class="float-end">' +
        App.money(stay.estimated_cost) + "</span></div>" +
        '<p class="small text-muted-soft mb-2">' + App.escapeHtml(stay.recommendation) + "</p>" +
        (stay.suggestions || [])
          .map(function (item) {
            return (
              '<div class="small d-flex justify-content-between gap-2 py-1">' +
              "<span>" + App.escapeHtml(item.name) +
              (item.area ? ' <span class="text-muted-soft">· ' + App.escapeHtml(item.area) + "</span>" : "") +
              "</span>" +
              (item.approx_cost_per_night
                ? '<span class="fw-semibold">' + App.money(item.approx_cost_per_night) + "/night</span>"
                : "") +
              "</div>"
            );
          })
          .join("") +
        "</div>";
    }

    if (!html) document.getElementById("logisticsCard").hidden = true;
    else document.getElementById("logisticsContent").innerHTML = html;
  }

  function renderPacking(items) {
    const container = document.getElementById("packingList");
    if (!items.length) {
      container.innerHTML = '<p class="small text-muted-soft mb-0">No packing list yet - generate one below.</p>';
      return;
    }
    container.innerHTML = items
      .map(function (item, index) {
        const id = "pack-" + index;
        return (
          '<div class="form-check">' +
          '<input class="form-check-input" type="checkbox" id="' + id + '">' +
          '<label class="form-check-label small" for="' + id + '">' + App.escapeHtml(item) + "</label>" +
          "</div>"
        );
      })
      .join("");
  }

  function renderTips(tips) {
    if (!tips.length) return;
    document.getElementById("tipsCard").hidden = false;
    document.getElementById("tipsList").innerHTML = tips
      .map((tip) => '<li class="small mb-2">' + App.escapeHtml(tip) + "</li>")
      .join("");
  }

  /* ------------------------------------------------------------- weather */
  async function loadWeather(destination) {
    if (!destination) return;
    try {
      const data = await App.api("/api/weather/" + encodeURIComponent(destination));
      const weather = data.weather || {};
      if (!weather.available) return;

      document.getElementById("weatherCard").hidden = false;
      const current = weather.current || {};
      document.getElementById("weatherContent").innerHTML =
        '<div class="weather-now">' +
        '<i class="bi ' + App.escapeHtml(current.icon || "bi-cloud") + '"></i>' +
        "<div><div class='temp'>" + (current.temperature != null ? current.temperature + "°C" : "--") + "</div>" +
        "<div class='small text-muted-soft'>" + App.escapeHtml(current.description || "") + " · " +
        App.escapeHtml(weather.location || "") + "</div></div></div>" +
        '<div class="weather-days">' +
        (weather.forecast || [])
          .map(function (day) {
            return (
              '<div class="weather-day">' +
              '<div class="d">' + App.formatDate(day.date, { weekday: "short" }) + "</div>" +
              '<i class="bi ' + App.escapeHtml(day.icon || "bi-cloud") + '"></i>' +
              '<div class="t">' + (day.temp_max != null ? day.temp_max + "°" : "-") + "</div>" +
              (day.rain_probability != null ? '<div class="r">' + day.rain_probability + "%</div>" : "") +
              "</div>"
            );
          })
          .join("") +
        "</div>" +
        '<div class="small text-muted-soft mt-2">Source: ' + App.escapeHtml(weather.source || "") + "</div>";
    } catch (err) {
      /* Weather is optional - stay silent. */
    }
  }

  /* ------------------------------------------------------------ actions */
  function renderFavorite() {
    const button = document.getElementById("favoriteBtn");
    const hint = document.getElementById("saveHint");

    if (!state.tripId) {
      hint.classList.remove("d-none");
      return;
    }
    button.hidden = false;
    paintFavorite();
    button.addEventListener("click", async function () {
      try {
        const data = await App.api("/api/trips/" + state.tripId + "/favorite", { method: "POST", body: {} });
        state.isFavorite = data.is_favorite;
        paintFavorite();
        App.toast(state.isFavorite ? "Added to favourites." : "Removed from favourites.", "success");
      } catch (err) {
        App.toast(err.message, "error");
      }
    });
  }

  function paintFavorite() {
    const button = document.getElementById("favoriteBtn");
    button.querySelector("i").className = state.isFavorite ? "bi bi-heart-fill me-1 text-danger" : "bi bi-heart me-1";
    button.querySelector("span").textContent = state.isFavorite ? "Favourited" : "Favourite";
  }

  function initPacking() {
    document.getElementById("packingBtn").addEventListener("click", async function (event) {
      const button = event.currentTarget;
      App.setLoading(button, true, "Packing...");
      try {
        const data = await App.api("/api/ai/packing-list", {
          method: "POST",
          body: { trip_id: state.tripId, trip: state.trip, itinerary: state.itinerary },
        });
        renderPacking(data.packing_list || []);
        App.toast("Packing list updated.", "success");
      } catch (err) {
        App.toast(err.message, "error");
      } finally {
        App.setLoading(button, false);
      }
    });
  }

  function initOptimize() {
    document.getElementById("optimizeBtn").addEventListener("click", async function (event) {
      const button = event.currentTarget;
      const status = (state.itinerary || {}).budget_status || {};
      const target = status.user_budget || (state.trip || {}).budget_amount;

      if (!target) {
        App.toast("Add an exact budget on the planner to use the optimiser.", "warning");
        return;
      }

      App.setLoading(button, true, "Optimising...");
      try {
        const data = await App.api("/api/ai/optimize-budget", {
          method: "POST",
          body: {
            trip_id: state.tripId,
            trip: state.trip,
            itinerary: state.itinerary,
            target_budget: target,
          },
        });
        document.getElementById("optimizeResult").innerHTML =
          '<div class="alert alert-success py-2 px-3 small mb-2">' +
          "<strong>New estimate: " + App.money(data.optimized_total) + "</strong> " +
          "(saves " + App.money(data.savings) + ")" +
          (data.summary ? "<div class='mt-1'>" + App.escapeHtml(data.summary) + "</div>" : "") +
          "</div>" +
          (data.suggestions || [])
            .map(function (item) {
              return (
                '<div class="d-flex gap-2 small py-2" style="border-bottom:1px dashed var(--line)">' +
                '<i class="bi bi-scissors text-warning mt-1"></i><div>' +
                "<strong>" + App.escapeHtml(item.area) + "</strong>" +
                (item.saving ? ' <span class="text-under fw-semibold">-' + App.money(item.saving) + "</span>" : "") +
                "<div class='text-muted-soft'>" + App.escapeHtml(item.change) + "</div>" +
                "</div></div>"
              );
            })
            .join("");
      } catch (err) {
        App.toast(err.message, "error");
      } finally {
        App.setLoading(button, false);
      }
    });
  }

  document.getElementById("printBtn").addEventListener("click", () => window.print());
  initPacking();
  initOptimize();

  /* ------------------------------------------------------------ helpers */
  function formatRange(start, end) {
    if (!start && !end) return "";
    if (start && end) return App.formatDate(start) + " → " + App.formatDate(end);
    return App.formatDate(start || end);
  }

  function plural(count, word) {
    const number = Number(count) || 0;
    if (!number) return "";
    return number + " " + word + (number === 1 ? "" : "s");
  }

  // Expose trip state so chat.js can send context with each question.
  window.ItineraryState = state;

  load();
})();
