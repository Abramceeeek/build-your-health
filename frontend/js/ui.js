// ─── USER UI ────────────────────────────────────
function updateUserUI() {
  if (!currentUser) return;
  const el = document.getElementById;
  document.getElementById('userName').textContent = currentUser.first_name || 'User';
  document.getElementById('userTier').textContent = `${currentUser.tier} · Lvl ${currentUser.level}`;

  const initials = (currentUser.first_name || 'U')[0].toUpperCase();
  const avatar = document.getElementById('userAvatar');
  avatar.textContent = initials;

  const tierColors = {Bronze:'#CD7F32',Silver:'#C0C0C0',Gold:'#FFD700',Opal:'#AF52DE',Diamond:'#00C7BE',Champion:'#FF2D55'};
  document.getElementById('userTier').style.color = tierColors[currentUser.tier] || '#CD7F32';
  updateMenuProfile();
}

function _ringLabel(value, emptyText) {
  if ((value || 0) > 0) return value + '%';
  return `<div class="ring-mini-bar"><div class="ring-mini-fill" style="width:0%"></div></div><small class="ring-hint">${emptyText}</small>`;
}

function updateRings(rings) {
  const h = rings.health || 0;
  const f = rings.fitness || 0;
  const s = rings.sleep || 0;
  const fc = rings.face || 0;

  document.getElementById('ringHealthPct').innerHTML = _ringLabel(h, 'Log to start');
  document.getElementById('ringFitnessPct').innerHTML = _ringLabel(f, 'Train to score');
  document.getElementById('ringSleepPct').innerHTML = _ringLabel(s, 'Log sleep');
  document.getElementById('ringFacePct').innerHTML = _ringLabel(fc, 'Add a face photo');

  const allEmpty = !h && !f && !s && !fc;
  let cta = document.getElementById('ringEmptyCta');
  if (allEmpty && !cta) {
    cta = document.createElement('div');
    cta.id = 'ringEmptyCta';
    cta.className = 'ring-cta-empty';
    cta.innerHTML = '<span>No plan yet</span><button class="empty-cta" onclick="switchPage(\'assistant\')">Generate Plan →</button>';
    document.querySelector('.rings-card').appendChild(cta);
  } else if (!allEmpty && cta) {
    cta.remove();
  }

  const _cs = getComputedStyle(document.documentElement);
  animateRing(document.getElementById('ringHealth'),  h,  _cs.getPropertyValue('--ring-health').trim(),  10, 1000);
  animateRing(document.getElementById('ringFitness'), f,  _cs.getPropertyValue('--ring-fitness').trim(), 10,  900);
  animateRing(document.getElementById('ringSleep'),   s,  _cs.getPropertyValue('--ring-sleep').trim(),   10,  800);
  animateRing(document.getElementById('ringFace'),    fc, _cs.getPropertyValue('--ring-face').trim(),     8, 1100);
}

function updateStats(today) {
  const done = today.done || 0;
  const total = today.total || 0;
  document.getElementById('statDone').textContent = done;
  // M6 — fraction is more motivating than a raw "left" count.
  document.getElementById('statLeft').textContent = `${done}/${total}`;

  const streak = currentUser?.streak_days || 0;
  const streakEl = document.getElementById('statStreak');
  streakEl.classList.remove('streak-day1', 'streak-building', 'streak-active', 'streak-broken');
  if (streak === 0 && isFirstDay(currentUser)) {
    streakEl.textContent = 'Day 1';
    streakEl.classList.add('streak-day1');
  } else if (streak === 0) {
    streakEl.textContent = 0;
    streakEl.classList.add('streak-broken');
  } else if (streak < 7) {
    streakEl.textContent = streak;
    streakEl.classList.add('streak-building');
  } else {
    streakEl.textContent = `${streak} 🔥`;
    streakEl.classList.add('streak-active');
  }
}

// ─── COMPETE PAGE ───────────────────────────────
async function loadCompetePage() {
  if (currentUser) {
    document.getElementById('ovrNumber').textContent = Math.round(currentUser.ovr_rating || 0);
    document.getElementById('ovrTier').textContent = currentUser.tier || 'Bronze';
    document.getElementById('ovrXp').textContent = `${currentUser.xp || 0} XP  ·  Level ${currentUser.level || 1}`;

    const tierColors = {Bronze:'#CD7F32',Silver:'#C0C0C0',Gold:'#FFD700',Opal:'#AF52DE',Diamond:'#00C7BE',Champion:'#FF2D55'};
    const color = tierColors[currentUser.tier] || '#CD7F32';
    animateRing(document.getElementById('ovrCanvas'), currentUser.ovr_rating || 0, color, 8, 1000);
    document.getElementById('ovrTier').style.color = color;
  }

  try {
    const comps = await API.getMyCompetitions();
    const listEl = document.getElementById('competitionsList');

    if (!comps || comps.length === 0) {
      listEl.innerHTML = '<div class="card"><div class="card-subtitle" style="text-align:center">No competitions yet. Create one and invite friends!</div></div>';
    } else {
      listEl.innerHTML = comps.map(c => `
        <div class="card" style="cursor:pointer;margin-bottom:8px" onclick="loadLeaderboard(${c.id})">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <div class="card-title">${c.name}</div>
              <div class="card-subtitle">${c.member_count} members · ${c.comp_type}</div>
            </div>
            <div style="text-align:right">
              <div style="font-size:11px;color:var(--text-tertiary)">Code</div>
              <div style="font-size:14px;font-weight:700;color:var(--blue)">${c.invite_code}</div>
            </div>
          </div>
        </div>
      `).join('');

      if (!activeCompId && comps.length > 0) {
        loadLeaderboard(comps[0].id);
      }
    }
  } catch (e) {
    console.error(e);
  }

  if (weekData.length) {
    drawWeekBars(document.getElementById('compWeekBars'), weekData);
  }
}

