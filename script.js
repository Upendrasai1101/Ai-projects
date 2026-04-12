/* ================================================================
   script.js — Panda AI V4.4 (Hugging Face Edition)
   Fixes: Enter key (desktop+mobile), auto-scroll, button sync
   ================================================================ */

'use strict';

// ── State ──
let sessionId       = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2,7);
let isLoading       = false;
let ttsEnabled      = false;
let isListening     = false;
let recognition     = null;
let chatSessions    = [];
let currentSession  = null;
let currentMessages = [];

// ── DOM ──
const chatBox       = () => document.getElementById('chat-box');
const userInput     = () => document.getElementById('user-input');
const sendBtn       = () => document.getElementById('send-btn');
const themeToggle   = () => document.getElementById('theme-toggle');
const langSelect    = () => document.getElementById('lang-select');
const voiceBtn      = () => document.getElementById('voice-btn');
const ttsBtn        = () => document.getElementById('tts-btn');
const newsBtn       = () => document.getElementById('news-btn');
const statusBar     = () => document.getElementById('status-bar');
const chatList      = () => document.getElementById('chat-list');
const newChatBtn    = () => document.getElementById('new-chat-btn');
const topbarTitle   = () => document.getElementById('topbar-title');
const sidebarEl     = () => document.getElementById('sidebar');
const sidebarToggle = () => document.getElementById('sidebar-toggle');
const newsList      = () => document.getElementById('news-list');
const newsSection   = () => document.getElementById('news-section');

// ── Theme init ──
(function initTheme() {
  const saved = localStorage.getItem('pandaTheme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  const btn = themeToggle();
  if (btn) btn.textContent = saved === 'dark' ? '☀️' : '🌙';
})();

// ── Sessions from localStorage ──
(function initSessions() {
  try {
    chatSessions = JSON.parse(localStorage.getItem('pandaSessions') || '[]');
  } catch { chatSessions = []; }
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
  if (box) {
    box.scrollTop = box.scrollHeight;
    // double-rAF for reliability after DOM paint
    requestAnimationFrame(() => {
      requestAnimationFrame(() => { box.scrollTop = box.scrollHeight; });
    });
  }
}

// ── Status bar ──
function setStatus(msg, cls) {
  const bar = statusBar();
  if (!bar) return;
  bar.textContent = msg || '';
  bar.className   = msg ? ('show ' + (cls || '')) : '';
}

// ── Minimal markdown renderer ──
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
  // Wrap consecutive <li> in <ul>
  t = t.replace(/(<li>[\s\S]*?<\/li>)+/g, m => '<ul>' + m + '</ul>');
  // Paragraphs
  t = t.replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>');
  return '<p>' + t + '</p>';
}

// ── Append message ──
function appendMessage(role, content, searched) {
  // Hide welcome screen on first message
  const welcome = document.getElementById('welcome');
  if (welcome) welcome.remove();

  const box  = chatBox();
  if (!box) return null;

  const wrap   = document.createElement('div');
  wrap.className = `message ${role}`;

  if (role === 'ai' && searched) {
    const badge = document.createElement('div');
    badge.className   = 'search-badge';
    badge.innerHTML   = '🌐 Live Search';
    wrap.appendChild(badge);
  }

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if (role === 'ai') {
    bubble.innerHTML = renderMd(content);
  } else {
    bubble.textContent = content;
  }
  wrap.appendChild(bubble);

  // Copy button for AI
  if (role === 'ai') {
    const copy = document.createElement('button');
    copy.className   = 'copy-btn';
    copy.textContent = '📋';
    copy.title       = 'Copy response';
    copy.onclick     = () => {
      navigator.clipboard.writeText(content).then(() => {
        copy.textContent = '✅';
        setTimeout(() => { copy.textContent = '📋'; }, 1500);
      }).catch(() => {});
    };
    wrap.appendChild(copy);
  }

  box.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

// ── Loading dots ──
function showLoading() {
  const box = chatBox();
  if (!box) return;
  const wrap   = document.createElement('div');
  wrap.id        = 'loading-msg';
  wrap.className = 'message ai';
  const bub    = document.createElement('div');
  bub.className  = 'bubble loading';
  bub.innerHTML  = '<span></span><span></span><span></span>';
  wrap.appendChild(bub);
  box.appendChild(wrap);
  scrollToBottom();
}
function hideLoading() {
  const el = document.getElementById('loading-msg');
  if (el) el.remove();
}

// ════════════════════════════════════════
//  CORE: sendMessage()
// ════════════════════════════════════════
async function sendMessage(overrideText) {
  const inp = userInput();
  const msg = (overrideText !== undefined ? overrideText : (inp ? inp.value : '')).trim();

  if (!msg || isLoading) return;

  // Lock UI
  isLoading = true;
  const btn = sendBtn();
  if (btn) btn.disabled = true;
  if (inp) { inp.value = ''; inp.style.height = 'auto'; }

  // Session
  if (!currentSession) startSession();
  currentMessages.push({ role: 'user', content: msg });
  persistSessions();

  appendMessage('user', msg);
  showLoading();
  setStatus('🐼 Panda AI is thinking...', 'thinking-status');

  const ls = langSelect();
  const langCode  = ls ? ls.value : 'en';
  const langInstr = LANG_MAP[langCode] || '';

  try {
    const resp = await fetch('/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        message:          msg,
        session_id:       sessionId,
        lang_instruction: langInstr,
      }),
    });

    const data = await resp.json();
    hideLoading();

    if (data.error) {
      appendMessage('ai', '⚠️ ' + data.error, false);
    } else {
      const reply    = data.reply    || '';
      const searched = data.searched || false;

      currentMessages.push({ role: 'ai', content: reply });

      // Update session title on first exchange
      if (currentSession && currentMessages.filter(m => m.role === 'user').length === 1) {
        currentSession.title = msg.slice(0, 42);
        const tt = topbarTitle();
        if (tt) tt.textContent = currentSession.title;
        renderChatList();
      }
      persistSessions();

      appendMessage('ai', reply, searched);

      if (ttsEnabled && reply) speakText(reply);
    }

  } catch (err) {
    hideLoading();
    appendMessage('ai', '⚠️ Network error. Check your connection and try again.', false);
    console.error('sendMessage error:', err);
  }

  setStatus('');
  isLoading = false;
  if (btn) btn.disabled = false;
  if (inp) inp.focus();
}

