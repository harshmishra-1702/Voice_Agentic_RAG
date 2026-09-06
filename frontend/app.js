/**
 * VoiceOps CyberOps Quantum HUD — Application Controller
 * Features:
 *  - 60fps Interactive Neural Particle Background Canvas
 *  - Dual-Mode Realtime Audio Visualizer (Quantum Spectrum & Holographic Reactor)
 *  - LiveKit WebRTC Full-Duplex Audio & Data Channel Routing
 *  - Procedural Web Audio SFX Synthesizer
 *  - Dynamic Knowledge Ingestion & ChromaDB Vector Store Management
 *  - Turn-Fencing Telemetry & Stale Discard Barge-in Indicators
 */

// ============================================================================
// 1. PROCEDURAL CYBER AUDIO SFX SYNTHESIZER
// ============================================================================

class CyberSoundEffects {
  constructor() {
    this.ctx = null;
    this.enabled = localStorage.getItem('voiceops_sfx_enabled') !== 'false';
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
  }

  toggle() {
    this.enabled = !this.enabled;
    localStorage.setItem('voiceops_sfx_enabled', this.enabled);
    return this.enabled;
  }

  playBlip(freq = 880, duration = 0.04) {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    try {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(freq * 1.5, this.ctx.currentTime + duration);

      gain.gain.setValueAtTime(0.08, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);

      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {}
  }

  playConnectChime() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    try {
      const now = this.ctx.currentTime;
      [523.25, 659.25, 783.99, 1046.50].forEach((freq, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, now + idx * 0.08);

        gain.gain.setValueAtTime(0.1, now + idx * 0.08);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.08 + 0.25);

        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now + idx * 0.08);
        osc.stop(now + idx * 0.08 + 0.25);
      });
    } catch (e) {}
  }

  playMicTone(active) {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    try {
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';

      const startFreq = active ? 440 : 880;
      const endFreq = active ? 880 : 440;

      osc.frequency.setValueAtTime(startFreq, now);
      osc.frequency.exponentialRampToValueAtTime(endFreq, now + 0.12);

      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);

      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.12);
    } catch (e) {}
  }

  playBargeInAlert() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    try {
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sawtooth';

      osc.frequency.setValueAtTime(320, now);
      osc.frequency.setValueAtTime(220, now + 0.1);
      osc.frequency.setValueAtTime(320, now + 0.2);

      gain.gain.setValueAtTime(0.15, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.35);
    } catch (e) {}
  }
}

const sfx = new CyberSoundEffects();

// ============================================================================
// 2. 60FPS INTERACTIVE NEURAL PARTICLE CANVAS ENGINE
// ============================================================================

class NeuralParticleBackground {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.particles = [];
    this.numParticles = window.innerWidth > 1400 ? 90 : 60;
    this.mouse = { x: -1000, y: -1000, radius: 140 };
    this.audioEnergy = 0; // modulated by audio visualizer

