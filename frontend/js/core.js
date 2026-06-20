// ─── TELEGRAM INIT ──────────────────────────────
const tg = window.Telegram && window.Telegram.WebApp;
let currentUser = null;
let selectedDay = null;
let weekData = [];
let activeCompId = null;
const DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const COLORS = ['#FF3B30','#FF9500','#34C759','#007AFF','#5856D6','#FF2D55','#AF52DE','#00C7BE'];

const IS_LOCAL = ['localhost', '127.0.0.1'].includes(location.hostname);
const HAS_TELEGRAM = !!(tg && tg.initData);

if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor('#000000');
  tg.setBackgroundColor('#000000');
}

// Inside Telegram the native chrome provides navigation — hide our header to avoid doubling.
if (HAS_TELEGRAM) {
  document.querySelector('.app-header')?.classList.add('tg-hidden');
  document.body.classList.add('in-telegram');
}

// ─── TELEGRAM GATE ──────────────────────────────
// Outside Telegram and not running locally → show gate, halt the rest of the app.
async function _showTelegramGate() {
  document.querySelectorAll('.app-header, .side-menu, .menu-overlay, .page').forEach(el => {
    el.style.display = 'none';
  });
  const gate = document.getElementById('tgGate');
  if (!gate) return;
  gate.hidden = false;
  try {
    const r = await fetch('/api/public/config');
    const cfg = await r.json();
    if (cfg.bot_username) {
      const a = document.getElementById('tgGateLink');
      if (a) a.href = `https://t.me/${cfg.bot_username}?startapp=1`;
    }
  } catch (_) { /* fallback href stays */ }
}

if (!HAS_TELEGRAM && !IS_LOCAL) {
  _showTelegramGate();
}

// ─── INIT ───────────────────────────────────────
async function init() {
  // Persist the device timezone (fire-and-forget) so "today", streaks, heatmap and reminders
  // follow the user's local calendar day. getTimezoneOffset() is minutes behind UTC, so negate.
  API.setTimezone(-new Date().getTimezoneOffset()).catch(() => {});

  // Check registration & truth gate
  try {
    const status = await API.getRegistrationStatus();
    if (!status.is_registered) {
      document.getElementById('registrationOverlay').style.display = 'flex';
      return;
    }
    document.getElementById('registrationOverlay').style.display = 'none';
    if (!status.truth_confirmed_today) {
      document.getElementById('truthOverlay').style.display = 'flex';
      return;
    }
    document.getElementById('truthOverlay').style.display = 'none';
  } catch (e) {
    // Registration status unknown — keep overlay visible rather than exposing a broken dashboard.
    // User can retry by tapping the button below.
    const overlay = document.getElementById('registrationOverlay');
    if (overlay && overlay.style.display !== 'none') {
      const retryEl = overlay.querySelector('.wizard-retry-msg') || document.createElement('div');
      retryEl.className = 'wizard-retry-msg';
      retryEl.style.cssText = 'text-align:center;color:var(--text-tertiary);font-size:12px;margin-top:8px';
      retryEl.innerHTML = 'Could not connect. <button onclick="init()" style="background:none;border:none;color:var(--blue);cursor:pointer;font-size:12px;padding:0">Retry</button>';
      if (!overlay.querySelector('.wizard-retry-msg')) (overlay.querySelector('.ob-container') || overlay).appendChild(retryEl);
    }
    return;
  }

  loadDashboard();
}