// ── quickSend (chips) ──
function quickSend(el) {
  // Strip emoji and trim
  const text = el.textContent.replace(/[\u{1F300}-\u{1FAFF}]/gu, '').trim();
  sendMessage(text || el.textContent.trim());
}

// ════════════════════════════════════════
//  EVENT LISTENERS (attached after DOM ready)
// ════════════════════════════════════════
document.addEventListener('DOMContentLoaded', function () {

  // ── Send button ──
  const sb = sendBtn();
  if (sb) sb.addEventListener('click', () => sendMessage());

  // ── Enter key fix (desktop + mobile) ──
  const inp = userInput();
  if (inp) {
    // Auto-resize
    inp.addEventListener('input', function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 130) + 'px';
    });

    // keydown fires before keypress — more reliable on mobile
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();   // stop newline
        e.stopPropagation();
        sendMessage();
        return false;
      }
    });

    // Fallback: keypress (older Android WebViews)
    inp.addEventListener('keypress', function (e) {
      if ((e.key === 'Enter' || e.keyCode === 13) && !e.shiftKey) {
        e.preventDefault();
        e.stopPropagation();
        sendMessage();
        return false;
      }
    });

    inp.focus();
  }

  // ── Theme toggle ──
  const tt = themeToggle();
  if (tt) {
    tt.addEventListener('click', () => {
      const cur  = document.documentElement.getAttribute('data-theme');
      const next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('pandaTheme', next);
      tt.textContent = next === 'dark' ? '☀️' : '🌙';
    });
  }

  // ── Sidebar toggle (mobile) ──
  const st = sidebarToggle();
  const sd = sidebarEl();
  if (st && sd) {
    st.addEventListener('click', () => sd.classList.toggle('open'));
    document.addEventListener('click', (e) => {
      if (sd.classList.contains('open') && !sd.contains(e.target) && e.target !== st) {
        sd.classList.remove('open');
      }
    });
  }

  // ── New chat button ──
  const nc = newChatBtn();
  if (nc) nc.addEventListener('click', newChat);

  // ── TTS button ──
  const tb = ttsBtn();
  if (tb) {
    tb.addEventListener('click', () => {
      ttsEnabled = !ttsEnabled;
      tb.style.background  = ttsEnabled ? 'rgba(74,158,107,0.2)' : '';
      tb.style.borderColor = ttsEnabled ? 'var(--accent)' : '';
      if (!ttsEnabled && window.speechSynthesis) {
        window.speechSynthesis.cancel();
        tb.classList.remove('speaking');
      }
    });
  }

  // ── Voice button ──
  const vb = voiceBtn();
  if (vb) vb.addEventListener('click', toggleVoice);

  // ── News button ──
  const nb = newsBtn();
  if (nb) nb.addEventListener('click', toggleNews);

});

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
    alert('Voice input is not supported in this browser. Try Chrome on desktop.');
    return;
  }
  const vb = voiceBtn();
  if (isListening) {
    if (recognition) recognition.stop();
    isListening = false;
    if (vb) vb.classList.remove('listening');
    setStatus('');
    return;
  }
  const SR  = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  const ls  = langSelect();
  const lc  = ls ? ls.value : 'en';
  recognition.lang           = lc === 'te' ? 'te-IN' : lc === 'hi' ? 'hi-IN' : 'en-US';
  recognition.interimResults = true;
  recognition.continuous     = false;

  recognition.onstart = () => {
    isListening = true;
    if (vb) vb.classList.add('listening');
    setStatus('🎤 Listening...', 'listening-status');
  };
  recognition.onresult = (e) => {
    const transcript = Array.from(e.results).map(r => r[0].transcript).join('');
    const inp = userInput();
    if (inp) inp.value = transcript;
  };
  recognition.onend = () => {
    isListening = false;
    if (vb) vb.classList.remove('listening');
    setStatus('');
    const inp = userInput();
    if (inp && inp.value.trim()) sendMessage();
  };
  recognition.onerror = (e) => {
    console.error('Speech error:', e.error);
    isListening = false;
    if (vb) vb.classList.remove('listening');
    setStatus('');
  };
  recognition.start();
}

