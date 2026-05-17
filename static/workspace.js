(function () {
  "use strict";

  const emptyState = document.getElementById("empty-state");
  const chatPanel = document.getElementById("chat-panel");
  const messagesEl = document.getElementById("messages");
  const uploadForm = document.getElementById("upload-form");
  if (!uploadForm) return;

  const uploadBtn = document.getElementById("upload-btn");
  const uploadStatus = document.getElementById("upload-status");
  const docPanel = document.getElementById("doc-panel");
  const docStats = document.getElementById("doc-stats");
  const removeDocBtn = document.getElementById("remove-doc-btn");
  const retrievalInput = document.getElementById("retrieval-k");
  const retrievalOut = document.getElementById("retrieval-k-out");
  const clearBtn = document.getElementById("clear-btn");
  const exportMdBtn = document.getElementById("export-md-btn");
  const exportTxtBtn = document.getElementById("export-txt-btn");
  const toolbarActions = document.getElementById("toolbar-actions");
  const mainHeading = document.getElementById("main-heading");
  const mainLead = document.getElementById("main-lead");
  const chatForm = document.getElementById("chat-form");
  const queryInput = document.getElementById("query");
  const sendBtn = document.getElementById("send-btn");
  const summarizeBtn = document.getElementById("summarize-btn");
  const suggestBtn = document.getElementById("suggest-btn");
  const busyLine = document.getElementById("busy-line");
  const toastRegion = document.getElementById("toast-region");
  const modalOverlay = document.getElementById("modal-overlay");
  const modal = document.getElementById("modal");
  const modalTitle = document.getElementById("modal-title");
  const modalBody = document.getElementById("modal-body");
  const modalCancel = document.getElementById("modal-cancel");
  const modalConfirm = document.getElementById("modal-confirm");

  let modalResolve = null;

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function formatBody(text) {
    return escapeHtml(text).replace(/\n/g, "<br />");
  }

  function toast(message, isError) {
    const t = document.createElement("div");
    t.className = "toast" + (isError ? " toast-error" : "");
    t.textContent = message;
    toastRegion.appendChild(t);
    setTimeout(function () {
      t.remove();
    }, 5000);
  }

  function openModal(title, body) {
    modalTitle.textContent = title;
    modalBody.textContent = body;
    modalOverlay.classList.remove("hidden");
    modal.classList.remove("hidden");
    modalConfirm.focus();
    return new Promise(function (resolve) {
      modalResolve = resolve;
    });
  }

  function closeModal(result) {
    modalOverlay.classList.add("hidden");
    modal.classList.add("hidden");
    if (modalResolve) {
      modalResolve(result);
      modalResolve = null;
    }
  }

  modalCancel.addEventListener("click", function () {
    closeModal(false);
  });
  modalConfirm.addEventListener("click", function () {
    closeModal(true);
  });
  modalOverlay.addEventListener("click", function () {
    closeModal(false);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) {
      closeModal(false);
    }
  });

  function setIndexed(indexed) {
    emptyState.classList.toggle("hidden", indexed);
    chatPanel.classList.toggle("hidden", !indexed);
    docPanel.classList.toggle("hidden", !indexed);
    toolbarActions.classList.toggle("hidden", !indexed);
  }

  function setBusy(busy) {
    busyLine.classList.toggle("hidden", !busy);
    uploadBtn.disabled = busy;
    sendBtn.disabled = busy;
    summarizeBtn.disabled = busy;
    suggestBtn.disabled = busy;
    queryInput.disabled = busy;
    removeDocBtn.disabled = busy;
    retrievalInput.disabled = busy;
    clearBtn.disabled = busy;
    exportMdBtn.disabled = busy;
    exportTxtBtn.disabled = busy;
  }

  function renderDoc(doc) {
    docStats.innerHTML = "";
    if (!doc) return;
    function addRow(label, value) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value;
      docStats.appendChild(dt);
      docStats.appendChild(dd);
    }
    addRow("File", doc.filename || "—");
    addRow("Pages", String(doc.page_count != null ? doc.page_count : "—"));
    addRow("Chunks", String(doc.chunk_count != null ? doc.chunk_count : "—"));
    addRow("Characters", String(doc.char_count != null ? doc.char_count : "—"));
    if (doc.indexed_at) {
      try {
        const d = new Date(doc.indexed_at);
        addRow(
          "Indexed",
          d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
        );
      } catch (e) {
        addRow("Indexed", doc.indexed_at);
      }
    }
  }

  function renderMainHeader(doc) {
    if (!doc) {
      mainHeading.textContent = "No document loaded";
      mainLead.textContent =
        "Upload a PDF to index it for question answering. Everything runs on this machine.";
      return;
    }
    mainHeading.textContent = doc.filename || "Document";
    const parts = [];
    if (doc.chunk_count != null) parts.push(doc.chunk_count + " indexed segments");
    if (doc.page_count != null) parts.push(doc.page_count + " pages");
    mainLead.textContent =
      parts.join(" · ") +
      ". Answers use retrieved segments; verify critical facts in the PDF.";
  }

  function renderMessages(messages) {
    messagesEl.innerHTML = "";
    for (let i = 0; i < messages.length; i++) {
      const m = messages[i];
      const row = document.createElement("div");
      row.className =
        "msg-row " + (m.role === "user" ? "msg-row-user" : "msg-row-assistant");

      const label = document.createElement("div");
      label.className = "msg-label";
      label.textContent = m.role === "user" ? "You" : "Assistant";
      row.appendChild(label);

      const bubble = document.createElement("div");
      bubble.className =
        "bubble " + (m.role === "user" ? "bubble-user" : "bubble-assistant");
      bubble.innerHTML = formatBody(m.content || "");
      row.appendChild(bubble);

      if (m.role === "assistant") {
        const tools = document.createElement("div");
        tools.className = "msg-tools";
        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "btn btn-ghost btn-icon";
        copyBtn.textContent = "Copy";
        copyBtn.setAttribute("aria-label", "Copy assistant reply");
        copyBtn.addEventListener("click", function () {
          navigator.clipboard.writeText(m.content || "").then(
            function () {
              toast("Copied to clipboard.");
            },
            function () {
              toast("Could not copy.", true);
            }
          );
        });
        tools.appendChild(copyBtn);
        row.appendChild(tools);

        if (m.sources && m.sources.length) {
          const det = document.createElement("details");
          det.className = "sources";
          const sum = document.createElement("summary");
          sum.textContent = "Context segments used (" + m.sources.length + ")";
          det.appendChild(sum);
          for (let j = 0; j < m.sources.length; j++) {
            const s = m.sources[j];
            const div = document.createElement("div");
            div.className = "source-item";
            const rank = document.createElement("span");
            rank.className = "source-rank";
            rank.textContent = "#" + (s.rank != null ? s.rank : j + 1);
            div.appendChild(rank);
            div.appendChild(document.createTextNode(s.excerpt || ""));
            det.appendChild(div);
          }
          row.appendChild(det);
        }
      }

      messagesEl.appendChild(row);
    }
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function updateExportButtons(messages) {
    const has = messages && messages.length > 0;
    exportMdBtn.disabled = !has;
    exportTxtBtn.disabled = !has;
  }

  async function refreshState() {
    const r = await fetch("/api/state");
    const data = await r.json();
    if (!data.ok) return;
    setIndexed(data.indexed);
    renderDoc(data.doc);
    renderMainHeader(data.doc);
    if (typeof data.retrieval_k === "number") {
      retrievalInput.value = String(data.retrieval_k);
      retrievalOut.textContent = String(data.retrieval_k);
    }
    renderMessages(data.messages || []);
    updateExportButtons(data.messages || []);
  }

  retrievalInput.addEventListener("input", function () {
    retrievalOut.textContent = retrievalInput.value;
  });

  retrievalInput.addEventListener("change", async function () {
    const k = parseInt(retrievalInput.value, 10);
    try {
      const r = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ retrieval_k: k }),
      });
      const data = await r.json();
      if (!data.ok) {
        toast(data.error || "Could not save setting.", true);
        return;
      }
      if (typeof data.retrieval_k === "number") {
        retrievalInput.value = String(data.retrieval_k);
        retrievalOut.textContent = String(data.retrieval_k);
      }
    } catch (e) {
      toast("Network error while saving settings.", true);
    }
  });

  uploadForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const fd = new FormData(uploadForm);
    const fileInput = document.getElementById("pdf");
    if (!fileInput.files || !fileInput.files.length) {
      uploadStatus.textContent = "Select a PDF first.";
      return;
    }
    uploadStatus.textContent = "";
    setBusy(true);
    try {
      const r = await fetch("/api/upload", { method: "POST", body: fd });
      const data = await r.json();
      if (!data.ok) {
        uploadStatus.textContent = data.error || "Indexing failed.";
        toast(data.error || "Indexing failed.", true);
        return;
      }
      uploadStatus.textContent = "Indexed successfully.";
      toast("Document ready.");
      setIndexed(true);
      renderDoc(data.doc);
      renderMainHeader(data.doc);
      renderMessages(data.messages || []);
      updateExportButtons(data.messages || []);
      if (typeof data.retrieval_k === "number") {
        retrievalInput.value = String(data.retrieval_k);
        retrievalOut.textContent = String(data.retrieval_k);
      }
    } catch (err) {
      uploadStatus.textContent = "Network error.";
      toast("Network error during upload.", true);
    } finally {
      setBusy(false);
    }
  });

  clearBtn.addEventListener("click", async function () {
    const ok = await openModal(
      "Clear conversation",
      "This removes all messages for this session. Your indexed document stays loaded."
    );
    if (!ok) return;
    setBusy(true);
    try {
      const r = await fetch("/api/clear", { method: "POST" });
      const data = await r.json();
      if (data.ok) {
        renderMessages(data.messages || []);
        updateExportButtons(data.messages || []);
        toast("Conversation cleared.");
      }
    } finally {
      setBusy(false);
    }
  });

  removeDocBtn.addEventListener("click", async function () {
    const ok = await openModal(
      "Remove document",
      "This clears the index and conversation. You can upload again at any time."
    );
    if (!ok) return;
    setBusy(true);
    try {
      const r = await fetch("/api/remove-document", { method: "POST" });
      const data = await r.json();
      if (data.ok) {
        setIndexed(false);
        renderDoc(null);
        renderMainHeader(null);
        renderMessages([]);
        updateExportButtons([]);
        uploadStatus.textContent = "";
        document.getElementById("pdf").value = "";
        toast("Document removed.");
      }
    } finally {
      setBusy(false);
    }
  });

  async function downloadExport(format) {
    try {
      const r = await fetch("/api/export?format=" + encodeURIComponent(format));
      if (!r.ok) {
        toast("Export failed.", true);
        return;
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download =
        format === "txt" ? "docquery-conversation.txt" : "docquery-conversation.md";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast("Download started.");
    } catch (e) {
      toast("Could not export.", true);
    }
  }

  exportMdBtn.addEventListener("click", function () {
    downloadExport("md");
  });
  exportTxtBtn.addEventListener("click", function () {
    downloadExport("txt");
  });

  chatForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const message = queryInput.value.trim();
    if (!message) return;
    queryInput.value = "";
    setBusy(true);
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message }),
      });
      const data = await r.json();
      if (!data.ok) {
        toast(data.error || "Request failed.", true);
        return;
      }
      renderMessages(data.messages || []);
      updateExportButtons(data.messages || []);
    } finally {
      setBusy(false);
    }
  });

  summarizeBtn.addEventListener("click", async function () {
    setBusy(true);
    try {
      const r = await fetch("/api/summarize", { method: "POST" });
      const data = await r.json();
      if (!data.ok) {
        toast(data.error || "Summarize failed.", true);
        return;
      }
      renderMessages(data.messages || []);
      updateExportButtons(data.messages || []);
    } finally {
      setBusy(false);
    }
  });

  suggestBtn.addEventListener("click", async function () {
    setBusy(true);
    try {
      const r = await fetch("/api/suggest", { method: "POST" });
      const data = await r.json();
      if (!data.ok) {
        toast(data.error || "Could not generate suggestions.", true);
        return;
      }
      renderMessages(data.messages || []);
      updateExportButtons(data.messages || []);
    } finally {
      setBusy(false);
    }
  });

  queryInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.requestSubmit();
    }
  });

  refreshState();
})();