    this.init();
  }

  init() {
    this.resize();
    window.addEventListener('resize', () => this.resize());
    window.addEventListener('mousemove', (e) => {
      this.mouse.x = e.clientX;
      this.mouse.y = e.clientY;
    });
    window.addEventListener('mouseleave', () => {
      this.mouse.x = -1000;
      this.mouse.y = -1000;
    });

    this.createParticles();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    this.canvas.width = this.width;
    this.canvas.height = this.height;
  }

  createParticles() {
    this.particles = [];
    const colors = ['#38BDF8', '#7DD3FC', '#34D399', '#94A3B8'];
    for (let i = 0; i < this.numParticles; i++) {
      this.particles.push({
        x: Math.random() * this.width,
        y: Math.random() * this.height,
        vx: (Math.random() - 0.5) * 0.32,
        vy: (Math.random() - 0.5) * 0.32,
        radius: Math.random() * 1.8 + 0.8,
        color: colors[Math.floor(Math.random() * colors.length)],
        alpha: Math.random() * 0.35 + 0.15
      });
    }
  }

  setAudioEnergy(energy) {
    this.audioEnergy = energy; // 0.0 to 1.0
  }

  animate() {
    this.ctx.clearRect(0, 0, this.width, this.height);

    const speedMultiplier = 1 + this.audioEnergy * 1.5;

    // Update & draw particles
    for (let i = 0; i < this.particles.length; i++) {
      const p = this.particles[i];

      p.x += p.vx * speedMultiplier;
      p.y += p.vy * speedMultiplier;

      // Wrap boundaries
      if (p.x < 0) p.x = this.width;
      if (p.x > this.width) p.x = 0;
      if (p.y < 0) p.y = this.height;
      if (p.y > this.height) p.y = 0;

      // Gentle mouse interaction
      const dx = this.mouse.x - p.x;
      const dy = this.mouse.y - p.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < this.mouse.radius) {
        const force = (this.mouse.radius - dist) / this.mouse.radius;
        p.x -= (dx / dist) * force * 1.0;
        p.y -= (dy / dist) * force * 1.0;
      }

      // Draw particle dot
      this.ctx.beginPath();
      const radius = p.radius + this.audioEnergy * 0.8;
      this.ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
      this.ctx.fillStyle = p.color;
      this.ctx.globalAlpha = p.alpha + this.audioEnergy * 0.15;
      this.ctx.fill();

      // Connect subtle lines to nearby particles
      for (let j = i + 1; j < this.particles.length; j++) {
        const p2 = this.particles[j];
        const ldx = p.x - p2.x;
        const ldy = p.y - p2.y;
        const ldist = Math.sqrt(ldx * ldx + ldy * ldy);
        const maxDist = 110 + this.audioEnergy * 30;

        if (ldist < maxDist) {
          const lineAlpha = (1 - ldist / maxDist) * 0.12;
          this.ctx.beginPath();
          this.ctx.moveTo(p.x, p.y);
          this.ctx.lineTo(p2.x, p2.y);
          this.ctx.strokeStyle = '#38BDF8';
          this.ctx.globalAlpha = lineAlpha;
          this.ctx.lineWidth = 0.6;
          this.ctx.stroke();
        }
      }
    }

    this.ctx.globalAlpha = 1;
    requestAnimationFrame(this.animate);
  }
}

const bgAnimation = new NeuralParticleBackground('bg-canvas');

// ============================================================================
// 3. APPLICATION STATE & DOM REFERENCES
// ============================================================================

const DOM = {
  // Navigation & Badges
  headerTurnCounter: document.getElementById('header-turn-counter'),
  headerVectorStats: document.getElementById('header-vector-stats'),
  headerConnectBtn: document.getElementById('header-connect-btn'),
  headerConnectText: document.getElementById('header-connect-text'),
  connectionDot: document.getElementById('connection-dot'),
  connectionStatusText: document.getElementById('connection-status-text'),
  sfxToggleBtn: document.getElementById('sfx-toggle-btn'),
  sfxIconOn: document.getElementById('sfx-icon-on'),
  sfxIconOff: document.getElementById('sfx-icon-off'),

  // Modal Connect Overlay
  connectOverlay: document.getElementById('connect-overlay'),
  connectBtn: document.getElementById('connect-btn'),
  errorMsg: document.getElementById('error-message'),

  // Audio Telemetry & Visualizer
  waveformCanvas: document.getElementById('waveform-canvas'),
  holographicOverlay: document.getElementById('holographic-core-overlay'),
  statusPill: document.getElementById('status-pill'),
  agentStateDot: document.getElementById('agent-state-dot'),
  agentPausedBadge: document.getElementById('agent-paused-badge'),
  activeTurnVal: document.getElementById('active-turn-val'),
  startListenBtn: document.getElementById('start-listen-btn'),
  startListenText: document.getElementById('start-listen-text'),
  pauseAgentBtn: document.getElementById('pause-agent-btn'),
  pauseAgentText: document.getElementById('pause-agent-text'),
  pauseIconSvg: document.getElementById('pause-icon-svg'),
  playIconSvg: document.getElementById('play-icon-svg'),
  levelMeterBar: document.getElementById('level-meter-bar'),
  vizModeSpectrum: document.getElementById('viz-mode-spectrum'),
  vizModeRadar: document.getElementById('viz-mode-radar'),
  agentAudio: document.getElementById('agent-audio'),

  // Drag & Drop Ingestion
  dropzone: document.getElementById('dropzone'),
  fileInput: document.getElementById('file-input'),
  uploadProgressContainer: document.getElementById('upload-progress-container'),
  uploadProgressBar: document.getElementById('upload-progress-bar'),
  progressText: document.getElementById('progress-text'),
  docPillsContainer: document.getElementById('doc-pills-container'),
  refreshDocsBtn: document.getElementById('refresh-docs-btn'),

  // Transcript Stream
  transcriptContainer: document.getElementById('transcript-container'),
  clearTranscriptBtn: document.getElementById('clear-transcript-btn'),
  simulateBargeinBtn: document.getElementById('simulate-bargein-btn'),

  // Quick Prompt Chips
  promptChips: document.querySelectorAll('.prompt-chip')
};

