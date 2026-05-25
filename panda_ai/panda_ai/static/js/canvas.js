// FILE: static/js/canvas.js
// HTML5 Canvas drawing board.
// 100% frontend in V8.5. No AI calls from this file.
// V8.6 hook: exportCanvas() sends Base64 to /canvas/save
// which canvas_handler.py stores for Groq Vision analysis.

// ============================================================
// STATE
// ============================================================
let _canvas    = null;
let _ctx       = null;
let _drawing   = false;
let _tool      = 'brush';    // 'brush' or 'eraser'
let _color     = '#000000';
let _brushSize = 4;
let _sessionId = 'default';  // update this from your session logic if needed

// ============================================================
// INIT - called once when modal opens for the first time
// ============================================================
function initCanvas() {
  _canvas = document.getElementById('drawing-canvas');
  _ctx    = _canvas.getContext('2d');

  // Fill white background so exported PNG is not transparent
  _ctx.fillStyle = '#ffffff';
  _ctx.fillRect(0, 0, _canvas.width, _canvas.height);

  // Mouse events for desktop
  _canvas.addEventListener('mousedown',  _startDraw);
  _canvas.addEventListener('mousemove',  _draw);
  _canvas.addEventListener('mouseup',    _stopDraw);
  _canvas.addEventListener('mouseleave', _stopDraw);

  // Touch events for mobile
  _canvas.addEventListener('touchstart',  _startDraw, { passive: false });
  _canvas.addEventListener('touchmove',   _draw,      { passive: false });
  _canvas.addEventListener('touchend',    _stopDraw);
}

// ============================================================
// POSITION HELPER - works for both mouse and touch events
// ============================================================
function _getPos(e) {
  e.preventDefault();
  var rect    = _canvas.getBoundingClientRect();
  var clientX = e.touches ? e.touches[0].clientX : e.clientX;
  var clientY = e.touches ? e.touches[0].clientY : e.clientY;
  return {
    x: clientX - rect.left,
    y: clientY - rect.top,
  };
}

// ============================================================
// DRAWING LOOP
// ============================================================
function _startDraw(e) {
  _drawing = true;
  var pos = _getPos(e);
  _ctx.beginPath();
  _ctx.moveTo(pos.x, pos.y);
}

function _draw(e) {
  if (!_drawing) return;
  var pos = _getPos(e);

  // Eraser uses a larger width and white color to paint over drawing
  _ctx.lineWidth   = _tool === 'eraser' ? _brushSize * 4 : _brushSize;
  _ctx.lineCap     = 'round';
  _ctx.lineJoin    = 'round';
  _ctx.strokeStyle = _tool === 'eraser' ? '#ffffff' : _color;

  _ctx.lineTo(pos.x, pos.y);
  _ctx.stroke();
}

function _stopDraw() {
  _drawing = false;
  _ctx.beginPath();  // reset path so next stroke starts fresh
}

// ============================================================
// PUBLIC CONTROLS - called from HTML onclick attributes
// ============================================================

function setTool(tool) {
  _tool = tool;
}

function updateColor(value) {
  _color = value;
  // If user picks a color while eraser is active, switch back to brush
  if (_tool === 'eraser') {
    _tool = 'brush';
  }
}

function updateSize(value) {
  _brushSize = Number(value);
  var label = document.getElementById('canvas-size-label');
  if (label) label.textContent = value + 'px';
}

function clearCanvas() {
  if (!_ctx) return;
  _ctx.fillStyle = '#ffffff';
  _ctx.fillRect(0, 0, _canvas.width, _canvas.height);
}

// ============================================================
// MODAL OPEN / CLOSE
// ============================================================

function openCanvas() {
  var modal = document.getElementById('canvas-modal');
  modal.style.display = 'flex';
  // Initialize drawing canvas only on first open
  if (!_canvas) {
    initCanvas();
  }
}

function closeCanvas() {
  document.getElementById('canvas-modal').style.display = 'none';
}

// ============================================================
// EXPORT - convert canvas to Base64 and send to backend
// ============================================================

async function exportCanvas() {
  if (!_canvas) return;

  // toDataURL returns: "data:image/png;base64,<base64string>"
  var base64 = _canvas.toDataURL('image/png');

  try {
    var res = await fetch('/canvas/save', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        image:      base64,
        session_id: _sessionId,
      }),
    });

    var data = await res.json();

    closeCanvas();

    // appendMessage is defined in script.js which loads before canvas.js
    if (typeof appendMessage === 'function') {
      appendMessage(
        'user',
        '[Canvas Drawing Sent - ' + (data.size_kb || '?') + 'KB]',
        false,
        null
      );
      appendMessage(
        'ai',
        data.message || 'Canvas received.',
        false,
        null
      );
    }

  } catch (err) {
    console.error('Canvas export error:', err);
    alert('Failed to send canvas to server. Please try again.');
  }
}
