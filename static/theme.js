(function () {
  "use strict";

  var THEME_KEY = "docquery-theme";

  function syncMetaThemeColor() {
    var meta = document.getElementById("meta-theme-color");
    if (!meta) return;
    var dark = document.documentElement.getAttribute("data-theme") === "dark";
    meta.setAttribute("content", dark ? "#12151c" : "#ffffff");
  }

  function syncThemeButtons() {
    var th = document.documentElement.getAttribute("data-theme") || "light";
    document.querySelectorAll("#theme-light, #theme-dark").forEach(function (btn) {
      if (!btn) return;
      var isLight = btn.id === "theme-light";
      btn.setAttribute("aria-pressed", (isLight ? th === "light" : th === "dark") ? "true" : "false");
    });
  }

  function applyTheme(mode) {
    if (mode !== "light" && mode !== "dark") return;
    document.documentElement.setAttribute("data-theme", mode);
    try {
      localStorage.setItem(THEME_KEY, mode);
    } catch (e) {}
    syncMetaThemeColor();
    syncThemeButtons();
  }

  function bindThemeButtons() {
    var light = document.getElementById("theme-light");
    var dark = document.getElementById("theme-dark");
    if (light) light.addEventListener("click", function () { applyTheme("light"); });
    if (dark) dark.addEventListener("click", function () { applyTheme("dark"); });
  }

  function initHealthPill() {
    var pill = document.getElementById("health-pill");
    if (!pill) return;
    fetch("/api/health")
      .then(function (r) { return r.json(); })
      .then(function (h) {
        if (!h.ok) return;
        if (h.ollama_reachable) {
          pill.textContent = "Ollama online";
          pill.className = "pill pill-ok";
          pill.title = "Reached " + (h.ollama_host || "") + " (HTTP API).";
        } else {
          pill.textContent = "Ollama offline";
          pill.className = "pill pill-warn";
          pill.title =
            (h.ollama_error ? h.ollama_error + " — " : "") +
            "Check that Ollama is running and OLLAMA_HOST matches (default http://127.0.0.1:11434).";
        }
      })
      .catch(function () {
        pill.textContent = "Status unknown";
        pill.className = "pill pill-muted";
      });
  }

  syncMetaThemeColor();
  syncThemeButtons();
  bindThemeButtons();
  initHealthPill();
})();