async function loadLeaderboard(compId) {
  activeCompId = compId;
  try {
    const entries = await API.getLeaderboard(compId);
    const listEl = document.getElementById('leaderboardList');

    const rankIcons = ['🥇','🥈','🥉'];
    const rankCls = ['gold','silver','bronze'];

    listEl.innerHTML = entries.map((e, i) => {
      const rankStr = i < 3 ? rankIcons[i] : String(i + 1);
      const color = COLORS[Math.abs(e.telegram_id) % COLORS.length];
      const initials = (e.first_name || '?')[0].toUpperCase();

      return `<div class="lb-row${e.is_self ? ' is-self' : ''}">
        <div class="lb-rank ${rankCls[i] || ''}">${rankStr}</div>
        <div class="lb-avatar" style="background:${color}">${initials}</div>
        <div class="lb-info">
          <div class="lb-name">${e.first_name}${e.is_self ? ' (you)' : ''}</div>
          <div class="lb-sub">${e.tasks_completed} tasks · ${e.completion_pct}%</div>
        </div>
        <div class="lb-score">${e.score}</div>
      </div>`;
    }).join('');
    loadHighlights(compId);
  } catch (e) {
    console.error(e);
  }
}

async function loadHighlights(compId) {
  try {
    const data = await fetch(`/api/competitions/${compId}/highlights`, {
      headers: { Authorization: getAuthHeader() }
    }).then(r => r.json());

    const section = document.getElementById('highlightsSection');
    const list = document.getElementById('highlightsList');

    if (data.highlights && data.highlights.length > 0) {
      section.style.display = 'block';
      list.innerHTML = data.highlights.map(h =>
        `<div class="highlight-item">
          <div class="highlight-icon">${h.icon}</div>
          <div class="highlight-info">
            <div class="highlight-label">${h.label}</div>
            <div class="highlight-name">${h.name} — ${h.value}</div>
          </div>
        </div>`
      ).join('');
    } else {
      section.style.display = 'none';
    }
  } catch (e) {
    document.getElementById('highlightsSection').style.display = 'none';
  }
}

// H10 — quick share. Mints (or reuses) a competition and pushes a Telegram share dialog.
async function shareCompeteInvite() {
  let code = null;
  try {
    const comps = await API.getMyCompetitions();
    if (comps && comps.length > 0) {
      code = comps[0].invite_code;
    } else {
      const created = await API.createCompetition({
        name: 'claudeGYM Challenge',
        comp_type: 'weekly',
        max_members: 10,
      });
      code = created.invite_code;
    }
  } catch (e) {
    showToast('Could not create invite — try Create instead.');
    return;
  }
  if (!code) return;

  const text = `Join my claudeGYM challenge! Code: ${code}`;
  const url = `https://t.me/share/url?url=${encodeURIComponent(location.origin + '?invite=' + code)}&text=${encodeURIComponent(text)}`;
  if (window.Telegram?.WebApp?.openTelegramLink) {
    window.Telegram.WebApp.openTelegramLink(url);
  } else {
    window.open(url, '_blank');
  }
  haptic('success');
}

// L7 — show tier progression so "Bronze · Lvl 1" reads as a starting point, not a label.
const TIER_LADDER = [
  { name: 'Bronze',   xp: 0,     color: '#CD7F32', emoji: '🥉' },
  { name: 'Silver',   xp: 500,   color: '#C0C0C0', emoji: '🥈' },
  { name: 'Gold',     xp: 1500,  color: '#FFD700', emoji: '🥇' },
  { name: 'Opal',     xp: 3500,  color: '#AF52DE', emoji: '🟣' },
  { name: 'Diamond',  xp: 7000,  color: '#00C7BE', emoji: '💎' },
  { name: 'Champion', xp: 15000, color: '#FF2D55', emoji: '👑' },
];

function showTierSheet() {
  const xp = currentUser?.xp || 0;
  const rows = TIER_LADDER.map(t => {
    const reached = xp >= t.xp;
    const status = reached ? 'Reached' : `${t.xp - xp} XP to go`;
    return `<div class="tier-row${reached ? ' reached' : ''}">
      <span class="tier-emoji">${t.emoji}</span>
      <span class="tier-name" style="color:${t.color}">${t.name}</span>
      <span class="tier-xp">${t.xp.toLocaleString()} XP</span>
      <span class="tier-status">${status}</span>
    </div>`;
  }).join('');
  openModal(`
    <h3 style="font-size:18px;font-weight:700;margin-bottom:8px">Tier progression</h3>
    <p style="font-size:12px;color:var(--text-tertiary);margin-bottom:14px">You're at ${xp.toLocaleString()} XP. Earn XP by completing tasks and hitting streaks.</p>
    <div class="tier-ladder">${rows}</div>
  `);
}

