'use strict';

// ── State ──
let sessionId        = 'sess_' + Date.now();
let isLoading        = false;
let ttsEnabled       = false;
let isListening      = false;
let recognition      = null;
let chatSessions     = [];
let currentSession   = null;
let currentMessages  = [];
let pendingFiles     = [];
let currentStudioType = 'image';

const $          = id => document.getElementById(id);
const chatBox    = () => $('chat-box');
const userInput  = () => $('user-input');
const sendBtn    = () => $('send-btn');
const statusBar  = () => $('status-bar');
const chatList   = () => $('chat-list');
const topbarTitle= () => $('topbar-title');
const sidebarEl  = () => $('sidebar');

// ── Theme ──
(function(){
    const s = localStorage.getItem('pandaTheme') || 'light';
    document.documentElement.setAttribute('data-theme', s);
    const b = $('theme-toggle'); if(b) b.textContent = s==='dark'?'☀️':'🌙';
})();

// ── Sessions ──
(function(){
    try { chatSessions = JSON.parse(localStorage.getItem('pandaSessions') || '[]'); }
    catch { chatSessions = []; }
    renderChatList();
})();

const LANG_MAP = {
    en:'Respond in English.',te:'Respond fully in Telugu (తెలుగు లో జవాబు ఇవ్వండి).',
    hi:'Respond fully in Hindi (हिंदी में उत्तर दें).',ta:'Respond fully in Tamil.',
    es:'Respond fully in Spanish.',fr:'Respond fully in French.',de:'Respond fully in German.',
    ja:'Respond fully in Japanese.',zh:'Respond fully in Chinese.',ar:'Respond fully in Arabic.',
};

// Studio configuration per type
const STUDIO_CONFIG = {
    image: {
        badge:     '⚡ Cloudflare Workers AI + Unsplash',
        badgeClass:'engine-badge cf',
        hint:      '💡 "a serene panda in bamboo forest at dawn, photorealistic 4K" — Stable Diffusion XL',
        tabClass:  'img-tab',
    },
    video: {
        badge:     '🎞 Pexels HD Video Library',
        badgeClass:'engine-badge pexels',
        hint:      '💡 "peaceful mountain waterfall, cinematic, slow motion" — Pexels curated video',
        tabClass:  'vid-tab',
    },
    audio: {
        badge:     '🎵 Panda CDN Music Library · No API Key',
        badgeClass:'engine-badge pixabay',
        hint:      '💡 Try: "happy", "lofi", "cinematic", "nature", "techno", "meditation", "epic", "jazz"',
        tabClass:  'aud-tab',
    },
};

// Illusion loading messages per type
const ILLUSION_STEPS = {
    image: [
        '🔍 Panda is analysing your prompt…',
        '🎨 Synthesising AI layers…',
        '✨ Applying visual enhancements…',
        '🖼️ Rendering high-resolution output…',
    ],
    video: [
        '🔍 Scanning cinematic database…',
        '🎞 Matching your scene…',
        '⚡ Selecting HD footage…',
        '🎥 Preparing your video…',
    ],
    audio: [
        '🔍 Analysing musical style from your prompt…',
        '🎼 Matching mood to our music library…',
        '🎹 Selecting the perfect track…',
        '🎵 Loading your audio experience…',
    ],
};

