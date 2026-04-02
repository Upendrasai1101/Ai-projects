const STORAGE_KEY = 'pandaai_chats';
let chats = {};
let activeChatId = null;
let currentLang = localStorage.getItem('pandaai_lang') || 'en';
let isDark = localStorage.getItem('pandaai_theme') === 'dark';
let ttsEnabled = localStorage.getItem('pandaai_tts') === 'true';
let isListening = false;
let isSpeaking = false;
let isSending = false;

const langPrompts = {
  en:'Respond in English.', te:'Respond in Telugu (తెలుగు).', hi:'Respond in Hindi (हिन्दी).',
  ta:'Respond in Tamil (தமிழ்).', es:'Respond in Spanish.', fr:'Respond in French.',
  de:'Respond in German.', ja:'Respond in Japanese.', zh:'Respond in Chinese.', ar:'Respond in Arabic.'
};
const langCodes = {
  en:'en-US', te:'te-IN', hi:'hi-IN', ta:'ta-IN', es:'es-ES',
  fr:'fr-FR', de:'de-DE', ja:'ja-JP', zh:'zh-CN', ar:'ar-SA'
};

// DOM elements
const chatBox      = document.getElementById('chat-box');
const input        = document.getElementById('user-input');
const sendBtn      = document.getElementById('send-btn');
const chatList     = document.getElementById('chat-list');
const newChatBtn   = document.getElementById('new-chat-btn');
const topbarTitle  = document.getElementById('topbar-title');
const sidebarEl    = document.getElementById('sidebar');
const sidebarToggle= document.getElementById('sidebar-toggle');
const themeToggle  = document.getElementById('theme-toggle');
const langSelect   = document.getElementById('lang-select');
const voiceBtn     = document.getElementById('voice-btn');
const ttsBtn       = document.getElementById('tts-btn');
const newsBtn      = document.getElementById('news-btn');
const statusBar    = document.getElementById('status-bar');
const newsSection  = document.getElementById('news-section');
const newsList     = document.getElementById('news-list');

// ── Theme ──
function applyTheme() {
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  themeToggle.textContent = isDark ? '☀️' : '🌙';
  localStorage.setItem('pandaai_theme', isDark ? 'dark' : 'light');
}
themeToggle.addEventListener('click', () => { isDark = !isDark; applyTheme(); });

// ── TTS ──
function applyTTS() {
  ttsBtn.style.opacity = ttsEnabled ? '1' : '0.4';
  ttsBtn.title = ttsEnabled ? 'Voice Output ON (click to disable)' : 'Voice Output OFF (click to enable)';
  localStorage.setItem('pandaai_tts', ttsEnabled);
}

ttsBtn.addEventListener('click', () => {
  if (isSpeaking) { window.speechSynthesis.cancel(); isSpeaking=false; ttsBtn.classList.remove('speaking'); return; }
  ttsEnabled = !ttsEnabled; applyTTS();
});