async function loadDashboard() {
  try {
    const [dashboard, week] = await Promise.all([
      API.getDashboard().catch(() => null),
      API.getWeekTasks().catch(() => null),
    ]);

    if (dashboard) {
      currentUser = dashboard.user;
      updateUserUI();
      updateRings(dashboard.rings || {});
      updateStats(dashboard.today || {});

      // C3 — Day 1 with no tasks: show a welcome empty state above the rings
      // so the dashboard reads as "ready", not "broken zeros".
      const noTasks = !(dashboard.today && dashboard.today.total);
      const banner = document.getElementById('day1Welcome');
      if (banner) banner.remove();
      if (isFirstDay(currentUser) && noTasks) {
        const host = document.getElementById('pageToday')?.querySelector('.main-content');
        if (host) {
          const wrap = document.createElement('div');
          wrap.id = 'day1Welcome';
          host.prepend(wrap);
          renderEmpty(wrap, {
            icon: '👋',
            title: `Welcome${currentUser?.first_name ? ', ' + currentUser.first_name : ''}`,
            body: 'Generate your first plan to start training.',
            ctaLabel: 'Generate plan',
            ctaOnClick: () => switchPage('assistant'),
          });
        }
      }

      if (dashboard.habits) {
        renderHabits(dashboard.habits);
      }
    }

    if (week && week.week) {
      weekData = week.week;
      const todayStr = new Date().toISOString().slice(0, 10);
      // 11-day window is today-centred. Find today by date, fall back to middle.
      const todayEntry = weekData.find(d => d.date === todayStr);
      selectedDay = todayEntry?.date
        || weekData[Math.floor(weekData.length / 2)]?.date
        || weekData[0]?.date;
      renderDayScroller();
      loadDayTasks(selectedDay);
    }
  } catch (e) {
    console.error('Init error:', e);
    setupFallback();
  }

  loadHealthTracker();
  loadHeatmap();
  loadAchievements();

  // Mark initial tab active
  const initTab = document.querySelector('.bottom-tab[data-page="today"]');
  if (initTab) initTab.classList.add('active');

  const params = new URLSearchParams(window.location.search);
  if (params.get('page')) switchPage(params.get('page'));
  if (params.get('invite')) {
    showJoinComp(params.get('invite'));
  }
  // Referral capture (?ref=<id> or Telegram start_param "ref_<id>")
  const startParam = (window.Telegram && Telegram.WebApp && Telegram.WebApp.initDataUnsafe && Telegram.WebApp.initDataUnsafe.start_param) || '';
  const refRaw = params.get('ref') || startParam.replace(/^ref_/, '');
  if (refRaw && /^\d+$/.test(refRaw)) window._referredBy = parseInt(refRaw, 10);
}

