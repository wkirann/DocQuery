(function () {
  "use strict";

  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  fetch("/api/state")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data.ok) return;
      if (data.indexed && data.doc) {
        setText("dash-doc-status", "Indexed");
        setText("dash-doc-name", data.doc.filename || "");
      } else {
        setText("dash-doc-status", "None");
        setText("dash-doc-name", "Upload a PDF in Workspace.");
      }
      var n = (data.messages && data.messages.length) || 0;
      setText("dash-msg-count", String(n));
      setText("dash-retrieval-k", String(data.retrieval_k != null ? data.retrieval_k : "—"));
    })
    .catch(function () {
      setText("dash-doc-status", "Unavailable");
    });
})();