// Application State
let room = null;
let audioContext = null;
let analyser = null;
let dataArray = null;
let animFrameId = null;
let visualizerMode = 'spectrum'; // 'spectrum' | 'radar'
let currentTurn = 0;
let lastAgentText = '';
let peakHistory = [];
let isAgentAudioPaused = false;

// ============================================================================
// 4. AUDIO CONTEXT & DUAL VISUALIZER PIPELINE
// ============================================================================

function setupAudioContext() {
  if (audioContext) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioCtx();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 128;
    analyser.smoothingTimeConstant = 0.8;
    const bufferLength = analyser.frequencyBinCount;
    dataArray = new Uint8Array(bufferLength);
    peakHistory = new Array(bufferLength).fill(0);

    // Capture microphone for local FFT reactivity
    navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
    }).catch(err => {
      console.warn("Local mic not routed to analyzer directly:", err);
    });

    resizeVisualizerCanvas();
    drawVisualizer();
  } catch (err) {
    console.error("AudioContext initialization failed:", err);
  }
}

function resizeVisualizerCanvas() {
  if (!DOM.waveformCanvas) return;
  DOM.waveformCanvas.width = DOM.waveformCanvas.offsetWidth;
  DOM.waveformCanvas.height = DOM.waveformCanvas.offsetHeight;
}
window.addEventListener('resize', resizeVisualizerCanvas);
setTimeout(resizeVisualizerCanvas, 150);

// Visualizer Mode Switchers
DOM.vizModeSpectrum.addEventListener('click', () => {
  visualizerMode = 'spectrum';
  DOM.vizModeSpectrum.classList.add('active');
  DOM.vizModeRadar.classList.remove('active');
  DOM.holographicOverlay.classList.add('hidden');
  sfx.playBlip(700);
});

DOM.vizModeRadar.addEventListener('click', () => {
  visualizerMode = 'radar';
  DOM.vizModeRadar.classList.add('active');
  DOM.vizModeSpectrum.classList.remove('active');
  DOM.vizModeOverlay = DOM.holographicOverlay;
  DOM.holographicOverlay.classList.remove('hidden');
  sfx.playBlip(950);
});

// Main Visualizer Render Loop
function drawVisualizer() {
  animFrameId = requestAnimationFrame(drawVisualizer);
  if (!analyser || !dataArray) return;

  analyser.getByteFrequencyData(dataArray);

  const canvas = DOM.waveformCanvas;
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  // Calculate overall energy
  let sum = 0;
  for (let i = 0; i < dataArray.length; i++) {
    sum += dataArray[i];
  }
  const avg = sum / dataArray.length;
  const energyNorm = Math.min(avg / 140, 1.0);
  bgAnimation.setAudioEnergy(energyNorm);

  // Update VU meter bar
  if (DOM.levelMeterBar) {
    DOM.levelMeterBar.style.width = `${Math.min(energyNorm * 100, 100)}%`;
  }

  if (visualizerMode === 'spectrum') {
    renderSpectrumVisualizer(ctx, width, height, dataArray);
  } else {
    renderReactorVisualizer(ctx, width, height, dataArray, energyNorm);
  }
}

// Mode 1: Quantum Frequency Spectrum Bars
function renderSpectrumVisualizer(ctx, width, height, data) {
  const barsCount = data.length;
  const barWidth = (width / barsCount) * 1.6;
  let x = 0;

  for (let i = 0; i < barsCount; i++) {
    const barHeight = (data[i] / 255) * (height * 0.85);

    // Peak holding logic
    if (barHeight > peakHistory[i]) {
      peakHistory[i] = barHeight;
    } else {
      peakHistory[i] = Math.max(0, peakHistory[i] - 1.0);
    }

    // Soothing Gradient: Ice Cyan to Fresh Mint
    const grad = ctx.createLinearGradient(0, height, 0, height - barHeight);
    grad.addColorStop(0, 'rgba(56, 189, 248, 0.12)');
    grad.addColorStop(0.5, '#38BDF8');
    grad.addColorStop(1, '#34D399');

    ctx.fillStyle = grad;
    ctx.fillRect(x, height - barHeight, barWidth - 2, barHeight);

    // Soft Warm Amber Peak Cap
    ctx.fillStyle = '#F59E0B';
    ctx.fillRect(x, height - peakHistory[i] - 2, barWidth - 2, 2);

    x += barWidth;
  }
}

