// ── State ──────────────────────────────────────────────────────────────────
let messages = [];
let attachedFiles = [];
let currentModel = 'qwen2.5:1.5b';
let sessionId = newSessionId();
let isThinking = false;
let currentReader = null;
let recognition = null;
let isRecording = false;
let voiceSilenceTimer = null;     // For pause-detection
let voiceInterimText = '';        // Accumulates interim voice text

function newSessionId() {
  return 'sess-' + Math.random().toString(36).slice(2,10) + '-' + Date.now();
}

window.onload = () => { loadModels(); loadHistory(); initVoice(); };

// ── Markdown Renderer ──────────────────────────────────────────────────────
function renderMarkdown(text) {
  // Escape HTML first
  let t = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Fenced code blocks ```lang\n...\n```
  t = t.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const l = lang ? `<span class="code-lang">${lang}</span>` : '';
    return `<div class="code-block">${l}<button class="copy-btn" onclick="copyCode(this)">Copy</button><pre><code>${code.trim()}</code></pre></div>`;
  });

  // Inline code `code`
  t = t.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

  // Bold **text**
  t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Italic *text* or _text_
  t = t.replace(/\*(.+?)\*/g, '<em>$1</em>');
  t = t.replace(/_([^_]+)_/g, '<em>$1</em>');

  // Headers ### ## #
  t = t.replace(/^### (.+)$/gm, '<h4>$1</h4>');
  t = t.replace(/^## (.+)$/gm, '<h3>$1</h3>');
  t = t.replace(/^# (.+)$/gm, '<h2>$1</h2>');

  // Horizontal rule ---
  t = t.replace(/^---+$/gm, '<hr>');

  // Numbered list
  t = t.replace(/^\d+\. (.+)$/gm, '<li class="ol-item">$1</li>');
  t = t.replace(/(<li class="ol-item">[\s\S]*?<\/li>)+/g, m => `<ol>${m}</ol>`);

  // Bullet list - * +
  t = t.replace(/^[-*+] (.+)$/gm, '<li>$1</li>');
  t = t.replace(/(<li>[\s\S]*?<\/li>)+/g, m => {
    if (m.includes('ol-item')) return m;
    return `<ul>${m}</ul>`;
  });

  // Blockquote
  t = t.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

  // Line breaks (double newline = paragraph, single = <br>)
  t = t.replace(/\n\n/g, '</p><p>');
  t = t.replace(/\n/g, '<br>');
  t = `<p>${t}</p>`;

  // Clean empty paragraphs
  t = t.replace(/<p><\/p>/g, '');
  t = t.replace(/<p>(<[uo]l>|<h[2-4]>|<div|<pre|<hr|<blockquote)/g, '$1');
  t = t.replace(/(<\/[uo]l>|<\/h[2-4]>|<\/div>|<\/pre>|<hr>|<\/blockquote>)<\/p>/g, '$1');

  return t;
}

function copyCode(btn) {
  const code = btn.nextElementSibling.textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy', 1500);
  });
}

// ── Models ─────────────────────────────────────────────────────────────────
async function loadModels() {
  try {
    const r = await fetch('/models');
    const data = await r.json();
    const dd = document.getElementById('model-dropdown');
    const effort = m =>
      m.includes('0.5') ? '⚡ Tiny' :
      m.includes('1.5') ? '⚡ Fastest' :
      m.includes('3b')  ? '🚀 Fast' :
      m.includes('7b')  ? '🧠 Smart' : '⚖️ Balanced';
    dd.innerHTML = data.models.map(m =>
      `<div class="model-option" onclick="selectModel('${m}')">${m}<span class="model-effort">${effort(m)}</span></div>`
    ).join('');
    const preferred = data.models.find(m => m.includes('1.5')) ||
                      data.models.find(m => m.includes('3b')) ||
                      data.models[0];
    if (preferred) selectModel(preferred);
  } catch(e) {}
}

function toggleModelDropdown(e) {
  e.stopPropagation();
  document.getElementById('model-dropdown').classList.toggle('open');
}
function selectModel(model) {
  currentModel = model;
  document.getElementById('model-label').textContent = model;
  document.getElementById('model-dropdown').classList.remove('open');
  document.querySelectorAll('.model-option').forEach(el =>
    el.classList.toggle('active', el.textContent.trim().startsWith(model))
  );
}
document.addEventListener('click', () =>
  document.getElementById('model-dropdown').classList.remove('open')
);