function speak(text) {
  if (!ttsEnabled || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const clean = text.replace(/[#*`>]/g,'').replace(/\n/g,' ').trim();
  const utt = new SpeechSynthesisUtterance(clean);
  const targetLang = langCodes[currentLang] || 'en-US';

  // Load voices and find match
  const trySpeak = () => {
    const voices = window.speechSynthesis.getVoices();
    const matchVoice = voices.find(v => v.lang.startsWith(targetLang.split('-')[0]));
    if (currentLang === 'te' && !matchVoice) {
      showStatus('⚠️ Telugu voice not available. Speaking in English.', 'thinking');
      setTimeout(hideStatus, 3000);
      utt.lang = 'en-US';
    } else if (matchVoice) {
      utt.voice = matchVoice;
      utt.lang = matchVoice.lang;
    } else {
      utt.lang = 'en-US';
    }
    utt.rate = 1; utt.pitch = 1;
    utt.onstart = () => { isSpeaking=true; ttsBtn.classList.add('speaking'); };
    utt.onend   = () => { isSpeaking=false; ttsBtn.classList.remove('speaking'); };
    window.speechSynthesis.speak(utt);
  };

  if (window.speechSynthesis.getVoices().length === 0) {
    window.speechSynthesis.addEventListener('voiceschanged', trySpeak, { once: true });
  } else { trySpeak(); }
}

// ── Status bar ──
function showStatus(msg, type='') {
  statusBar.textContent = msg;
  statusBar.className = 'show ' + type + '-status';
}
function hideStatus() { statusBar.className = ''; statusBar.textContent = ''; }

// ── Language ──
langSelect.value = currentLang;
langSelect.addEventListener('change', () => {
  currentLang = langSelect.value;
  localStorage.setItem('pandaai_lang', currentLang);
});

// ── Voice Input ──
let recognition = null;
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    isListening=true; voiceBtn.classList.add('listening');
    voiceBtn.textContent='🔴'; showStatus('🎤 Listening... speak now!','listening');
  };
  recognition.onresult = (e) => {
    const t = e.results[0][0].transcript;
    input.value = t;
    input.style.height='auto';
    input.style.height=Math.min(input.scrollHeight,130)+'px';
  };
  recognition.onend = () => {
    isListening=false; voiceBtn.classList.remove('listening');
    voiceBtn.textContent='🎤'; hideStatus();
    if (input.value.trim()) setTimeout(() => sendMessage(), 500);
  };
  recognition.onerror = () => {
    isListening=false; voiceBtn.classList.remove('listening');
    voiceBtn.textContent='🎤'; hideStatus();
  };

  voiceBtn.addEventListener('click', () => {
    if (isListening) { recognition.stop(); return; }
    recognition.lang = langCodes[currentLang] || 'en-US';
    recognition.start();
  });
} else {
  voiceBtn.style.opacity='0.4'; voiceBtn.title='Voice not supported in this browser';
}

// ── News ──
async function loadNews() {
  newsSection.style.display = 'block';
  newsList.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">⏳ Loading news...</div>';
  try {
    const res = await fetch('/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json; charset=utf-8'},
      body: JSON.stringify({
        message: 'Top 5 latest news headlines from India today',
        lang_instruction: '',
        session_id: 'news_'+Date.now()
      })
    });
    const data = await res.json();
    if (data.reply) {
      const lines = data.reply.split('\n').filter(l => l.trim().length > 5).slice(0,5);
      if (lines.length) {
        newsList.innerHTML = lines.map(l => {
          const safe = l.trim().replace(/"/g,'&quot;').replace(/'/g,'&#39;');
          return `<div class="news-item" data-text="${safe}" onclick="quickSendText(this)">📌 ${l.trim()}</div>`;
        }).join('');
      } else {
        newsList.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">No news found.</div>';
      }
    }
  } catch {
    newsList.innerHTML = '<div style="color:#888;font-size:11px;padding:6px">⚠️ Could not load news.</div>';
  }
}

newsBtn.addEventListener('click', () => {
  if (newsSection.style.display === 'none' || !newsSection.style.display) loadNews();
  else newsSection.style.display = 'none';
});

function quickSendText(el) {
  const text = typeof el === 'string' ? el : el.dataset.text;
  input.value = text;
  if (window.innerWidth <= 700) sidebarEl.classList.remove('open');
  sendMessage();
}