// Mode 2: Holographic Reactor Core Radial Wave
function renderReactorVisualizer(ctx, width, height, data, energy) {
  const centerX = width / 2;
  const centerY = height / 2;
  const baseRadius = 42 + energy * 18;

  ctx.save();
  ctx.translate(centerX, centerY);

  ctx.beginPath();
  const points = data.length;
  for (let i = 0; i < points; i++) {
    const angle = (i / points) * Math.PI * 2;
    const offset = (data[i] / 255) * 30;
    const r = baseRadius + offset;
    const px = Math.cos(angle) * r;
    const py = Math.sin(angle) * r;

    if (i === 0) {
      ctx.moveTo(px, py);
    } else {
      ctx.lineTo(px, py);
    }
  }
  ctx.closePath();
  ctx.strokeStyle = energy > 0.15 ? '#38BDF8' : 'rgba(56, 189, 248, 0.4)';
  ctx.lineWidth = 2.2;
  ctx.shadowBlur = 8;
  ctx.shadowColor = '#38BDF8';
  ctx.stroke();

  // Secondary inner seafoam aura
  ctx.beginPath();
  ctx.arc(0, 0, Math.max(10, baseRadius - 14), 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(52, 211, 153, 0.45)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  ctx.restore();
}

// ============================================================================
// 5. LIVEKIT WEBRTC OPERATOR CONNECTION
// ============================================================================

async function connectOperatorSession() {
  try {
    DOM.errorMsg.classList.add('hidden');
    DOM.connectBtn.disabled = true;
    DOM.connectBtn.innerHTML = `
      <svg class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M21 12a9 9 0 1 1-6.219-8.56"></path>
      </svg>
      <span>MINTING TOKEN & CONNECTING...</span>
    `;

    sfx.playBlip(600);

    const res = await fetch('/api/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_name: "sre-operator" })
    });

    if (!res.ok) {
      const errDetail = await res.json().catch(() => ({}));
      throw new Error(errDetail.detail || `Token minting failed (${res.status})`);
    }

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

    setupRoomEventListeners(room);
    await room.connect(url, token);

    // Initialize Web Audio Context
    setupAudioContext();

    // Update UI states
    DOM.connectOverlay.classList.add('hidden');
    DOM.connectionDot.classList.remove('dot-offline');
    DOM.connectionDot.classList.add('dot-connected');
    DOM.connectionStatusText.textContent = 'ONLINE // SECURE';
    DOM.headerConnectText.textContent = 'DISCONNECT';

    // Clear empty state in transcript
    const emptyState = DOM.transcriptContainer.querySelector('.empty-state-cyber');
    if (emptyState) emptyState.remove();

    DOM.startListenBtn.classList.remove('hidden');
    updateAgentStatus('Awaiting Operator Mic...', '#FF6A00');
    sfx.playConnectChime();

    // Post session initialized event to transcript
    appendSystemEvent("WebRTC session initialized. LiveKit room connected. Agent dispatched.");

  } catch (err) {
    console.error("Connection error:", err);
    DOM.errorMsg.textContent = err.message || "Failed to establish WebRTC connection.";
    DOM.errorMsg.classList.remove('hidden');
    DOM.connectBtn.disabled = false;
    DOM.connectBtn.innerHTML = `
      <span class="btn-text">INITIALIZE OPERATOR SESSION</span>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <line x1="5" y1="12" x2="19" y2="12"></line>
        <polyline points="12 5 19 12 12 19"></polyline>
      </svg>
    `;
  }
}

DOM.connectBtn.addEventListener('click', connectOperatorSession);

DOM.headerConnectBtn.addEventListener('click', () => {
  if (room && room.state === 'connected') {
    room.disconnect();
    sfx.playBlip(400);
  } else {
    DOM.connectOverlay.classList.remove('hidden');
    sfx.playBlip(600);
  }
});

// Microphone Activation Toggle
DOM.startListenBtn.addEventListener('click', async () => {
  if (!room || room.state !== 'connected') {
    DOM.connectOverlay.classList.remove('hidden');
    return;
  }

  const isEnabled = room.localParticipant.isMicrophoneEnabled;
  if (!isEnabled) {
    await room.localParticipant.setMicrophoneEnabled(true);
    setupAudioContext();
    DOM.startListenText.textContent = 'OPERATOR MIC ACTIVE';
    DOM.startListenBtn.classList.add('active-mic');
    updateAgentStatus('Listening for speech...', '#10B981');
    sfx.playMicTone(true);
  } else {
    await room.localParticipant.setMicrophoneEnabled(false);
    DOM.startListenText.textContent = 'START OPERATOR MIC';
    DOM.startListenBtn.classList.remove('active-mic');
    updateAgentStatus('Mic Muted', '#94A3B8');
    sfx.playMicTone(false);
  }
});

