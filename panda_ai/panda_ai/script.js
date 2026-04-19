'use strict';

// ── State ──
let sessionId='sess_'+Date.now(); let isLoading=false; let ttsEnabled=false;
let isListening=false; let recognition=null; let chatSessions=[];
let currentSession=null; let currentMessages=[]; let pendingFiles=[];

const $=id=>document.getElementById(id);
const chatBox=()=>$('chat-box'); const userInput=()=>$('user-input');
const sendBtn=()=>$('send-btn'); const themeToggle=()=>$('theme-toggle');
const langSelect=()=>$('lang-select'); const voiceBtn=()=>$('voice-btn');
const ttsBtn=()=>$('tts-btn'); const newsBtn=()=>$('news-btn');
const statusBar=()=>$('status-bar'); const chatList=()=>$('chat-list');
const newChatBtn=()=>$('new-chat-btn'); const topbarTitle=()=>$('topbar-title');
const sidebarEl=()=>$('sidebar'); const sidebarToggle=()=>$('sidebar-toggle');
const newsList=()=>$('news-list'); const newsSection=()=>$('news-section');
const uploadBtn=()=>$('upload-btn'); const fileInput=()=>$('file-input');
const filePreview=()=>$('file-preview');

// ── Init ──
(function(){const s=localStorage.getItem('pandaTheme')||'light';document.documentElement.setAttribute('data-theme',s);const b=themeToggle();if(b)b.textContent=s==='dark'?'☀️':'🌙';})();
(function(){try{chatSessions=JSON.parse(localStorage.getItem('pandaSessions')||'[]');}catch{chatSessions=[];}renderChatList();})();

const LANG_MAP={en:'Respond in English.',te:'Respond fully in Telugu (తెలుగు లో జవాబు ఇవ్వండి).',hi:'Respond fully in Hindi (हिंदी में उत्तर दें).',ta:'Respond fully in Tamil.',es:'Respond fully in Spanish.',fr:'Respond fully in French.',de:'Respond fully in German.',ja:'Respond fully in Japanese.',zh:'Respond fully in Chinese.',ar:'Respond fully in Arabic.'};

function scrollToBottom(){const b=chatBox();if(!b)return;requestAnimationFrame(()=>requestAnimationFrame(()=>{b.scrollTop=b.scrollHeight;}));}
function setStatus(msg,cls){const bar=statusBar();if(!bar)return;bar.textContent=msg||'';bar.className=msg?('show '+(cls||'')):'';  }
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

function renderMd(text){
  let t=text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/```(\w*)\n?([\s\S]*?)```/g,'<pre><code>$2</code></pre>')
    .replace(/`([^`\n]+)`/g,'<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>').replace(/^## (.+)$/gm,'<h2>$1</h2>').replace(/^# (.+)$/gm,'<h1>$1</h1>')
    .replace(/^[\*\-] (.+)$/gm,'<li>$1</li>').replace(/^\d+\.\s(.+)$/gm,'<li>$1</li>');
  t=t.replace(/(<li>[\s\S]*?<\/li>)+/g,m=>'<ul>'+m+'</ul>');
  t=t.replace(/\n{2,}/g,'</p><p>').replace(/\n/g,'<br>');
  return '<p>'+t+'</p>';
}

function addMsgActions(wrap,text){
  const a=document.createElement('div');a.className='msg-actions';
  const lb=document.createElement('button');lb.className='tts-msg-btn';lb.innerHTML='🔊 Listen';
  lb.onclick=()=>{
    if(window.speechSynthesis.speaking){window.speechSynthesis.cancel();lb.innerHTML='🔊 Listen';lb.classList.remove('speaking');return;}
    const plain=text.replace(/[#*`_\[\]()>~<]/g,'').slice(0,600);
    const utt=new SpeechSynthesisUtterance(plain);
    const lc=langSelect()?langSelect().value:'en';
    utt.lang=lc==='te'?'te-IN':lc==='hi'?'hi-IN':lc==='ta'?'ta-IN':'en-US';utt.rate=0.95;
    utt.onstart=()=>{lb.innerHTML='⏹ Stop';lb.classList.add('speaking');};
    utt.onend=()=>{lb.innerHTML='🔊 Listen';lb.classList.remove('speaking');};
    window.speechSynthesis.speak(utt);
  };
  a.appendChild(lb);wrap.appendChild(a);
  const r=document.createElement('div');r.className='emoji-reactions';
  ['👍','❤️','😊','🔥','👏'].forEach(e=>{const b=document.createElement('button');b.className='emoji-btn';b.textContent=e;b.onclick=()=>b.classList.toggle('reacted');r.appendChild(b);});
  wrap.appendChild(r);
}

