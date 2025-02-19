const API = 'http://localhost:8000';
let ws = null;
let documents = [];
let chatHistory = [];
let isDark = false;

// ---- THEME ----
function toggleTheme() {
  isDark = !isDark;
  document.getElementById('htmlRoot').classList.toggle('dark', isDark);
}

// ---- GRAPH STATS ----
async function loadGraphStats() {
  try {
    const r = await fetch(`${API}/api/v1/graph/stats`);
    if (!r.ok) return;
    const data = await r.json();
    document.getElementById('statDocs').textContent = data.total_documents || data.docs || 0;
    document.getElementById('statChunks').textContent = data.total_chunks || data.chunks || 0;
    document.getElementById('graphStats').classList.remove('hidden');
    document.getElementById('docCount').textContent = data.total_documents || data.docs || 0;
  } catch {}
}

// ---- DOCUMENTS ----
async function loadDocuments() {
  try {
    const r = await fetch(`${API}/api/v1/documents`);
    if (!r.ok) return;
    const data = await r.json();
    documents = Array.isArray(data) ? data : data.documents || [];
    renderDocumentList();
    document.getElementById('docCount').textContent = documents.length;
  } catch {}
}

function renderDocumentList() {
  const container = document.getElementById('documentList');
  if (documents.length === 0) {
    container.innerHTML = '<div class="text-xs text-muted italic text-center pt-4">No documents yet</div>';
    return;
  }
  container.innerHTML = '';
  documents.forEach(doc => {
    const card = document.createElement('div');
    card.className = 'doc-card';
    const ext = (doc.filename || doc.name || '').split('.').pop().toLowerCase();
    const icons = { pdf: '📄', png: '🖼️', jpg: '🖼️', jpeg: '🖼️', txt: '📝', md: '📝', default: '📁' };
    const icon = icons[ext] || icons.default;
    card.innerHTML = `
      <div class="doc-icon">${icon}</div>
      <div class="flex-1 min-w-0">
        <div class="text-xs font-medium truncate" style="color:var(--foreground)">${doc.filename || doc.name || doc.id}</div>
        <div class="text-xs text-muted">${doc.size ? formatSize(doc.size) : ext.toUpperCase()}</div>
      </div>
      <button onclick="deleteDocument('${doc.id || doc.doc_id}')" class="text-muted hover:text-red-500 text-xs flex-shrink-0 transition">
        <i class="fas fa-trash-alt"></i>
      </button>
    `;
    container.appendChild(card);
  });
}

async function deleteDocument(docId) {
  try {
    await fetch(`${API}/api/v1/documents/${docId}`, { method: 'DELETE' });
    showToast('Document removed', 'success');
    loadDocuments();
    loadGraphStats();
  } catch (e) { showToast('Delete failed', 'error'); }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + 'B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + 'KB';
  return (bytes / 1048576).toFixed(1) + 'MB';
}

// ---- FILE UPLOAD ----
function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.add('drag-over');
}
function handleDragLeave(e) {
  document.getElementById('dropZone').classList.remove('drag-over');
}
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('dropZone').classList.remove('drag-over');
  if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files);
}

async function uploadFile(files) {
  const file = files[0];
  if (!file) return;
  const ext = file.name.split('.').pop().toLowerCase();
  const endpoint = ['pdf'].includes(ext) ? 'pdf' : ['png','jpg','jpeg','gif','webp'].includes(ext) ? 'image' : 'pdf';

  showUploadProgress(file.name, 0);
  const formData = new FormData();
  formData.append('file', file);

  try {
    // Animate progress
    let p = 0;
    const interval = setInterval(() => {
      p = Math.min(p + 10, 90);
      updateUploadProgress(p);
    }, 200);

    const r = await fetch(`${API}/api/v1/ingest/${endpoint}`, { method: 'POST', body: formData });
    clearInterval(interval);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    updateUploadProgress(100);
    setTimeout(() => hideUploadProgress(), 1000);
    showToast(`"${file.name}" indexed successfully`, 'success');
    loadDocuments();
    loadGraphStats();
  } catch (e) {
    hideUploadProgress();
    showToast(`Upload failed: ${e.message}`, 'error');
  }
}

function showUploadProgress(name, pct) {
  document.getElementById('uploadProgress').classList.remove('hidden');
  document.getElementById('uploadFileName').textContent = name;
  updateUploadProgress(pct);
}
function updateUploadProgress(pct) {
  document.getElementById('uploadPct').textContent = pct + '%';
  document.getElementById('uploadBar').style.width = pct + '%';
}
function hideUploadProgress() {
  document.getElementById('uploadProgress').classList.add('hidden');
}