// Feature: Pause / Resume Agent Voice Response Output
function toggleAgentAudioPause() {
  isAgentAudioPaused = !isAgentAudioPaused;

  if (DOM.agentAudio) {
    DOM.agentAudio.muted = isAgentAudioPaused;
    if (isAgentAudioPaused) {
      DOM.agentAudio.pause();
    } else {
      DOM.agentAudio.play().catch(() => {});
    }
  }

  if (DOM.pauseAgentBtn) {
    if (isAgentAudioPaused) {
      DOM.pauseAgentBtn.classList.add('is-paused');
      DOM.pauseAgentText.textContent = 'RESUME VOICE';
      DOM.pauseIconSvg.classList.add('hidden');
      DOM.playIconSvg.classList.remove('hidden');
      if (DOM.agentPausedBadge) DOM.agentPausedBadge.classList.remove('hidden');
      sfx.playBlip(380);
      appendSystemEvent("Agent voice output paused. (Audio muted, transcription continues in background)");
    } else {
      DOM.pauseAgentBtn.classList.remove('is-paused');
      DOM.pauseAgentText.textContent = 'PAUSE AGENT VOICE';
      DOM.pauseIconSvg.classList.remove('hidden');
      DOM.playIconSvg.classList.add('hidden');
      if (DOM.agentPausedBadge) DOM.agentPausedBadge.classList.add('hidden');
      sfx.playBlip(720);
      appendSystemEvent("Agent voice output resumed.");
    }
  }
}

if (DOM.pauseAgentBtn) {
  DOM.pauseAgentBtn.addEventListener('click', toggleAgentAudioPause);
}

// Global Keyboard Shortcut [P] to pause/resume agent voice
window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'p' || e.key === 'P') {
    e.preventDefault();
    toggleAgentAudioPause();
  }
});

// LiveKit Room Event Handlers
function setupRoomEventListeners(targetRoom) {
  // Audio Track Subscription (Agent Voice)
  targetRoom.on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {
    if (track.kind === 'audio') {
      track.attach(DOM.agentAudio);
      DOM.agentAudio.muted = isAgentAudioPaused;
      if (isAgentAudioPaused) {
        DOM.agentAudio.pause();
      }
      if (audioContext && analyser) {
        try {
          const mediaStream = new MediaStream([track.mediaStreamTrack]);
          const source = audioContext.createMediaStreamSource(mediaStream);
          source.connect(analyser);
        } catch (e) {
          console.warn("Could not route incoming audio to analyser:", e);
        }
      }
    }
  });

  // Realtime Speech Transcription
  targetRoom.on(LivekitClient.RoomEvent.TranscriptionReceived, (transcriptions, participant) => {
    for (const t of transcriptions) {
      const isFinal = t.isFinal || t.final;
      if (isFinal && t.text && t.text.trim().length > 0) {
        const isUser = participant?.identity === targetRoom.localParticipant?.identity;
        appendTranscript(isUser ? 'user' : 'agent', t.text.trim());
      }
    }
  });

  // Data Channel Telemetry & Status Events
  targetRoom.on(LivekitClient.RoomEvent.DataReceived, (data, participant, kind, topic) => {
    if (topic === 'voiceops_status') {
      try {
        const event = JSON.parse(new TextDecoder().decode(data));
        handleStatusEvent(event);
      } catch (e) {
        console.error("Failed to parse data channel message:", e);
      }
    } else if (topic === 'lk-chat') {
      try {
        const chatMsg = JSON.parse(new TextDecoder().decode(data));
        if (participant !== targetRoom.localParticipant) {
          appendTranscript('agent', chatMsg.message);
        }
      } catch (e) {}
    }
  });

  // Room Disconnect Handler
  targetRoom.on(LivekitClient.RoomEvent.Disconnected, () => {
    DOM.connectionDot.classList.add('dot-offline');
    DOM.connectionDot.classList.remove('dot-connected');
    DOM.connectionStatusText.textContent = 'OFFLINE';
    DOM.headerConnectText.textContent = 'CONNECT';
    DOM.connectOverlay.classList.remove('hidden');
    DOM.connectBtn.disabled = false;
    DOM.connectBtn.innerHTML = `
      <span class="btn-text">RECONNECT OPERATOR SESSION</span>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <line x1="5" y1="12" x2="19" y2="12"></line>
        <polyline points="12 5 19 12 12 19"></polyline>
      </svg>
    `;
    DOM.startListenBtn.classList.add('hidden');
    updateAgentStatus('Disconnected', '#EF4444');
    appendSystemEvent("WebRTC session disconnected.");
  });
}