// ── Sidebar & Theme ────────────────────────────────────────────────────────
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('collapsed');
}
function toggleTheme() {
  document.body.classList.toggle('light');
  document.getElementById('theme-toggle').classList.toggle('on');
}

// ── Signup ─────────────────────────────────────────────────────────────────
function showSignup() { document.getElementById('signup-modal').classList.remove('hidden'); }
function closeSignup() { document.getElementById('signup-modal').classList.add('hidden'); }
function doSignup() {
  const name = document.getElementById('signup-name').value.trim();
  const email = document.getElementById('signup-email').value.trim();
  if (!name || !email) { alert('Please fill name and email.'); return; }
  document.querySelector('.user-name').textContent = name;
  document.querySelector('.user-avatar').textContent = name[0].toUpperCase();
  closeSignup();
}

// ── Voice Input (with pause detection) ────────────────────────────────────
// Instead of sending immediately on result, we wait for a 1.5s pause in speech.
// This gives you time to finish your sentence naturally.
function initVoice() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    document.getElementById('mic-btn').style.display = 'none';
    return;
  }
  recognition = new SpeechRecognition();
  recognition.continuous = true;        // Keep listening continuously
  recognition.interimResults = true;    // Show partial results while speaking
  recognition.lang = 'en-US';

  recognition.onresult = (e) => {
    let interimTranscript = '';
    let finalTranscript = '';

    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript;
      if (e.results[i].isFinal) {
        finalTranscript += t;
      } else {
        interimTranscript += t;
      }
    }

    // Show what's being heard in the input box
    const input = document.getElementById('user-input');
    const displayText = (voiceInterimText + finalTranscript + interimTranscript).trim();
    input.value = displayText;
    autoResize(input);

    if (finalTranscript) {
      voiceInterimText += finalTranscript;
    }

    // Reset the silence timer on every new speech
    clearTimeout(voiceSilenceTimer);

    // After 1.5 seconds of silence, send the message
    voiceSilenceTimer = setTimeout(() => {
      const text = input.value.trim();
      if (text && isRecording) {
        stopRecording();
        sendMessage();
      }
    }, 1500);
  };

  recognition.onerror = (e) => {
    if (e.error !== 'no-speech') stopRecording();
  };

  recognition.onend = () => {
    // Restart if still in recording mode (browser auto-stops after silence)
    if (isRecording) {
      try { recognition.start(); } catch(e) {}
    }
  };
}

function toggleVoice() {
  if (!recognition) return;
  if (isRecording) {
    clearTimeout(voiceSilenceTimer);
    recognition.stop();
    stopRecording();
  } else {
    voiceInterimText = '';
    document.getElementById('user-input').value = '';
    recognition.start();
    startRecording();
  }
}

function startRecording() {
  isRecording = true;
  const btn = document.getElementById('mic-btn');
  btn.classList.add('recording');
  btn.textContent = '⏹';
  document.getElementById('user-input').placeholder = '🎤 Listening... (pause to send)';
}

function stopRecording() {
  isRecording = false;
  clearTimeout(voiceSilenceTimer);
  voiceInterimText = '';
  const btn = document.getElementById('mic-btn');
  btn.classList.remove('recording');
  btn.textContent = '🎤';
  document.getElementById('user-input').placeholder = 'Message Awura AI...';
}

// ── History ────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const r = await fetch('/history');
    renderHistory(await r.json());
  } catch(e) {}
}
function renderHistory(items) {
  const list = document.getElementById('history-list');
  if (!items.length) {
    list.innerHTML = '<div style="font-size:12px;color:var(--text2);padding:4px 6px">No chats yet</div>';
    return;
  }
  list.innerHTML = items.map(item => `
    <div class="history-item" id="hist-${item.id}" onclick="loadChatHistory('${item.id}','${escAttr(item.title)}')">
      <span class="history-title">💬 ${escHtml(item.title)}</span>
      <button class="history-del" onclick="deleteChatHistory(event,'${item.id}')">✕</button>
    </div>`).join('');
}
async function loadChatHistory(id, title) {
  try {
    const r = await fetch(`/history/${id}`);
    const data = await r.json();
    if (!data.messages) return;
    const parsed = JSON.parse(data.messages);
    messages = parsed; sessionId = id;
    document.getElementById('chat-title').textContent = title;
    document.getElementById('welcome')?.remove();
    const el = document.getElementById('messages');
    el.innerHTML = '';
    parsed.forEach(m => {
      if (m.role !== 'system') addBubble(m.role === 'user' ? 'user' : 'ai', m.content);
    });
    document.querySelectorAll('.history-item').forEach(e => e.classList.remove('active'));
    document.getElementById('hist-' + id)?.classList.add('active');
  } catch(e) {}
}
async function deleteChatHistory(e, id) {
  e.stopPropagation();
  await fetch(`/history/${id}`, { method: 'DELETE' });
  loadHistory();
  if (sessionId === id) newChat();
}
async function saveCurrentChat() {
  if (!messages.length) return;
  const title = messages[0]?.content?.slice(0,40) || 'Chat';
  await fetch('/history/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, title, messages: JSON.stringify(messages) })
  });
  loadHistory();
}