function showCreateComp() {
  openModal(`
    <h3 style="font-size:18px;font-weight:700;margin-bottom:16px">Create Competition</h3>
    <label class="input-label">Name</label>
    <input class="input-field" id="compName" placeholder="e.g., Weekly Grind" style="margin-bottom:12px">
    <label class="input-label">Duration</label>
    <select class="input-field" id="compType" style="margin-bottom:12px">
      <option value="weekly">Weekly (7 days)</option>
      <option value="monthly">Monthly (30 days)</option>
      <option value="sprint">Sprint (custom)</option>
    </select>
    <label class="input-label">Challenge Type</label>
    <select class="input-field" id="compChallenge" style="margin-bottom:16px">
      <option value="classic">Classic (overall score)</option>
      <option value="consistent">Most Consistent (daily completion)</option>
      <option value="streak">Streak Wars (longest streak)</option>
      <option value="nutrition">Nutrition Champion (meal logging)</option>
      <option value="strength">Iron Will (weight progression)</option>
    </select>
    <button class="btn btn-primary" onclick="createComp()">Create & Get Invite Link</button>
  `);
}

async function createComp() {
  const name = document.getElementById('compName').value.trim();
  const type = document.getElementById('compType').value;
  const challenge = document.getElementById('compChallenge').value;
  if (!name) { showToast('Enter a name'); return; }

  try {
    const res = await API.createCompetition({ name, comp_type: type, challenge_type: challenge });
    closeModal();
    showToast('Competition created!');

    const shareText = `Join my claudeGYM competition! Code: ${res.invite_code}`;
    if (tg && tg.switchInlineQuery) {
      tg.switchInlineQuery(shareText);
    }

    loadCompetePage();
  } catch (e) {
    showToast('Failed: ' + e.message);
  }
}

function showJoinComp(prefillCode) {
  openModal(`
    <h3 style="font-size:18px;font-weight:700;margin-bottom:16px">Join Competition</h3>
    <label class="input-label">Invite Code</label>
    <input class="input-field" id="joinCode" placeholder="e.g., ABC12345" value="${prefillCode || ''}" style="margin-bottom:16px">
    <button class="btn btn-primary" onclick="joinComp()">Join</button>
  `);
}

async function joinComp() {
  const code = document.getElementById('joinCode').value.trim();
  if (!code) { showToast('Enter a code'); return; }

  try {
    await API.joinCompetition(code);
    closeModal();
    showToast('Joined competition!');
    loadCompetePage();
  } catch (e) {
    showToast('Failed: ' + e.message);
  }
}

// ─── BADGES ────────────────────────────────────
let allBadges = [];

async function loadBadges() {
  try {
    const data = await API.getBadges();
    allBadges = data.badges || [];
    document.getElementById('badgeCounter').textContent = `${data.unlocked}/${data.total} unlocked`;
    renderBadges(allBadges);
  } catch (e) {
    console.error('Badge load error:', e);
  }
}

function renderBadges(badges) {
  const grid = document.getElementById('badgeGrid');
  const rarityColors = { common: 'var(--text-tertiary)', rare: 'var(--blue)', epic: 'var(--purple)', legendary: 'var(--yellow)' };

  // M3 — show name + requirement on locked badges so users have a target,
  // not a wall of "???"
  grid.innerHTML = badges.map(b => {
    const locked = !b.unlocked;
    const borderColor = locked ? 'var(--separator)' : (rarityColors[b.rarity] || 'var(--text-tertiary)');
    const requirement = b.requirement_text || b.description || '';
    return `<div class="badge-item${locked ? ' locked' : ''}" style="border-color:${borderColor}" title="${requirement}">
      <div class="badge-icon">${locked ? '🔒' : b.icon}</div>
      <div class="badge-name">${b.name}</div>
      <div class="badge-rarity" style="color:${rarityColors[b.rarity] || 'var(--text-tertiary)'}">${b.rarity}</div>
      ${locked && requirement ? `<div class="badge-req">${requirement}</div>` : ''}
    </div>`;
  }).join('');
}

function filterBadges(category, btn) {
  document.querySelectorAll('.badge-filter').forEach(f => f.classList.remove('active'));
  btn.classList.add('active');

  if (category === 'all') {
    renderBadges(allBadges);
  } else {
    renderBadges(allBadges.filter(b => b.category === category));
  }
}

