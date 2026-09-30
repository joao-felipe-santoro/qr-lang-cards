/*
 * Lang Card Reader — app.js
 * Adapted from the Arduino QR/Barcode Scanner example.
 * Main changes vs original:
 *   - handleCodeDetected shows words in 3 languages (pt-br / en / de)
 *   - renderScanInfo builds lang-block cards instead of QR content
 *   - renderScans shows card_id + timestamp (scan_log has no content/image)
 *   - Unknown card IDs show an error banner
 */

const canvasElement           = document.getElementById('videoCanvas');
const ctx                     = canvasElement.getContext('2d');
const scanInfoElement         = document.getElementById('scanInfo');
const recentScansListElement  = document.getElementById('recentScansList');
const initialListErrorElement = document.getElementById('initialListError');
const cameraStatusElement     = document.getElementById('cameraStatus');
const scanMessageElement      = document.getElementById('scanMessage');
const rescanButtonContainer   = document.getElementById('rescan-button-container');
const deleteScanElement       = document.getElementById('delete-scan');
let errorContainer            = document.getElementById('error-container');

const MAX_RECENT_SCANS = 5;
let scans = [];
let currentImageBitmap = null;

const ui = new WebUI();
ui.on_connect(onUIConnected);
ui.on_disconnect(onUIDisconnected);
ui.on_message('code_detected', handleCodeDetected);
ui.on_message('frame_detected', handleFrameDetected);
ui.on_message('error', handleOnError);

function onUIConnected() {
  if (errorContainer) {
    errorContainer.style.display = 'none';
    errorContainer.textContent = '';
  }
}

function onUIDisconnected() {
  if (currentImageBitmap) {
    currentImageBitmap.close();
    currentImageBitmap = null;
  }
  if (errorContainer) {
    errorContainer.textContent = 'Conexão com o dispositivo perdida. Verifique a conexão.';
    errorContainer.style.display = 'block';
  }
}

// ── Handlers ──────────────────────────────────────────────────────────────────
async function handleCodeDetected(message) {
  updateCameraStatus('hide');
  renderScanInfo(message);
  addScan(message);
  renderScans();
  await renderLatestScanImage(message.image, message.image_type);

  if (message.audio && message.audio.length > 0) {
    await playAudioSequence(message.audio);
  }
}

async function handleFrameDetected(message) {
  updateCameraStatus('show');
  scanInfoElement.innerHTML = '';
  rescanButtonContainer.style.display = 'none';
  await renderFrameImage(message.image, message.image_type);
}

function handleOnError(message) {
  if (errorContainer) {
    errorContainer.textContent = message;
    errorContainer.style.display = 'block';
  }
}

function updateCameraStatus(action = 'show') {
  if (cameraStatusElement) {
    cameraStatusElement.style.display = action === 'hide' ? 'none' : 'flex';
  }
}

// ── Scan info (right panel — lang-card specific) ───────────────────────────────
function renderScanInfo(message) {
  if (message.status === 'unknown') {
    scanInfoElement.innerHTML = `
      <div class="unknown-banner">
        ⚠️ ID desconhecido: <strong>${message.card_id}</strong><br>
        <small>Verifique cards_source.csv</small>
      </div>`;
    rescanButtonContainer.style.display = 'flex';
    return;
  }

  const ts = new Date(message.timestamp).toLocaleTimeString('pt-BR', {
    hour: '2-digit', minute: '2-digit',
  });

  const blocksHtml = Object.entries(message.words).map(([key, word]) => {
    const label = message.labels[key] || key;
    return `
      <div class="lang-block">
        <span class="lang-label">${label}</span>
        <span class="lang-word">${word}</span>
      </div>`;
  }).join('');

  scanInfoElement.innerHTML = `
    <div class="lang-card-id">${message.card_id}</div>
    <div class="lang-blocks">${blocksHtml}</div>
    <div class="lang-timestamp">${ts}</div>`;

  rescanButtonContainer.style.display = 'flex';
}

// ── Recent scans list ─────────────────────────────────────────────────────────
function addScan(newScan) {
  scans.unshift(newScan);
  if (scans.length > MAX_RECENT_SCANS) scans.pop();
}