// ── New Chat ───────────────────────────────────────────────────────────────
function newChat() {
  messages = []; attachedFiles = [];
  sessionId = newSessionId();
  document.getElementById('chat-title').textContent = 'New Chat';
  document.getElementById('attached-bar').style.display = 'none';
  document.getElementById('attached-bar').innerHTML = '';
  document.getElementById('messages').innerHTML = `
    <div class="welcome" id="welcome">
      <div class="welcome-icon">✦</div>
      <h2>Awura AI Assistant</h2>
      <p>Runs fully on your device. Private, fast, no internet required.</p>
      <div class="chips">
        <div class="chip" onclick="sendChip('What time and date is it right now?')">🕐 Current time</div>
        <div class="chip" onclick="sendChip('Show me all employees in the database')">👥 Employees</div>
        <div class="chip" onclick="sendChip('What are the current projects?')">📋 Projects</div>
        <div class="chip" onclick="sendChip('Calculate 1234 * 56')">🧮 Calculate</div>
        <div class="chip" onclick="sendChip('Explain machine learning in simple terms')">🤖 AI concepts</div>
        <div class="chip" onclick="sendChip('Write a Python hello world function')">💻 Code</div>
      </div>
    </div>`;
  document.querySelectorAll('.history-item').forEach(e => e.classList.remove('active'));
}

// ── File Upload ────────────────────────────────────────────────────────────
async function attachFiles(files) {
  for (const file of files) {
    if (attachedFiles.includes(file.name)) continue;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await fetch('/upload', { method: 'POST', body: fd });
      attachedFiles.push((await r.json()).filename);
      renderAttachedBar();
    } catch(e) {}
  }
  document.getElementById('file-input').value = '';
}
function renderAttachedBar() {
  const bar = document.getElementById('attached-bar');
  if (!attachedFiles.length) { bar.style.display = 'none'; bar.innerHTML = ''; return; }
  bar.style.display = 'flex';
  bar.innerHTML = attachedFiles.map((f,i) =>
    `<div class="attached-chip">📄 ${escHtml(f)}<button onclick="removeAttached(${i})">✕</button></div>`
  ).join('');
}
function removeAttached(i) {
  fetch(`/upload/${encodeURIComponent(attachedFiles[i])}`, { method: 'DELETE' });
  attachedFiles.splice(i, 1);
  renderAttachedBar();
}

// ── Input Helpers ──────────────────────────────────────────────────────────
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 130) + 'px';
}
function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}
function sendChip(text) {
  document.getElementById('user-input').value = text;
  sendMessage();
}

// ── Stop ───────────────────────────────────────────────────────────────────
function stopGeneration() {
  currentReader?.cancel();
  currentReader = null;
  setThinking(false);
}
function setThinking(val) {
  isThinking = val;
  document.getElementById('send-btn').style.display = val ? 'none' : 'flex';
  const s = document.getElementById('stop-btn');
  s.style.display = val ? 'flex' : 'none';
  s.style.alignItems = 'center';
  s.style.justifyContent = 'center';
}

