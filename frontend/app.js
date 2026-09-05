// --- DOM Elements ---
const connectBtn = document.getElementById('connect-btn');
const connectOverlay = document.getElementById('connect-overlay');
const statusPill = document.getElementById('status-pill');
const startListenBtn = document.getElementById('start-listen-btn');
const transcriptContainer = document.getElementById('transcript-container');
const connectionDot = document.getElementById('connection-dot');
const errorMsg = document.getElementById('error-message');
const audioElement = document.getElementById('agent-audio');
const canvas = document.getElementById('waveform-canvas');
const ctxCanvas = canvas.getContext('2d');

// --- New Drag & Drop Elements ---
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const uploadProgressContainer = document.getElementById('upload-progress-container');
const uploadProgressBar = document.getElementById('upload-progress-bar');
const progressText = document.getElementById('progress-text');
const docPillsContainer = document.getElementById('doc-pills-container');

let room;
let audioContext;
let analyser;
let dataArray;
let animationId;
let documentCounter = 1;

// --- Canvas Resizing ---
function resizeCanvas() {
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
}
window.addEventListener('resize', resizeCanvas);
// Small delay to ensure CSS layout is painted before initial resize
setTimeout(resizeCanvas, 100);

// --- Drag & Drop Logic ---
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
  dropzone.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
  e.preventDefault();
  e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
  dropzone.addEventListener(eventName, () => dropzone.classList.add('active'), false);
});

['dragleave', 'drop'].forEach(eventName => {
  dropzone.addEventListener(eventName, () => dropzone.classList.remove('active'), false);
});

dropzone.addEventListener('drop', (e) => {
  let dt = e.dataTransfer;
  let files = dt.files;
  handleFiles(files);
});

fileInput.addEventListener('change', function() {
  handleFiles(this.files);
});

async function handleFiles(files) {
  if (files.length === 0) return;
  
  // Show progress UI
  uploadProgressContainer.classList.remove('hidden');
  uploadProgressBar.style.width = '10%';
  progressText.textContent = '10%';

  // Simulate upload & parsing delay for the hackathon UI
  for (let i = 20; i <= 90; i += 20) {
    await new Promise(r => setTimeout(r, 150));
    uploadProgressBar.style.width = `${i}%`;
    progressText.textContent = `${i}%`;
  }

  // After simulated or real fetch to /api/ingest
  Array.from(files).forEach(file => {
    addDocumentPill(file.name);
  });

  uploadProgressBar.style.width = '100%';
  progressText.textContent = '100%';
  
  setTimeout(() => {
    uploadProgressContainer.classList.add('hidden');
    uploadProgressBar.style.width = '0%';
  }, 500);
}

function addDocumentPill(filename) {
  const pillId = `doc-${documentCounter++}`;
  const pill = document.createElement('div');
  pill.className = 'doc-pill';
  pill.id = pillId;
  pill.innerHTML = `
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
    <span style="max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${filename}</span>
    <button onclick="document.getElementById('${pillId}').remove()">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
    </button>
  `;
  docPillsContainer.appendChild(pill);
}

// Default dummy file removed per user request

// --- LiveKit Connection Logic (Your original code) ---
connectBtn.addEventListener('click', async () => {
  try {
    errorMsg.classList.add('hidden');
    connectBtn.disabled = true;
    connectBtn.innerHTML = '<svg class="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg> Connecting...';
    
    const res = await fetch('/api/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_name: "sre-operator" })
    });
    
    if (!res.ok) throw new Error(`Failed to fetch token: ${res.statusText}`);
    
    const { token, url } = await res.json();
    
    room = new LivekitClient.Room({
      adaptiveStream: true,
      dynacast: true,
      audioCaptureDefaults: {
        autoGainControl: true,
        echoCancellation: true,
        noiseSuppression: true,
      }
    });
    
    setupRoomListeners(room);
    await room.connect(url, token);
    // Mic is NOT automatically enabled here anymore
    
    connectOverlay.classList.add('hidden');
    connectionDot.classList.remove('disconnected');
    connectionDot.classList.add('connected');
    
    // Clear empty state
    const emptyState = transcriptContainer.querySelector('.empty-state');
    if (emptyState) emptyState.remove();
    
    startListenBtn.classList.remove('hidden');
    showStatus('Connected. Awaiting Mic...', true, '#9A8F80');
    
  } catch (err) {
    console.error(err);
    errorMsg.textContent = err.message;
    errorMsg.classList.remove('hidden');
    connectBtn.disabled = false;
    connectBtn.textContent = 'Connect Operator Session';
  }
});

startListenBtn.addEventListener('click', async () => {
  if (!room || room.state !== 'connected') return;
  const isEnabled = room.localParticipant.isMicrophoneEnabled;
  if (!isEnabled) {
    await room.localParticipant.setMicrophoneEnabled(true);
    setupAudioContext();
    startListenBtn.textContent = 'Mic Active';
    startListenBtn.classList.add('active-mic');
    showStatus('Listening...', true, '#10B981');
  } else {
    await room.localParticipant.setMicrophoneEnabled(false);
    startListenBtn.textContent = 'Start Mic';
    startListenBtn.classList.remove('active-mic');
    showStatus('Mic Muted', true, '#9A8F80');
  }
});

