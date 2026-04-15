'use strict';

// ── State ──
let sessionId       = 'sess_' + Date.now();
let isLoading       = false;
let ttsEnabled      = false;
let isListening     = false;
let recognition     = null;
let chatSessions    = [];
let currentSession  = null;
let currentMessages = [];
let pendingFiles    = [];   // V5: files waiting to be uploaded

// ── DOM helpers ──
const $  = id => document.getElementById(id);
const chatBox       = () => $('chat-box');
const userInput     = () => $('user-input');
const sendBtn       = () => $('send-btn');
const themeToggle   = () => $('theme-toggle');
const langSelect    = () => $('lang-select');
const voiceBtn      = () => $('voice-btn');
const ttsBtn        = () => $('tts-btn');
const newsBtn       = () => $('news-btn');
const statusBar     = () => $('status-bar');
const chatList      = () => $('chat-list');
const newChatBtn    = () => $('new-chat-btn');
const topbarTitle   = () => $('topbar-title');
const sidebarEl     = () => $('sidebar');
const sidebarToggle = () => $('sidebar-toggle');
const newsList      = () => $('news-list');
const newsSection   = () => $('news-section');
const uploadBtn     = () => $('upload-btn');
const fileInput     = () => $('file-input');
const filePreview   = () => $('file-preview');