function appendMessage(role,content,searched,fileBadge){
  const w=document.getElementById('welcome');if(w)w.remove();
  const box=chatBox();if(!box)return null;
  const row=document.createElement('div');row.className=`msg-row ${role}`;
  const av=document.createElement('div');av.className=role==='ai'?'avatar panda':'avatar user-av';av.textContent=role==='ai'?'🐼':'👤';row.appendChild(av);
  const mc=document.createElement('div');mc.className='msg-content';
  if(role==='ai'&&searched){const b=document.createElement('div');b.className='search-badge';b.innerHTML='🌐 Live Search';mc.appendChild(b);}
  if(fileBadge){const b=document.createElement('div');b.className='file-badge';b.innerHTML=`📁 ${fileBadge}`;mc.appendChild(b);}
  const bub=document.createElement('div');bub.className=role==='ai'?'bubble ai':'bubble user';
  bub.innerHTML=role==='ai'?renderMd(content):escHtml(content);
  mc.appendChild(bub);
  if(role==='ai')addMsgActions(mc,content);
  row.appendChild(mc);box.appendChild(row);scrollToBottom();return row;
}

function showLoading(){
  const box=chatBox();if(!box)return;
  const row=document.createElement('div');row.id='loading-msg';row.className='msg-row ai';
  const av=document.createElement('div');av.className='avatar panda';av.textContent='🐼';row.appendChild(av);
  const mc=document.createElement('div');mc.className='msg-content';
  const bub=document.createElement('div');bub.className='bubble ai';
  bub.innerHTML='<div class="typing-dots"><span></span><span></span><span></span></div>';
  mc.appendChild(bub);row.appendChild(mc);box.appendChild(row);scrollToBottom();
}
function hideLoading(){const el=document.getElementById('loading-msg');if(el)el.remove();}

// ── File upload ──
function updateFilePreview(){
  const p=filePreview();if(!p)return;
  if(!pendingFiles.length){p.innerHTML='';p.classList.remove('show');return;}
  p.classList.add('show');
  p.innerHTML='📎 '+pendingFiles.map((f,i)=>`<span class="file-tag">${f.name} <span class="file-tag-remove" onclick="removeFile(${i})">✕</span></span>`).join('');
}
function removeFile(idx){pendingFiles.splice(idx,1);updateFilePreview();}

async function uploadAndAnalyze(){
  if(!pendingFiles.length)return;
  const question=(userInput()?userInput().value.trim():'')||'Please summarize this file';
  const fileNames=pendingFiles.map(f=>f.name).join(', ');
  isLoading=true;const btn=sendBtn();if(btn)btn.disabled=true;
  if(userInput()){userInput().value='';userInput().style.height='auto';}
  if(!currentSession)startSession();
  currentMessages.push({role:'user',content:`[File] ${fileNames}: ${question}`});persistSessions();
  appendMessage('user',`📎 ${fileNames}\n${question}`);showLoading();setStatus('📁 Analyzing...','thinking-status');
  try{
    const fd=new FormData();pendingFiles.forEach(f=>fd.append('files',f));
    fd.append('question',question);fd.append('session_id',sessionId);
    const res=await fetch('/upload',{method:'POST',body:fd});const data=await res.json();
    hideLoading();
    if(data.error)appendMessage('ai','⚠️ '+data.error,false,null);
    else{currentMessages.push({role:'ai',content:data.reply||''});persistSessions();appendMessage('ai',data.reply||'',data.searched||false,data.file_type||'File');if(ttsEnabled&&data.reply)speakText(data.reply);}
  }catch{hideLoading();appendMessage('ai','⚠️ Upload failed.',false,null);}
  pendingFiles=[];updateFilePreview();if(fileInput())fileInput().value='';
  setStatus('');isLoading=false;if(btn)btn.disabled=false;if(userInput())userInput().focus();
}

