/* ============================================================
   script.js — Panda AI V4.4
   Synced with: index.html IDs + app.py /chat /news /reset
   ============================================================ */

// ── State ──
let sessionId       = 'session_' + Date.now();
let isLoading       = false;
let ttsEnabled      = false;
let isListening     = false;
let currentSpeech   = null;
let recognition     = null;
let chatSessions    = JSON.parse(localStorage.getItem('pandaChatSessions') || '[]');
let currentSession  = null;
let currentMessages = [];

// ── DOM refs ──
const chatBox       = document.getElementById('chat-box');
const userInput     = document.getElementById('user-input');
const sendBtn       = document.getElementById('send-btn');
const themeToggle   = document.getElementById('theme-toggle');
const langSelect    = document.getElementById('lang-select');
const voiceBtn      = document.getElementById('voice-btn');
const ttsBtn        = document.getElementById('tts-btn');
const newsBtn       = document.getElementById('news-btn');
const statusBar     = document.getElementById('status-bar');
const chatList      = document.getElementById('chat-list');
const newChatBtn    = document.getElementById('new-chat-btn');
const topbarTitle   = document.getElementById('topbar-title');
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebar       = document.getElementById('sidebar');
const newsList      = document.getElementById('news-list');
const newsSection   = document.getElementById('news-section');

// ── Theme ──
const savedTheme = localStorage.getItem('pandaTheme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);
if (themeToggle) themeToggle.textContent = savedTheme === 'dark' ? '☀️' : '🌙';

themeToggle && themeToggle.addEventListener('click', () => {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const next   = isDark ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('pandaTheme', next);
  themeToggle.textContent = next === 'dark' ? '☀️' : '🌙';
});

// ── Sidebar toggle (mobile) ──
sidebarToggle && sidebarToggle.addEventListener('click', () => {
  sidebar.classList.toggle('open');
});
document.addEventListener('click', (e) => {
  if (sidebar.classList.contains('open') &&
      !sidebar.contains(e.target) &&
      e.target !== sidebarToggle) {
    sidebar.classList.remove('open');
  }
});

// ── Auto-resize textarea ──
userInput && userInput.addEventListener('input', () => {
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 130) + 'px';
});

// ── Send on Enter (Shift+Enter = newline) ──
userInput && userInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// ── Send button ──
sendBtn && sendBtn.addEventListener('click', sendMessage);