// ════════════════════════════════════════
// UTILITIES
// ════════════════════════════════════════
function scrollToBottom(){
    const b=chatBox(); if(!b) return;
    requestAnimationFrame(()=>requestAnimationFrame(()=>{ b.scrollTop=b.scrollHeight; }));
}
function setStatus(msg,cls){
    const bar=statusBar(); if(!bar) return;
    bar.textContent=msg||''; bar.className=msg?('show '+(cls||'')):'';
}
function escHtml(s){
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
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

// ════════════════════════════════════════
// DOWNLOAD HELPERS
// All downloads are local — no external redirect
// ════════════════════════════════════════

/**
 * Download a file from a URL by proxying through fetch.
 * Falls back to opening in new tab if CORS blocks fetch.
 */
async function downloadFromUrl(url, fname){
    try{
        const res  = await fetch(url);
        const blob = await res.blob();
        const burl = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href=burl; a.download=fname;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(()=>URL.revokeObjectURL(burl), 10000);
    }catch{
        // CORS fallback — open in new tab
        window.open(url,'_blank');
    }
}

/**
 * Download from base64 (used for CF image — raw PNG bytes).
 */
function downloadFromBase64(b64, mime, fname){
    try{
        const bytes=atob(b64); const buf=new Uint8Array(bytes.length);
        for(let i=0;i<bytes.length;i++) buf[i]=bytes.charCodeAt(i);
        const blob=new Blob([buf],{type:mime});
        const url=URL.createObjectURL(blob);
        const a=document.createElement('a'); a.href=url; a.download=fname;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        setTimeout(()=>URL.revokeObjectURL(url),10000);
    }catch(e){
        console.error('Download failed:',e); alert('Download failed. Try again.');
    }
}

// ════════════════════════════════════════
// PROFILE & USER IDENTITY (V8.3)
// ════════════════════════════════════════
async function checkFirstVisit() {
  try {
    const res  = await fetch('/profile');
    const data = await res.json();
    if (data.is_new_user) {
      showWelcomeModal();
    } else {
      applyUserName(data.profile.name || "there");
    }
  } catch {
    // Silent fail — don't block chat
  }
}

function applyUserName(name) {
  document.querySelectorAll('[data-user-name]')
    .forEach(el => el.textContent = name);
}

function showWelcomeModal() {
  document.getElementById('profile-overlay').style.display = 'flex';
}

async function saveUserProfile() {
  const input = document.getElementById('profile-name-input');
  const name  = input.value.trim();
  if (!name) { input.style.borderColor = '#e44'; return; }

  await fetch('/profile', {
    method:  'POST',
    headers: {'Content-Type': 'application/json'},
    body:    JSON.stringify({ name })
  });

  document.getElementById('profile-overlay').style.display = 'none';
  applyUserName(name);
}

// ════════════════════════════════════════
// SOURCES RENDERING (V8.3)
// ════════════════════════════════════════
function renderSources(sources) {
  if (!sources || !sources.length) return '';
  const links = sources
    .filter(s => s.url)
    .map(s => {
      const url = escHtml(s.url);
      const title = escHtml(s.title || 'Source');
      const source = escHtml(s.source || 'Unknown');
      return `<a href="${url}" target="_blank" rel="noopener" style="display:flex;gap:6px;align-items:center;font-size:0.78rem;color:var(--accent);text-decoration:none;padding:4px 0;margin:2px 0;">
        <span style="opacity:0.5">↗</span>
        <span>${title} — ${source}</span>
      </a>`;
    }).join('');
  if (!links) return '';
  return `<div style="margin-top:10px;padding-top:8px;border-top:0.5px solid var(--border);">
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.6px;color:var(--muted);margin-bottom:6px;font-weight:700;">Sources</div>
    <div style="display:flex;flex-direction:column;gap:0;">${links}</div>
  </div>`;
}

// ════════════════════════════════════════
// MESSAGE RENDERING
// ════════════════════════════════════════
function addMsgActions(wrap, text){
    const a=document.createElement('div'); a.className='msg-actions';
    const lb=document.createElement('button'); lb.className='tts-msg-btn'; lb.innerHTML='🔊 Listen';
    lb.onclick=()=>{
        if(window.speechSynthesis.speaking){window.speechSynthesis.cancel();lb.innerHTML='🔊 Listen';lb.classList.remove('speaking');return;}
        const plain=text.replace(/[#*`_\[\]()>~<]/g,'').slice(0,600);
        const utt=new SpeechSynthesisUtterance(plain);
        const lc=$('lang-select')?$('lang-select').value:'en';
        utt.lang=lc==='te'?'te-IN':lc==='hi'?'hi-IN':lc==='ta'?'ta-IN':'en-US'; utt.rate=0.95;
        utt.onstart=()=>{lb.innerHTML='⏹ Stop';lb.classList.add('speaking');};
        utt.onend=()=>{lb.innerHTML='🔊 Listen';lb.classList.remove('speaking');};
        window.speechSynthesis.speak(utt);
    };
    a.appendChild(lb);
    const r=document.createElement('div'); r.className='emoji-reactions';
    ['👍','❤️','😊','🔥','👏'].forEach(e=>{
        const b=document.createElement('button'); b.className='emoji-btn'; b.textContent=e;
        b.onclick=()=>b.classList.toggle('reacted'); r.appendChild(b);
    });
    wrap.appendChild(a); wrap.appendChild(r);
}

function appendMessage(role,content,searched,fileBadge){
    const w=document.getElementById('welcome'); if(w) w.remove();
    const box=chatBox(); if(!box) return null;
    const row=document.createElement('div'); row.className=`msg-row ${role}`;
    const av=document.createElement('div');
    av.className=role==='ai'?'avatar panda':'avatar user-av';
    av.textContent=role==='ai'?'🐼':'👤';
    row.appendChild(av);
    const mc=document.createElement('div'); mc.className='msg-content';
    if(role==='ai'&&searched){const b=document.createElement('div');b.className='search-badge';b.innerHTML='🌐 Live Search';mc.appendChild(b);}
    if(fileBadge){const b=document.createElement('div');b.className='file-badge';b.innerHTML=`📁 ${fileBadge}`;mc.appendChild(b);}
    const bub=document.createElement('div'); bub.className=role==='ai'?'bubble ai':'bubble user';
    bub.innerHTML=role==='ai'?renderMd(content):escHtml(content);
    mc.appendChild(bub);
    if(role==='ai') addMsgActions(mc,content);
    row.appendChild(mc); box.appendChild(row); scrollToBottom();
    return row;
}

function showLoading(){
    const box=chatBox(); if(!box) return;
    const row=document.createElement('div'); row.id='loading-msg'; row.className='msg-row ai';
    const av=document.createElement('div'); av.className='avatar panda'; av.textContent='🐼'; row.appendChild(av);
    const mc=document.createElement('div'); mc.className='msg-content';
    const bub=document.createElement('div'); bub.className='bubble ai';
    bub.innerHTML='<div class="typing-dots"><span></span><span></span><span></span></div>';
    mc.appendChild(bub); row.appendChild(mc); box.appendChild(row); scrollToBottom();
}
function hideLoading(){const el=$('loading-msg');if(el)el.remove();}

// ════════════════════════════════════════
// FILE UPLOAD
// ════════════════════════════════════════
function updateFilePreview(){
    const p=$('file-preview'); if(!p) return;
    if(!pendingFiles.length){p.innerHTML='';p.classList.remove('show');return;}
    p.classList.add('show');
    p.innerHTML='📎 '+pendingFiles.map((f,i)=>`<span class="file-tag">${f.name} <span class="file-tag-remove" onclick="removeFile(${i})">✕</span></span>`).join('');
}
function removeFile(idx){pendingFiles.splice(idx,1);updateFilePreview();}

// ── V8.2: Cloud-aware status messages per file type ──────────────────────────
// Maps file extension → human-readable cloud processing status.
// Shown in the status bar while the server-side cloud API call runs.
// Replaces the old generic "Analysing file..." message.
const FILE_PROCESSING_STATUS = {
    // Images → HF BLIP captioning API
    jpg:  '🖼️ Sending to HF BLIP — captioning your image...',
    jpeg: '🖼️ Sending to HF BLIP — captioning your image...',
    png:  '🖼️ Sending to HF BLIP — captioning your image...',
    bmp:  '🖼️ Sending to HF BLIP — captioning your image...',
    tiff: '🖼️ Sending to HF BLIP — captioning your image...',
    // Audio → Groq Whisper API
    mp3:  '🎵 Sending to Groq Whisper — transcribing audio...',
    wav:  '🎵 Sending to Groq Whisper — transcribing audio...',
    ogg:  '🎵 Sending to Groq Whisper — transcribing audio...',
    // Video → ffmpeg extract → Groq Whisper API
    mp4:  '🎬 Extracting audio → Groq Whisper — this may take ~15s...',
    avi:  '🎬 Extracting audio → Groq Whisper — this may take ~15s...',
    mov:  '🎬 Extracting audio → Groq Whisper — this may take ~15s...',
    // Documents (fast, local extraction — no cloud)
    pdf:  '📄 Reading PDF...',
    docx: '📝 Reading Word document...',
    xlsx: '📊 Reading Excel spreadsheet...',
    xls:  '📊 Reading Excel spreadsheet...',
    pptx: '📋 Reading PowerPoint...',
};

function getFileStatusMsg(files) {
    // If multiple files, show generic message
    if (files.length > 1) return '📎 Processing files...';
    const ext = files[0].name.split('.').pop().toLowerCase();
    return FILE_PROCESSING_STATUS[ext] || '📁 Analysing file...';
}

async function uploadAndAnalyze(){
    if(!pendingFiles.length) return;
    showChat();
    const question=(userInput()?.value.trim())||'Please summarize this file';
    const fileNames=pendingFiles.map(f=>f.name).join(', ');
    isLoading=true; const btn=sendBtn(); if(btn) btn.disabled=true;
    if(userInput()){userInput().value='';userInput().style.height='auto';}
    if(!currentSession) startSession();
    currentMessages.push({role:'user',content:`[File] ${fileNames}: ${question}`}); persistSessions();
    appendMessage('user',`📎 ${fileNames}\n${question}`);

    // V8.2: Show cloud-specific processing status instead of generic message
    const statusMsg = getFileStatusMsg(pendingFiles);
    showLoading(); setStatus(statusMsg, '');

    try{
        const fd=new FormData(); pendingFiles.forEach(f=>fd.append('files',f));
        fd.append('question',question); fd.append('session_id',sessionId);
        const res=await fetch('/upload',{method:'POST',body:fd});
        const data=await res.json(); hideLoading();
        if(data.error) appendMessage('ai','⚠️ '+data.error,false,null);
        else{currentMessages.push({role:'ai',content:data.reply||''});persistSessions();appendMessage('ai',data.reply||'',data.searched||false,data.file_type||'File');if(ttsEnabled&&data.reply)speakText(data.reply);}
    }catch{hideLoading();appendMessage('ai','⚠️ Upload failed. Please try again.',false,null);}
    pendingFiles=[];updateFilePreview();const fi=$('file-input');if(fi)fi.value='';
    setStatus('');isLoading=false;if(btn)btn.disabled=false;userInput()?.focus();
}

// ════════════════════════════════════════
// SEND — unchanged core
// ════════════════════════════════════════
async function sendMessage(overrideText){
    if(pendingFiles.length){await uploadAndAnalyze();return;}
    showChat();
    const inp=userInput();
    const msg=(overrideText!==undefined?overrideText:(inp?inp.value:'')).trim();
    if(!msg||isLoading) return;
    isLoading=true; const btn=sendBtn(); if(btn) btn.disabled=true;
    if(inp){inp.value='';inp.style.height='auto';}
    if(!currentSession) startSession();
    currentMessages.push({role:'user',content:msg}); persistSessions();
    appendMessage('user',msg); showLoading(); setStatus('🐼 Thinking...','');
    if(currentMessages.filter(m=>m.role==='user').length===1){
        const t=msg.slice(0,35); if(topbarTitle()) topbarTitle().textContent=t;
        if(currentSession){currentSession.title=t;renderChatList();}
    }
    const ls=$('lang-select'); const langInstr=LANG_MAP[ls?ls.value:'en']||'';
    try{
        const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({message:msg,session_id:sessionId,lang_instruction:langInstr})});
        const data=await res.json(); hideLoading();
        if(data.error) appendMessage('ai','⚠️ '+data.error,false,null);
        else{currentMessages.push({role:'ai',content:data.reply||''});persistSessions();
            const msgEl=appendMessage('ai',data.reply||'',data.searched||false,null);
            // Add sources under the message if available
            if(data.sources && data.sources.length > 0 && msgEl) {
                const sourcesDiv=document.createElement('div');
                sourcesDiv.innerHTML=renderSources(data.sources);
                const bubble=msgEl.querySelector('.bubble.ai');
                if(bubble && bubble.parentElement) bubble.parentElement.appendChild(sourcesDiv);
            }
            if(ttsEnabled&&data.reply)speakText(data.reply);}
    }catch{hideLoading();appendMessage('ai','⚠️ Network error.',false,null);}
    setStatus('');isLoading=false;if(btn)btn.disabled=false;inp?.focus();
}

function quickSend(el){const t=el.textContent.replace(/[\u{1F300}-\u{1FAFF}]/gu,'').trim();sendMessage(t||el.textContent.trim());}

function speakText(text){
    if(!window.speechSynthesis) return; window.speechSynthesis.cancel();
    const plain=text.replace(/[#*`_\[\]()>~]/g,'').slice(0,500);
    const utt=new SpeechSynthesisUtterance(plain);
    const lc=$('lang-select')?$('lang-select').value:'en';
    utt.lang=lc==='te'?'te-IN':lc==='hi'?'hi-IN':lc==='ta'?'ta-IN':'en-US'; utt.rate=0.95;
    const tb=$('tts-btn');
    utt.onstart=()=>tb&&tb.classList.add('speaking');
    utt.onend=()=>tb&&tb.classList.remove('speaking');
    window.speechSynthesis.speak(utt);
}

function toggleVoice(){
    if(!('webkitSpeechRecognition'in window||'SpeechRecognition'in window)){alert('Use Chrome for voice input.');return;}
    const vb=$('voice-btn');
    if(isListening){recognition&&recognition.stop();return;}
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    recognition=new SR();
    const lc=$('lang-select')?$('lang-select').value:'en';
    recognition.lang=lc==='te'?'te-IN':lc==='hi'?'hi-IN':'en-US';
    recognition.interimResults=true; recognition.continuous=false;
    recognition.onstart=()=>{isListening=true;vb&&vb.classList.add('listening');setStatus('🎤 Listening...','');};
    recognition.onresult=e=>{const t=Array.from(e.results).map(r=>r[0].transcript).join('');const i=userInput();if(i)i.value=t;};
    recognition.onend=()=>{isListening=false;vb&&vb.classList.remove('listening');setStatus('');const i=userInput();if(i&&i.value.trim())sendMessage();};
    recognition.onerror=()=>{isListening=false;vb&&vb.classList.remove('listening');setStatus('');};
    recognition.start();
}

// ════════════════════════════════════════
// WEATHER
// ════════════════════════════════════════
async function loadWeather(){
    const emoji=$('w-emoji'),temp=$('w-temp'),desc=$('w-desc'),city=$('w-city');
    if(temp) temp.textContent='Loading...';
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
    }catch(e){if(temp)temp.textContent='Unavailable';}
}

// ════════════════════════════════════════
// NEWS
// ════════════════════════════════════════
async function loadNewsDigest(category,tabEl){
    document.querySelectorAll('.digest-tab').forEach(t=>t.classList.remove('active'));
    if(tabEl) tabEl.classList.add('active');
    const grid=$('news-cards-grid'); if(!grid) return;
    grid.innerHTML='<div class="news-cards-wrap">'+
        Array(4).fill(`<div class="news-card skeleton"><div class="skeleton-line" style="width:38%"></div><div class="skeleton-line" style="width:92%"></div><div class="skeleton-line" style="width:74%"></div><div class="skeleton-line" style="width:52%"></div></div>`).join('')+'</div>';
    try{
        const res=await fetch(`/news?category=${category}`);
        const data=await res.json(); const cards=data.cards||[];
        if(!cards.length){grid.innerHTML='<div style="text-align:center;color:var(--muted);padding:24px">No news available.</div>';return;}
        grid.innerHTML='<div class="news-cards-wrap">'+cards.map((c,i)=>`
            <div class="news-card" style="animation-delay:${i*0.06}s"
                 onclick="closeModal('news-modal');sendMessage(${JSON.stringify('Tell me about: '+c.title)})">
                <div class="news-card-cat">${c.category}</div>
                <div class="news-card-title">${escHtml(c.title)}</div>
                <div class="news-card-summary">${escHtml(c.summary||'')}</div>
                <div class="news-card-meta">${escHtml(c.source||'')} · ${c.published||''}</div>
            </div>`).join('')+'</div>';
    }catch{grid.innerHTML='<div style="color:#888;padding:20px">Failed to load.</div>';}
}

function toggleNews(){openModal('news-modal');loadNewsDigest('general',document.querySelector('.digest-tab'));}

// ════════════════════════════════════════
// V8 STUDIO — Media Generation
// ════════════════════════════════════════
function setStudioType(type, tabEl){
    currentStudioType = type;
    document.querySelectorAll('.studio-tab').forEach(t=>t.classList.remove('active'));
    if(tabEl) tabEl.classList.add('active');

    const cfg = STUDIO_CONFIG[type];
    const badge = $('engine-badge');
    if(badge){badge.textContent=cfg.badge; badge.className=cfg.badgeClass;}
    const hint = $('studio-hint'); if(hint) hint.textContent=cfg.hint;
    const out  = $('studio-output');
    if(out) out.innerHTML=`<div class="studio-status">Ready to generate ${type}!</div>`;
}

function openStudio(type='image'){
    openModal('studio-modal');
    const tabs = document.querySelectorAll('.studio-tab');
    const order= ['image','video','audio'];
    const idx  = order.indexOf(type);
    if(tabs[idx]) setStudioType(type, tabs[idx]);
}

/**
 * Run the 4-step illusion loading sequence.
 * Each step shows for ~1 second before the real API call is made.
 * Returns a cleanup function.
 */
function runIllusionSteps(type, outputEl){
    const steps = ILLUSION_STEPS[type] || ILLUSION_STEPS.image;
    let idx = 0;
    // Show first step immediately
    const render = (msg) => {
        if(!outputEl) return;
        outputEl.innerHTML = `
            <div style="display:flex;flex-direction:column;align-items:center;gap:14px;width:100%">
                <div style="display:flex;gap:6px">
                    <span style="width:10px;height:10px;border-radius:50%;background:var(--accent);animation:typeBounce 1.2s infinite;animation-delay:0s"></span>
                    <span style="width:10px;height:10px;border-radius:50%;background:var(--accent);animation:typeBounce 1.2s infinite;animation-delay:.2s"></span>
                    <span style="width:10px;height:10px;border-radius:50%;background:var(--accent);animation:typeBounce 1.2s infinite;animation-delay:.4s"></span>
                </div>
                <div class="illusion-step">${msg}</div>
            </div>`;
    };
    render(steps[0]);
    const timer = setInterval(()=>{
        idx = (idx+1) % steps.length;
        render(steps[idx]);
    }, 1000);
    return () => clearInterval(timer);
}

async function generateStudioMedia(){
    const promptEl = $('studio-prompt');
    const outputEl = $('studio-output');
    const genBtn   = $('studio-gen-btn');
    const prompt   = promptEl ? promptEl.value.trim() : '';
    if(!prompt){alert('Please enter a prompt!');return;}

    if(genBtn){genBtn.disabled=true;genBtn.textContent='⏳ Generating...';}

    // Start illusion loading sequence (4-second premium feel)
    const stopIllusion = runIllusionSteps(currentStudioType, outputEl);

    // Parallel: fire real API request immediately
    let data = null;
    let apiError = null;
    try{
        const res = await fetch('/generate-media',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({type:currentStudioType,prompt}),
        });
        data = await res.json();
        if(data.error) apiError = data.error;
    }catch(err){
        apiError = 'Network error — please check your connection.';
        console.error('Studio API error:',err);
    }

    // Minimum 4-second illusion: wait for rest of delay if API was fast
    // (already async — illusion timer keeps running until we call stop)
    // We add a small wait so illusion shows at least 2 full steps:
    await new Promise(r=>setTimeout(r,2000));
    stopIllusion();

    if(genBtn){genBtn.disabled=false;genBtn.textContent='✨ Generate';}

    if(apiError){
        if(outputEl) outputEl.innerHTML=`<div class="studio-status">⚠️ ${escHtml(apiError)}</div>`;
        return;
    }

    // ── Render result in output card ──
    renderStudioOutput(data, prompt, outputEl);

    // ── Push card to chat ──
    pushMediaToChat(data, prompt);
}

function renderStudioOutput(data, prompt, outputEl){
    if(!outputEl) return;
    outputEl.innerHTML = '';

    if(data.type === 'image'){
        // CF: base64 PNG | Unsplash: URL
        const img = document.createElement('img');
        if(data.b64){
            img.src = `data:${data.mime||'image/png'};base64,${data.b64}`;
        }else{
            img.src = data.url;
        }
        img.alt = prompt;
        img.onerror = ()=>{ outputEl.innerHTML='<div class="studio-status">⚠️ Image failed. Try again.</div>'; };

        const src  = data.source==='cloudflare'?'⚡ Cloudflare SD':'📷 Unsplash';
        const info = document.createElement('div');
        info.style.cssText='font-size:10px;color:var(--muted);text-align:center;margin-top:4px';
        info.textContent = `${src} · "${prompt.slice(0,40)}${prompt.length>40?'…':''}"`;

        const dlBtn = document.createElement('button');
        dlBtn.className='studio-dl-btn';
        dlBtn.innerHTML='⬇️ Download Image';
        dlBtn.onclick = ()=>{
            if(data.b64) downloadFromBase64(data.b64, data.mime||'image/png','panda_image.png');
            else downloadFromUrl(data.url,'panda_image.jpg');
        };

        outputEl.appendChild(img); outputEl.appendChild(info); outputEl.appendChild(dlBtn);

    }else if(data.type === 'video'){
        const vid = document.createElement('video');
        vid.src     = data.url;
        vid.controls= true; vid.autoplay=true; vid.muted=true; vid.loop=true;
        vid.style.cssText='width:100%;border-radius:12px;max-height:280px';
        vid.onerror = ()=>{ outputEl.innerHTML='<div class="studio-status">⚠️ Video failed to load.</div>'; };

        const info=document.createElement('div');
        info.style.cssText='font-size:10px;color:var(--muted);text-align:center;margin-top:4px';
        info.textContent=`🎞 Pexels HD · "${prompt.slice(0,40)}${prompt.length>40?'…':''}"`;

        const dlBtn=document.createElement('button');
        dlBtn.className='studio-dl-btn'; dlBtn.innerHTML='⬇️ Download Video';
        dlBtn.onclick=()=>downloadFromUrl(data.url,'panda_video.mp4');

        outputEl.appendChild(vid); outputEl.appendChild(info); outputEl.appendChild(dlBtn);

    }else if(data.type === 'audio'){
        const lbl=document.createElement('div');
        lbl.style.cssText='font-size:12px;font-weight:700;color:var(--accent);margin-bottom:6px;text-align:center';
        lbl.innerHTML=`🎵 "${escHtml(data.title||prompt)}"`;

        const cat=document.createElement('div');
        cat.style.cssText='font-size:10px;color:var(--muted);text-align:center;margin-bottom:8px';
        cat.textContent=`Category: ${(data.category||'ambient').toUpperCase()} · Panda CDN Library`;

        const aud=document.createElement('audio');
        aud.src=data.url; aud.controls=true; aud.autoplay=true;
        aud.style.cssText='width:100%;border-radius:10px';
        aud.onerror=()=>{ outputEl.innerHTML='<div class="studio-status">⚠️ Audio failed to load. Try another prompt.</div>'; };

        const info=document.createElement('div');
        info.style.cssText='font-size:10px;color:var(--muted);text-align:center;margin-top:4px';
        info.textContent='✅ Zero API key · Royalty-Free CDN · Plays instantly';

        const dlBtn=document.createElement('a');
        dlBtn.className='studio-dl-btn'; dlBtn.innerHTML='⬇️ Download Audio';
        dlBtn.href=data.url; dlBtn.target='_blank'; dlBtn.download='panda_audio.mp3';

        outputEl.appendChild(lbl); outputEl.appendChild(cat); outputEl.appendChild(aud);
        outputEl.appendChild(info); outputEl.appendChild(dlBtn);
    }
}

/**
 * Push a media card to the chat bubble after generation.
 * Image → <img>
 * Video → <video> player
 * Audio → <audio> player
 * All have a Download button.
 */
function pushMediaToChat(data, prompt){
    const w=document.getElementById('welcome'); if(w) w.remove();
    const box=chatBox(); if(!box) return;

    const row=document.createElement('div'); row.className='msg-row ai';
    const av=document.createElement('div'); av.className='avatar panda'; av.textContent='🐼';
    row.appendChild(av);

    const mc=document.createElement('div'); mc.className='msg-content';
    const card=document.createElement('div'); card.className='media-bubble-card';

    // Header
    const hdr=document.createElement('div'); hdr.className='media-bubble-header';
    const typeLabels={image:'🖼️ Generated Image',video:'🎥 Generated Video',audio:'🎵 Generated Audio'};
    const srcLabels={cloudflare:'⚡ CF Workers AI',unsplash:'📷 Unsplash',pexels:'🎞 Pexels',pixabay:'🎵 Pixabay',cdn:'🎵 CDN Library'};
    hdr.innerHTML=`<span>${typeLabels[data.type]||'🎨 Media'}</span><span style="font-size:9px;opacity:.7">${srcLabels[data.source]||''}</span>`;
    card.appendChild(hdr);

    const body=document.createElement('div'); body.className='media-bubble-body';

    if(data.type==='image'){
        const img=document.createElement('img');
        if(data.b64) img.src=`data:${data.mime||'image/png'};base64,${data.b64}`;
        else img.src=data.url;
        img.alt=prompt; img.loading='lazy';
        const dlBtn=document.createElement('a'); dlBtn.className='media-dl-btn';
        dlBtn.innerHTML='⬇️ Download';
        dlBtn.onclick=e=>{e.preventDefault();data.b64?downloadFromBase64(data.b64,data.mime||'image/png','panda_image.png'):downloadFromUrl(data.url,'panda_image.jpg');};
        body.appendChild(img); body.appendChild(dlBtn);

    }else if(data.type==='video'){
        const vid=document.createElement('video');
        vid.src=data.url; vid.controls=true; vid.muted=true; vid.loop=true;
        if(data.thumb){vid.poster=data.thumb;}
        const dlBtn=document.createElement('a'); dlBtn.className='media-dl-btn';
        dlBtn.innerHTML='⬇️ Download Video';
        dlBtn.onclick=e=>{e.preventDefault();downloadFromUrl(data.url,'panda_video.mp4');};
        body.appendChild(vid); body.appendChild(dlBtn);

    }else if(data.type==='audio'){
        const lbl=document.createElement('div');
        lbl.style.cssText='font-size:11px;font-weight:700;color:var(--accent);margin-bottom:4px';
        lbl.textContent=`🎵 "${data.title||prompt}"`;
        const cat=document.createElement('div');
        cat.style.cssText='font-size:9px;color:var(--muted);margin-bottom:6px';
        cat.textContent=`${(data.category||'ambient').toUpperCase()} · CDN Library`;
        const aud=document.createElement('audio');
        aud.src=data.url; aud.controls=true;
        aud.onerror=()=>{ aud.insertAdjacentHTML('afterend','<div style="color:var(--muted);font-size:11px;margin-top:4px">⚠️ Audio playback failed</div>'); };
        const dlBtn=document.createElement('a'); dlBtn.className='media-dl-btn';
        dlBtn.innerHTML='⬇️ Download'; dlBtn.href=data.url;
        dlBtn.target='_blank'; dlBtn.download='panda_audio.mp3';
        body.appendChild(lbl); body.appendChild(cat); body.appendChild(aud); body.appendChild(dlBtn);
    }

    card.appendChild(body); mc.appendChild(card);
    addMsgActions(mc, `Generated ${data.type}: ${prompt}`);
    row.appendChild(mc); box.appendChild(row); scrollToBottom();
}

// ════════════════════════════════════════
// MODALS
// ════════════════════════════════════════
function openModal(id){const m=$(id);if(m)m.classList.add('show');sidebarEl()&&sidebarEl().classList.remove('open');}
function closeModal(id){const m=$(id);if(m)m.classList.remove('show');}

// ════════════════════════════════════════
// TASKS
// ════════════════════════════════════════
async function saveTask(){
    const nameEl=$('task-name'),timeEl=$('task-time');
    const name=nameEl?nameEl.value.trim():''; if(!name){alert('Enter a task');return;}
    await fetch('/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task:name,remind_at:timeEl?timeEl.value:''})});
    if(nameEl)nameEl.value='';if(timeEl)timeEl.value=''; loadTasksList();
}
async function loadTasksList(){
    const list=$('task-list'); if(!list) return;
    try{
        const res=await fetch('/tasks');const data=await res.json();const tasks=data.tasks||[];
        if(!tasks.length){list.innerHTML='<div class="no-tasks">No tasks yet!</div>';return;}
        list.innerHTML=tasks.map(t=>`<div class="task-item ${t.done?'done':''}">
            <div class="task-item-text"><div>${escHtml(t.task)}</div>${t.remind_at?`<div class="task-item-time">⏰ ${new Date(t.remind_at).toLocaleString()}</div>`:''}</div>
            ${!t.done?`<button class="task-done-btn" onclick="markTaskDone(${t.id})">✓</button>`:'<span style="color:#4a9e6b">✓</span>'}
            <button class="task-del-btn" onclick="deleteTask(${t.id})">✕</button></div>`).join('');
    }catch{list.innerHTML='<div class="no-tasks">Error loading.</div>';}
}
async function markTaskDone(id){await fetch(`/tasks/${id}/done`,{method:'POST'});loadTasksList();}
async function deleteTask(id){await fetch(`/tasks/${id}`,{method:'DELETE'});loadTasksList();}

// ════════════════════════════════════════
// SESSIONS
// ════════════════════════════════════════
function startSession(){sessionId='sess_'+Date.now()+'_'+Math.random().toString(36).slice(2,7);currentMessages=[];currentSession={id:sessionId,title:'New Chat',messages:[],ts:Date.now()};chatSessions.unshift(currentSession);persistSessions();renderChatList();if(topbarTitle())topbarTitle().textContent='New Chat';}
function persistSessions(){if(currentSession){currentSession.messages=[...currentMessages];currentSession.ts=Date.now();}try{localStorage.setItem('pandaSessions',JSON.stringify(chatSessions.slice(0,30)));}catch{}}
function loadSession(id){
    showChat();
    const s=chatSessions.find(s=>s.id===id);if(!s)return;currentSession=s;sessionId=s.id;currentMessages=s.messages?[...s.messages]:[];const box=chatBox();if(box){box.innerHTML='';currentMessages.forEach(m=>appendMessage(m.role,m.content));}if(topbarTitle())topbarTitle().textContent=s.title||'Chat';renderChatList();sidebarEl()&&sidebarEl().classList.remove('open');
}
function deleteSession(id){chatSessions=chatSessions.filter(s=>s.id!==id);persistSessions();if(currentSession&&currentSession.id===id){currentSession=null;currentMessages=[];const box=chatBox();if(box)box.innerHTML=buildWelcomeHTML();}renderChatList();}
function renderChatList(){const cl=chatList();if(!cl)return;if(!chatSessions.length){cl.innerHTML='<div class="no-chats">No chats yet 🐼<br>Start a new chat!</div>';return;}cl.innerHTML=chatSessions.map(s=>`<div class="chat-item ${currentSession&&currentSession.id===s.id?'active':''}" onclick="loadSession('${s.id}')"><span class="chat-item-icon">💬</span><div class="chat-item-text"><div class="chat-item-title">${escHtml(s.title||'New Chat')}</div><div class="chat-item-time">${new Date(s.ts).toLocaleDateString()}</div></div><button class="chat-item-del" onclick="event.stopPropagation();deleteSession('${s.id}')">🗑</button></div>`).join('');}

function buildWelcomeHTML(){
    return `<div id="welcome" style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:16px;text-align:center;padding:20px">
        <div class="welcome-icon">🐼</div>
        <h2 style="font-family:'Comfortaa',cursive;font-size:38px;color:var(--black)">Panda AI V8 Studio</h2>
        <p style="color:var(--muted);font-size:14px;max-width:440px;line-height:1.7">Real-time AI · Deep Search · IST-aware · 🖼️ Image · 🎥 Video · 🎵 Audio 🎋</p>
        <div id="weather-widget" onclick="loadWeather()" title="Click to refresh"
             style="background:var(--glass-bg);backdrop-filter:var(--glass-blur);border:1.5px solid var(--glass-border);border-radius:18px;padding:14px 22px;display:flex;align-items:center;gap:16px;cursor:pointer;position:relative;min-width:210px;box-shadow:var(--glass-shadow)">
            <div class="w-emoji" id="w-emoji">🌡️</div>
            <div class="w-info">
                <div class="w-temp" id="w-temp">--°C</div>
                <div class="w-desc" id="w-desc">Loading...</div>
                <div class="w-city" id="w-city">📍 Detecting...</div>
            </div>
        </div>
        <div class="web-badge">🌐 Deep Search · 🖼️ CF Image · 🎥 Pexels · 🎵 Pixabay</div>
        <div class="chips">
            <div class="chip" onclick="quickSend(this)">Today's IPL score 🏏</div>
            <div class="chip" onclick="quickSend(this)">Write Python code 🐍</div>
            <div class="chip" onclick="quickSend(this)">Latest India news 📰</div>
            <div class="chip" onclick="quickSend(this)">Tell me a fun fact 🎯</div>
        </div>
    </div>`;
}

function newChat(){
    showChat();
    const box=chatBox();if(box)box.innerHTML=buildWelcomeHTML();startSession();pendingFiles=[];updateFilePreview();userInput()&&userInput().focus();sidebarEl()&&sidebarEl().classList.remove('open');setTimeout(loadWeather,600);
}

// ════════════════════════════════════════
// V8.4 MODULES: MAIL, PAD, STUDY
// ════════════════════════════════════════

// ──── CONTAINER VISIBILITY MANAGEMENT ────
/**
 * Switch views cleanly: hide ALL view containers, show only the target, 
 * and manage active state for sidebar tab buttons.
 * @param {string} viewId - The ID of the view container to show (e.g., 'chat-container', 'mail-container')
 */
function switchView(viewId){
    // Hide all view containers
    document.querySelectorAll('.view-container').forEach(container => {
        container.style.display = 'none';
    });
    
    // Show the target view
    const targetView = $(viewId);
    if(targetView){
        targetView.style.display = 'flex';
    }
    
    // Update active tab button states
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if(btn.getAttribute('data-view') === viewId){
            btn.classList.add('active');
        }
    });
    
    // Update topbar title
    const titleEl = $('topbar-title');
    if(titleEl){
        const labelMap = {
            'chat-container': 'New Chat',
            'mail-container': '✉️ Panda Mail',
            'pad-container': '📝 Panda Pad',
            'study-container': '🎓 Study Buddy'
        };
        titleEl.textContent = labelMap[viewId] || 'Panda AI';
    }
}

