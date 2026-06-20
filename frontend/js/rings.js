function drawRing(canvas, percentage, color, lineWidth = 8, startAngle = -Math.PI / 2) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const size = canvas.clientWidth;

  // The canvas isn't laid out yet (e.g. drawn while its page is hidden) — skip; it will be
  // redrawn when visible. Otherwise radius below would go negative and arc() would throw.
  if (size <= lineWidth * 2) return;

  canvas.width = size * dpr;
  canvas.height = size * dpr;
  ctx.scale(dpr, dpr);

  const cx = size / 2;
  const cy = size / 2;
  const radius = (size - lineWidth * 2) / 2;

  ctx.clearRect(0, 0, size, size);

  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.strokeStyle = color + '25';
  ctx.lineWidth = lineWidth;
  ctx.lineCap = 'round';
  ctx.stroke();

  const endAngle = startAngle + (Math.PI * 2 * Math.min(percentage / 100, 1));
  ctx.beginPath();
  ctx.arc(cx, cy, radius, startAngle, endAngle);
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineCap = 'round';
  ctx.stroke();

  if (percentage >= 100) {
    const glowGrad = ctx.createRadialGradient(cx, cy, radius - 5, cx, cy, radius + 5);
    glowGrad.addColorStop(0, color + '00');
    glowGrad.addColorStop(0.5, color + '40');
    glowGrad.addColorStop(1, color + '00');
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.strokeStyle = glowGrad;
    ctx.lineWidth = lineWidth + 4;
    ctx.stroke();
  }
}

function drawTripleRings(container, health, fitness, sleep) {
  const canvases = container.querySelectorAll('canvas');
  if (canvases.length < 3) return;

  drawRing(canvases[0], sleep, '#AF52DE', 10);
  drawRing(canvases[1], fitness, '#007AFF', 10);
  drawRing(canvases[2], health, '#34C759', 10);
}

function animateRing(canvas, targetPct, color, lineWidth = 8, duration = 800) {
  let start = null;
  let currentPct = 0;

  function frame(ts) {
    if (!start) start = ts;
    const elapsed = ts - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    currentPct = eased * targetPct;
    drawRing(canvas, currentPct, color, lineWidth);
    if (progress < 1) requestAnimationFrame(frame);
  }

  requestAnimationFrame(frame);
}

// Claude editorial palette — readable on warm off-white, distinct enough as rings.
const RING_COLORS = {
  health:  '#3B6D11',  // success-text
  fitness: '#185FA5',  // info-text
  sleep:   '#854F0B',  // warning-text
  face:    '#CC5533',  // accent
};

function animateTripleRings(container, health, fitness, sleep, face) {
  const canvases = container.querySelectorAll('canvas');
  if (canvases.length >= 3) {
    animateRing(canvases[0], health  || 0, RING_COLORS.health,  10, 800);   // outer
    animateRing(canvases[1], fitness || 0, RING_COLORS.fitness, 10, 900);
    animateRing(canvases[2], sleep   || 0, RING_COLORS.sleep,   10, 1000);
  }
  if (canvases.length >= 4 && face !== undefined) {
    animateRing(canvases[3], face || 0, RING_COLORS.face, 10, 1100);
  }
}