// ── Send Message ───────────────────────────────────────────────────────────
async function sendMessage() {
  const input = document.getElementById('user-input');
  const text = input.value.trim();
  if (!text || isThinking) return;

  document.getElementById('welcome')?.remove();
  if (!messages.length) document.getElementById('chat-title').textContent = text.slice(0,40);

  messages.push({ role: 'user', content: text });
  const fileLabel = attachedFiles.length ? ' 📎 ' + attachedFiles.join(', ') : '';
  addBubble('user', text + fileLabel);
  input.value = ''; input.style.height = 'auto';

  const sentFiles = [...attachedFiles];
  attachedFiles = [];
  renderAttachedBar();

  const thinkId = 'think-' + Date.now();
  addThinking(thinkId);
  setThinking(true);

  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: currentModel, messages, file_names: sentFiles, session_id: sessionId })
    });

    const reader = resp.body.getReader();
    currentReader = reader;
    const decoder = new TextDecoder();
    let aiText = '', bubbleEl = null;
    const thinkEl = document.getElementById(thinkId);

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of decoder.decode(value).split('\n')) {
          if (!line.startsWith('data: ')) continue;
          let data; try { data = JSON.parse(line.slice(6)); } catch { continue; }

          if (data.type === 'tool') {
            thinkEl?.remove();
            const wrap = document.createElement('div');
            wrap.className = 'msg ai';
            const did = 'det-' + thinkId;
            wrap.innerHTML = `
              <div class="avatar ai-av">✦</div>
              <div style="max-width:calc(100% - 44px)">
                <div class="tool-pill" onclick="document.getElementById('${did}').classList.toggle('show')">
                  ⚡ ${escHtml(data.tool)} <span style="opacity:.5;font-size:10px">▾</span>
                </div>
                <div class="tool-detail" id="${did}">${escHtml(data.result)}</div>
                <div class="bubble md-content" id="b-${thinkId}"></div>
              </div>`;
            document.getElementById('messages').appendChild(wrap);
            bubbleEl = document.getElementById('b-' + thinkId);
            scrollBottom();

          } else if (data.type === 'token') {
            if (!bubbleEl) {
              thinkEl?.remove();
              const d = document.createElement('div');
              d.className = 'msg ai';
              d.innerHTML = `<div class="avatar ai-av">✦</div><div class="bubble md-content" id="b-${thinkId}"></div>`;
              document.getElementById('messages').appendChild(d);
              bubbleEl = document.getElementById('b-' + thinkId);
            }
            aiText += data.content;
            // Show raw text while streaming (faster), render markdown on done
            bubbleEl.innerHTML = escHtml(aiText) + '<span class="cursor"></span>';
            scrollBottom();

          } else if (data.type === 'done') {
            if (bubbleEl) {
              // Render markdown on completion
              bubbleEl.innerHTML = renderMarkdown(aiText);
            }
            messages.push({ role: 'assistant', content: aiText });
            saveCurrentChat();

          } else if (data.type === 'error') {
            thinkEl?.remove();
            addBubble('ai', '❌ ' + data.content + '\n\nMake sure Ollama is running:\n  ollama serve');
          }
        }
      }
    } catch(e) {
      if (bubbleEl && aiText) {
        bubbleEl.innerHTML = renderMarkdown(aiText) + '<span style="color:var(--text2);font-size:11px"> [stopped]</span>';
      }
      document.getElementById(thinkId)?.remove();
    }
  } catch(e) {
    document.getElementById(thinkId)?.remove();
    addBubble('ai', '❌ Cannot connect to Ollama.\n\nRun this first:\n  ollama serve');
  }

  currentReader = null;
  setThinking(false);
  scrollBottom();
}

// ── UI Helpers ─────────────────────────────────────────────────────────────
function addBubble(role, text) {
  const msgs = document.getElementById('messages');
  const d = document.createElement('div');
  d.className = `msg ${role}`;
  if (role === 'user') {
    d.innerHTML = `<div class="avatar user-av">R</div><div class="bubble">${escHtml(text)}</div>`;
  } else {
    d.innerHTML = `<div class="avatar ai-av">✦</div><div class="bubble md-content">${renderMarkdown(text)}</div>`;
  }
  msgs.appendChild(d);
  scrollBottom();
}
function addThinking(id) {
  const msgs = document.getElementById('messages');
  const d = document.createElement('div');
  d.className = 'msg ai'; d.id = id;
  d.innerHTML = `<div class="avatar ai-av">✦</div>
    <div class="bubble thinking">
      <div class="dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
      <span>Thinking...</span>
    </div>`;
  msgs.appendChild(d);
  scrollBottom();
}
function escHtml(t) {
  return String(t)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/\n/g,'<br>');
}
function escAttr(t) {
  return String(t).replace(/'/g, "\\'").replace(/"/g, '&quot;');
}
function scrollBottom() {
  const m = document.getElementById('messages');
  m.scrollTop = m.scrollHeight;
}