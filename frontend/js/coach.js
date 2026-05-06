/**
 * Coach page — templated morning/evening briefs + free-form chat.
 *
 * Pulls /api/coach/today (no LLM) for the daily briefs, and posts to
 * /api/coach/message (Claude Haiku, capped) for free-form chat.
 *
 * Designed to live inside #pageCoach; mounts lazily the first time the
 * page becomes active.
 */
const CoachModule = (() => {
  let _mounted = false;
  let _sending = false;

  async function open() {
    if (!_mounted) _mount();
    await Promise.all([_loadBriefs(), _loadHistory()]);
  }

  function _mount() {
    const root = document.getElementById('pageCoach');
    if (!root) return;
    root.innerHTML = `
      <div class="coach-shell">
        <section class="coach-briefs" id="coachBriefs">
          <div class="coach-loading">Loading today's brief...</div>
        </section>
        <section class="coach-chat">
          <header class="coach-chat-header">
            <h2>Coach chat</h2>
            <p class="coach-chat-sub">Tell me how you feel, or about an injury. I'll log it and adjust your next plan.</p>
          </header>
          <div class="coach-chat-thread" id="coachThread"></div>
          <form class="coach-chat-form" id="coachForm">
            <textarea
              id="coachInput"
              placeholder="What's on your mind?"
              maxlength="2000"
              rows="2"
            ></textarea>
            <button type="submit" class="btn btn-primary" id="coachSendBtn">Send</button>
          </form>
        </section>
      </div>
    `;
    root.querySelector('#coachForm').addEventListener('submit', _onSubmit);
    _mounted = true;
  }

  async function _loadBriefs() {
    try {
      const data = await API.getCoachToday();
      const el = document.getElementById('coachBriefs');
      if (!el) return;
      const morning = data.morning || {};
      const evening = data.evening || {};
      // L4 — cards link straight into Today so users can act on the brief.
      el.innerHTML = `
        <article class="coach-brief" role="link" tabindex="0" onclick="switchPage('today')">
          <div class="coach-brief-label">This morning</div>
          <p class="coach-brief-headline">${_esc(morning.headline || 'Make today count.')}</p>
          ${morning.first_priority ? `<p class="coach-brief-meta">First up — <strong>${_esc(morning.first_priority)}</strong></p>` : ''}
          <p class="coach-brief-meta">${morning.gym_total || 0} gym sets, ${morning.tasks_total || 0} tasks total.</p>
        </article>
        <article class="coach-brief" role="link" tabindex="0" onclick="switchPage('today')">
          <div class="coach-brief-label">This evening</div>
          <p class="coach-brief-headline">${_esc(evening.reflection_question || '')}</p>
          <p class="coach-brief-meta">Today: ${evening.tasks_done || 0} of ${evening.tasks_total || 0} done${evening.gym_total ? ` · gym ${evening.gym_done || 0}/${evening.gym_total}` : ''} · streak ${data.streak_days || 0}d</p>
        </article>
      `;
    } catch (e) {
      const el = document.getElementById('coachBriefs');
      if (el) el.innerHTML = `<p class="coach-error">Couldn't load brief: ${_esc(e.message || 'unknown')}</p>`;
    }
  }

  async function _loadHistory() {
    try {
      const msgs = await API.getCoachMessages(50);
      _renderThread(msgs);
    } catch (e) {
      _renderThread([]);
    }
  }

  // H3 — give new users prompts to start the conversation.
  const COACH_CHIPS = [
    { emoji: '💪', text: 'How does my plan look?' },
    { emoji: '😴', text: "I'm sore / tired today" },
    { emoji: '🔄', text: 'I need to swap an exercise' },
  ];

  function _chipsHTML() {
    return `<div class="coach-chips">${COACH_CHIPS.map((c, i) =>
      `<button type="button" class="coach-chip" data-chip="${i}">${c.emoji} ${_esc(c.text)}</button>`
    ).join('')}</div>`;
  }

  function _wireChips() {
    document.querySelectorAll('#coachThread .coach-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        const c = COACH_CHIPS[parseInt(btn.dataset.chip, 10)];
        const input = document.getElementById('coachInput');
        if (input) input.value = c.text;
        document.getElementById('coachForm')?.requestSubmit();
      });
    });
  }

  // L12 — human-readable time for dividers
  function _fmtRelTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    const now = new Date();
    const time = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    const dStr = d.toISOString().slice(0, 10);
    const todayStr = now.toISOString().slice(0, 10);
    const yest = new Date(now); yest.setDate(now.getDate() - 1);
    if (dStr === todayStr) return `Today · ${time}`;
    if (dStr === yest.toISOString().slice(0, 10)) return `Yesterday · ${time}`;
    return (typeof fmtDate === 'function' ? fmtDate(iso) : dStr) + ` · ${time}`;
  }

  function _renderThread(msgs) {
    const el = document.getElementById('coachThread');
    if (!el) return;
    if (!msgs || !msgs.length) {
      el.innerHTML = `<p class="coach-empty">No messages yet. Try one of these or write your own:</p>${_chipsHTML()}`;
      _wireChips();
      return;
    }
    // L12 — insert time dividers when gap ≥5 min or date changes
    const parts = [];
    let lastTs = null;
    for (const m of msgs) {
      const ts = m.created_at ? new Date(m.created_at).getTime() : null;
      const gapOk = ts && lastTs && (ts - lastTs >= 5 * 60 * 1000);
      const dateChange = ts && lastTs && new Date(ts).toISOString().slice(0, 10) !== new Date(lastTs).toISOString().slice(0, 10);
      if (gapOk || dateChange) {
        parts.push(`<div class="msg-divider">${_fmtRelTime(m.created_at)}</div>`);
      }
      parts.push(_msgHTML(m));
      if (ts) lastTs = ts;
    }
    el.innerHTML = parts.join('');
    el.scrollTop = el.scrollHeight;
  }

  function _appendMessages(msgs) {
    const el = document.getElementById('coachThread');
    if (!el) return;
    if (el.querySelector('.coach-empty')) el.innerHTML = '';
    el.insertAdjacentHTML('beforeend', msgs.map((m) => _msgHTML(m)).join(''));
    el.scrollTop = el.scrollHeight;
  }

  function _msgHTML(m) {
    const role = m.role === 'user' ? 'user' : 'assistant';
    const flag = m.flagged_injury
      ? ` <span class="coach-flag" title="Flagged as injury">flagged</span>`
      : '';
    return `
      <div class="coach-msg coach-msg-${role}">
        <div class="coach-msg-body">${_esc(m.body)}</div>
        ${flag}
      </div>
    `;
  }

  async function _onSubmit(e) {
    e.preventDefault();
    if (_sending) return;
    const input = document.getElementById('coachInput');
    const btn = document.getElementById('coachSendBtn');
    const body = (input?.value || '').trim();
    if (!body) return;

    _sending = true;
    btn.disabled = true;
    btn.textContent = 'Sending...';

    try {
      const res = await API.sendCoachMessage(body);
      input.value = '';
      _appendMessages([res.user_message, res.assistant_message]);
    } catch (err) {
      if (typeof showToast === 'function') {
        showToast(err.message || 'Failed to send', 'error');
      }
    } finally {
      _sending = false;
      btn.disabled = false;
      btn.textContent = 'Send';
    }
  }

  function _esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  return { open };
})();
