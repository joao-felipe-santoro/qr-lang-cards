const socket = io();

const dot        = document.getElementById('status-dot');
const statusLbl  = document.getElementById('status-label');
const waitingMsg = document.getElementById('waiting-msg');
const cardDisplay = document.getElementById('card-display');
const cardIdEl   = document.getElementById('card-id');
const langBlocks = document.getElementById('lang-blocks');
const timestampEl= document.getElementById('scan-timestamp');
const historyEl  = document.getElementById('history-list');

// ── Connection state ──────────────────────────────────────────────────────────
socket.on('connect', () => {
  dot.className = 'connected';
  statusLbl.textContent = 'Aguardando leitura...';
  loadHistory();
});

socket.on('disconnect', () => {
  dot.className = 'error';
  statusLbl.textContent = 'Desconectado';
});

// ── Scan result ───────────────────────────────────────────────────────────────
socket.on('scan_result', (data) => {
  if (data.status === 'unknown') {
    showUnknown(data.card_id);
    return;
  }

  showCard(data);
  loadHistory();

  dot.className = 'playing';
  statusLbl.textContent = 'Tocando...';

  // Reset status after estimated audio duration (≈ 3 s per language × 3)
  setTimeout(() => {
    dot.className = 'connected';
    statusLbl.textContent = 'Aguardando leitura...';
  }, 10000);
});

// ── Display helpers ───────────────────────────────────────────────────────────
function showCard(data) {
  waitingMsg.style.display  = 'none';
  cardDisplay.style.display = 'block';
  cardDisplay.classList.add('fade-in');

  cardIdEl.textContent = data.card_id;

  langBlocks.innerHTML = '';
  for (const [key, word] of Object.entries(data.words)) {
    const label = data.labels[key] || key;
    langBlocks.innerHTML += `
      <div class="lang-block">
        <span class="lang-label">${label}</span>
        <span class="lang-word">${word}</span>
      </div>`;
  }

  const ts = new Date(data.timestamp * 1000);
  timestampEl.textContent = ts.toLocaleTimeString('pt-BR');
}

function showUnknown(cardId) {
  waitingMsg.style.display  = 'none';
  cardDisplay.style.display = 'block';
  cardDisplay.classList.add('fade-in');

  langBlocks.innerHTML = `
    <div class="unknown-banner">
      ⚠️ ID desconhecido: <strong>${cardId}</strong><br>
      <small>Verifique cards_source.csv</small>
    </div>`;

  cardIdEl.textContent  = '';
  timestampEl.textContent = '';
}

// ── History ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res  = await fetch('/list_scans');
    const rows = await res.json();

    if (!rows || rows.length === 0) return;

    historyEl.innerHTML = rows.map(r => {
      const t = new Date(r.timestamp * 1000).toLocaleTimeString('pt-BR');
      return `
        <div class="history-item fade-in">
          <span class="hcard">${r.card_id}</span>
          <span class="htime">${t}</span>
        </div>`;
    }).join('');
  } catch (e) {
    console.warn('History fetch failed:', e);
  }
}

// ── Reset ─────────────────────────────────────────────────────────────────────
function resetDetection() {
  socket.emit('reset', {});
  waitingMsg.style.display  = 'block';
  cardDisplay.style.display = 'none';
  dot.className = 'connected';
  statusLbl.textContent = 'Aguardando leitura...';
}