// Data Channel Status Handler (Turn Fencing, Tool State, Barge-In Discards)
function handleStatusEvent(evt) {
  const kind = evt.event;

  if (evt.turn_id !== undefined) {
    currentTurn = evt.turn_id;
    DOM.activeTurnVal.textContent = `TURN ${currentTurn}`;
    DOM.headerTurnCounter.textContent = `TURN #${currentTurn}`;
  }

  if (kind === 'tool_start') {
    const isRag = evt.tool === 'query_runbook_rag';
    const label = isRag ? 'Searching Vector Runbooks (3s)...' : `Checking host: ${evt.host || evt.tool}...`;
    updateAgentStatus(label, '#38BDF8');
    appendToolEvent('start', evt.tool, evt.query || evt.host);
  } else if (kind === 'tool_complete') {
    updateAgentStatus('Tool Executed Successfully', '#34D399');
    appendToolEvent('complete', evt.tool, evt.result || `${evt.result_count || 0} chunks returned`);
    setTimeout(() => {
      updateAgentStatus('Listening...', '#34D399');
    }, 2000);
  } else if (kind === 'stale_discard') {
    // Crucial: Hard-Voice Interruption Recovery Evidence
    updateAgentStatus('⚠ Discarded Stale State', '#FB7185');
    appendStaleDiscard(evt.from_turn, evt.to_turn);
    sfx.playBargeInAlert();
    setTimeout(() => {
      updateAgentStatus('Listening...', '#34D399');
    }, 2500);
  } else if (kind === 'tool_error') {
    updateAgentStatus(evt.error || 'Tool Error', '#FB7185');
    setTimeout(() => {
      updateAgentStatus('Listening...', '#34D399');
    }, 3000);
  }
}

function updateAgentStatus(text, color = '#38BDF8') {
  DOM.statusPill.textContent = text;
  DOM.statusPill.style.color = color;
  DOM.agentStateDot.style.backgroundColor = color;
  DOM.agentStateDot.style.boxShadow = `0 0 8px ${color}`;
}

// ============================================================================
// 6. TRANSCRIPT STREAM ENGINE
// ============================================================================

function appendTranscript(role, text) {
  if (role === 'agent') {
    if (text === lastAgentText) return;
    lastAgentText = text;
  } else {
    lastAgentText = '';
  }

  const bubble = document.createElement('div');
  bubble.className = `transcript-bubble transcript-${role}`;

  const now = new Date();
  const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;

  bubble.innerHTML = `
    <div class="bubble-meta">
      <span class="role-tag role-${role}">${role === 'user' ? 'OPERATOR' : 'VOICEOPS AGENT'}</span>
      <span class="time-tag">[${timeStr}]</span>
    </div>
    <div class="bubble-content">${escapeHTML(text)}</div>
  `;

  DOM.transcriptContainer.appendChild(bubble);
  scrollToBottom();
}

function appendToolEvent(type, tool, detail) {
  const div = document.createElement('div');
  div.className = 'transcript-tool-badge';
  const icon = type === 'start' ? '⚡' : '✓';
  div.innerHTML = `<span>${icon}</span> <span>[TOOL ${type.toUpperCase()}] <strong>${escapeHTML(tool)}</strong> — ${escapeHTML(typeof detail === 'object' ? JSON.stringify(detail) : String(detail))}</span>`;
  DOM.transcriptContainer.appendChild(div);
  scrollToBottom();
}

function appendStaleDiscard(fromTurn, toTurn) {
  const card = document.createElement('div');
  card.className = 'transcript-stale-card';
  card.innerHTML = `
    <span class="stale-icon">⚠</span>
    <div>
      <strong>BARGE-IN DETECTED:</strong> Stale tool execution cancelled and discarded (Turn ${fromTurn} → Turn ${toTurn}).
      <div style="font-size: 0.68rem; color: #FCA5A5; margin-top: 0.15rem;">Turn-fencing layer successfully prevented outdated context pollution.</div>
    </div>
  `;
  DOM.transcriptContainer.appendChild(card);
  scrollToBottom();
}

