const connectBtn = document.getElementById('connect-btn');
const connectOverlay = document.getElementById('connect-overlay');
const statusPill = document.getElementById('status-pill');
const transcriptContainer = document.getElementById('transcript-container');
const connectionDot = document.getElementById('connection-dot');
const errorMsg = document.getElementById('error-message');
const audioElement = document.getElementById('agent-audio');
const canvas = document.getElementById('waveform-canvas');
const ctxCanvas = canvas.getContext('2d');

let room;
let audioContext;
let analyser;
let dataArray;
let animationId;

function resizeCanvas() {
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

connectBtn.addEventListener('click', async () => {
  try {
    errorMsg.classList.add('hidden');
    connectBtn.disabled = true;
    connectBtn.textContent = 'Connecting...';
    
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
    await room.localParticipant.setMicrophoneEnabled(true);
    
    setupAudioContext();
    
    connectOverlay.classList.add('hidden');
    connectionDot.classList.remove('disconnected');
    connectionDot.classList.add('connected');
    
    showStatus('Listening...', true);
    
  } catch (err) {
    console.error(err);
    errorMsg.textContent = err.message;
    errorMsg.classList.remove('hidden');
    connectBtn.disabled = false;
    connectBtn.textContent = 'Connect';
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
    }
  });

  room.on(LivekitClient.RoomEvent.Disconnected, () => {
    connectionDot.classList.add('disconnected');
    connectionDot.classList.remove('connected');
    connectOverlay.classList.remove('hidden');
    connectBtn.disabled = false;
    connectBtn.textContent = 'Connect';
    errorMsg.textContent = 'Disconnected from server.';
    errorMsg.classList.remove('hidden');
    cancelAnimationFrame(animationId);
  });
}

function handleStatusEvent(evt) {
  const kind = evt.event;
  if (kind === 'tool_start') {
    const label = evt.tool === 'query_runbook_rag' ? 'Searching runbooks...' : `Checking ${evt.host || evt.tool}...`;
    showStatus(label, true);
  } else if (kind === 'tool_complete') {
    showStatus('Done', false);
    setTimeout(() => { showStatus('Listening...', true); }, 2000);
  } else if (kind === 'stale_discard') {
    showStatus('⚠ Discarded', false, 'var(--accent-muted)');
    appendStaleDiscard(evt.from_turn, evt.to_turn);
    setTimeout(() => { showStatus('Listening...', true); }, 2000);
  } else if (kind === 'tool_error') {
    showStatus(evt.error || 'Error', false, '#EF4444');
    setTimeout(() => { showStatus('Listening...', true); }, 3000);
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

function appendTranscript(role, text) {
  const div = document.createElement('div');
  div.className = `transcript-entry transcript-${role}`;
  
  const meta = document.createElement('div');
  meta.className = 'transcript-meta';
  const now = new Date();
  meta.textContent = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;
  
  const content = document.createElement('div');
  content.className = 'transcript-text';
  content.textContent = `${role === 'user' ? 'You' : 'Agent'}: ${text}`;
  
  div.appendChild(meta);
  div.appendChild(content);
  transcriptContainer.appendChild(div);
  
  transcriptContainer.parentElement.scrollTop = transcriptContainer.parentElement.scrollHeight;
}

function appendStaleDiscard(fromTurn, toTurn) {
  const div = document.createElement('div');
  div.className = 'transcript-stale';
  div.textContent = `⚠ stale result discarded (turn ${fromTurn} → turn ${toTurn})`;
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
  
  ctxCanvas.fillStyle = '#14110D';
  ctxCanvas.fillRect(0, 0, canvas.width, canvas.height);
  
  const barWidth = (canvas.width / dataArray.length) * 2.5;
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
    ctxCanvas.fillRect(x, canvas.height - scaledHeight, barWidth, scaledHeight);
    x += barWidth + 1;
  }
}