// ── News panel ──
async function toggleNews() {
  const ns = newsSection();
  const nl = newsList();
  if (!ns || !nl) return;
  const visible = ns.style.display !== 'none' && ns.style.display !== '';
  ns.style.display = visible ? 'none' : 'block';
  if (!visible) {
    nl.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">Loading news...</div>';
    try {
      const res  = await fetch('/news');
      const data = await res.json();
      if (data.news && data.news.length) {
        nl.innerHTML = data.news.map(h =>
          `<div class="news-item" onclick="sendMessage(${JSON.stringify('Tell me about: ' + h)})">📰 ${h}</div>`
        ).join('');
      } else {
        nl.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">No news available right now.</div>';
      }
    } catch {
      nl.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">Failed to load news.</div>';
    }
  }
}

// ── Session management ──
function startSession() {
  sessionId       = 'sess_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7);
  currentMessages = [];
  currentSession  = { id: sessionId, title: 'New Chat', messages: currentMessages, ts: Date.now() };
  chatSessions.unshift(currentSession);
  persistSessions();
  renderChatList();
  const tt = topbarTitle();
  if (tt) tt.textContent = 'New Chat';
}

function persistSessions() {
  if (currentSession) {
    currentSession.messages = [...currentMessages];
    currentSession.ts       = Date.now();
  }
  try {
    localStorage.setItem('pandaSessions', JSON.stringify(chatSessions.slice(0, 30)));
  } catch { /* storage full */ }
}

function loadSession(id) {
  const s = chatSessions.find(s => s.id === id);
  if (!s) return;
  currentSession  = s;
  sessionId       = s.id;
  currentMessages = s.messages ? [...s.messages] : [];

  const box = chatBox();
  if (box) {
    box.innerHTML = '';
    currentMessages.forEach(m => appendMessage(m.role, m.content));
  }
  const tt = topbarTitle();
  if (tt) tt.textContent = s.title || 'Chat';
  renderChatList();
  const sd = sidebarEl();
  if (sd) sd.classList.remove('open');
}

function deleteSession(id) {
  chatSessions = chatSessions.filter(s => s.id !== id);
  persistSessions();
  if (currentSession && currentSession.id === id) {
    currentSession  = null;
    currentMessages = [];
    const box = chatBox();
    if (box) box.innerHTML = buildWelcomeHTML();
  }
  renderChatList();
}

function renderChatList() {
  const cl = chatList();
  if (!cl) return;
  if (!chatSessions.length) {
    cl.innerHTML = '<div class="no-chats">No chats yet 🐼<br>Start a new chat!</div>';
    return;
  }
  cl.innerHTML = chatSessions.map(s => `
    <div class="chat-item ${currentSession && currentSession.id === s.id ? 'active' : ''}"
         onclick="loadSession('${s.id}')">
      <span class="chat-item-icon">💬</span>
      <div class="chat-item-text">
        <div class="chat-item-title">${escHtml(s.title || 'New Chat')}</div>
        <div class="chat-item-time">${new Date(s.ts).toLocaleDateString()}</div>
      </div>
      <button class="chat-item-del" onclick="event.stopPropagation();deleteSession('${s.id}')">🗑</button>
    </div>`
  ).join('');
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function buildWelcomeHTML() {
  return `<div id="welcome" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:18px;text-align:center">
    <div class="welcome-icon">🐼</div>
    <h2 style="font-family:'Comfortaa',cursive;font-size:42px;color:var(--black)">Panda AI</h2>
    <p style="color:var(--muted);font-size:15px;max-width:380px;line-height:1.6">Calm, wise and always helpful — just like a panda! 🎋</p>
    <div class="web-badge">🌐 Real-time Web Search Enabled</div>
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
  const inp = userInput();
  if (inp) inp.focus();
  const sd = sidebarEl();
  if (sd) sd.classList.remove('open');
}