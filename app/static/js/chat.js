/* =========================================================================
   chat.js - the AI travel assistant panel on the itinerary page.
   ========================================================================= */
(function () {
  "use strict";

  const launcher = document.getElementById("chatLauncher");
  const panel = document.getElementById("chatPanel");
  if (!launcher || !panel) return;

  const body = document.getElementById("chatBody");
  const form = document.getElementById("chatForm");
  const input = document.getElementById("chatInput");
  const suggestions = document.getElementById("chatSuggestions");

  const SUGGESTIONS = [
    "Suggest a good restaurant near my hotel",
    "What should I do on Day 3 if it rains?",
    "Can I reduce my trip cost?",
    "Suggest hidden places most tourists miss",
  ];

  const history = [];
  let busy = false;

  /* --- Rendering -------------------------------------------------------- */
  function addMessage(text, who, extraClass) {
    const element = document.createElement("div");
    element.className = "chat-msg " + who + (extraClass ? " " + extraClass : "");
    element.textContent = text;
    body.appendChild(element);
    body.scrollTop = body.scrollHeight;
    return element;
  }

  function renderSuggestions() {
    suggestions.innerHTML = "";
    SUGGESTIONS.forEach(function (text) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = text;
      button.addEventListener("click", function () {
        input.value = text;
        form.dispatchEvent(new Event("submit", { cancelable: true }));
      });
      suggestions.appendChild(button);
    });
  }

  function greet() {
    if (body.childElementCount) return;
    const state = window.ItineraryState || {};
    const destination = (state.trip && state.trip.destination) || "your trip";
    addMessage(
      "Hi! I know your " + destination + " plan. Ask me to change a day, find food, " +
        "cut costs or handle bad weather.",
      "bot"
    );
    renderSuggestions();
  }

  /* --- Sending ---------------------------------------------------------- */
  async function send(event) {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || busy) return;

    busy = true;
    input.value = "";
    addMessage(message, "user");
    history.push({ role: "user", content: message });

    const typing = addMessage("Thinking...", "bot", "typing");

    const state = window.ItineraryState || {};
    try {
      const data = await App.api("/api/ai/chat", {
        method: "POST",
        body: {
          message: message,
          history: history.slice(-10, -1),
          trip_id: state.tripId || null,
          trip: state.trip || null,
          itinerary: state.itinerary || null,
        },
      });
      typing.remove();
      addMessage(data.reply, "bot");
      history.push({ role: "assistant", content: data.reply });
    } catch (err) {
      typing.remove();
      addMessage(err.message, "bot");
      App.toast(err.message, "error");
    } finally {
      busy = false;
      input.focus();
    }
  }

  /* --- Wiring ----------------------------------------------------------- */
  function toggle(open) {
    panel.classList.toggle("open", open);
    launcher.innerHTML = open
      ? '<i class="bi bi-x-lg"></i>'
      : '<i class="bi bi-chat-dots-fill"></i>';
    if (open) {
      greet();
      input.focus();
    }
  }

  launcher.addEventListener("click", () => toggle(!panel.classList.contains("open")));
  document.getElementById("chatClose").addEventListener("click", () => toggle(false));
  form.addEventListener("submit", send);
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && panel.classList.contains("open")) toggle(false);
  });
})();
