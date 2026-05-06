// ─── EMPTY STATE HELPERS ────────────────────────
// Shared helpers used across screens so Day 1 looks intentional, not broken.

const ONE_DAY_MS = 86400 * 1000;

function accountAgeDays(user) {
  if (!user || !user.joined_at) return 0;
  const joined = new Date(user.joined_at).getTime();
  if (!joined) return 0;
  return Math.max(0, Math.floor((Date.now() - joined) / ONE_DAY_MS));
}

function isFirstDay(user) {
  return accountAgeDays(user) < 1;
}

// L11 — render ISO dates as humans read them.
function fmtDate(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return new Intl.DateTimeFormat(undefined, {
      day: 'numeric', month: 'short', year: 'numeric',
    }).format(d);
  } catch (_) {
    return iso;
  }
}

function renderEmpty(container, opts) {
  if (!container) return;
  const icon = opts.icon || '✨';
  const title = opts.title || '';
  const body = opts.body || '';
  const ctaLabel = opts.ctaLabel || '';
  const ctaId = `emptyCta_${Math.random().toString(36).slice(2, 8)}`;
  container.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">${icon}</div>
      <div class="empty-title">${title}</div>
      <div class="empty-body">${body}</div>
      ${ctaLabel ? `<button id="${ctaId}" class="empty-cta">${ctaLabel}</button>` : ''}
    </div>
  `;
  if (ctaLabel && opts.ctaOnClick) {
    const btn = document.getElementById(ctaId);
    if (btn) btn.onclick = opts.ctaOnClick;
  }
}