// ─── ACHIEVEMENTS ───────────────────────────────
async function loadAchievements() {
  try {
    const achs = await API.getAchievements();
    const el = document.getElementById('achievementsList');

    if (!achs || achs.length === 0) {
      el.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-tertiary);font-size:13px">Complete tasks to unlock achievements</div>';
      return;
    }

    el.innerHTML = achs.map(a => `
      <div class="achievement-item animate-in">
        <div class="achievement-icon">${a.icon}</div>
        <div class="achievement-info">
          <div class="achievement-title">${a.title}</div>
          <div class="achievement-desc">${a.description}</div>
        </div>
      </div>
    `).join('');
  } catch (e) {}
}

// ─── HABITS ─────────────────────────────────────
function renderHabits(habits) {
  const el = document.getElementById('habitsList');
  if (!el) return;

  if (!habits || habits.length === 0) {
    el.innerHTML = '<div style="text-align:center;padding:16px;color:var(--text-tertiary);font-size:13px">Track habits like quitting smoking, alcohol, etc.</div>';
    return;
  }

  const icons = {smoking:'🚭',alcohol:'🚫',sugar:'🍬',junk_food:'🍔',social_media:'📵',caffeine:'☕'};

  el.innerHTML = habits.map(h => {
    const icon = icons[h.name?.toLowerCase()] || icons[h.habit_name?.toLowerCase()] || '✅';
    const name = h.name || h.habit_name || '';
    const days = h.days_since || 0;

    const months = Math.floor(days / 30);
    const remainDays = days % 30;
    let timeStr = `${days}d`;
    if (months > 0) timeStr = `${months}mo ${remainDays}d`;

    return `<div class="habit-card">
      <div class="habit-icon">${icon}</div>
      <div class="habit-info">
        <div class="habit-name">${name}</div>
        <div class="habit-since">since quitting</div>
      </div>
      <div class="habit-counter">
        <div class="habit-days">${timeStr}</div>
        <div class="habit-unit">clean</div>
      </div>
    </div>`;
  }).join('');
}

async function loadHabitsPage() {
  try {
    const habits = await API.getHabits();
    renderHabits(habits);
  } catch (e) {}
}

function showAddHabit() {
  openModal(`
    <h3 style="font-size:18px;font-weight:700;margin-bottom:16px">Add Tracker</h3>
    <label class="input-label">What are you quitting?</label>
    <input class="input-field" id="habitName" placeholder="e.g., Smoking, Alcohol, Sugar" style="margin-bottom:12px">
    <label class="input-label">Quit Date</label>
    <input class="input-field" id="habitDate" type="date" value="${new Date().toISOString().split('T')[0]}" style="margin-bottom:16px">
    <button class="btn btn-green" onclick="addHabit()">Start Tracking</button>
  `);
}

async function addHabit() {
  const name = document.getElementById('habitName').value.trim();
  const date = document.getElementById('habitDate').value;
  if (!name) { showToast('Enter a habit name'); return; }

  try {
    await API.createHabit({ habit_name: name, quit_date: date });
    closeModal();
    showToast('Tracker added!');
    loadHabitsPage();
  } catch (e) {
    showToast('Failed: ' + e.message);
  }
}

// ─── CONTRIBUTION CALENDAR ──────────────────────
async function loadCalendar() {
  try {
    const data = await API.getCalendarData(6);
    renderCalendar(data);
  } catch (e) {
    console.error('Calendar error:', e);
  }
}

function renderCalendar(data) {
  if (!data) return;

  const grid = document.getElementById('calendarGrid');
  const days = data.days || {};
  const summary = data.summary || {};

  document.getElementById('calStatActive').textContent = summary.active_days || 0;
  document.getElementById('calStatPerfect').textContent = summary.perfect_days || 0;
  document.getElementById('calStatPct').textContent = (summary.overall_pct || 0) + '%';
  // M13 — for new accounts, "X days in last 6 months" feels like a deficit.
  // Frame it as a journey instead.
  const ageDays = accountAgeDays(currentUser);
  document.getElementById('calendarSummary').textContent = ageDays < 14
    ? `Day ${ageDays + 1} of your journey 🚀`
    : `${summary.active_days || 0} days in the last 6 months`;

  const today = new Date();
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - 26 * 7);
  startDate.setDate(startDate.getDate() - startDate.getDay());

  let html = '';
  const current = new Date(startDate);

  for (let week = 0; week < 26; week++) {
    html += '<div class="calendar-week">';
    for (let dow = 0; dow < 7; dow++) {
      const dateStr = current.toISOString().split('T')[0];
      const dayData = days[dateStr];
      const pct = dayData ? dayData.pct : 0;
      const isFuture = current > today;

      let level = '';
      if (!isFuture && dayData) {
        if (pct >= 80) level = ' l4';
        else if (pct >= 60) level = ' l3';
        else if (pct >= 30) level = ' l2';
        else if (pct > 0) level = ' l1';
      }

      const tooltip = dayData ? `${dateStr}: ${dayData.done}/${dayData.total} (${pct}%)` : dateStr;
      html += `<div class="calendar-cell${level}" title="${tooltip}"></div>`;
      current.setDate(current.getDate() + 1);
    }
    html += '</div>';
  }

  grid.innerHTML = html;

  grid.scrollLeft = grid.scrollWidth;
}

// ─── BODY METRICS ───────────────────────────────
let _latestMetrics = null;