async function shareReferral() {
  try {
    if (!currentUser || !currentUser.id) { showToast('Open the app first'); return; }
    const cfg = await fetch('/api/public/config').then(r => r.json());
    const bot = cfg.bot_username;
    if (!bot) { showToast('Referral link unavailable'); return; }
    const link = `https://t.me/${bot}?start=ref_${currentUser.id}`;
    const text = 'Join me on claudeGYM — we both get +7 days of Pro!';
    if (window.Telegram && Telegram.WebApp && Telegram.WebApp.openTelegramLink) {
      Telegram.WebApp.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`);
    } else if (navigator.clipboard) {
      await navigator.clipboard.writeText(link);
      showToast('Referral link copied');
    }
  } catch (e) {
    showToast('Could not create referral link');
  }
}

async function showWeeklyReview() {
  if (typeof closeMenu === 'function') closeMenu();
  openModal('<div style="text-align:center;padding:24px;color:var(--text-secondary)">Generating your weekly review…</div>');
  try {
    const d = await API.getWeeklyReview();
    const r = (d && d.review) || {};
    const acts = (r.action_items || []).map(a => `<li>${escHtml(a)}</li>`).join('');
    const cites = (r.citations || []).map(c =>
      `<a href="${escHtml(c.url)}" target="_blank" rel="noopener" style="color:var(--accent);font-size:12px;display:block;margin-top:4px">${escHtml(c.title)}</a>`
    ).join('');
    openModal(`
      <h3 style="font-size:18px;font-weight:700;margin-bottom:6px">Weekly Review${r.overall_grade ? ' · ' + escHtml(r.overall_grade) : ''}</h3>
      <p style="color:var(--text-secondary);margin-bottom:12px">${escHtml(r.headline || '')}</p>
      ${r.top_win ? `<div style="font-size:13px;margin-bottom:6px"><b>Top win:</b> ${escHtml(r.top_win)}</div>` : ''}
      ${r.top_fix ? `<div style="font-size:13px;margin-bottom:6px"><b>Top fix:</b> ${escHtml(r.top_fix)}</div>` : ''}
      ${acts ? `<ul style="font-size:13px;margin:8px 0 8px 18px;line-height:1.6">${acts}</ul>` : ''}
      ${cites ? `<div style="margin-top:12px;font-size:11px;color:var(--text-tertiary)">Backed by research</div>${cites}` : ''}
    `);
  } catch (e) {
    openModal(`<div style="padding:18px;color:var(--text-secondary)">${escHtml((e && e.message) || 'Could not load review')}.<br><br>Weekly Review is a Pro feature.</div>`);
  }
}

function setupFallback() {
  // Offline / first-load fallback: produce an 11-day window centred on today
  // so the scroller still renders something while the API is unreachable.
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - 5);

  weekData = [];
  for (let i = 0; i < 11; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const wd = (d.getDay() + 6) % 7; // 0=Mon..6=Sun
    weekData.push({
      date: d.toISOString().split('T')[0],
      day_name: DAYS[wd],
      pct: 0, done: 0, total: 0,
      day_type: [0,2,4].includes(wd) ? 'gym' : 'rest',
      focus: ['Push day','Recovery','Pull day','Recovery','Legs + core','Active rest','Full rest'][wd],
    });
  }
  const todayStr = today.toISOString().split('T')[0];
  selectedDay = weekData.find(d => d.date === todayStr)?.date || weekData[5]?.date;
  renderDayScroller();
  loadDayTasks(selectedDay);
}

// ─── SIDE MENU ─────────────────────────────────
function toggleMenu() {
  const menu = document.getElementById('sideMenu');
  const overlay = document.getElementById('menuOverlay');
  const btn = document.getElementById('hamburgerBtn');
  const isOpen = menu.classList.contains('open');
  if (isOpen) { closeMenu(); } else {
    menu.classList.add('open');
    overlay.classList.add('open');
    btn.classList.add('open');
  }
}

function closeMenu() {
  document.getElementById('sideMenu').classList.remove('open');
  document.getElementById('menuOverlay').classList.remove('open');
  document.getElementById('hamburgerBtn').classList.remove('open');
}

function menuNavigate(page) {
  closeMenu();
  switchPage(page);
}

function updateMenuProfile() {
  if (!currentUser) return;
  const initials = (currentUser.first_name || 'U')[0].toUpperCase();
  document.getElementById('menuAvatar').textContent = initials;
  document.getElementById('menuUserName').textContent = currentUser.first_name || 'User';
  document.getElementById('menuUserTier').textContent = `${currentUser.tier} · Lvl ${currentUser.level}`;
}

// ─── PAGE SWITCHING ─────────────────────────────
function switchPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.menu-item').forEach(n => n.classList.remove('active'));
  document.querySelectorAll('.bottom-tab').forEach(n => n.classList.remove('active'));

  const pageId = 'page' + page.charAt(0).toUpperCase() + page.slice(1);
  const pageEl = document.getElementById(pageId);
  if (pageEl) pageEl.classList.add('active');

  const menuEl = document.querySelector(`.menu-item[data-page="${page}"]`);
  if (menuEl) menuEl.classList.add('active');

  const tabEl = document.querySelector(`.bottom-tab[data-page="${page}"]`);
  if (tabEl) tabEl.classList.add('active');

  // Scroll to top on page change
  window.scrollTo(0, 0);

  if (page === 'progress') { loadCalendar(); loadBadges(); loadAchievements(); loadHabitsPage(); loadHeatmap(); loadCompetePage(); }
  if (page === 'assistant') { loadMetrics(); loadProgressTimeline(); loadAssistantStatus(); }
  if (page === 'nutrition') loadNutritionPage();
  if (page === 'settings') loadSettingsPage();
  if (page === 'face') { /* Coming soon page — no data to load */ }

  haptic('selection');
}

// ─── TOAST ──────────────────────────────────────
let toastTimer;
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2500);
}

// ─── HAPTICS ────────────────────────────────────
function haptic(type) {
  if (!tg || !tg.HapticFeedback) return;
  if (type === 'selection') tg.HapticFeedback.selectionChanged();
  else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
  else tg.HapticFeedback.impactOccurred(type);
}

// ─── START ──────────────────────────────────────
if (HAS_TELEGRAM || IS_LOCAL) init();
