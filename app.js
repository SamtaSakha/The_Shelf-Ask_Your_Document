const API_BASE = "/api";

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const uploadStatus = document.getElementById("upload-status");
const docList = document.getElementById("doc-list");
const emptyShelf = document.getElementById("empty-shelf");
const docCount = document.getElementById("doc-count");
const scopeValue = document.getElementById("scope-value");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const questionInput = document.getElementById("question-input");
const sendBtn = document.getElementById("send-btn");

let documents = [];        // {document_id, filename, num_chunks, char_count}
let selectedIds = new Set(); // empty set == "search all"
let history = [];          // rolling chat history sent to backend

// ---------------- Upload ----------------

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) uploadFiles(fileInput.files);
  fileInput.value = "";
});

async function uploadFiles(fileList) {
  const formData = new FormData();
  for (const file of fileList) formData.append("files", file);

  setUploadStatus(`Indexing ${fileList.length} file(s)…`, false);

  try {
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Upload failed (${res.status})`);
    }
    const data = await res.json();
    documents.push(...data.documents);
    renderDocList();
    setUploadStatus(`Added ${data.documents.length} document(s) to the shelf.`, false);
  } catch (e) {
    setUploadStatus(e.message, true);
  }
}

function setUploadStatus(text, isError) {
  uploadStatus.textContent = text;
  uploadStatus.classList.toggle("error", isError);
  if (!isError) {
    setTimeout(() => {
      if (uploadStatus.textContent === text) uploadStatus.textContent = "";
    }, 4000);
  }
}

// ---------------- Document list ----------------

function renderDocList() {
  docList.querySelectorAll(".doc-card").forEach((el) => el.remove());
  emptyShelf.style.display = documents.length ? "none" : "block";
  docCount.textContent = `${documents.length} item${documents.length === 1 ? "" : "s"}`;

  for (const doc of documents) {
    const li = document.createElement("li");
    li.className = "doc-card";
    li.innerHTML = `
      <div class="doc-card-top">
        <span class="doc-name">${escapeHtml(doc.filename)}</span>
        <button class="doc-remove" title="Remove" data-id="${doc.document_id}">×</button>
      </div>
      <div class="doc-meta">${doc.num_chunks} chunks · ${formatChars(doc.char_count)}</div>
      <label class="doc-checkbox-row">
        <input type="checkbox" data-id="${doc.document_id}" class="doc-select" checked />
        include in search
      </label>
    `;
    docList.appendChild(li);
  }

  docList.querySelectorAll(".doc-remove").forEach((btn) => {
    btn.addEventListener("click", () => removeDocument(btn.dataset.id));
  });
  docList.querySelectorAll(".doc-select").forEach((cb) => {
    cb.addEventListener("change", updateScope);
  });

  updateScope();
}

function updateScope() {
  const checkboxes = [...docList.querySelectorAll(".doc-select")];
  const uncheckedIds = checkboxes.filter((cb) => !cb.checked).map((cb) => cb.dataset.id);
  const allChecked = uncheckedIds.length === 0;

  selectedIds = allChecked ? new Set() : new Set(checkboxes.filter((cb) => cb.checked).map((cb) => cb.dataset.id));

  if (documents.length === 0) {
    scopeValue.textContent = "no documents uploaded";
  } else if (allChecked) {
    scopeValue.textContent = "all documents";
  } else if (selectedIds.size === 0) {
    scopeValue.textContent = "none selected";
  } else {
    scopeValue.textContent = `${selectedIds.size} selected document(s)`;
  }
}

async function removeDocument(id) {
  try {
    const res = await fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to remove document");
    documents = documents.filter((d) => d.document_id !== id);
    renderDocList();
  } catch (e) {
    setUploadStatus(e.message, true);
  }
}

// ---------------- Chat ----------------

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  addMessage("user", question);
  questionInput.value = "";
  autoGrow();
  history.push({ role: "user", content: question });

  const thinkingEl = addThinkingBubble();
  setFormEnabled(false);

  try {
    const body = {
      question,
      document_ids: selectedIds.size > 0 ? [...selectedIds] : null,
      history: history.slice(0, -1),
    };
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    const data = await res.json();
    thinkingEl.remove();
    addMessage("assistant", data.answer, data.sources);
    history.push({ role: "assistant", content: data.answer });
  } catch (e) {
    thinkingEl.remove();
    addMessage("assistant", `Something went wrong: ${e.message}`);
  } finally {
    setFormEnabled(true);
    questionInput.focus();
  }
});

questionInput.addEventListener("input", autoGrow);
questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    chatForm.requestSubmit();
  }
});

function autoGrow() {
  questionInput.style.height = "auto";
  questionInput.style.height = Math.min(questionInput.scrollHeight, 160) + "px";
}

function setFormEnabled(enabled) {
  sendBtn.disabled = !enabled;
  questionInput.disabled = !enabled;
}

function addMessage(role, text, sources) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);

  if (sources && sources.length) {
    const sourcesWrap = document.createElement("div");
    sourcesWrap.className = "sources";
    const label = document.createElement("div");
    label.className = "sources-label";
    label.textContent = `Sources (${sources.length})`;
    sourcesWrap.appendChild(label);

    for (const s of sources) {
      const card = document.createElement("div");
      card.className = "source-card";
      card.innerHTML = `
        <div class="source-card-top">
          <span>${escapeHtml(s.filename)} · chunk ${s.chunk_index}</span>
          <span class="source-score">match ${(s.score * 100).toFixed(0)}%</span>
        </div>
        <div class="source-excerpt">${escapeHtml(s.text)}</div>
      `;
      sourcesWrap.appendChild(card);
    }
    wrap.appendChild(sourcesWrap);
  }

  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
  return wrap;
}

function addThinkingBubble() {
  const wrap = document.createElement("div");
  wrap.className = "msg assistant";
  wrap.innerHTML = `<div class="bubble thinking">Reading the documents…</div>`;
  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
  return wrap;
}

// ---------------- Helpers ----------------

function formatChars(n) {
  if (n < 1000) return `${n} chars`;
  return `${(n / 1000).toFixed(1)}k chars`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------------- Init ----------------

async function loadExistingDocuments() {
  try {
    const res = await fetch(`${API_BASE}/documents`);
    if (!res.ok) return;
    const data = await res.json();
    documents = data.documents;
    renderDocList();
  } catch {
    // backend not reachable yet — ignore, user will see it on first action
  }
}

loadExistingDocuments();
