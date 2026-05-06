function drawSparkline(canvas, data, color = '#007AFF', filled = false) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;

  canvas.width = w * dpr;
  canvas.height = h * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  if (!data || data.length < 2) return;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 2;

  const points = data.map((val, i) => ({
    x: padding + (i / (data.length - 1)) * (w - padding * 2),
    y: padding + (1 - (val - min) / range) * (h - padding * 2),
  }));

  if (filled) {
    ctx.beginPath();
    ctx.moveTo(points[0].x, h);
    points.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.lineTo(points[points.length - 1].x, h);
    ctx.closePath();

    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, color + '40');
    grad.addColorStop(1, color + '05');
    ctx.fillStyle = grad;
    ctx.fill();
  }

  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);

  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const curr = points[i];
    const cpx = (prev.x + curr.x) / 2;
    ctx.bezierCurveTo(cpx, prev.y, cpx, curr.y, curr.x, curr.y);
  }

  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.stroke();

  const last = points[points.length - 1];
  ctx.beginPath();
  ctx.arc(last.x, last.y, 3, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

function drawWeekBars(container, weekData, color = '#007AFF') {
  const dayNames = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

  // H8 — empty-day bars get a ghost outline so the chart doesn't look broken
  // when a week has no data yet.
  container.innerHTML = weekData.map((d, i) => {
    const pct = d.pct || 0;
    const fill = pct === 0
      ? `<div class="week-bar-fill ghost"></div>`
      : `<div class="week-bar-fill" style="height:${pct}%;background:${pct >= 100 ? '#34C759' : color}"></div>`;
    return `<div class="week-bar-col">
      <div class="week-bar-track">${fill}</div>
      <span class="week-bar-label">${dayNames[i]}</span>
    </div>`;
  }).join('');
}