function appendSystemEvent(msg) {
  const div = document.createElement('div');
  div.style.fontFamily = 'var(--font-mono)';
  div.style.fontSize = '0.66rem';
  div.style.color = 'var(--text-muted)';
  div.style.padding = '0.2rem 0';
  div.textContent = `// ${msg}`;
  DOM.transcriptContainer.appendChild(div);
  scrollToBottom();
}

function scrollToBottom() {
  const container = DOM.transcriptContainer.parentElement;
  container.scrollTop = container.scrollHeight;
}

function escapeHTML(str) {
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}

DOM.clearTranscriptBtn.addEventListener('click', () => {
  DOM.transcriptContainer.innerHTML = '';
  sfx.playBlip(500);
});

// ============================================================================
// 7. DYNAMIC KNOWLEDGE INGESTION & VECTOR STORE
// ============================================================================

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
  DOM.dropzone.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
  }, false);
});

['dragenter', 'dragover'].forEach(eventName => {
  DOM.dropzone.addEventListener(eventName, () => DOM.dropzone.classList.add('active'), false);
});

['dragleave', 'drop'].forEach(eventName => {
  DOM.dropzone.addEventListener(eventName, () => DOM.dropzone.classList.remove('active'), false);
});

DOM.dropzone.addEventListener('drop', (e) => {
  const files = e.dataTransfer.files;
  handleFileUploads(files);
});

DOM.fileInput.addEventListener('change', function() {
  handleFileUploads(this.files);
});

async function handleFileUploads(files) {
  if (!files || files.length === 0) return;

  DOM.uploadProgressContainer.classList.remove('hidden');
  DOM.uploadProgressBar.style.width = '15%';
  DOM.progressText.textContent = 'Parsing Chunks...';
  sfx.playBlip(750);

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const formData = new FormData();
    formData.append("file", file);

    const progressPct = Math.round(((i + 0.5) / files.length) * 80);
    DOM.uploadProgressBar.style.width = `${progressPct}%`;
    DOM.progressText.textContent = `Ingesting ${file.name}...`;

    try {
      const response = await fetch('/api/ingest', {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error("Upload failed");
    } catch (err) {
      console.error(err);
      alert("Failed to upload " + file.name);
    }
  }

  DOM.uploadProgressBar.style.width = '100%';
  DOM.progressText.textContent = 'Vector Indexing Complete!';
  sfx.playConnectChime();

  setTimeout(() => {
    DOM.uploadProgressContainer.classList.add('hidden');
    DOM.uploadProgressBar.style.width = '0%';
    loadIndexedDocuments();
  }, 1200);
}

// Load Document Repository from Backend (/api/documents)
async function loadIndexedDocuments() {
  try {
    const res = await fetch('/api/documents');
    if (!res.ok) throw new Error("Failed to load documents");
    const docs = await res.json();

    DOM.docPillsContainer.innerHTML = '';

    if (docs.length === 0) {
      DOM.docPillsContainer.innerHTML = `
        <div class="pills-loading-placeholder">
          No runbooks indexed yet. Drop a .pdf or .md file above!
        </div>
      `;
      DOM.headerVectorStats.textContent = '0 CHUNKS';
      return;
    }

    let totalChunks = 0;
    docs.forEach(doc => {
      totalChunks += doc.chunks_count || 0;
      const item = document.createElement('div');
      item.className = 'doc-pill-item';
      item.innerHTML = `
        <div class="doc-pill-left">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--neon-accent)" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <span class="doc-file-name" title="${escapeHTML(doc.filename)}">${escapeHTML(doc.filename)}</span>
          <span class="doc-chunk-tag">${doc.chunks_count || 0} chunks</span>
        </div>
        <button class="doc-delete-btn" title="Delete from disk and ChromaDB" data-file="${escapeHTML(doc.filename)}">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      `;

      item.querySelector('.doc-delete-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        deleteDocument(doc.filename);
      });

      DOM.docPillsContainer.appendChild(item);
    });

    DOM.headerVectorStats.textContent = `${totalChunks} CHUNKS`;

  } catch (err) {
    console.error("Failed to fetch documents:", err);
    DOM.docPillsContainer.innerHTML = `
      <div class="pills-loading-placeholder" style="color: var(--neon-danger);">
        Could not load vector store repository.
      </div>
    `;
  }
}