async function loadMetrics() {
  try {
    const data = await API.getLatestMetrics();
    _latestMetrics = (data && !data.message) ? data : null;
    if (_latestMetrics) {
      if (_latestMetrics.height_cm) document.getElementById('metricHeight').textContent = _latestMetrics.height_cm;
      if (_latestMetrics.weight_kg) document.getElementById('metricWeight').textContent = _latestMetrics.weight_kg;
      if (_latestMetrics.body_fat_pct) document.getElementById('metricBF').textContent = _latestMetrics.body_fat_pct;
      if (_latestMetrics.waist_cm) document.getElementById('metricWaist').textContent = _latestMetrics.waist_cm;
    }

    // H6 — nudge users to fill body-fat / waist so plan & calorie targets sharpen.
    document.getElementById('metricsNudge')?.remove();
    const missing = !(data && data.body_fat_pct && data.waist_cm);
    if (missing) {
      const grid = document.getElementById('metricsGrid');
      if (grid) {
        const nudge = document.createElement('button');
        nudge.id = 'metricsNudge';
        nudge.className = 'metrics-nudge';
        nudge.textContent = 'Add body fat % for more accurate targets →';
        nudge.onclick = showAddMetrics;
        grid.parentElement.insertBefore(nudge, grid.nextSibling);
      }
    }
  } catch (e) {}
}

function showAddMetrics() {
  const m = _latestMetrics || {};
  const v = (key, fallback) => m[key] != null ? m[key] : '';
  openModal(`
    <h3 style="font-size:18px;font-weight:700;margin-bottom:16px">Update Body Metrics</h3>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px">
      <div>
        <label class="input-label">Height (cm)</label>
        <input class="input-field" id="mHeight" type="number" placeholder="175" value="${v('height_cm')}">
      </div>
      <div>
        <label class="input-label">Weight (kg)</label>
        <input class="input-field" id="mWeight" type="number" placeholder="75" value="${v('weight_kg')}">
      </div>
      <div>
        <label class="input-label">Body Fat %</label>
        <input class="input-field" id="mBF" type="number" placeholder="18" value="${v('body_fat_pct')}">
      </div>
      <div>
        <label class="input-label">Waist (cm)</label>
        <input class="input-field" id="mWaist" type="number" placeholder="82" value="${v('waist_cm')}">
      </div>
      <div>
        <label class="input-label">Chest (cm)</label>
        <input class="input-field" id="mChest" type="number" placeholder="100" value="${v('chest_cm')}">
      </div>
      <div>
        <label class="input-label">Bicep (cm)</label>
        <input class="input-field" id="mBicep" type="number" placeholder="35" value="${v('bicep_cm')}">
      </div>
      <div>
        <label class="input-label">Neck (cm)</label>
        <input class="input-field" id="mNeck" type="number" placeholder="38" value="${v('neck_cm')}">
      </div>
      <div>
        <label class="input-label">Thigh (cm)</label>
        <input class="input-field" id="mThigh" type="number" placeholder="55" value="${v('thigh_cm')}">
      </div>
    </div>
    <button class="btn btn-green" onclick="saveMetrics()">Save Measurements</button>
  `);
}

async function saveMetrics() {
  const data = {
    height_cm: parseFloat(document.getElementById('mHeight').value) || null,
    weight_kg: parseFloat(document.getElementById('mWeight').value) || null,
    body_fat_pct: parseFloat(document.getElementById('mBF').value) || null,
    waist_cm: parseFloat(document.getElementById('mWaist').value) || null,
    chest_cm: parseFloat(document.getElementById('mChest').value) || null,
    bicep_cm: parseFloat(document.getElementById('mBicep').value) || null,
    neck_cm: parseFloat(document.getElementById('mNeck').value) || null,
    thigh_cm: parseFloat(document.getElementById('mThigh').value) || null,
  };

  try {
    await API.saveMetrics(data);
    closeModal();
    // L9 — 1-in-5 nudge toward honesty
    showToast(Math.random() < 0.2 ? 'Honest data = better results 🤝' : 'Metrics saved!');
    loadMetrics();
  } catch (e) {
    showToast('Failed: ' + e.message);
  }
}

// ─── HEATMAP ────────────────────────────────────
async function loadHeatmap() {
  const frontEl = document.getElementById('heatmapFront');
  const backEl = document.getElementById('heatmapBack');

  const svgFront = await loadSVGInline(frontEl, 'assets/body-front.svg');
  const svgBack = await loadSVGInline(backEl, 'assets/body-back.svg');

  let muscleData = {
    chest: 0, shoulders: 0, back: 0, biceps: 0, triceps: 0,
    forearms: 0, core: 0, quads: 0, hamstrings: 0, glutes: 0, calves: 0,
  };

  try {
    const heatmapRes = await API.getWeeklyHeatmap();
    if (heatmapRes && heatmapRes.muscle_data) {
      muscleData = heatmapRes.muscle_data;
    }
  } catch (e) {}

  if (svgFront) applyHeatmapToInlineSVG(svgFront, muscleData);
  if (svgBack) applyHeatmapToInlineSVG(svgBack, muscleData);

  // H4 — when nothing's lit up yet, surface a hint instead of a black silhouette.
  const empty = isAllZero(muscleData);
  document.querySelectorAll('.heatmap-empty-hint').forEach(n => n.remove());
  if (empty) {
    [frontEl, backEl].forEach(el => {
      if (!el) return;
      const hint = document.createElement('div');
      hint.className = 'heatmap-empty-hint';
      hint.textContent = 'Complete workouts to light up your muscle map';
      el.appendChild(hint);
    });
  }
}