// ── Send ──
async function sendMessage(overrideText){
  if(pendingFiles.length){await uploadAndAnalyze();return;}
  const inp=userInput();const msg=(overrideText!==undefined?overrideText:(inp?inp.value:'')).trim();
  if(!msg||isLoading)return;
  isLoading=true;const btn=sendBtn();if(btn)btn.disabled=true;
  if(inp){inp.value='';inp.style.height='auto';}
  if(!currentSession)startSession();
  currentMessages.push({role:'user',content:msg});persistSessions();
  appendMessage('user',msg);showLoading();setStatus('🐼 Thinking...','thinking-status');
  if(currentMessages.filter(m=>m.role==='user').length===1){const t=msg.slice(0,35);if(topbarTitle())topbarTitle().textContent=t;if(currentSession){currentSession.title=t;renderChatList();}}
  const ls=langSelect();const langInstr=LANG_MAP[ls?ls.value:'en']||'';
  try{
    const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,session_id:sessionId,lang_instruction:langInstr})});
    const data=await res.json();hideLoading();
    if(data.error)appendMessage('ai','⚠️ '+data.error,false,null);
    else{currentMessages.push({role:'ai',content:data.reply||''});persistSessions();appendMessage('ai',data.reply||'',data.searched||false,null);if(ttsEnabled&&data.reply)speakText(data.reply);}
  }catch{hideLoading();appendMessage('ai','⚠️ Network error.',false,null);}
  setStatus('');isLoading=false;if(btn)btn.disabled=false;if(inp)inp.focus();
}