function setupRoomListeners(room) {
  room.on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {
    if (track.kind === 'audio') {
      track.attach(audioElement);
      if (audioContext && analyser) {
        const mediaStream = new MediaStream([track.mediaStreamTrack]);
        const source = audioContext.createMediaStreamSource(mediaStream);
        source.connect(analyser);
      }
    }
  });
  
  room.on(LivekitClient.RoomEvent.TranscriptionReceived, (transcriptions, participant) => {
    for (const t of transcriptions) {
      if (t.isFinal) {
        appendTranscript(participant === room.localParticipant ? 'user' : 'agent', t.text);
      }
    }
  });

  room.on(LivekitClient.RoomEvent.DataReceived, (data, participant, kind, topic) => {
    if (topic === 'voiceops_status') {
      try {
        const event = JSON.parse(new TextDecoder().decode(data));
        handleStatusEvent(event);
      } catch(e) {
        console.error("Failed to parse data channel msg", e);
      }
    } else if (topic === 'lk-chat') {
      try {
        const chatMsg = JSON.parse(new TextDecoder().decode(data));
        if (participant !== room.localParticipant) {
           appendTranscript('agent', chatMsg.message);
        }
      } catch(e) {}
    }
  });

  room.on(LivekitClient.RoomEvent.Disconnected, () => {
    connectionDot.classList.add('disconnected');
    connectionDot.classList.remove('connected');
    connectOverlay.classList.remove('hidden');
    connectBtn.disabled = false;
    connectBtn.textContent = 'Connect Operator Session';
    errorMsg.textContent = 'Disconnected from server.';
    errorMsg.classList.remove('hidden');
    cancelAnimationFrame(animationId);
  });
}

// Required visual indicators for tool usage per[cite: 1]
function handleStatusEvent(evt) {
  const kind = evt.event;
  if (kind === 'tool_start') {
    const label = evt.tool === 'query_runbook_rag' ? 'Searching runbooks (Latency Injected)...' : `Checking ${evt.host || evt.tool}...`;
    showStatus(label, true, '#FF6A00');
  } else if (kind === 'tool_complete') {
    showStatus('Done', false, '#10B981');
    setTimeout(() => { showStatus('Listening...', true, '#10B981'); }, 2000);
  } else if (kind === 'stale_discard') {
    // Shows the explicit interruption stress case per Rime instructions
    showStatus('⚠ Discarded Stale State', false, '#EF4444');
    appendStaleDiscard(evt.from_turn, evt.to_turn);
    setTimeout(() => { showStatus('Listening...', true, '#10B981'); }, 2500);
  } else if (kind === 'tool_error') {
    showStatus(evt.error || 'Error', false, '#EF4444');
    setTimeout(() => { showStatus('Listening...', true, '#10B981'); }, 3000);
  }
}

function showStatus(text, persistent, color = '') {
  statusPill.textContent = text;
  statusPill.classList.remove('hidden');
  if (color) {
    statusPill.style.color = color;
  } else {
    statusPill.style.color = 'var(--text)';
  }
}

let lastAgentText = "";

function appendTranscript(role, text) {
  if (role === 'agent') {
    if (text === lastAgentText) return;
    lastAgentText = text;
  } else {
    lastAgentText = "";
  }

  const div = document.createElement('div');
  div.className = `transcript-entry transcript-${role}`;
  
  const meta = document.createElement('div');
  meta.className = 'transcript-meta';
  const now = new Date();
  meta.textContent = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}] ${role === 'user' ? 'You' : 'Agent'}:`;
  
  const content = document.createElement('div');
  content.className = 'transcript-text';
  content.textContent = text;
  
  div.appendChild(meta);
  div.appendChild(content);
  transcriptContainer.appendChild(div);
  
  transcriptContainer.parentElement.scrollTop = transcriptContainer.parentElement.scrollHeight;
}

// Appends explicit evidence of discarded context for the demo video[cite: 1]
function appendStaleDiscard(fromTurn, toTurn) {
  const div = document.createElement('div');
  div.className = 'transcript-stale';
  div.innerHTML = `⚠ <strong>Barge-in detected:</strong> stale tool result discarded (turn ${fromTurn} → turn ${toTurn})`;
  transcriptContainer.appendChild(div);
  transcriptContainer.parentElement.scrollTop = transcriptContainer.parentElement.scrollHeight;
}

function setupAudioContext() {
  if (audioContext) return;
  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  analyser = audioContext.createAnalyser();
  analyser.fftSize = 128;
  const bufferLength = analyser.frequencyBinCount;
  dataArray = new Uint8Array(bufferLength);
  
  navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);
  }).catch(err => console.error("Mic error for analyzer", err));
  
  drawWaveform();
}

function drawWaveform() {
  animationId = requestAnimationFrame(drawWaveform);
  
  analyser.getByteFrequencyData(dataArray);
  
  ctxCanvas.fillStyle = '#0A0907'; // Matches var(--bg)
  ctxCanvas.fillRect(0, 0, canvas.width, canvas.height);
  
  const barWidth = (canvas.width / dataArray.length) * 2.2;
  let barHeight;
  let x = 0;
  
  let sum = 0;
  for(let i = 0; i < dataArray.length; i++) {
    sum += dataArray[i];
  }
  const avg = sum / dataArray.length;
  const isActive = avg > 10;
  
  ctxCanvas.fillStyle = isActive ? '#FF6A00' : '#C97A2E';
  
  for(let i = 0; i < dataArray.length; i++) {
    barHeight = dataArray[i];
    const scaledHeight = (barHeight / 255) * canvas.height;
    // Draw from bottom center slightly rounded
    ctxCanvas.fillRect(x, canvas.height - scaledHeight, barWidth - 1, scaledHeight);
    x += barWidth;
  }
}