/**
 * Legacy function for backward compatibility — shows chat
 */
function showChat(){
    switchView('chat-container');
}

// ──── PANDA MAIL ────
function toggleMailMode(){
    currentMailMode = currentMailMode === 'pitch' ? 'draft' : 'pitch';
    const btn = $('mail-mode-toggle');
    const pitchForm = $('mail-pitch-form');
    const draftForm = $('mail-draft-form');
    
    if(currentMailMode === 'pitch'){
        if(btn) btn.textContent = '📧 Pitch Mode';
        if(pitchForm) pitchForm.style.display = 'flex';
        if(draftForm) draftForm.style.display = 'none';
    } else {
        if(btn) btn.textContent = '✍️ Draft Mode';
        if(pitchForm) pitchForm.style.display = 'none';
        if(draftForm) draftForm.style.display = 'flex';
    }
}

async function generateMail(mode){
    const output = $('mail-output');
    const outputText = $('mail-output-text');
    if(!output || !outputText) return;
    
    let payload = {};
    
    if(mode === 'pitch'){
        payload = {
            sender_name: $('mail-sender-name')?.value || '',
            sender_role: $('mail-sender-role')?.value || '',
            sender_skills: $('mail-sender-skills')?.value || '',
            sender_project: $('mail-sender-project')?.value || '',
            target_job: $('mail-target-job')?.value || '',
            recipient: $('mail-recipient')?.value || ''
        };
    } else {
        payload = {
            subject: $('mail-subject')?.value || '',
            context: $('mail-context')?.value || '',
            tone: $('mail-tone')?.value || 'formal'
        };
    }
    
    outputText.textContent = '⏳ Generating email...';
    output.style.display = 'block';
    
    try{
        const res = await fetch('/mail/generate',{
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mode, ...payload})
        });
        const data = await res.json();
        
        if(data.error){
            outputText.textContent = '⚠️ ' + data.error;
        } else {
            outputText.textContent = data.email || 'No email generated.';
        }
    }catch(e){
        console.error('Mail generation error:', e);
        outputText.textContent = '⚠️ Network error. Please try again.';
    }
}