// ─── PROGRESS TIMELINE ──────────────────────────
async function loadProgressTimeline() {
  try {
    const res = await API.getProgressTimeline();
    const el = document.getElementById('progressTimeline');
    if (!res || !res.weeks || res.weeks.length === 0) {
      el.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-tertiary);font-size:13px">Complete tasks to build your timeline</div>';
      return;
    }

    el.innerHTML = res.weeks.map((w, idx) => {
      if (w.is_first_week) {
        return `<div class="card" style="margin-bottom:8px">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="font-size:13px;color:var(--text-secondary)">Week of ${fmtDate(w.week_start)}</div>
            <div style="font-size:13px;color:var(--green)">Plan started ✓</div>
          </div>
        </div>`;
      }

      const catBars = Object.entries(w.categories || {}).map(([cat, pct]) => {
        const colors = {health:'var(--green)',fitness:'var(--blue)',sleep:'var(--purple)',face:'var(--orange)'};
        return `<div style="flex:1">
          <div style="height:4px;background:var(--bg-tertiary);border-radius:2px;overflow:hidden">
            <div style="height:100%;width:${pct}%;background:${colors[cat]||'var(--blue)'};border-radius:2px"></div>
          </div>
          <div style="font-size:9px;color:var(--text-tertiary);margin-top:2px;text-transform:capitalize">${cat}</div>
        </div>`;
      }).join('');

      return `<div class="card" style="margin-bottom:8px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div style="font-size:12px;color:var(--text-secondary)">${fmtDate(w.week_start)}</div>
          <div style="font-size:16px;font-weight:800;color:${w.pct >= 80 ? 'var(--green)' : w.pct >= 50 ? 'var(--orange)' : w.pct > 0 ? 'var(--red)' : 'var(--text-tertiary)'}">${w.pct}%</div>
        </div>
        <div class="progress-bar" style="margin-bottom:8px">
          <div class="progress-fill" style="width:${w.pct}%;background:${w.pct >= 80 ? 'var(--green)' : w.pct >= 50 ? 'var(--orange)' : w.pct > 0 ? 'var(--red)' : 'var(--bg-tertiary)'}"></div>
        </div>
        <div style="display:flex;gap:8px">${catBars}</div>
        <div style="font-size:11px;color:var(--text-tertiary);margin-top:4px">${w.done}/${w.total} tasks completed</div>
      </div>`;
    }).join('');
  } catch (e) {
    console.error('Timeline error:', e);
  }
}

// ─── MODAL ──────────────────────────────────────
function openModal(html) {
  const closeBtn = `<button onclick="closeModal()" aria-label="Close" style="position:absolute;top:12px;right:12px;background:none;border:none;color:var(--text-tertiary);font-size:20px;line-height:1;cursor:pointer;padding:4px">✕</button>`;
  document.getElementById('modalContent').innerHTML = `<div style="position:relative">${closeBtn}${html}</div>`;
  document.getElementById('modalOverlay').classList.add('active');
}

function closeModal(e) {
  // Called directly (no arg) from X button or code — always close.
  // Called from overlay onclick — close only if click landed on overlay itself.
  if (e instanceof Event && e.target !== document.getElementById('modalOverlay')) return;
  document.getElementById('modalOverlay').classList.remove('active');
}

// ─── NUTRITION PAGE ─────────────────────────────
let nutritionData = null;
let selectedMealType = 'breakfast';
let selectedFood = null;
let foodSearchTimeout = null;

function getTodayStr() {
  return new Date().toISOString().slice(0, 10);
}

async function loadNutritionPage() {
  try {
    const data = await API.getDailyNutrition(getTodayStr());
    nutritionData = data;
    renderNutritionSummary(data);
    renderMealSections(data.meals);
    _renderNutritionNudge(data.total_calories === 0);
  } catch (e) {
    renderNutritionSummary({
      total_calories: 0, total_protein: 0, total_carbs: 0, total_fat: 0,
      target_calories: 2200, target_protein: 150, target_carbs: 250, target_fat: 70,
    });
    _renderNutritionNudge(true);
  }
}

function _renderNutritionNudge(show) {
  const existing = document.getElementById('nutritionNudge');
  if (existing) existing.remove();
  if (!show) return;
  const card = document.getElementById('nutritionSummaryCard');
  if (!card) return;
  const nudge = document.createElement('div');
  nudge.id = 'nutritionNudge';
  nudge.className = 'empty-state';
  nudge.innerHTML = `
    <div class="empty-icon">🥗</div>
    <div class="empty-title">Nothing logged today</div>
    <div class="empty-body">Track your meals to hit your macro targets and fuel your training.</div>
    <button class="empty-cta" onclick="openFoodSearch('breakfast')">Search your first meal</button>
  `;
  card.parentElement.insertBefore(nudge, card.nextSibling);
}