// ── Language map ──
const langMap = {
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

// ── Markdown renderer (lightweight) ──
function renderMarkdown(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    // code blocks
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // headings
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // bullet lists
    .replace(/^[\*\-] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    // numbered lists
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // line breaks
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

// ── Append message bubble ──
function appendMessage(role, content, searched = false) {
  const welcome = document.getElementById('welcome');
  if (welcome) welcome.remove();

  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (role === 'ai') {
    if (searched) {
      const badge = document.createElement('div');
      badge.className = 'search-badge';
      badge.innerHTML = '🌐 Live Search';
      wrap.appendChild(badge);
    }
    bubble.innerHTML = '<p>' + renderMarkdown(content) + '</p>';
  } else {
    bubble.textContent = content;
  }

  // Copy button for AI messages
  if (role === 'ai') {
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    copyBtn.textContent = '📋';
    copyBtn.title = 'Copy';
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(content).then(() => {
        copyBtn.textContent = '✅';
        setTimeout(() => copyBtn.textContent = '📋', 1500);
      });
    };
    wrap.appendChild(copyBtn);
  }

  wrap.appendChild(bubble);
  chatBox.appendChild(wrap);
  chatBox.scrollTop = chatBox.scrollHeight;
  return wrap;
}

// ── Loading bubble ──
function showLoading() {
  const wrap = document.createElement('div');
  wrap.className = 'message ai';
  wrap.id = 'loading-bubble';
  const bubble = document.createElement('div');
  bubble.className = 'bubble loading';
  bubble.innerHTML = '<span></span><span></span><span></span>';
  wrap.appendChild(bubble);
  chatBox.appendChild(wrap);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function hideLoading() {
  const el = document.getElementById('loading-bubble');
  if (el) el.remove();
}

// ── Status bar ──
function setStatus(msg, cls = '') {
  if (!statusBar) return;
  statusBar.textContent = msg;
  statusBar.className   = msg ? `show ${cls}` : '';
}

// ── Emoji reactions ──
const REACTIONS = ['❤️','👍','😮','😂','🔥','💯'];
function addReactions(wrap) {
  const bar = document.createElement('div');
  bar.className = 'reactions';
  REACTIONS.forEach(e => {
    const btn = document.createElement('button');
    btn.className = 'reaction-btn';
    btn.textContent = e;
    btn.onclick = () => {
      btn.classList.toggle('active');
    };
    bar.appendChild(btn);
  });
  wrap.appendChild(bar);
}

// ── MAIN: sendMessage ──
async function sendMessage(text) {
  const msg = (text || userInput.value).trim();
  if (!msg || isLoading) return;

  isLoading       = true;
  sendBtn.disabled = true;
  userInput.value  = '';
  userInput.style.height = 'auto';

  // Save to current session
  if (!currentSession) startNewSession();
  currentMessages.push({ role: 'user', content: msg });
  saveSession();

  appendMessage('user', msg);
  showLoading();
  setStatus('🐼 Panda AI is thinking...', 'thinking-status');

  const langInstruction = langMap[langSelect ? langSelect.value : 'en'] || '';

  try {
    const res = await fetch('/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        message:          msg,
        session_id:       sessionId,
        lang_instruction: langInstruction,
      }),
    });

    const data = await res.json();
    hideLoading();

    if (data.error) {
      const errWrap = appendMessage('ai', '⚠️ ' + data.error);
      addReactions(errWrap);
    } else {
      const reply   = data.reply || '';
      const searched = data.searched || false;

      currentMessages.push({ role: 'ai', content: reply });
      saveSession();

      const aiWrap = appendMessage('ai', reply, searched);
      addReactions(aiWrap);

      // Update sidebar title with first user message
      if (currentMessages.filter(m => m.role === 'user').length === 1) {
        currentSession.title = msg.slice(0, 40);
        updateChatList();
        if (topbarTitle) topbarTitle.textContent = currentSession.title;
      }

      // TTS
      if (ttsEnabled && reply) speakText(reply);
    }

  } catch (err) {
    hideLoading();
    appendMessage('ai', '⚠️ Network error. Please check your connection.');
    console.error('Chat error:', err);
  }

  setStatus('');
  isLoading        = false;
  sendBtn.disabled  = false;
  userInput.focus();
}