function copyMailToClipboard(){
    const text = $('mail-output-text');
    if(!text) return;
    const content = text.textContent;
    if(!content || content.startsWith('⏳') || content.startsWith('⚠️')) return;
    
    navigator.clipboard.writeText(content).then(()=>{
        const btn = $('mail-copy-btn');
        if(btn){
            const original = btn.textContent;
            btn.textContent = '✅ Copied!';
            setTimeout(()=>{ btn.textContent = original; }, 2000);
        }
    });
}

// ──── PANDA PAD ────
let padDebounceTimer;
let padSaveTimeout;

async function savePad(){
    clearTimeout(padDebounceTimer);
    padDebounceTimer = setTimeout(async ()=>{
        const textarea = $('pad-textarea');
        const status = $('pad-status');
        
        if(!textarea) return;
        const content = textarea.value;
        
        if(status) status.innerHTML = '<span style="width:6px;height:6px;border-radius:50%;background:var(--accent);animation:blink 2s infinite"></span><span>Saving...</span>';
        
        try{
            await fetch('/pad/save',{
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({content, session_id: sessionId})
            });
            
            if(status){
                status.innerHTML = '<span style="width:6px;height:6px;border-radius:50%;background:#4ade80"></span><span>Saved</span>';
                clearTimeout(padSaveTimeout);
                padSaveTimeout = setTimeout(()=>{
                    if(status) status.innerHTML = '<span style="width:6px;height:6px;border-radius:50%;background:#4ade80;animation:blink 2s infinite"></span><span>Draft</span>';
                }, 2000);
            }
        }catch(e){
            console.error('Pad save error:', e);
            if(status) status.innerHTML = '<span style="width:6px;height:6px;border-radius:50%;background:#ef4444"></span><span>Error</span>';
        }
    }, 1500);
}