function renderScans() {
  recentScansListElement.innerHTML = '';

  if (scans.length === 0) {
    recentScansListElement.innerHTML = `
      <div class="no-recent-scans">
        <img src="./img/barcode.svg">
        Nenhuma leitura recente
      </div>`;
    scanMessageElement.style.display = 'none';
    deleteScanElement.style.display = 'none';
    return;
  }

  scanMessageElement.style.display = 'block';
  deleteScanElement.style.display = 'block';

  scans.forEach(scan => {
    const row = document.createElement('div');
    row.className = 'scan-card-row';

    const ts = new Date(scan.timestamp).toLocaleString('pt-BR').replace(',', ' —');
    row.innerHTML = `
      <span class="scan-card-id">${scan.card_id}</span>
      <span class="scan-card-time">${ts}</span>`;

    recentScansListElement.appendChild(row);
  });
}

function clearRecentScans() {
  scans = [];
  renderScans();
}

// ── History fetch from DB ─────────────────────────────────────────────────────
async function listScans() {
  try {
    const response = await fetch(`http://${window.location.host}/list_scans`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const data = await response.json();

    if (data.error) {
      initialListErrorElement.textContent = `Erro ao carregar leituras: ${data.error}`;
      initialListErrorElement.style.display = 'block';
      return;
    }
    if (!data.scans) {
      initialListErrorElement.textContent = 'Dados inválidos recebidos do servidor.';
      initialListErrorElement.style.display = 'block';
      return;
    }

    scans = data.scans.slice(0, MAX_RECENT_SCANS);
    renderScans();
  } catch (error) {
    initialListErrorElement.textContent = `Erro ao buscar leituras: ${error.message}`;
    initialListErrorElement.style.display = 'block';
  }
}

// ── Canvas rendering (unchanged from original) ────────────────────────────────
async function renderLatestScanImage(image, image_type) {
  if (!image) return;
  try {
    const bytes = base64ToUint8Array(image);
    const blob  = new Blob([bytes], { type: image_type });

    if (currentImageBitmap) currentImageBitmap.close();
    currentImageBitmap = await createImageBitmap(blob);

    if (canvasElement.width  !== currentImageBitmap.width)  canvasElement.width  = currentImageBitmap.width;
    if (canvasElement.height !== currentImageBitmap.height) canvasElement.height = currentImageBitmap.height;

    ctx.drawImage(currentImageBitmap, 0, 0);
  } catch (error) {
    console.error('Error rendering scan image:', error);
  }
}

async function renderFrameImage(image, image_type) {
  try {
    const bytes = base64ToUint8Array(image);
    const blob  = new Blob([bytes], { type: image_type });

    if (currentImageBitmap) currentImageBitmap.close();
    currentImageBitmap = await createImageBitmap(blob);

    if (canvasElement.width  !== currentImageBitmap.width)  canvasElement.width  = currentImageBitmap.width;
    if (canvasElement.height !== currentImageBitmap.height) canvasElement.height = currentImageBitmap.height;

    ctx.drawImage(currentImageBitmap, 0, 0);
  } catch (error) {
    console.error('Error rendering frame:', error);
  }
}

// ── Audio playback (browser-side) ────────────────────────────────────────────
async function playAudioSequence(audioFiles) {
  for (const audio of audioFiles) {
    await playAudio(audio.data, audio.type);
    await new Promise(resolve => setTimeout(resolve, 400));
  }
}

function playAudio(base64Data, mimeType) {
  return new Promise((resolve) => {
    const bytes = base64ToUint8Array(base64Data);
    const blob  = new Blob([bytes], { type: mimeType });
    const url   = URL.createObjectURL(blob);
    const el    = new Audio(url);
    el.onended = () => { URL.revokeObjectURL(url); resolve(); };
    el.onerror = () => { URL.revokeObjectURL(url); resolve(); };
    el.play().catch(() => resolve());
  });
}

function base64ToUint8Array(base64) {
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

// ── Rescan ────────────────────────────────────────────────────────────────────
function rescan() {
  ui.send_message('reset_detection');
  scanInfoElement.innerHTML = '';
  rescanButtonContainer.style.display = 'none';
  updateCameraStatus('show');
}

// ── Init ──────────────────────────────────────────────────────────────────────
listScans();
ui.send_message('reset_detection');