// ── Quick chips ──
function quickSend(element) {
  const text = element.textContent.replace(/[^\w\s'.,?!]/g, '').trim();
  sendMessage(text);
}

// ── TTS ──
function speakText(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const plain  = text.replace(/[#*`_\[\]()>]/g, '').slice(0, 500);
  const utt    = new SpeechSynthesisUtterance(plain);
  utt.lang     = langSelect ? (langSelect.value === 'te' ? 'te-IN' : langSelect.value === 'hi' ? 'hi-IN' : 'en-US') : 'en-US';
  utt.rate     = 0.95;
  utt.onstart  = () => ttsBtn && ttsBtn.classList.add('speaking');
  utt.onend    = () => ttsBtn && ttsBtn.classList.remove('speaking');
  currentSpeech = utt;
  window.speechSynthesis.speak(utt);
}

ttsBtn && ttsBtn.addEventListener('click', () => {
  ttsEnabled = !ttsEnabled;
  ttsBtn.style.background = ttsEnabled ? 'rgba(74,158,107,0.2)' : '';
  ttsBtn.style.borderColor = ttsEnabled ? 'var(--accent)' : '';
  if (!ttsEnabled && window.speechSynthesis) {
    window.speechSynthesis.cancel();
    ttsBtn.classList.remove('speaking');
  }
});

// ── Voice Input ──
voiceBtn && voiceBtn.addEventListener('click', () => {
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    alert('Voice input not supported in this browser.');
    return;
  }
  if (isListening) {
    recognition && recognition.stop();
    return;
  }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.lang        = langSelect && langSelect.value === 'te' ? 'te-IN' : langSelect && langSelect.value === 'hi' ? 'hi-IN' : 'en-US';
  recognition.interimResults = true;

  recognition.onstart = () => {
    isListening = true;
    voiceBtn.classList.add('listening');
    setStatus('🎤 Listening...', 'listening-status');
  };
  recognition.onresult = (e) => {
    const transcript = Array.from(e.results).map(r => r[0].transcript).join('');
    userInput.value  = transcript;
  };
  recognition.onend = () => {
    isListening = false;
    voiceBtn.classList.remove('listening');
    setStatus('');
    if (userInput.value.trim()) sendMessage();
  };
  recognition.onerror = () => {
    isListening = false;
    voiceBtn.classList.remove('listening');
    setStatus('');
  };
  recognition.start();
});

// ── News ──
newsBtn && newsBtn.addEventListener('click', async () => {
  if (!newsSection || !newsList) return;
  const visible = newsSection.style.display !== 'none';
  newsSection.style.display = visible ? 'none' : 'block';
  if (!visible) {
    newsList.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">Loading...</div>';
    try {
      const res  = await fetch('/news');
      const data = await res.json();
      if (data.news && data.news.length) {
        newsList.innerHTML = data.news.map(h =>
          `<div class="news-item" onclick="sendMessage('Tell me about: ${h.replace(/'/g,"\\'")}')">📰 ${h}</div>`
        ).join('');
      } else {
        newsList.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">No news available</div>';
      }
    } catch {
      newsList.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">Failed to load news</div>';
    }
  }
});

// ── Session management ──
function startNewSession() {
  sessionId       = 'session_' + Date.now();
  currentMessages = [];
  currentSession  = {
    id:       sessionId,
    title:    'New Chat',
    messages: currentMessages,
    ts:       Date.now(),
  };
  chatSessions.unshift(currentSession);
  saveSession();
  updateChatList();
  if (topbarTitle) topbarTitle.textContent = 'New Chat';
}

function saveSession() {
  if (currentSession) {
    currentSession.messages = currentMessages;
    currentSession.ts       = Date.now();
  }
  localStorage.setItem('pandaChatSessions', JSON.stringify(chatSessions.slice(0, 30)));
}

function loadSession(id) {
  const s = chatSessions.find(s => s.id === id);
  if (!s) return;
  currentSession  = s;
  sessionId       = s.id;
  currentMessages = s.messages || [];

  // Re-render chat
  chatBox.innerHTML = '';
  currentMessages.forEach(m => appendMessage(m.role, m.content));
  if (topbarTitle) topbarTitle.textContent = s.title || 'Chat';
  updateChatList();
  sidebar.classList.remove('open');
}

function deleteSession(id) {
  chatSessions = chatSessions.filter(s => s.id !== id);
  localStorage.setItem('pandaChatSessions', JSON.stringify(chatSessions));
  if (currentSession && currentSession.id === id) {
    chatBox.innerHTML = '<div id="welcome" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:18px;text-align:center"><div class="welcome-icon">🐼</div><h2>Panda AI</h2><p>Start a new chat!</p></div>';
    currentSession  = null;
    currentMessages = [];
  }
  updateChatList();
}

function updateChatList() {
  if (!chatList) return;
  if (!chatSessions.length) {
    chatList.innerHTML = '<div class="no-chats">No chats yet 🐼<br>Start a new chat!</div>';
    return;
  }
  chatList.innerHTML = chatSessions.map(s => `
    <div class="chat-item ${currentSession && currentSession.id === s.id ? 'active' : ''}"
         onclick="loadSession('${s.id}')">
      <span class="chat-item-icon">💬</span>
      <div class="chat-item-text">
        <div class="chat-item-title">${s.title || 'New Chat'}</div>
        <div class="chat-item-time">${new Date(s.ts).toLocaleDateString()}</div>
      </div>
      <button class="chat-item-del" onclick="event.stopPropagation();deleteSession('${s.id}')">🗑</button>
    </div>
  `).join('');
}

// ── New chat button ──
newChatBtn && newChatBtn.addEventListener('click', () => {
  chatBox.innerHTML = '';
  const welcome = document.createElement('div');
  welcome.id = 'welcome';
  welcome.style.cssText = 'display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:18px;text-align:center';
  welcome.innerHTML = `
    <div class="welcome-icon">🐼</div>
    <h2 style="font-family:'Comfortaa',cursive;font-size:42px">Panda AI</h2>
    <p style="color:var(--muted);font-size:15px">Calm, wise and always helpful — just like a panda! 🎋</p>
    <div class="web-badge">🌐 Real-time Web Search Enabled</div>
    <div class="chips">
      <div class="chip" onclick="quickSend(this)">Today's news 📰</div>
      <div class="chip" onclick="quickSend(this)">Write Python code 🐍</div>
      <div class="chip" onclick="quickSend(this)">IPL 2026 results 🏏</div>
      <div class="chip" onclick="quickSend(this)">Tell me a fun fact 🎯</div>
    </div>`;
  chatBox.appendChild(welcome);

  startNewSession();
  userInput && userInput.focus();
  sidebar.classList.remove('open');
});

// ── Init ──
updateChatList();
userInput && userInput.focus();