/* =========================================================================
   planner.js - client-side validation, submission and the loading sequence.
   ========================================================================= */
(function () {
  "use strict";

  const form = document.getElementById("plannerForm");
  if (!form) return;

  const loadingPanel = document.getElementById("loadingPanel");
  const errorPanel = document.getElementById("errorPanel");
  const errorMessage = document.getElementById("errorMessage");
  const durationNote = document.getElementById("durationNote");
  const durationText = document.getElementById("durationText");
  const startDate = document.getElementById("start_date");
  const endDate = document.getElementById("end_date");
  const notes = document.getElementById("notes");
  const notesCount = document.getElementById("notesCount");
  const MAX_DAYS = 21;

  let stepTimer = null;

  /* --- Defaults and prefill -------------------------------------------- */
  function isoDate(offsetDays) {
    const date = new Date();
    date.setDate(date.getDate() + offsetDays);
    return date.toISOString().slice(0, 10);
  }

  function initDates() {
    const today = isoDate(0);
    startDate.min = today;
    endDate.min = today;
    if (!startDate.value) startDate.value = isoDate(14);
    if (!endDate.value) endDate.value = isoDate(18);
    updateDuration();
  }

  function applyPrefill() {
    const prefill = App.takePrefill();
    if (!prefill) return;

    if (prefill.destination) form.destination.value = prefill.destination;
    if (prefill.start_location) form.start_location.value = prefill.start_location;
    if (prefill.budget_amount) document.getElementById("budget_amount").value = prefill.budget_amount;

    // A destination tag can be an interest ("Beaches") or a style ("Luxury"),
    // so try both groups for every incoming value.
    const incoming = (prefill.interests || []).concat(prefill.travel_style || []);
    incoming.forEach(function (value) {
      const key = cssEscape(String(value).toLowerCase().trim());
      const input =
        form.querySelector('input[name="interests"][value="' + key + '"]') ||
        form.querySelector('input[name="travel_style"][value="' + key + '"]');
      if (input) input.checked = true;
    });

    App.toast("Planner prefilled for " + (prefill.destination || "your trip") + ".", "info");
  }

  function cssEscape(value) {
    return String(value).replace(/["\\]/g, "\\$&");
  }

  /* --- Duration --------------------------------------------------------- */
  function dayCount() {
    if (!startDate.value || !endDate.value) return 0;
    const start = new Date(startDate.value);
    const end = new Date(endDate.value);
    const diff = Math.round((end - start) / 86400000) + 1;
    return diff;
  }

  function updateDuration() {
    const days = dayCount();
    if (days > 0) {
      durationNote.classList.remove("d-none");
      const nights = days - 1;
      durationText.textContent =
        days + (days === 1 ? " day" : " days") +
        (nights > 0 ? ", " + nights + (nights === 1 ? " night" : " nights") : "") +
        (days > MAX_DAYS ? " - we plan up to " + MAX_DAYS + " days at a time" : "");
    } else {
      durationNote.classList.add("d-none");
    }
    endDate.min = startDate.value || isoDate(0);
  }

  /* --- Selection limits -------------------------------------------------- */
  function enforceLimit(name) {
    const inputs = Array.prototype.slice.call(form.querySelectorAll('input[name="' + name + '"]'));
    const max = Number(inputs[0] && inputs[0].dataset.max) || 99;
    inputs.forEach(function (input) {
      input.addEventListener("change", function () {
        const checked = inputs.filter((item) => item.checked);
        if (checked.length > max) {
          input.checked = false;
          App.toast("You can pick up to " + max + " options here.", "warning");
        }
      });
    });
  }

  /* --- Validation -------------------------------------------------------- */
  function setInvalid(field, isInvalid) {
    field.classList.toggle("is-invalid", isInvalid);
  }

  function validate() {
    let firstInvalid = null;

    [form.destination, form.start_location].forEach(function (field) {
      const invalid = field.value.trim().length < 2;
      setInvalid(field, invalid);
      if (invalid && !firstInvalid) firstInvalid = field;
    });

    const noStart = !startDate.value;
    setInvalid(startDate, noStart);
    if (noStart && !firstInvalid) firstInvalid = startDate;

    const days = dayCount();
    const badEnd = !endDate.value || days < 1;
    setInvalid(endDate, badEnd);
    if (badEnd && !firstInvalid) firstInvalid = endDate;

    const travelers = Number(form.travelers.value);
    const badTravelers = !travelers || travelers < 1 || travelers > 30;
    setInvalid(form.travelers, badTravelers);
    if (badTravelers && !firstInvalid) firstInvalid = form.travelers;

    if (firstInvalid) {
      firstInvalid.focus();
      firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
      App.toast("Please fix the highlighted fields.", "error");
      return false;
    }

    if (days > MAX_DAYS) {
      App.toast("We plan up to " + MAX_DAYS + " days - only the first " + MAX_DAYS + " will be planned.", "warning");
    }
    return true;
  }

  /* --- Payload ----------------------------------------------------------- */
  function checkedValues(name) {
    return Array.prototype.slice
      .call(form.querySelectorAll('input[name="' + name + '"]:checked'))
      .map((input) => input.value);
  }

  function buildPayload() {
    const budget = document.getElementById("budget_amount").value;
    const transport = form.querySelector('input[name="transportation"]:checked');
    const stay = form.querySelector('input[name="accommodation"]:checked');
    const level = form.querySelector('input[name="budget_level"]:checked');

    return {
      destination: form.destination.value.trim(),
      start_location: form.start_location.value.trim(),
      start_date: startDate.value,
      end_date: endDate.value,
      duration_days: Math.min(dayCount() || 3, MAX_DAYS),
      travelers: Number(form.travelers.value) || 1,
      budget_level: level ? level.value : "moderate",
      budget_amount: budget ? Number(budget) : null,
      travel_style: checkedValues("travel_style"),
      interests: checkedValues("interests"),
      transportation: transport ? transport.value : "",
      accommodation: stay ? stay.value : "",
      notes: notes.value.trim(),
    };
  }

  /* --- Loading sequence --------------------------------------------------- */
  function startLoadingSequence() {
    const steps = Array.prototype.slice.call(document.querySelectorAll("#loaderSteps [data-step]"));
    let index = 0;
    steps.forEach(function (step) {
      step.className = "";
      step.querySelector("i").className = "bi bi-circle";
    });

    function advance() {
      if (index > 0) {
        steps[index - 1].className = "done";
        steps[index - 1].querySelector("i").className = "bi bi-check-circle-fill";
      }
      if (index < steps.length) {
        steps[index].className = "active";
        steps[index].querySelector("i").className = "bi bi-arrow-right-circle-fill";
        index += 1;
        stepTimer = setTimeout(advance, 6000);
      }
    }
    advance();
  }

  function stopLoadingSequence() {
    if (stepTimer) clearTimeout(stepTimer);
    stepTimer = null;
  }

  function showPanel(which) {
    form.classList.toggle("d-none", which !== "form");
    loadingPanel.classList.toggle("d-none", which !== "loading");
    errorPanel.classList.toggle("d-none", which !== "error");
    window.scrollTo({ top: form.offsetTop - 120, behavior: "smooth" });
  }

  /* --- Submit -------------------------------------------------------------- */
  async function submit(event) {
    event.preventDefault();
    if (!validate()) return;

    const payload = buildPayload();
    showPanel("loading");
    startLoadingSequence();

    try {
      const data = await App.api("/api/trips/generate", { method: "POST", body: payload });
      stopLoadingSequence();

      App.saveItinerary({
        trip: data.trip,
        itinerary: data.itinerary,
        trip_id: data.trip_id,
        saved: data.saved,
        generated_at: Date.now(),
      });

      window.location.href = data.trip_id ? "/itinerary?trip=" + data.trip_id : "/itinerary";
    } catch (err) {
      stopLoadingSequence();
      errorMessage.textContent = err.message;
      showPanel("error");
      App.toast(err.message, "error");
    }
  }

  /* --- Wire up -------------------------------------------------------------- */
  initDates();
  applyPrefill();
  enforceLimit("travel_style");
  enforceLimit("interests");

  startDate.addEventListener("change", updateDuration);
  endDate.addEventListener("change", updateDuration);
  notes.addEventListener("input", function () {
    notesCount.textContent = notes.value.length;
  });
  [form.destination, form.start_location, form.travelers].forEach(function (field) {
    field.addEventListener("input", function () {
      setInvalid(field, false);
    });
  });

  form.addEventListener("submit", submit);
  document.getElementById("retryBtn").addEventListener("click", function () {
    showPanel("form");
  });
})();