async function loadPad(){
    try{
        const res = await fetch('/pad/load?session_id=' + sessionId);
        const data = await res.json();
        const textarea = $('pad-textarea');
        if(textarea && data.content){
            textarea.value = data.content;
        }
    }catch(e){
        console.error('Pad load error:', e);
    }
}

// ──── STUDY BUDDY ────
function switchStudyMode(mode){
    currentStudyMode = mode;
    const tutorBtn = $('study-mode-tutor');
    const summaryBtn = $('study-mode-summary');
    const tutorForm = $('study-tutor-form');
    const summaryForm = $('study-summary-form');
    
    if(mode === 'tutor'){
        if(tutorBtn) tutorBtn.style.background = 'rgba(34,197,94,0.15)';
        if(summaryBtn) summaryBtn.style.background = 'rgba(100,116,139,0.15)';
        if(tutorForm) tutorForm.style.display = 'flex';
        if(summaryForm) summaryForm.style.display = 'none';
    } else {
        if(tutorBtn) tutorBtn.style.background = 'rgba(34,197,94,0.07)';
        if(summaryBtn) summaryBtn.style.background = 'rgba(100,116,139,0.15)';
        if(tutorForm) tutorForm.style.display = 'none';
        if(summaryForm) summaryForm.style.display = 'flex';
    }
}