async function deleteDocument(filename) {
  if (!confirm(`Are you sure you want to delete '${filename}' from vector memory?`)) return;

  try {
    const res = await fetch(`/api/documents/${encodeURIComponent(filename)}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error("Delete failed");
    sfx.playBlip(350);
    loadIndexedDocuments();
  } catch (err) {
    alert("Could not delete file: " + err.message);
  }
}

DOM.refreshDocsBtn.addEventListener('click', () => {
  sfx.playBlip(800);
  loadIndexedDocuments();
});

// ============================================================================
// 8. QUICK PROMPTS & SIMULATION ENGINE
// ============================================================================

DOM.promptChips.forEach(chip => {
  chip.addEventListener('click', () => {
    const prompt = chip.dataset.prompt;
    if (!prompt) return;

    sfx.playBlip(750);
    appendTranscript('user', prompt);

    // If connected to live session, the agent listens or processes
    // In addition, execute simulated server call for immediate UI feedback
    if (prompt.includes('prod-db-01')) {
      simulateServerCheck('prod-db-01');
    } else if (prompt.includes('auth-service-02')) {
      simulateServerCheck('auth-service-02');
    } else if (prompt.includes('runbook') || prompt.includes('latency')) {
      simulateRunbookQuery('high latency incident recovery steps');
    }
  });
});

// Hard-Voice Barge-in Demonstration Trigger
DOM.simulateBargeinBtn.addEventListener('click', () => {
  sfx.playBlip(400);
  const turnBefore = currentTurn;
  currentTurn += 1;
  DOM.activeTurnVal.textContent = `TURN ${currentTurn}`;
  DOM.headerTurnCounter.textContent = `TURN #${currentTurn}`;

  appendTranscript('user', "Wait, stop that! Check auth-service-02 instead!");
  handleStatusEvent({
    event: 'stale_discard',
    tool: 'query_runbook_rag',
    from_turn: turnBefore,
    to_turn: currentTurn
  });

  setTimeout(() => {
    appendTranscript('agent', "Acknowledged. Interrupted previous runbook search and discarded stale results. Checking auth-service-02 now.");
  }, 450);
});

async function simulateServerCheck(host) {
  updateAgentStatus(`Checking ${host}...`, '#38BDF8');
  try {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'check_server', host: host })
    });
    const data = await res.json();
    setTimeout(() => {
      appendToolEvent('complete', 'check_server_status', data);
      appendTranscript('agent', data.message || `Server ${host} is operational.`);
      updateAgentStatus('Listening...', '#34D399');
    }, 750);
  } catch (e) {
    updateAgentStatus('Listening...', '#34D399');
  }
}

async function simulateRunbookQuery(query) {
  updateAgentStatus('Searching Vector Runbooks (3s)...', '#38BDF8');
  try {
    const res = await fetch('/api/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'query_runbook', query: query })
    });
    const data = await res.json();
    setTimeout(() => {
      appendToolEvent('complete', 'query_runbook_rag', data);
      appendTranscript('agent', data.message || "Retrieved runbook sections.");
      updateAgentStatus('Listening...', '#34D399');
    }, 2000);
  } catch (e) {
    updateAgentStatus('Listening...', '#34D399');
  }
}

// SFX Toggle Handler
DOM.sfxToggleBtn.addEventListener('click', () => {
  const isEnabled = sfx.toggle();
  if (isEnabled) {
    DOM.sfxIconOn.classList.remove('hidden');
    DOM.sfxIconOff.classList.add('hidden');
    DOM.sfxToggleBtn.querySelector('.btn-tooltip').textContent = 'SFX ON';
    sfx.playBlip(900);
  } else {
    DOM.sfxIconOn.classList.add('hidden');
    DOM.sfxIconOff.classList.remove('hidden');
    DOM.sfxToggleBtn.querySelector('.btn-tooltip').textContent = 'SFX OFF';
  }
});

// Update initial SFX icon state
if (!sfx.enabled) {
  DOM.sfxIconOn.classList.add('hidden');
  DOM.sfxIconOff.classList.remove('hidden');
  DOM.sfxToggleBtn.querySelector('.btn-tooltip').textContent = 'SFX OFF';
}

// 3D Tilt Micro-interaction for Glass Panels
document.querySelectorAll('[data-tilt]').forEach(panel => {
  panel.addEventListener('mousemove', (e) => {
    const rect = panel.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    const rotateX = (-y / rect.height) * 4;
    const rotateY = (x / rect.width) * 4;
    panel.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
  });

  panel.addEventListener('mouseleave', () => {
    panel.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)';
  });
});

// Initial Bootstrap on Load
window.addEventListener('DOMContentLoaded', () => {
  loadIndexedDocuments();
});