// ── Theme init ──
(function initTheme() {
  const saved = localStorage.getItem('pandaTheme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  const btn = themeToggle();
  if (btn) btn.textContent = saved === 'dark' ? '☀️' : '🌙';
})();

// ── Sessions init ──
(function initSessions() {
  try { chatSessions = JSON.parse(localStorage.getItem('pandaSessions') || '[]'); }
  catch { chatSessions = []; }
  renderChatList();
})();

// ── Language map ──
const LANG_MAP = {
  en: 'Respond in English.',
  te: 'Respond fully in Telugu (తెలుగు లో జవాబు ఇవ్వండి).',
  hi: 'Respond fully in Hindi (हिंदी में उत्तर दें).',
  ta: 'Respond fully in Tamil.',
  es: 'Respond fully in Spanish.',
  fr: 'Respond fully in French.',
  de: 'Respond fully in German.',
  ja: 'Respond fully in Japanese.',
  zh: 'Respond fully in Chinese.',
  ar: 'Respond fully in Arabic.',
};

// ── Auto-scroll ──
function scrollToBottom() {
  const box = chatBox();
  if (!box) return;
  requestAnimationFrame(() => requestAnimationFrame(() => { box.scrollTop = box.scrollHeight; }));
}

// ── Status bar ──
function setStatus(msg, cls) {
  const bar = statusBar();
  if (!bar) return;
  bar.textContent = msg || '';
  bar.className   = msg ? ('show ' + (cls || '')) : '';
}

// ── Markdown renderer ──
function renderMd(text) {
  let t = text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm,  '<h2>$1</h2>')
    .replace(/^# (.+)$/gm,   '<h1>$1</h1>')
    .replace(/^[\*\-] (.+)$/gm, '<li>$1</li>')
    .replace(/^\d+\.\s(.+)$/gm, '<li>$1</li>');
  t = t.replace(/(<li>[\s\S]*?<\/li>)+/g, m => '<ul>' + m + '</ul>');
  t = t.replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>');
  return '<p>' + t + '</p>';
}

// ── Listen + Reactions (Issue 1 fix) ──
function addMsgActions(wrap, text) {
  const actions   = document.createElement('div');
  actions.className = 'msg-actions';

  const listenBtn = document.createElement('button');
  listenBtn.className = 'tts-msg-btn';
  listenBtn.innerHTML = '🔊 Listen';
  listenBtn.onclick   = () => {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      listenBtn.innerHTML = '🔊 Listen';
      listenBtn.classList.remove('speaking');
      return;
    }
    const plain = text.replace(/[#*`_\[\]()>~<]/g, '').slice(0, 600);
    const utt   = new SpeechSynthesisUtterance(plain);
    const ls    = langSelect();
    const lc    = ls ? ls.value : 'en';
    utt.lang    = lc === 'te' ? 'te-IN' : lc === 'hi' ? 'hi-IN' : lc === 'ta' ? 'ta-IN' : 'en-US';
    utt.rate    = 0.95;
    utt.onstart = () => { listenBtn.innerHTML = '⏹ Stop'; listenBtn.classList.add('speaking'); };
    utt.onend   = () => { listenBtn.innerHTML = '🔊 Listen'; listenBtn.classList.remove('speaking'); };
    window.speechSynthesis.speak(utt);
  };
  actions.appendChild(listenBtn);
  wrap.appendChild(actions);

  const reactions = document.createElement('div');
  reactions.className = 'emoji-reactions';
  ['👍','❤️','😊','🔥','👏'].forEach(emoji => {
    const btn = document.createElement('button');
    btn.className   = 'emoji-btn';
    btn.textContent = emoji;
    btn.onclick     = () => btn.classList.toggle('reacted');
    reactions.appendChild(btn);
  });
  wrap.appendChild(reactions);
}

// ── Append message ──
function appendMessage(role, content, searched, fileBadge) {
  const welcome = document.getElementById('welcome');
  if (welcome) welcome.remove();

  const box = chatBox();
  if (!box) return null;

  const row        = document.createElement('div');
  row.className    = `msg-row ${role}`;

  const avatar     = document.createElement('div');
  avatar.className = role === 'ai' ? 'avatar panda' : 'avatar user-av';
  avatar.textContent = role === 'ai' ? '🐼' : '👤';
  row.appendChild(avatar);

  const mc         = document.createElement('div');
  mc.className     = 'msg-content';

  // Badges
  if (role === 'ai' && searched) {
    const b = document.createElement('div');
    b.className = 'search-badge';
    b.innerHTML = '🌐 Live Search';
    mc.appendChild(b);
  }
  if (fileBadge) {
    const b = document.createElement('div');
    b.className = 'file-badge';
    b.innerHTML = `📁 ${fileBadge}`;
    mc.appendChild(b);
  }

  const bubble     = document.createElement('div');
  bubble.className = role === 'ai' ? 'bubble ai' : 'bubble user';
  bubble.innerHTML = role === 'ai' ? renderMd(content) : escHtml(content);
  mc.appendChild(bubble);

  if (role === 'ai') addMsgActions(mc, content);

  row.appendChild(mc);
  box.appendChild(row);
  scrollToBottom();
  return row;
}

// ── Loading dots ──
function showLoading() {
  const box = chatBox();
  if (!box) return;
  const row = document.createElement('div');
  row.id = 'loading-msg'; row.className = 'msg-row ai';
  const av = document.createElement('div');
  av.className = 'avatar panda'; av.textContent = '🐼';
  row.appendChild(av);
  const mc = document.createElement('div'); mc.className = 'msg-content';
  const bub = document.createElement('div'); bub.className = 'bubble ai';
  bub.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
  mc.appendChild(bub); row.appendChild(mc); box.appendChild(row);
  scrollToBottom();
}
function hideLoading() {
  const el = document.getElementById('loading-msg');
  if (el) el.remove();
}

// ════════════════════════════════════════
// V5: FILE UPLOAD LOGIC
// Synced with /upload route in app.py
// ════════════════════════════════════════
function updateFilePreview() {
  const preview = filePreview();
  if (!preview) return;
  if (!pendingFiles.length) {
    preview.innerHTML = '';
    preview.classList.remove('show');
    return;
  }
  preview.classList.add('show');
  preview.innerHTML = '📎 ' + pendingFiles.map((f, i) =>
    `<span class="file-tag">${f.name} <span class="file-tag-remove" onclick="removeFile(${i})">✕</span></span>`
  ).join('');
}

function removeFile(idx) {
  pendingFiles.splice(idx, 1);
  updateFilePreview();
}

async function uploadAndAnalyze() {
  if (!pendingFiles.length) return;

  const question   = (userInput() ? userInput().value.trim() : '') || 'Please summarize this file';
  const fileNames  = pendingFiles.map(f => f.name).join(', ');

  isLoading = true;
  const btn = sendBtn();
  if (btn) btn.disabled = true;
  if (userInput()) { userInput().value = ''; userInput().style.height = 'auto'; }

  if (!currentSession) startSession();
  currentMessages.push({ role: 'user', content: `[File Upload] ${fileNames}: ${question}` });
  persistSessions();

  appendMessage('user', `📎 ${fileNames}\n${question}`);
  showLoading();
  setStatus('📁 Analyzing file...', 'thinking-status');

  try {
    const formData = new FormData();
    pendingFiles.forEach(f => formData.append('files', f));
    formData.append('question',   question);
    formData.append('session_id', sessionId);

    // POST to /upload — synced with app.py /upload route
    const res  = await fetch('/upload', { method: 'POST', body: formData });
    const data = await res.json();
    hideLoading();

    if (data.error) {
      appendMessage('ai', '⚠️ ' + data.error, false, null);
    } else {
      const reply    = data.reply || '';
      const fileType = data.file_type || 'File';
      currentMessages.push({ role: 'ai', content: reply });
      persistSessions();
      appendMessage('ai', reply, false, fileType);
      if (ttsEnabled && reply) speakText(reply);
    }
  } catch (err) {
    hideLoading();
    appendMessage('ai', '⚠️ File upload failed. Please try again.', false, null);
    console.error('Upload error:', err);
  }

  // Clear pending files
  pendingFiles = [];
  updateFilePreview();
  if (fileInput()) fileInput().value = '';

  setStatus('');
  isLoading = false;
  if (btn) btn.disabled = false;
  if (userInput()) userInput().focus();
}

// ════════════════════════════════════════
// MAIN: sendMessage()
// ════════════════════════════════════════
async function sendMessage(overrideText) {
  // If files pending → upload instead
  if (pendingFiles.length) {
    await uploadAndAnalyze();
    return;
  }

  const inp = userInput();
  const msg = (overrideText !== undefined ? overrideText : (inp ? inp.value : '')).trim();
  if (!msg || isLoading) return;

  isLoading = true;
  const btn = sendBtn();
  if (btn) btn.disabled = true;
  if (inp) { inp.value = ''; inp.style.height = 'auto'; }

  if (!currentSession) startSession();
  currentMessages.push({ role: 'user', content: msg });
  persistSessions();

  appendMessage('user', msg);
  showLoading();
  setStatus('🐼 Panda AI is thinking...', 'thinking-status');

  // Update topbar title
  if (currentMessages.filter(m => m.role === 'user').length === 1) {
    const title = msg.slice(0, 35);
    if (topbarTitle()) topbarTitle().textContent = title;
    if (currentSession) { currentSession.title = title; renderChatList(); }
  }

  const ls       = langSelect();
  const langCode  = ls ? ls.value : 'en';
  const langInstr = LANG_MAP[langCode] || '';

  try {
    // POST to /chat — synced with app.py /chat route
    const res  = await fetch('/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ message: msg, session_id: sessionId, lang_instruction: langInstr }),
    });
    const data = await res.json();
    hideLoading();

    if (data.error) {
      appendMessage('ai', '⚠️ ' + data.error, false, null);
    } else {
      const reply    = data.reply    || '';
      const searched = data.searched || false;
      currentMessages.push({ role: 'ai', content: reply });
      persistSessions();
      appendMessage('ai', reply, searched, null);
      if (ttsEnabled && reply) speakText(reply);
    }
  } catch (err) {
    hideLoading();
    appendMessage('ai', '⚠️ Network error. Please check your connection.', false, null);
    console.error('Chat error:', err);
  }

  setStatus('');
  isLoading = false;
  if (btn) btn.disabled = false;
  if (inp) inp.focus();
}

// ── Quick chips ──
function quickSend(el) {
  const text = el.textContent.replace(/[\u{1F300}-\u{1FAFF}]/gu, '').trim();
  sendMessage(text || el.textContent.trim());
}

// ── TTS ──
function speakText(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const plain = text.replace(/[#*`_\[\]()>~]/g, '').slice(0, 500);
  const utt   = new SpeechSynthesisUtterance(plain);
  const ls    = langSelect();
  const lc    = ls ? ls.value : 'en';
  utt.lang    = lc === 'te' ? 'te-IN' : lc === 'hi' ? 'hi-IN' : lc === 'ta' ? 'ta-IN' : 'en-US';
  utt.rate    = 0.95;
  const tb    = ttsBtn();
  utt.onstart = () => tb && tb.classList.add('speaking');
  utt.onend   = () => tb && tb.classList.remove('speaking');
  window.speechSynthesis.speak(utt);
}

// ── Voice input ──
function toggleVoice() {
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    alert('Voice input not supported. Try Chrome on desktop.');
    return;
  }
  const vb = voiceBtn();
  if (isListening) { recognition && recognition.stop(); return; }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  const ls    = langSelect();
  const lc    = ls ? ls.value : 'en';
  recognition.lang           = lc === 'te' ? 'te-IN' : lc === 'hi' ? 'hi-IN' : 'en-US';
  recognition.interimResults = true;
  recognition.continuous     = false;
  recognition.onstart  = () => { isListening = true; vb && vb.classList.add('listening'); setStatus('🎤 Listening...', 'listening-status'); };
  recognition.onresult = (e) => { const t = Array.from(e.results).map(r => r[0].transcript).join(''); const inp = userInput(); if (inp) inp.value = t; };
  recognition.onend    = () => { isListening = false; vb && vb.classList.remove('listening'); setStatus(''); const inp = userInput(); if (inp && inp.value.trim()) sendMessage(); };
  recognition.onerror  = () => { isListening = false; vb && vb.classList.remove('listening'); setStatus(''); };
  recognition.start();
}

// ── News ──
async function toggleNews() {
  const ns = newsSection();
  const nl = newsList();
  if (!ns || !nl) return;
  const visible = ns.style.display === 'block';
  ns.style.display = visible ? 'none' : 'block';
  if (!visible) {
    nl.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">Loading...</div>';
    try {
      const res  = await fetch('/news');
      const data = await res.json();
      nl.innerHTML = data.news && data.news.length
        ? data.news.map(h => `<div class="news-item" onclick="sendMessage(${JSON.stringify('Tell me about: ' + h)})">📰 ${h}</div>`).join('')
        : '<div style="color:#888;font-size:11px;padding:6px">No news available.</div>';
    } catch {
      nl.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">Failed to load.</div>';
    }
  }
}

// ── Session management ──
function startSession() {
  sessionId       = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2,7);
  currentMessages = [];
  currentSession  = { id: sessionId, title: 'New Chat', messages: [], ts: Date.now() };
  chatSessions.unshift(currentSession);
  persistSessions();
  renderChatList();
  if (topbarTitle()) topbarTitle().textContent = 'New Chat';
}

function persistSessions() {
  if (currentSession) { currentSession.messages = [...currentMessages]; currentSession.ts = Date.now(); }
  try { localStorage.setItem('pandaSessions', JSON.stringify(chatSessions.slice(0,30))); } catch {}
}

function loadSession(id) {
  const s = chatSessions.find(s => s.id === id);
  if (!s) return;
  currentSession = s; sessionId = s.id; currentMessages = s.messages ? [...s.messages] : [];
  const box = chatBox();
  if (box) { box.innerHTML = ''; currentMessages.forEach(m => appendMessage(m.role, m.content)); }
  if (topbarTitle()) topbarTitle().textContent = s.title || 'Chat';
  renderChatList();
  sidebarEl() && sidebarEl().classList.remove('open');
}

function deleteSession(id) {
  chatSessions = chatSessions.filter(s => s.id !== id);
  persistSessions();
  if (currentSession && currentSession.id === id) {
    currentSession = null; currentMessages = [];
    const box = chatBox();
    if (box) box.innerHTML = buildWelcomeHTML();
  }
  renderChatList();
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderChatList() {
  const cl = chatList();
  if (!cl) return;
  if (!chatSessions.length) { cl.innerHTML = '<div class="no-chats">No chats yet 🐼<br>Start a new chat!</div>'; return; }
  cl.innerHTML = chatSessions.map(s => `
    <div class="chat-item ${currentSession && currentSession.id === s.id ? 'active' : ''}" onclick="loadSession('${s.id}')">
      <span class="chat-item-icon">💬</span>
      <div class="chat-item-text">
        <div class="chat-item-title">${escHtml(s.title || 'New Chat')}</div>
        <div class="chat-item-time">${new Date(s.ts).toLocaleDateString()}</div>
      </div>
      <button class="chat-item-del" onclick="event.stopPropagation();deleteSession('${s.id}')">🗑</button>
    </div>`).join('');
}

function buildWelcomeHTML() {
  return `<div id="welcome" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:18px;text-align:center">
    <div class="welcome-icon">🐼</div>
    <h2 style="font-family:'Comfortaa',cursive;font-size:42px;color:var(--black)">Panda AI</h2>
    <p style="color:var(--muted);font-size:15px;max-width:380px;line-height:1.6">Calm, wise and always helpful — just like a panda! 🎋</p>
    <div class="web-badge">🌐 Real-time Web Search + 📁 File Analysis</div>
    <div class="chips">
      <div class="chip" onclick="quickSend(this)">Today's news 📰</div>
      <div class="chip" onclick="quickSend(this)">Write Python code 🐍</div>
      <div class="chip" onclick="quickSend(this)">IPL 2026 results 🏏</div>
      <div class="chip" onclick="quickSend(this)">Tell me a fun fact 🎯</div>
    </div>
  </div>`;
}

function newChat() {
  const box = chatBox();
  if (box) box.innerHTML = buildWelcomeHTML();
  startSession();
  pendingFiles = []; updateFilePreview();
  userInput() && userInput().focus();
  sidebarEl() && sidebarEl().classList.remove('open');
}

// ════════════════════════════════════════
// EVENT LISTENERS
// ════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {

  // Send button
  sendBtn() && sendBtn().addEventListener('click', () => sendMessage());

  // Enter key (desktop + mobile)
  const inp = userInput();
  if (inp) {
    inp.addEventListener('input', function() {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 130) + 'px';
    });
    inp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.stopPropagation(); sendMessage(); return false; }
    });
    inp.addEventListener('keypress', function(e) {
      if ((e.key === 'Enter' || e.keyCode === 13) && !e.shiftKey) { e.preventDefault(); e.stopPropagation(); sendMessage(); return false; }
    });
    inp.focus();
  }

  // V5: File upload button → triggers hidden file input
  const ub = uploadBtn();
  const fi = fileInput();
  if (ub && fi) {
    ub.addEventListener('click', () => fi.click());
    fi.addEventListener('change', (e) => {
      const files = Array.from(e.target.files);
      if (files.length) {
        pendingFiles = [...pendingFiles, ...files];
        updateFilePreview();
        // Focus textarea so user can type question
        if (userInput()) {
          userInput().placeholder = 'Ask something about the file...';
          userInput().focus();
        }
      }
    });
    // Drag and drop on chat box
    const box = chatBox();
    if (box) {
      box.addEventListener('dragover', (e) => { e.preventDefault(); box.style.outline = '2px dashed var(--accent)'; });
      box.addEventListener('dragleave', () => { box.style.outline = ''; });
      box.addEventListener('drop', (e) => {
        e.preventDefault(); box.style.outline = '';
        const files = Array.from(e.dataTransfer.files);
        if (files.length) { pendingFiles = [...pendingFiles, ...files]; updateFilePreview(); }
      });
    }
  }

  // Theme toggle
  themeToggle() && themeToggle().addEventListener('click', () => {
    const cur  = document.documentElement.getAttribute('data-theme');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('pandaTheme', next);
    themeToggle().textContent = next === 'dark' ? '☀️' : '🌙';
  });

  // Sidebar toggle (mobile)
  const st = sidebarToggle(); const sd = sidebarEl();
  if (st && sd) {
    st.addEventListener('click', () => sd.classList.toggle('open'));
    document.addEventListener('click', e => {
      if (sd.classList.contains('open') && !sd.contains(e.target) && e.target !== st)
        sd.classList.remove('open');
    });
  }

  // New chat
  newChatBtn() && newChatBtn().addEventListener('click', newChat);

  // TTS toggle
  ttsBtn() && ttsBtn().addEventListener('click', () => {
    ttsEnabled = !ttsEnabled;
    const tb = ttsBtn();
    tb.style.background  = ttsEnabled ? 'rgba(74,158,107,0.2)' : '';
    tb.style.borderColor = ttsEnabled ? 'var(--accent)' : '';
    if (!ttsEnabled && window.speechSynthesis) { window.speechSynthesis.cancel(); tb.classList.remove('speaking'); }
  });

  // Voice + News
  voiceBtn() && voiceBtn().addEventListener('click', toggleVoice);
  newsBtn()  && newsBtn().addEventListener('click', toggleNews);

  // V5: Scheduled tasks check every 60s
  setInterval(async () => {
    try {
      const res  = await fetch('/tasks/due');
      const data = await res.json();
      if (data.tasks && data.tasks.length && 'Notification' in window) {
        data.tasks.forEach(t => {
          if (Notification.permission === 'granted') {
            new Notification('🐼 Panda AI Reminder', { body: t.task });
          }
        });
      }
    } catch {}
  }, 60000);

  // Request notification permission
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }
});