async function askTutor(){
    const question = $('study-question')?.value || '';
    const subject = $('study-subject')?.value || '';
    const level = $('study-level')?.value || 'intermediate';
    
    if(!question.trim()){
        alert('Please ask a question!');
        return;
    }
    
    const results = $('study-results');
    const resultsContent = $('study-results-content');
    
    if(results && resultsContent){
        resultsContent.textContent = '⏳ Getting your answer...';
        results.style.display = 'block';
    }
    
    try{
        const res = await fetch('/study/ask',{
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({question, subject, level})
        });
        const data = await res.json();
        
        if(resultsContent){
            if(data.error){
                resultsContent.textContent = '⚠️ ' + data.error;
            } else {
                resultsContent.innerHTML = renderMd(data.answer || 'No answer generated.');
            }
        }
    }catch(e){
        console.error('Tutor error:', e);
        if(resultsContent) resultsContent.textContent = '⚠️ Network error. Please try again.';
    }
}

async function generateStudySummary(){
    const topic = $('study-topic')?.value || '';
    const subject = $('study-topic-subject')?.value || '';
    const format = $('study-format')?.value || 'bullets';
    
    if(!topic.trim()){
        alert('Please enter a topic!');
        return;
    }
    
    const results = $('study-results');
    const resultsContent = $('study-results-content');
    
    if(results && resultsContent){
        resultsContent.textContent = '⏳ Building summary...';
        results.style.display = 'block';
    }
    
    try{
        const res = await fetch('/study/summarize',{
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({topic, subject, format})
        });
        const data = await res.json();
        
        if(resultsContent){
            if(data.error){
                resultsContent.textContent = '⚠️ ' + data.error;
            } else {
                resultsContent.innerHTML = renderMd(data.summary || 'No summary generated.');
            }
        }
    }catch(e){
        console.error('Summary error:', e);
        if(resultsContent) resultsContent.textContent = '⚠️ Network error. Please try again.';
    }
}