function quickSend(el){const t=el.textContent.replace(/[\u{1F300}-\u{1FAFF}]/gu,'').trim();sendMessage(t||el.textContent.trim());}
function speakText(text){if(!window.speechSynthesis)return;window.speechSynthesis.cancel();const plain=text.replace(/[#*`_\[\]()>~]/g,'').slice(0,500);const utt=new SpeechSynthesisUtterance(plain);const lc=langSelect()?langSelect().value:'en';utt.lang=lc==='te'?'te-IN':lc==='hi'?'hi-IN':lc==='ta'?'ta-IN':'en-US';utt.rate=0.95;const tb=ttsBtn();utt.onstart=()=>tb&&tb.classList.add('speaking');utt.onend=()=>tb&&tb.classList.remove('speaking');window.speechSynthesis.speak(utt);}

function toggleVoice(){
  if(!('webkitSpeechRecognition'in window||'SpeechRecognition'in window)){alert('Voice input not supported. Try Chrome.');return;}
  const vb=voiceBtn();if(isListening){recognition&&recognition.stop();return;}
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;recognition=new SR();
  const lc=langSelect()?langSelect().value:'en';recognition.lang=lc==='te'?'te-IN':lc==='hi'?'hi-IN':'en-US';
  recognition.interimResults=true;recognition.continuous=false;
  recognition.onstart=()=>{isListening=true;vb&&vb.classList.add('listening');setStatus('🎤 Listening...','listening-status');};
  recognition.onresult=(e)=>{const t=Array.from(e.results).map(r=>r[0].transcript).join('');const inp=userInput();if(inp)inp.value=t;};
  recognition.onend=()=>{isListening=false;vb&&vb.classList.remove('listening');setStatus('');const inp=userInput();if(inp&&inp.value.trim())sendMessage();};
  recognition.onerror=()=>{isListening=false;vb&&vb.classList.remove('listening');setStatus('');};
  recognition.start();
}

// ════════════════════════════════════════
// V6: WEATHER WIDGET
// GET /weather — Open-Meteo, IST-aware
// ════════════════════════════════════════
async function loadWeather(){
  const emoji=$('w-emoji'),temp=$('w-temp'),desc=$('w-desc'),city=$('w-city');
  if(temp)temp.textContent='Loading...';
  try{
    let lat='17.3850',lon='78.4867',cityName='Hyderabad';
    if(navigator.geolocation){
      await new Promise(resolve=>{
        navigator.geolocation.getCurrentPosition(
          pos=>{lat=pos.coords.latitude.toFixed(4);lon=pos.coords.longitude.toFixed(4);cityName='Your Location';resolve();},
          ()=>resolve(),{timeout:5000}
        );
      });
    }
    const res=await fetch(`/weather?lat=${lat}&lon=${lon}&city=${encodeURIComponent(cityName)}`);
    const data=await res.json();
    if(data.error){if(temp)temp.textContent='N/A';return;}
    if(emoji)emoji.textContent=data.emoji;
    if(temp)temp.textContent=data.temperature;
    if(desc)desc.textContent=`${data.description} · 💨 ${data.windspeed}`;
    if(city)city.textContent=`📍 ${data.city} · ${data.time||''}`;
  }catch(e){if(temp)temp.textContent='Unavailable';console.error('Weather:',e);}
}

// ════════════════════════════════════════
// V6: NEWS DIGEST
// GET /news?category=X
// ════════════════════════════════════════
async function toggleNews(){
  // Open news modal instead of sidebar section
  openModal('news-modal');
  await loadNewsDigest('general',document.querySelector('.digest-tab'));
}

async function loadNewsDigest(category,tabEl){
  // Update active tab
  document.querySelectorAll('.digest-tab').forEach(t=>t.classList.remove('active'));
  if(tabEl)tabEl.classList.add('active');

  const grid=$('news-cards-grid');
  if(grid)grid.innerHTML='<div style="text-align:center;color:var(--muted);padding:20px">Loading...</div>';

  try{
    const res=await fetch(`/news?category=${category}`);
    const data=await res.json();
    const cards=data.cards||[];
    if(!grid)return;
    if(!cards.length){grid.innerHTML='<div style="text-align:center;color:var(--muted);padding:20px">No news available</div>';return;}
    grid.innerHTML=`<div class="news-cards-wrap">`+cards.map(c=>`
      <div class="news-card" onclick="closeModal('news-modal');sendMessage(${JSON.stringify('Tell me about: '+c.title)})">
        <div class="news-card-cat">${c.category}</div>
        <div class="news-card-title">${escHtml(c.title)}</div>
        <div class="news-card-summary">${escHtml(c.summary||'')}</div>
        <div class="news-card-meta">${escHtml(c.source||'')} · ${c.published||''}</div>
      </div>`).join('')+`</div>`;
  }catch(e){if(grid)grid.innerHTML='<div style="color:#888;padding:20px">Failed to load.</div>';}
}

// ════════════════════════════════════════
// V6: MUSIC GENERATION
// POST /generate-music
// ════════════════════════════════════════
async function generateMusic(){
  const promptEl=$('music-prompt'),statusEl=$('music-status'),audioEl=$('music-audio'),genBtn=$('gen-music-btn');
  const prompt=promptEl?promptEl.value.trim():'calm relaxing music';
  if(!prompt){alert('Please enter a music prompt');return;}
  if(genBtn){genBtn.disabled=true;genBtn.textContent='⏳ Generating...';}
  if(statusEl)statusEl.textContent='🎵 Composing your music... (~30 seconds)';
  if(audioEl)audioEl.style.display='none';
  try{
    const res=await fetch('/generate-music',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt})});
    const data=await res.json();
    if(data.error){if(statusEl)statusEl.textContent='⚠️ '+data.error;}
    else if(data.audio_base64){
      const bytes=atob(data.audio_base64);const buf=new Uint8Array(bytes.length);
      for(let i=0;i<bytes.length;i++)buf[i]=bytes.charCodeAt(i);
      const blob=new Blob([buf],{type:'audio/wav'});const url=URL.createObjectURL(blob);
      if(audioEl){audioEl.src=url;audioEl.style.display='block';audioEl.play().catch(()=>{});}
      if(statusEl)statusEl.textContent=`🎵 "${prompt}" — Ready!`;
    }
  }catch(e){if(statusEl)statusEl.textContent='⚠️ Generation failed. Try again.';console.error('Music:',e);}
  if(genBtn){genBtn.disabled=false;genBtn.textContent='🎵 Generate';}
}

// ════════════════════════════════════════
// TASKS
// ════════════════════════════════════════
function openModal(id){const m=$(id);if(m)m.classList.add('show');sidebarEl()&&sidebarEl().classList.remove('open');}
function closeModal(id){const m=$(id);if(m)m.classList.remove('show');}

