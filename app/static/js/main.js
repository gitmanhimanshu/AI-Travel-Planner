/* =========================================================================
   main.js - shared helpers used by every page.
   Exposes a single global: window.App
   ========================================================================= */
(function () {
  "use strict";

  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  let csrfToken = csrfMeta ? csrfMeta.content : "";

  /* --- HTTP ------------------------------------------------------------- */
  async function api(path, options) {
    const opts = options || {};
    const method = (opts.method || "GET").toUpperCase();
    const headers = Object.assign(
      { Accept: "application/json" },
      opts.headers || {}
    );

    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (method !== "GET" && method !== "HEAD") headers["X-CSRF-Token"] = csrfToken;

    let response;
    try {
      response = await fetch(path, {
        method,
        headers,
        credentials: "same-origin",
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      });
    } catch (err) {
      throw new ApiError("You appear to be offline. Check your connection and try again.", 0);
    }

    let data = null;
    try {
      data = await response.json();
    } catch (err) {
      data = null;
    }

    if (data && data.csrf_token) csrfToken = data.csrf_token;

    if (!response.ok || (data && data.success === false)) {
      const message = (data && data.error) || defaultMessage(response.status);
      throw new ApiError(message, response.status);
    }
    return data || {};
  }

  function ApiError(message, status) {
    this.name = "ApiError";
    this.message = message;
    this.status = status;
  }
  ApiError.prototype = Object.create(Error.prototype);

  function defaultMessage(status) {
    if (status === 401) return "Please log in to continue.";
    if (status === 403) return "Your session expired. Refresh the page and try again.";
    if (status === 404) return "We could not find that.";
    if (status === 502) return "The AI service is unavailable right now.";
    return "Something went wrong. Please try again.";
  }

  /* --- Toasts ----------------------------------------------------------- */
  const TOAST_STYLES = {
    success: { bg: "text-bg-success", icon: "bi-check-circle-fill" },
    error: { bg: "text-bg-danger", icon: "bi-exclamation-triangle-fill" },
    info: { bg: "text-bg-dark", icon: "bi-info-circle-fill" },
    warning: { bg: "text-bg-warning", icon: "bi-exclamation-circle-fill" },
  };

  function toast(message, type) {
    const container = document.getElementById("toastContainer");
    if (!container) return;
    const style = TOAST_STYLES[type] || TOAST_STYLES.info;

    const el = document.createElement("div");
    el.className = "toast align-items-center " + style.bg + " border-0";
    el.setAttribute("role", "alert");
    el.innerHTML =
      '<div class="d-flex">' +
      '<div class="toast-body d-flex align-items-center gap-2">' +
      '<i class="bi ' + style.icon + '"></i><span></span></div>' +
      '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>' +
      "</div>";
    el.querySelector("span").textContent = message;

    container.appendChild(el);
    const instance = new bootstrap.Toast(el, { delay: 4500 });
    instance.show();
    el.addEventListener("hidden.bs.toast", () => el.remove());
  }

  /* --- Formatting ------------------------------------------------------- */
  function money(value, withSymbol) {
    const number = Number(value);
    if (!isFinite(number)) return withSymbol === false ? "0" : "₹0";
    const formatted = Math.round(number).toLocaleString("en-IN");
    return withSymbol === false ? formatted : "₹" + formatted;
  }

  function formatDate(iso, options) {
    if (!iso) return "";
    const date = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
    if (isNaN(date.getTime())) return iso;
    return date.toLocaleDateString(
      "en-IN",
      options || { day: "numeric", month: "short", year: "numeric" }
    );
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function titleCase(value) {
    return String(value || "")
      .split(" ")
      .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : ""))
      .join(" ");
  }

  /* --- Storage (used to carry an itinerary between pages) --------------- */
  const STORAGE_KEY = "aitp:lastItinerary";

  function saveItinerary(payload) {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
      return true;
    } catch (err) {
      return false;
    }
  }

  function loadItinerary() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      return null;
    }
  }

  function clearItinerary() {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch (err) {
      /* ignore */
    }
  }

  const PREFILL_KEY = "aitp:prefill";

  function savePrefill(data) {
    try {
      sessionStorage.setItem(PREFILL_KEY, JSON.stringify(data));
    } catch (err) {
      /* ignore */
    }
  }

  function takePrefill() {
    try {
      const raw = sessionStorage.getItem(PREFILL_KEY);
      sessionStorage.removeItem(PREFILL_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      return null;
    }
  }

  /* --- Buttons ---------------------------------------------------------- */
  function setLoading(button, isLoading, loadingText) {
    if (!button) return;
    if (isLoading) {
      button.dataset.originalHtml = button.innerHTML;
      button.disabled = true;
      button.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2"></span>' +
        escapeHtml(loadingText || "Working...");
    } else {
      button.disabled = false;
      if (button.dataset.originalHtml) button.innerHTML = button.dataset.originalHtml;
    }
  }

  /* --- Maps ------------------------------------------------------------- */
  function mapLink(query) {
    return "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(query || "");
  }

  /* --- Page wiring ------------------------------------------------------ */
  function initNav() {
    const nav = document.getElementById("appNav");
    if (!nav) return;
    const onScroll = () => nav.classList.toggle("is-scrolled", window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  function initLogout() {
    document.querySelectorAll("[data-logout]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await api("/api/auth/logout", { method: "POST", body: {} });
          clearItinerary();
          toast("Signed out.", "success");
          setTimeout(() => (window.location.href = "/"), 500);
        } catch (err) {
          toast(err.message, "error");
        }
      });
    });
  }

  function initReveal() {
    const items = document.querySelectorAll("[data-reveal]");
    if (!items.length || !("IntersectionObserver" in window)) return;
    items.forEach((el) => {
      el.style.opacity = "0";
      el.style.transform = "translateY(18px)";
      el.style.transition = "opacity .6s ease, transform .6s ease";
    });
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry, index) => {
          if (!entry.isIntersecting) return;
          setTimeout(() => {
            entry.target.style.opacity = "1";
            entry.target.style.transform = "none";
          }, index * 70);
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.12 }
    );
    items.forEach((el) => observer.observe(el));
  }

  document.addEventListener("DOMContentLoaded", () => {
    initNav();
    initLogout();
    initReveal();
  });

  window.App = {
    api,
    ApiError,
    toast,
    money,
    formatDate,
    escapeHtml,
    titleCase,
    setLoading,
    mapLink,
    saveItinerary,
    loadItinerary,
    clearItinerary,
    savePrefill,
    takePrefill,
    get csrfToken() {
      return csrfToken;
    },
  };
})();