// ── Storage ──
function loadChats() {
  try { chats = JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
  catch { chats = {}; }
}
function saveChats() { localStorage.setItem(STORAGE_KEY, JSON.stringify(chats)); }

function timeAgo(ts) {
  const d = Date.now()-ts;
  if(d<60000) return 'Just now';
  if(d<3600000) return Math.floor(d/60000)+'m ago';
  if(d<86400000) return Math.floor(d/3600000)+'h ago';
  return Math.floor(d/86400000)+'d ago';
}

function renderChatList() {
  const ids = Object.keys(chats).sort((a,b)=>chats[b].time-chats[a].time);
  if (!ids.length) {
    chatList.innerHTML='<div class="no-chats">No chats yet 🐼<br>Start a new chat!</div>';
    return;
  }
  chatList.innerHTML='';
  ids.forEach(id => {
    const c=chats[id];
    const div=document.createElement('div');
    div.className='chat-item'+(id===activeChatId?' active':'');
    div.innerHTML=`
      <span class="chat-item-icon">💬</span>
      <div class="chat-item-text">
        <div class="chat-item-title">${escapeHTML(c.title)}</div>
        <div class="chat-item-time">${timeAgo(c.time)}</div>
      </div>
      <button class="chat-item-del" onclick="deleteChat(event,'${id}')">🗑</button>`;
    div.addEventListener('click',()=>loadChat(id));
    chatList.appendChild(div);
  });
}

function startNewChat() {
  activeChatId='chat_'+Date.now();
  chats[activeChatId]={title:'New Chat',messages:[],time:Date.now()};
  saveChats(); renderChatList(); renderMessages();
  topbarTitle.textContent='New Chat';
  if(window.innerWidth<=700) sidebarEl.classList.remove('open');
}

function loadChat(id) {
  activeChatId=id; renderChatList(); renderMessages();
  topbarTitle.textContent=chats[id].title;
  if(window.innerWidth<=700) sidebarEl.classList.remove('open');
}

function deleteChat(e,id) {
  e.stopPropagation(); delete chats[id]; saveChats();
  if(activeChatId===id) {
    const r=Object.keys(chats);
    if(r.length) loadChat(r[0]); else startNewChat();
  } else renderChatList();
}

function renderMessages() {
  chatBox.innerHTML='';
  const c=chats[activeChatId];
  if(!c||!c.messages.length) {
    chatBox.innerHTML=`
      <div id="welcome">
        <div class="welcome-icon">🐼</div>
        <h2>Panda AI</h2>
        <p>Calm, wise and always helpful — just like a panda! 🎋</p>
        <div class="web-badge">🌐 Real-time Web Search Enabled</div>
        <div class="chips">
          <div class="chip" onclick="quickSend(this)">Today's news 📰</div>
          <div class="chip" onclick="quickSend(this)">Write Python code 🐍</div>
          <div class="chip" onclick="quickSend(this)">IPL 2026 results 🏏</div>
          <div class="chip" onclick="quickSend(this)">Tell me a fun fact 🎯</div>
        </div>
      </div>`;
    return;
  }
  c.messages.forEach(m=>appendBubble(m.role,m.text,false,m.searched));
  chatBox.scrollTop=chatBox.scrollHeight;
}

function appendBubble(role, text, isTyping=false, searched=false) {
  const row=document.createElement('div');
  row.className=`msg-row ${role}`;
  const av=document.createElement('div');
  av.className=`avatar ${role==='user'?'user-av':'panda'}`;
  av.textContent=role==='user'?'👤':'🐼';
  const mc=document.createElement('div');
  mc.className='msg-content';

  if(searched&&role==='ai') {
    const b=document.createElement('div');
    b.className='search-badge';
    b.innerHTML='🌐 Web searched';
    mc.appendChild(b);
  }

  const bubble=document.createElement('div');
  bubble.className=`bubble ${role==='user'?'user':'ai'}`;

  if(isTyping) {
    bubble.innerHTML='<div class="typing-dots"><span></span><span></span><span></span></div>';
    row.id='typing-row';
  } else {
    bubble.innerHTML=formatMessage(text);
    // Code copy buttons
    bubble.querySelectorAll('pre').forEach(pre => {
      const wrapper=document.createElement('div');
      wrapper.className='code-wrapper';
      pre.parentNode.insertBefore(wrapper,pre);
      wrapper.appendChild(pre);
      const btn=document.createElement('button');
      btn.className='copy-btn'; btn.textContent='📋 Copy';
      btn.addEventListener('click',()=>{
        const txt=pre.textContent;
        if(navigator.clipboard&&navigator.clipboard.writeText) {
          navigator.clipboard.writeText(txt).then(()=>setCopied(btn)).catch(()=>fallbackCopy(txt,btn));
        } else fallbackCopy(txt,btn);
      });
      wrapper.appendChild(btn);
    });

    if(role==='ai') {
      const actions=document.createElement('div');
      actions.className='msg-actions';
      const ttsMsg=document.createElement('button');
      ttsMsg.className='tts-msg-btn'; ttsMsg.textContent='🔊 Listen';
      ttsMsg.addEventListener('click',()=>speak(text));
      actions.appendChild(ttsMsg);
      const emojis=document.createElement('div');
      emojis.className='emoji-reactions';
      ['👍','❤️','😊','🔥','👏'].forEach(e=>{
        const btn=document.createElement('button');
        btn.className='emoji-btn'; btn.textContent=e;
        btn.addEventListener('click',()=>btn.classList.toggle('reacted'));
        emojis.appendChild(btn);
      });
      mc.appendChild(bubble); mc.appendChild(actions); mc.appendChild(emojis);
      row.appendChild(av); row.appendChild(mc);
      chatBox.appendChild(row); chatBox.scrollTop=chatBox.scrollHeight;
      return;
    }
  }
  mc.appendChild(bubble);
  row.appendChild(av); row.appendChild(mc);
  chatBox.appendChild(row); chatBox.scrollTop=chatBox.scrollHeight;
}

function setCopied(btn) {
  btn.textContent='✅ Copied!'; btn.classList.add('copied');
  setTimeout(()=>{ btn.textContent='📋 Copy'; btn.classList.remove('copied'); },2000);
}

function fallbackCopy(text,btn) {
  const ta=document.createElement('textarea');
  ta.value=text; ta.style.position='fixed'; ta.style.opacity='0';
  document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy'); setCopied(btn); }
  catch { btn.textContent='❌ Failed'; setTimeout(()=>{ btn.textContent='📋 Copy'; },2000); }
  document.body.removeChild(ta);
}

function escapeHTML(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function formatMessage(text) {
  text=text.replace(/```(\w*)\n?([\s\S]*?)```/g,(_,l,c)=>`<pre><code>${escapeHTML(c.trim())}</code></pre>`);
  text=text.replace(/`([^`]+)`/g,'<code>$1</code>');
  text=text.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>');
  text=text.replace(/\*(.*?)\*/g,'<em>$1</em>');
  text=text.replace(/\n/g,'<br>');
  return text;
}

function quickSend(el) {
  input.value=el.textContent.replace(/[📰🐍🏏🎯]/g,'').trim();
  sendMessage();
}

async function sendMessage() {
  const msg=input.value.trim();
  if(!msg||isSending) return;

  isSending=true;
  document.getElementById('welcome')?.remove();

  const langInstruction=langPrompts[currentLang]||'';

  chats[activeChatId].messages.push({role:'user',text:msg});
  if(chats[activeChatId].title==='New Chat') {
    chats[activeChatId].title=msg.slice(0,40)+(msg.length>40?'…':'');
    topbarTitle.textContent=chats[activeChatId].title;
  }
  chats[activeChatId].time=Date.now();
  saveChats(); renderChatList();

  input.value=''; input.style.height='auto';
  sendBtn.disabled=true;
  sendBtn.textContent='⏳';

  appendBubble('user',msg);
  appendBubble('ai','',true);
  showStatus('🤔 Thinking...','thinking');

  try {
    const res=await fetch('/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json; charset=utf-8'},
      body:JSON.stringify({
        message: msg,
        lang_instruction: langInstruction,
        session_id: activeChatId
      })
    });

    if(!res.ok) throw new Error(`Server error: ${res.status}`);

    const data=await res.json();
    document.getElementById('typing-row')?.remove();
    hideStatus();

    const reply=data.error?'⚠️ Error: '+data.error:data.reply;
    chats[activeChatId].messages.push({role:'ai',text:reply,searched:data.searched||false});
    saveChats();
    appendBubble('ai',reply,false,data.searched||false);
    if(ttsEnabled) speak(reply);

  } catch(err) {
    document.getElementById('typing-row')?.remove();
    hideStatus();
    appendBubble('ai','⚠️ Could not reach server. Please wait a few seconds and try again!');
  }

  sendBtn.disabled=false;
  sendBtn.textContent='➤';
  isSending=false;
  input.focus();
}

// Events
input.addEventListener('input',()=>{
  input.style.height='auto';
  input.style.height=Math.min(input.scrollHeight,130)+'px';
});
input.addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}
});
sendBtn.addEventListener('click',sendMessage);
newChatBtn.addEventListener('click',startNewChat);
sidebarToggle.addEventListener('click',()=>sidebarEl.classList.toggle('open'));

// Init
applyTheme(); applyTTS();
langSelect.value=currentLang;
loadChats();
const ids=Object.keys(chats).sort((a,b)=>chats[b].time-chats[a].time);
if(ids.length)loadChat(ids[0]);else startNewChat();