// ---- URL INGESTION ----
async function ingestUrl() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) return showToast('Please enter a URL', 'error');
  document.getElementById('urlInput').value = '';
  showToast('Ingesting URL…', 'info');
  try {
    const r = await fetch(`${API}/api/v1/ingest/url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    showToast('URL indexed!', 'success');
    loadDocuments();
    loadGraphStats();
  } catch (e) { showToast(`Failed: ${e.message}`, 'error'); }
}

// ---- CHAT / QA ----
function connectChatWS() {
  try {
    ws = new WebSocket('ws://localhost:8000/ws/chat');
    ws.onopen = () => document.getElementById('wsStatus').textContent = '● Streaming connected';
    ws.onclose = () => {
      document.getElementById('wsStatus').textContent = '○ Streaming disconnected (will retry)';
      setTimeout(connectChatWS, 5000);
    };
    ws.onerror = () => document.getElementById('wsStatus').textContent = '○ Streaming unavailable';
  } catch { document.getElementById('wsStatus').textContent = '○ Streaming unavailable'; }
}

async function sendQuestion() {
  const input = document.getElementById('questionInput');
  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  addUserMessage(question);
  const aiEl = addAIMessage('');

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ question }));
    let fullText = '';
    const originalOnMessage = ws.onmessage;
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'answer_chunk' && msg.content) {
          fullText += msg.content;
          aiEl.querySelector('.bubble').textContent = fullText;
          scrollChat();
        } else if (msg.type === 'done') {
          aiEl.querySelector('.bubble').classList.remove('streaming-cursor');
          if (msg.sources) renderCitations(msg.sources);
          ws.onmessage = originalOnMessage;
        } else if (msg.type === 'error') {
          aiEl.querySelector('.bubble').textContent = 'Error: ' + (msg.message || 'Unknown error');
          ws.onmessage = originalOnMessage;
        }
      } catch {}
    };
    aiEl.querySelector('.bubble').classList.add('streaming-cursor');
  } else {
    // REST fallback
    try {
      const r = await fetch(`${API}/api/v1/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const answer = data.answer || data.response || JSON.stringify(data);
      aiEl.querySelector('.bubble').textContent = answer;
      if (data.sources) renderCitations(data.sources);
      scrollChat();
    } catch (e) {
      aiEl.querySelector('.bubble').textContent = `Error: ${e.message}. Make sure the backend is running.`;
    }
  }
}

function addUserMessage(text) {
  const container = document.getElementById('chatMessages');
  // Remove welcome screen
  const welcome = container.querySelector('.text-center');
  if (welcome) welcome.remove();
  const msg = document.createElement('div');
  msg.className = 'msg-user';
  msg.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  container.appendChild(msg);
  scrollChat();
  return msg;
}

function addAIMessage(text) {
  const container = document.getElementById('chatMessages');
  const msg = document.createElement('div');
  msg.className = 'msg-ai';
  msg.innerHTML = `
    <div class="avatar"><i class="fas fa-magnifying-glass-chart text-xs"></i></div>
    <div class="bubble ${text ? '' : 'streaming-cursor'}">${escapeHtml(text) || '…'}</div>
  `;
  container.appendChild(msg);
  scrollChat();
  return msg;
}

function scrollChat() {
  const c = document.getElementById('chatMessages');
  c.scrollTop = c.scrollHeight;
}

function renderCitations(sources) {
  const container = document.getElementById('citationsList');
  container.innerHTML = '';
  if (!sources || sources.length === 0) {
    container.innerHTML = '<div class="text-xs text-muted italic">No sources found</div>';
    return;
  }
  sources.forEach((src, i) => {
    const card = document.createElement('div');
    card.className = 'citation-card';
    const score = src.score || src.relevance || 0;
    card.innerHTML = `
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-xs font-semibold" style="color:var(--secondary)">[${i + 1}]</span>
        <span class="text-xs truncate" style="color:var(--foreground)">${src.filename || src.doc_id || 'Source'}</span>
      </div>
      <div class="score-bar"><div class="score-fill" style="width:${Math.min(score * 100, 100)}%"></div></div>
      <div class="text-xs mt-2" style="color:var(--muted);line-height:1.5">${escapeHtml((src.text || src.content || '').substring(0, 150))}…</div>
    `;
    container.appendChild(card);
  });
}

function toggleCitations() {
  const panel = document.getElementById('citationsPanel');
  panel.classList.toggle('hidden');
}

function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ---- TOAST ----
function showToast(msg, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<i class="fas fa-${type === 'error' ? 'circle-xmark' : type === 'success' ? 'circle-check' : 'info-circle'} mr-2"></i>${msg}`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ---- INIT ----
loadDocuments();
loadGraphStats();
connectChatWS();