function renderNutritionSummary(d) {
  document.getElementById('nutCalVal').textContent = Math.round(d.total_calories);
  document.getElementById('nutProVal').textContent = Math.round(d.total_protein) + 'g';
  document.getElementById('nutCarbVal').textContent = Math.round(d.total_carbs) + 'g';
  document.getElementById('nutFatVal').textContent = Math.round(d.total_fat) + 'g';
  document.getElementById('nutCalTarget').textContent = `/ ${Math.round(d.target_calories)}`;
  document.getElementById('nutProTarget').textContent = `/ ${Math.round(d.target_protein)}g`;
  document.getElementById('nutCarbTarget').textContent = `/ ${Math.round(d.target_carbs)}g`;
  document.getElementById('nutFatTarget').textContent = `/ ${Math.round(d.target_fat)}g`;

  const calPct = Math.min(100, Math.round(d.total_calories / d.target_calories * 100));
  const proPct = Math.min(100, Math.round(d.total_protein / d.target_protein * 100));
  const carbPct = Math.min(100, Math.round(d.total_carbs / d.target_carbs * 100));
  const fatPct = Math.min(100, Math.round(d.total_fat / d.target_fat * 100));

  document.getElementById('calBar').style.width = calPct + '%';
  document.getElementById('proBar').style.width = proPct + '%';
  document.getElementById('carbBar').style.width = carbPct + '%';
  document.getElementById('fatBar').style.width = fatPct + '%';
  document.getElementById('calPct').textContent = calPct + '%';
  document.getElementById('proPct').textContent = proPct + '%';
  document.getElementById('carbPct').textContent = carbPct + '%';
  document.getElementById('fatPct').textContent = fatPct + '%';
}

function renderMealSections(meals) {
  ['breakfast', 'lunch', 'dinner', 'snack'].forEach(meal => {
    const items = meals[meal] || [];
    const container = document.getElementById(meal + 'Items');
    const totalCal = items.reduce((s, i) => s + (i.calories || 0), 0);
    document.getElementById(meal + 'Cal').textContent = Math.round(totalCal) + ' kcal';

    if (!items.length) {
      container.innerHTML = '<div class="meal-empty">No foods logged</div>';
      return;
    }
    container.innerHTML = items.map(i => `
      <div class="meal-item">
        <div class="meal-item-info">
          <div class="meal-item-name">${i.food_name}</div>
          <div class="meal-item-detail">${Math.round(i.quantity_grams)}g · ${Math.round(i.protein_g)}p · ${Math.round(i.carbs_g)}c · ${Math.round(i.fat_g)}f</div>
        </div>
        <div class="meal-item-cal">${Math.round(i.calories)}</div>
        <button class="meal-item-delete" onclick="deleteFood(${i.id})">×</button>
      </div>
    `).join('');
  });
}

function openFoodSearch(meal) {
  selectedMealType = meal || 'breakfast';
  document.getElementById('foodSearchOverlay').style.display = 'flex';
  document.getElementById('foodSearchInput').value = '';
  document.getElementById('foodSearchResults').innerHTML = '<div class="food-search-empty">Search for a food to log</div>';
  setTimeout(() => document.getElementById('foodSearchInput').focus(), 100);
  // Pre-select the right meal chip in the log modal
  const chips = document.querySelectorAll('#foodLogMeal .gate-chip');
  chips.forEach(c => c.classList.toggle('active', c.dataset.val === selectedMealType));
}

function closeFoodSearch() {
  document.getElementById('foodSearchOverlay').style.display = 'none';
  document.getElementById('customFoodForm').style.display = 'none';
}

