/* =========================================================================
   auth.js - login and registration forms.
   ========================================================================= */
(function () {
  "use strict";

  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$/;

  function nextUrl(fallback) {
    const params = new URLSearchParams(window.location.search);
    const next = params.get("next");
    // Only allow same-site relative paths, never an absolute URL.
    if (next && next.startsWith("/") && !next.startsWith("//")) return next;
    return fallback;
  }

  function setInvalid(field, isInvalid) {
    field.classList.toggle("is-invalid", isInvalid);
  }

  function initPasswordToggles() {
    document.querySelectorAll("[data-toggle-password]").forEach(function (button) {
      button.addEventListener("click", function () {
        const input = document.getElementById(button.dataset.togglePassword);
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.querySelector("i").className = showing ? "bi bi-eye" : "bi bi-eye-slash";
      });
    });
  }

  async function submitForm(form, url, buildBody, validate, buttonId, successMessage) {
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (!validate()) return;

      const button = document.getElementById(buttonId);
      App.setLoading(button, true, "Please wait...");
      try {
        await App.api(url, { method: "POST", body: buildBody() });
        App.toast(successMessage, "success");
        setTimeout(() => (window.location.href = nextUrl("/trips")), 400);
      } catch (err) {
        App.toast(err.message, "error");
        App.setLoading(button, false);
      }
    });
  }

  /* --- Login ------------------------------------------------------------ */
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    submitForm(
      loginForm,
      "/api/auth/login",
      () => ({ email: loginForm.email.value.trim(), password: loginForm.password.value }),
      function () {
        const badEmail = !EMAIL_RE.test(loginForm.email.value.trim());
        const badPassword = !loginForm.password.value;
        setInvalid(loginForm.email, badEmail);
        setInvalid(loginForm.password, badPassword);
        if (badEmail || badPassword) {
          (badEmail ? loginForm.email : loginForm.password).focus();
          return false;
        }
        return true;
      },
      "loginBtn",
      "Welcome back!"
    );
  }

  /* --- Register --------------------------------------------------------- */
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    submitForm(
      registerForm,
      "/api/auth/register",
      () => ({
        name: registerForm.name.value.trim(),
        email: registerForm.email.value.trim(),
        password: registerForm.password.value,
      }),
      function () {
        const badName = registerForm.name.value.trim().length < 2;
        const badEmail = !EMAIL_RE.test(registerForm.email.value.trim());
        const badPassword = registerForm.password.value.length < 8;
        setInvalid(registerForm.name, badName);
        setInvalid(registerForm.email, badEmail);
        setInvalid(registerForm.password, badPassword);
        const firstBad = badName ? registerForm.name : badEmail ? registerForm.email : badPassword ? registerForm.password : null;
        if (firstBad) {
          firstBad.focus();
          return false;
        }
        return true;
      },
      "registerBtn",
      "Account created."
    );
  }

  document.querySelectorAll("#loginForm input, #registerForm input").forEach(function (input) {
    input.addEventListener("input", () => setInvalid(input, false));
  });

  initPasswordToggles();
})();