function copyStudyResult(){
    const content = $('study-results-content');
    if(!content) return;
    
    const text = content.innerText;
    if(!text || text.startsWith('⏳') || text.startsWith('⚠️')) return;
    
    navigator.clipboard.writeText(text).then(()=>{
        const btn = $('study-copy-btn');
        if(btn){
            const original = btn.textContent;
            btn.textContent = '✅ Copied!';
            setTimeout(()=>{ btn.textContent = original; }, 2000);
        }
    });
}

// ════════════════════════════════════════
// EVENT LISTENERS
// ════════════════════════════════════════
document.addEventListener('DOMContentLoaded',()=>{
    checkFirstVisit();
    sendBtn()&&sendBtn().addEventListener('click',()=>sendMessage());
    const inp=userInput();
    if(inp){inp.addEventListener('input',function(){this.style.height='auto';this.style.height=Math.min(this.scrollHeight,130)+'px';});inp.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}});inp.focus();}
    $('theme-toggle')&&$('theme-toggle').addEventListener('click',()=>{const cur=document.documentElement.getAttribute('data-theme');const nxt=cur==='dark'?'light':'dark';document.documentElement.setAttribute('data-theme',nxt);localStorage.setItem('pandaTheme',nxt);$('theme-toggle').textContent=nxt==='dark'?'☀️':'🌙';});
    const st=$('sidebar-toggle'),sd=sidebarEl();
    if(st&&sd){st.addEventListener('click',()=>sd.classList.toggle('open'));document.addEventListener('click',e=>{if(sd.classList.contains('open')&&!sd.contains(e.target)&&e.target!==st)sd.classList.remove('open');});}
    $('new-chat-btn')&&$('new-chat-btn').addEventListener('click',()=>{newChat();switchView('chat-container');});
    $('tasks-btn')&&$('tasks-btn').addEventListener('click',()=>{openModal('tasks-modal');loadTasksList();});
    $('studio-btn')&&$('studio-btn').addEventListener('click',()=>openStudio('image'));
    $('news-btn')&&$('news-btn').addEventListener('click',()=>toggleNews());
    
    // V8.4: New module tab buttons — clean view switching with active state
    $('mail-btn')&&$('mail-btn').addEventListener('click',()=>{switchView('mail-container');sidebarEl()&&sidebarEl().classList.remove('open');});
    $('pad-btn')&&$('pad-btn').addEventListener('click',()=>{switchView('pad-container');loadPad();sidebarEl()&&sidebarEl().classList.remove('open');});
    $('study-btn')&&$('study-btn').addEventListener('click',()=>{switchView('study-container');sidebarEl()&&sidebarEl().classList.remove('open');});
    
    // Mail mode toggle
    $('mail-mode-toggle')&&$('mail-mode-toggle').addEventListener('click',toggleMailMode);
    
    // Pad auto-save
    const padTextarea = $('pad-textarea');
    if(padTextarea){
        padTextarea.addEventListener('input', savePad);
    }
    
    // Chat button from containers (implicit — clicking new-chat-btn or other chat actions)
    // Back to chat by clicking "New Chat" button
    
    ['tasks-modal','studio-modal','news-modal'].forEach(id=>{const m=$(id);if(m)m.addEventListener('click',e=>{if(e.target===m)closeModal(id);});});
    $('tts-btn')&&$('tts-btn').addEventListener('click',()=>{ttsEnabled=!ttsEnabled;const tb=$('tts-btn');if(tb){tb.style.background=ttsEnabled?'rgba(74,158,107,0.15)':'';tb.style.borderColor=ttsEnabled?'var(--accent)':'';}if(!ttsEnabled&&window.speechSynthesis)window.speechSynthesis.cancel();});
    $('voice-btn')&&$('voice-btn').addEventListener('click',toggleVoice);
    const ub=$('upload-btn'),fi=$('file-input');
    if(ub&&fi){
        ub.addEventListener('click',()=>fi.click());
        fi.addEventListener('change',e=>{const files=Array.from(e.target.files);if(files.length){pendingFiles=[...pendingFiles,...files];updateFilePreview();const i=userInput();if(i){i.placeholder='Ask about the file...';i.focus();}}});
        const box=chatBox();
        if(box){box.addEventListener('dragover',e=>{e.preventDefault();box.style.outline='2px dashed var(--accent)';});box.addEventListener('dragleave',()=>{box.style.outline='';});box.addEventListener('drop',e=>{e.preventDefault();box.style.outline='';const files=Array.from(e.dataTransfer.files);if(files.length){pendingFiles=[...pendingFiles,...files];updateFilePreview();}});}
    }
    setTimeout(loadWeather,800);
    setInterval(async()=>{try{const res=await fetch('/tasks/due');const data=await res.json();if(data.tasks&&data.tasks.length&&'Notification'in window){data.tasks.forEach(t=>{if(Notification.permission==='granted')new Notification('🐼 Panda AI Reminder',{body:t.task});});}}catch{}},60000);
    if('Notification'in window&&Notification.permission==='default')Notification.requestPermission();
});