function toggleCustomFoodForm() {
  const form = document.getElementById('customFoodForm');
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function submitCustomFood() {
  const name = document.getElementById('cfName').value.trim();
  const cal = parseFloat(document.getElementById('cfCal').value) || 0;
  const pro = parseFloat(document.getElementById('cfPro').value) || 0;
  const carb = parseFloat(document.getElementById('cfCarb').value) || 0;
  const fat = parseFloat(document.getElementById('cfFat').value) || 0;

  if (!name) { showToast('Enter a food name'); return; }
  if (cal <= 0) { showToast('Enter calories'); return; }

  try {
    const result = await API.addCustomFood({
      name, calories_per_100g: cal, protein_per_100g: pro,
      carbs_per_100g: carb, fat_per_100g: fat, fibre_per_100g: 0,
    });
    showToast('Custom food saved!');
    haptic('success');
    // Clear form and show it in search results
    document.getElementById('cfName').value = '';
    document.getElementById('cfCal').value = '';
    document.getElementById('cfPro').value = '';
    document.getElementById('cfCarb').value = '';
    document.getElementById('cfFat').value = '';
    document.getElementById('customFoodForm').style.display = 'none';
    // Pre-fill search with this food name
    document.getElementById('foodSearchInput').value = name;
    doFoodSearch();
  } catch (e) {
    showToast('Failed: ' + e.message);
  }
}

function debounceFoodSearch() {
  clearTimeout(foodSearchTimeout);
  foodSearchTimeout = setTimeout(doFoodSearch, 400);
}

async function doFoodSearch() {
  const q = document.getElementById('foodSearchInput').value.trim();
  if (q.length < 2) {
    document.getElementById('foodSearchResults').innerHTML = '<div class="food-search-empty">Type at least 2 characters</div>';
    return;
  }
  document.getElementById('foodSearchResults').innerHTML = '<div class="food-search-empty">Searching...</div>';

  try {
    const results = await API.searchFood(q);
    if (!results.length) {
      document.getElementById('foodSearchResults').innerHTML = '<div class="food-search-empty">No results found</div>';
      return;
    }
    document.getElementById('foodSearchResults').innerHTML = results.map((r, i) => `
      <div class="food-result-item" onclick='selectFoodResult(${JSON.stringify(r).replace(/'/g, "&#39;")})'>
        <div class="food-result-name">${r.name}</div>
        <div class="food-result-macros">
          ${Math.round(r.calories_per_100g)} kcal · ${Math.round(r.protein_per_100g)}p · ${Math.round(r.carbs_per_100g)}c · ${Math.round(r.fat_per_100g)}f
          <span class="food-result-source">${r.source === 'usda' ? 'USDA' : 'OFF'}</span>
        </div>
      </div>
    `).join('');
  } catch (e) {
    const isTimeout = e.name === 'TimeoutError' || e.name === 'AbortError';
    const msg = isTimeout ? 'Request timed out' : (e.message || 'Search failed');
    document.getElementById('foodSearchResults').innerHTML =
      `<div class="food-search-empty">${msg} — <button onclick="doFoodSearch()" style="background:none;border:none;color:var(--blue);cursor:pointer;font-size:inherit;padding:0">Retry</button></div>`;
  }
}

function selectFoodResult(food) {
  selectedFood = food;
  closeFoodSearch();
  document.getElementById('foodLogOverlay').style.display = 'flex';
  document.getElementById('foodLogTitle').textContent = food.name;
  document.getElementById('foodLogGrams').value = 100;
  updateFoodLogPreview();
}

function updateFoodLogPreview() {
  if (!selectedFood) return;
  const grams = parseFloat(document.getElementById('foodLogGrams').value) || 100;
  const factor = grams / 100;
  document.getElementById('foodLogNutrients').innerHTML = `
    <div class="food-log-macro-row">
      <span>Calories</span><span>${Math.round(selectedFood.calories_per_100g * factor)}</span>
    </div>
    <div class="food-log-macro-row">
      <span>Protein</span><span>${(selectedFood.protein_per_100g * factor).toFixed(1)}g</span>
    </div>
    <div class="food-log-macro-row">
      <span>Carbs</span><span>${(selectedFood.carbs_per_100g * factor).toFixed(1)}g</span>
    </div>
    <div class="food-log-macro-row">
      <span>Fat</span><span>${(selectedFood.fat_per_100g * factor).toFixed(1)}g</span>
    </div>
    <div class="food-log-macro-row">
      <span>Fibre</span><span>${(selectedFood.fibre_per_100g * factor).toFixed(1)}g</span>
    </div>
  `;
}

function closeFoodLog() {
  document.getElementById('foodLogOverlay').style.display = 'none';
  selectedFood = null;
}

async function submitFoodLog() {
  if (!selectedFood) return;
  const grams = parseFloat(document.getElementById('foodLogGrams').value) || 100;
  const factor = grams / 100;
  const mealChip = document.querySelector('#foodLogMeal .gate-chip.active');
  const meal = mealChip ? mealChip.dataset.val : selectedMealType;

  try {
    await API.logFood({
      date: getTodayStr(),
      meal_type: meal,
      food_name: selectedFood.name,
      quantity_grams: grams,
      calories: Math.round(selectedFood.calories_per_100g * factor * 10) / 10,
      protein_g: Math.round(selectedFood.protein_per_100g * factor * 10) / 10,
      carbs_g: Math.round(selectedFood.carbs_per_100g * factor * 10) / 10,
      fat_g: Math.round(selectedFood.fat_per_100g * factor * 10) / 10,
      fibre_g: Math.round(selectedFood.fibre_per_100g * factor * 10) / 10,
      source: selectedFood.source,
      source_id: selectedFood.source_id,
    });
    closeFoodLog();
    haptic('success');
    showToast('Food logged!');
    loadNutritionPage();
  } catch (e) {
    showToast('Failed to log food');
  }
}

async function deleteFood(logId) {
  try {
    await API.deleteNutritionLog(logId);
    haptic('success');
    loadNutritionPage();
  } catch (e) {
    showToast('Failed to delete');
  }
}

function toggleMealSection(meal) {
  const section = document.getElementById('meal' + meal.charAt(0).toUpperCase() + meal.slice(1));
  if (section) section.classList.toggle('expanded');
}

