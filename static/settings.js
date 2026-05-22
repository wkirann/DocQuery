(function () {
  "use strict";

  var statusEl = document.getElementById("settings-health-status");
  var detailEl = document.getElementById("settings-health-detail");

  fetch("/api/health")
    .then(function (r) { return r.json(); })
    .then(function (h) {
      if (!h.ok || !statusEl) return;
      if (h.ollama_reachable) {
        statusEl.textContent = "Online";
        statusEl.className = "";
        if (detailEl) {
          detailEl.textContent = "HTTP API responded at " + (h.ollama_host || "") + ".";
        }
      } else {
        statusEl.textContent = "Offline";
        statusEl.className = "text-danger";
        if (detailEl) {
          detailEl.textContent =
            (h.ollama_error || "Could not reach Ollama.") +
            " Ensure the daemon is running (e.g. Ollama app on Windows).";
        }
      }
    })
    .catch(function () {
      if (statusEl) statusEl.textContent = "Unknown";
      if (detailEl) detailEl.textContent = "Could not query the server.";
    });
})();