async function saveTask(){
  const nameEl=$('task-name'),timeEl=$('task-time');
  const name=nameEl?nameEl.value.trim():'';if(!name){alert('Enter a task');return;}
  await fetch('/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:name,remind_at:timeEl?timeEl.value:''})});
  if(nameEl)nameEl.value='';if(timeEl)timeEl.value='';loadTasksList();
}

async function loadTasksList(){
  const list=$('task-list');if(!list)return;
  try{
    const res=await fetch('/tasks');const data=await res.json();const tasks=data.tasks||[];
    if(!tasks.length){list.innerHTML='<div class="no-tasks">No tasks yet!</div>';return;}
    list.innerHTML=tasks.map(t=>`
      <div class="task-item ${t.done?'done':''}">
        <div class="task-item-text"><div>${escHtml(t.task)}</div>${t.remind_at?`<div class="task-item-time">⏰ ${new Date(t.remind_at).toLocaleString()}</div>`:''}</div>
        ${!t.done?`<button class="task-done-btn" onclick="markTaskDone(${t.id})">✓</button>`:'<span style="color:#4a9e6b">✓</span>'}
        <button class="task-del-btn" onclick="deleteTask(${t.id})">✕</button>
      </div>`).join('');
  }catch{list.innerHTML='<div class="no-tasks">Error loading.</div>';}
}

async function markTaskDone(id){await fetch(`/tasks/${id}/done`,{method:'POST'});loadTasksList();}
async function deleteTask(id){await fetch(`/tasks/${id}`,{method:'DELETE'});loadTasksList();}

// ── Sessions ──
function startSession(){sessionId='sess_'+Date.now()+'_'+Math.random().toString(36).slice(2,7);currentMessages=[];currentSession={id:sessionId,title:'New Chat',messages:[],ts:Date.now()};chatSessions.unshift(currentSession);persistSessions();renderChatList();if(topbarTitle())topbarTitle().textContent='New Chat';}
function persistSessions(){if(currentSession){currentSession.messages=[...currentMessages];currentSession.ts=Date.now();}try{localStorage.setItem('pandaSessions',JSON.stringify(chatSessions.slice(0,30)));}catch{}}
function loadSession(id){const s=chatSessions.find(s=>s.id===id);if(!s)return;currentSession=s;sessionId=s.id;currentMessages=s.messages?[...s.messages]:[];const box=chatBox();if(box){box.innerHTML='';currentMessages.forEach(m=>appendMessage(m.role,m.content));}if(topbarTitle())topbarTitle().textContent=s.title||'Chat';renderChatList();sidebarEl()&&sidebarEl().classList.remove('open');}
function deleteSession(id){chatSessions=chatSessions.filter(s=>s.id!==id);persistSessions();if(currentSession&&currentSession.id===id){currentSession=null;currentMessages=[];const box=chatBox();if(box)box.innerHTML=buildWelcomeHTML();}renderChatList();}
function renderChatList(){const cl=chatList();if(!cl)return;if(!chatSessions.length){cl.innerHTML='<div class="no-chats">No chats yet 🐼<br>Start a new chat!</div>';return;}cl.innerHTML=chatSessions.map(s=>`<div class="chat-item ${currentSession&&currentSession.id===s.id?'active':''}" onclick="loadSession('${s.id}')"><span class="chat-item-icon">💬</span><div class="chat-item-text"><div class="chat-item-title">${escHtml(s.title||'New Chat')}</div><div class="chat-item-time">${new Date(s.ts).toLocaleDateString()}</div></div><button class="chat-item-del" onclick="event.stopPropagation();deleteSession('${s.id}')">🗑</button></div>`).join('');}
function buildWelcomeHTML(){return `<div id="welcome" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:14px;text-align:center;padding:20px"><div class="welcome-icon">🐼</div><h2 style="font-family:'Comfortaa',cursive;font-size:36px;color:var(--black)">Panda AI V6</h2><p style="color:var(--muted);font-size:14px;max-width:380px;line-height:1.6">Real-time AI with Weather, Music & File Analysis 🎋</p><div id="weather-widget" onclick="loadWeather()" title="Click to refresh"><div class="w-emoji" id="w-emoji">🌡️</div><div class="w-info"><div class="w-temp" id="w-temp">--°C</div><div class="w-desc" id="w-desc">Loading weather...</div><div class="w-city" id="w-city">📍 Detecting...</div></div></div><div class="web-badge">🌐 Search + 📁 Files + 🌤️ Weather + 🎵 Music</div><div class="chips"><div class="chip" onclick="quickSend(this)">Today's news 📰</div><div class="chip" onclick="quickSend(this)">IPL 2026 results 🏏</div><div class="chip" onclick="quickSend(this)">Write Python code 🐍</div><div class="chip" onclick="quickSend(this)">Tell me a fun fact 🎯</div></div></div>`;}
function newChat(){const box=chatBox();if(box)box.innerHTML=buildWelcomeHTML();startSession();pendingFiles=[];updateFilePreview();userInput()&&userInput().focus();sidebarEl()&&sidebarEl().classList.remove('open');setTimeout(loadWeather,600);}

// ── Event Listeners ──
document.addEventListener('DOMContentLoaded',()=>{
  sendBtn()&&sendBtn().addEventListener('click',()=>sendMessage());
  const inp=userInput();
  if(inp){
    inp.addEventListener('input',function(){this.style.height='auto';this.style.height=Math.min(this.scrollHeight,130)+'px';});
    inp.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();e.stopPropagation();sendMessage();return false;}});
    inp.addEventListener('keypress',function(e){if((e.key==='Enter'||e.keyCode===13)&&!e.shiftKey){e.preventDefault();e.stopPropagation();sendMessage();return false;}});
    inp.focus();
  }
  themeToggle()&&themeToggle().addEventListener('click',()=>{const cur=document.documentElement.getAttribute('data-theme');const next=cur==='dark'?'light':'dark';document.documentElement.setAttribute('data-theme',next);localStorage.setItem('pandaTheme',next);themeToggle().textContent=next==='dark'?'☀️':'🌙';});
  const st=sidebarToggle(),sd=sidebarEl();
  if(st&&sd){st.addEventListener('click',()=>sd.classList.toggle('open'));document.addEventListener('click',e=>{if(sd.classList.contains('open')&&!sd.contains(e.target)&&e.target!==st)sd.classList.remove('open');});}
  newChatBtn()&&newChatBtn().addEventListener('click',newChat);
  $('tasks-btn')&&$('tasks-btn').addEventListener('click',()=>{openModal('tasks-modal');loadTasksList();});
  $('music-btn')&&$('music-btn').addEventListener('click',()=>openModal('music-modal'));
  ['tasks-modal','music-modal','news-modal'].forEach(id=>{const m=$(id);if(m)m.addEventListener('click',e=>{if(e.target===m)closeModal(id);});});
  ttsBtn()&&ttsBtn().addEventListener('click',()=>{ttsEnabled=!ttsEnabled;const tb=ttsBtn();tb.style.background=ttsEnabled?'rgba(74,158,107,0.2)':'';tb.style.borderColor=ttsEnabled?'var(--accent)':'';if(!ttsEnabled&&window.speechSynthesis){window.speechSynthesis.cancel();tb.classList.remove('speaking');}});
  voiceBtn()&&voiceBtn().addEventListener('click',toggleVoice);
  newsBtn()&&newsBtn().addEventListener('click',toggleNews);
  const ub=uploadBtn(),fi=fileInput();
  if(ub&&fi){
    ub.addEventListener('click',()=>fi.click());
    fi.addEventListener('change',e=>{const files=Array.from(e.target.files);if(files.length){pendingFiles=[...pendingFiles,...files];updateFilePreview();if(userInput()){userInput().placeholder='Ask about the file...';userInput().focus();}}});
    const box=chatBox();
    if(box){box.addEventListener('dragover',e=>{e.preventDefault();box.style.outline='2px dashed var(--accent)';});box.addEventListener('dragleave',()=>{box.style.outline='';});box.addEventListener('drop',e=>{e.preventDefault();box.style.outline='';const files=Array.from(e.dataTransfer.files);if(files.length){pendingFiles=[...pendingFiles,...files];updateFilePreview();}});}
  }
  // V6: Load weather on startup
  setTimeout(loadWeather, 800);
  // Tasks notification check
  setInterval(async()=>{try{const res=await fetch('/tasks/due');const data=await res.json();if(data.tasks&&data.tasks.length&&'Notification'in window){data.tasks.forEach(t=>{if(Notification.permission==='granted')new Notification('🐼 Panda AI Reminder',{body:t.task});});}}catch{}},60000);
  if('Notification'in window&&Notification.permission==='default')Notification.requestPermission();
});