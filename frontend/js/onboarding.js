// ─── ONBOARDING FLOW — Premium Registration ─────
// Replaces the old 5-step wizard with a 7-step (splash+6) premium flow.
// Steps 1-6 are rendered into #obStep1..#obStep6 on init.

let _obStep = 0;
const OB_TOTAL = 6;
const _obData = {
  gender: null, age: '25', height_cm: '175', weight_kg: '75',
  goals: [], experience_level: null,
  gym_schedule_type: 'specific_days', gym_specific_days: [0,2,4], gym_every_n_days: 2,
  available_equipment: null, injuries: '',
  muscle_schedule: {}, inactivity: null, ai_split: null,
};

// SVG icon helper (inline, no React needed)
const _ic = {
  check: `<svg width="W" height="H" viewBox="0 0 24 24" fill="none" stroke="C" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  arrow: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.7)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>`,
  bolt: `<svg width="W" height="H" viewBox="0 0 24 24" fill="C" stroke="none"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
  chart: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`,
};
function ic(name, w, h, c) {
  return (_ic[name]||'').replace(/W/g,w||'16').replace(/H/g,h||'16').replace(/C/g,c||'currentColor');
}

// ── Splash animation on load ──
function _obInitSplash() {
  setTimeout(() => {
    const logo = document.getElementById('obSplashLogo');
    if (logo) logo.classList.add('floating');
    const txt = document.getElementById('obSplashText');
    if (txt) { txt.style.opacity = '1'; txt.style.transform = 'translateY(0)'; }
    const stats = document.getElementById('obSplashStats');
    if (stats) stats.style.opacity = '1';
    const cta = document.getElementById('obSplashCTA');
    if (cta) { cta.style.opacity = '1'; cta.style.transform = 'translateY(0)'; }
  }, 100);
}

// ── Navigation ──
function obNext() {
  if (_obStep === 0) { _obStep = 1; _obRender(); return; }
  // Validate current step
  if (_obStep === 1 && !_obData.gender) { showToast('Please select your gender'); return; }
  if (_obStep === 2 && _obData.goals.length === 0) { showToast('Pick at least one goal'); return; }
  if (_obStep === 3) {
    if (!_obData.experience_level) { showToast('Select your experience level'); return; }
    if (!_obData.available_equipment) { showToast('Pick your available equipment'); return; }
  }
  if (_obStep === 5 && !_obData.inactivity) { showToast('Select an option'); return; }
  if (_obStep < OB_TOTAL) { _obStep++; _obRender('right'); }
}
function obBack() {
  if (_obStep > 0) { _obStep--; _obRender('left'); }
}

function _obRender(dir) {
  // Hide all steps
  for (let i = 0; i <= OB_TOTAL; i++) {
    const el = document.getElementById('obStep' + i);
    if (el) { el.classList.remove('active','slide-right','slide-left'); }
  }
  // Show progress header for steps 1-6
  const hdr = document.getElementById('obProgressHeader');
  if (hdr) hdr.style.display = _obStep >= 1 ? '' : 'none';
  // Update progress
  if (_obStep >= 1) {
    document.getElementById('obStepCounter').textContent = `${_obStep}/${OB_TOTAL}`;
    const bar = document.getElementById('obProgressBar');
    bar.innerHTML = '';
    for (let i = 1; i <= OB_TOTAL; i++) {
      const seg = document.createElement('div');
      seg.className = 'ob-progress-seg' + (i < _obStep ? ' filled' : '') + (i === _obStep ? ' active' : '');
      if (i === _obStep) seg.innerHTML = '<div class="ob-progress-fill"></div>';
      bar.appendChild(seg);
    }
  }
  // Render step content if needed
  const stepEl = document.getElementById('obStep' + _obStep);
  if (_obStep >= 1 && (!stepEl.dataset.rendered || _obStep === 4 || _obStep === 5 || _obStep === 6)) {
    _obRenderStep(_obStep, stepEl);
    stepEl.dataset.rendered = '1';
  }
  // Animate in
  stepEl.classList.add('active');
  if (dir) stepEl.classList.add(dir === 'right' ? 'slide-right' : 'slide-left');
  // Scroll to top
  document.getElementById('obContainer').scrollTop = 0;
  haptic('selection');
}

// ── BG helper ──
function _obBg(c1,c2,c3) {
  return `<div class="ob-bg"><div class="orb orb-1" style="background:radial-gradient(circle,${c1}18 0%,transparent 70%)"></div><div class="orb orb-2" style="background:radial-gradient(circle,${c2}14 0%,transparent 70%)"></div><div class="orb orb-3" style="background:radial-gradient(circle,${c3}10 0%,transparent 70%)"></div><div class="orb-glow"></div></div>`;
}

// ── Step renderers ──
function _obRenderStep(n, el) {
  switch(n) {
    case 1: _obRenderAbout(el); break;
    case 2: _obRenderGoals(el); break;
    case 3: _obRenderGym(el); break;
    case 4: _obRenderMuscles(el); break;
    case 5: _obRenderAI(el); break;
    case 6: _obRenderSummary(el); break;
  }
}

// ── STEP 1: About You ──
function _obRenderAbout(el) {
  const d = _obData;
  el.innerHTML = _obBg('#A855F7','#3B82FF','#14B8A6') + `
  <div style="position:relative;z-index:1">
    <div style="margin-bottom:28px">
      <p class="ob-step-label" style="color:var(--blue)">Step 1 of 6</p>
      <h2 class="ob-step-title">About You</h2>
      <p class="ob-step-subtitle">Your stats power the AI to build a personalized plan</p>
    </div>
    <div style="margin-bottom:24px">
      <label class="ob-section-label">Gender</label>
      <div class="ob-gender-grid" id="obGender"></div>
    </div>
    <div style="margin-bottom:16px" id="obDrumAge"></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px">
      <div id="obDrumHeight"></div>
      <div id="obDrumWeight"></div>
    </div>
    <div id="obBmiPreview" style="margin-bottom:24px"></div>
    <button class="ob-btn ob-btn-primary" id="obStep1Btn" onclick="obNext()">Continue ${_ic.arrow}</button>
    <button class="ob-btn-back" onclick="obBack()">← Back</button>
  </div>`;
  // Gender cards
  const gg = el.querySelector('#obGender');
  ['male','female'].forEach(g => {
    const card = document.createElement('button');
    card.className = 'ob-gender-card' + (d.gender === g ? ' selected' : '');
    card.innerHTML = `<span style="font-size:28px">${g==='male'?'♂':'♀'}</span><span style="font-size:15px;font-weight:600;color:${d.gender===g?'var(--text-primary)':'var(--text-secondary)'}">${g.charAt(0).toUpperCase()+g.slice(1)}</span>${d.gender===g?'<div class="ob-check-badge">'+ic('check',10,10,'#fff')+'</div>':''}`;
    card.onclick = () => { d.gender = g; _obRenderStep(1, el); haptic('selection'); };
    gg.appendChild(card);
  });
  // Drum pickers
  _obDrum(el.querySelector('#obDrumAge'), 'Age', d.age, 14, 80, 'yrs', v => { d.age = v; _obUpdateBmi(el); });
  _obDrum(el.querySelector('#obDrumHeight'), 'Height', d.height_cm, 100, 250, 'cm', v => { d.height_cm = v; _obUpdateBmi(el); });
  _obDrum(el.querySelector('#obDrumWeight'), 'Weight', d.weight_kg, 30, 300, 'kg', v => { d.weight_kg = v; _obUpdateBmi(el); });
  _obUpdateBmi(el);
}

function _obUpdateBmi(el) {
  const d = _obData, bmiEl = el.querySelector('#obBmiPreview');
  if (!d.height_cm || !d.weight_kg) { bmiEl.innerHTML = ''; return; }
  const bmi = (Number(d.weight_kg) / Math.pow(Number(d.height_cm)/100, 2)).toFixed(1);
  const cat = bmi < 18.5 ? 'Underweight' : bmi < 25 ? 'Normal' : bmi < 30 ? 'Overweight' : 'Obese';
  bmiEl.innerHTML = `<div class="ob-bmi-card"><div style="width:36px;height:36px;border-radius:10px;background:rgba(59,130,255,0.15);display:flex;align-items:center;justify-content:center">${_ic.chart}</div><div><div style="font-size:11px;color:var(--text-tertiary);font-weight:600;letter-spacing:0.05em;text-transform:uppercase">BMI</div><div style="font-size:18px;font-weight:700;font-family:var(--font-display)">${bmi}</div></div><div style="margin-left:auto;font-size:12px;color:var(--text-secondary)">${cat}</div></div>`;
}

// ── STEP 2: Goals ──
function _obRenderGoals(el) {
  const goals = [
    {id:'build_muscle',label:'Build Muscle',desc:'Progressive workouts + protein targets',color:'#3B82FF',iconBg:'rgba(59,130,255,0.1)'},
    {id:'lose_fat',label:'Lose Fat',desc:'Caloric deficit + cardio integration',color:'#F97316',iconBg:'rgba(249,115,22,0.1)'},
    {id:'face_improvement',label:'Face Transform',desc:'Jawline, mewing & skin protocols',color:'#EC4899',iconBg:'rgba(236,72,153,0.1)'},
    {id:'better_sleep',label:'Better Sleep',desc:'Sleep optimization & wind-down',color:'#A855F7',iconBg:'rgba(168,85,247,0.1)'},
    {id:'general_health',label:'General Health',desc:'Daily habits, steps & hydration',color:'#00C896',iconBg:'rgba(0,200,150,0.1)'},
    {id:'posture_correction',label:'Fix Posture',desc:'Corrective exercises injected daily',color:'#EAB308',iconBg:'rgba(234,179,8,0.1)'},
  ];
  const sel = _obData.goals;
  let cards = '';
  goals.forEach((g,i) => {
    const s = sel.includes(g.id);
    cards += `<button class="ob-goal-card${s?' selected':''}" data-gid="${g.id}" style="border-color:${s?g.color+'60':'var(--border)'};background:${s?g.iconBg:'var(--bg-tertiary)'};animation:ob-fadeUp 0.3s ease ${i*0.05}s both">
      <div class="ob-goal-icon" style="background:${g.color}18">${ic('bolt',20,20,g.color)}</div>
      <div style="flex:1"><div style="font-size:15px;font-weight:600;color:${s?'var(--text-primary)':'var(--text-secondary)'}">${g.label}</div><div style="font-size:12px;color:var(--text-tertiary);margin-top:2px">${g.desc}</div></div>
      <div class="ob-goal-check${s?' checked':''}" style="background:${s?g.color:'var(--bg-secondary)'};border:${s?'none':'1.5px solid var(--text-tertiary)'}">${s?ic('check',12,12,'#fff'):''}</div>
    </button>`;
  });
  const n = sel.length;
  el.innerHTML = _obBg('#F97316','#EC4899','#3B82FF') + `<div style="position:relative;z-index:1">
    <div style="margin-bottom:24px"><p class="ob-step-label" style="color:var(--orange)">Step 2 of 6</p><h2 class="ob-step-title">Your Goals</h2><p class="ob-step-subtitle">Pick everything you want — the AI handles the rest</p></div>
    <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:28px" id="obGoalList">${cards}</div>
    ${n>0?`<div style="margin-bottom:16px;animation:ob-fadeIn 0.3s ease;padding:10px 14px;border-radius:10px;background:rgba(59,130,255,0.08);border:1px solid rgba(59,130,255,0.2)"><p style="font-size:12px;color:var(--blue)"><strong>${n} goal${n>1?'s':''} selected</strong> — AI will optimize your plan for all of them</p></div>`:''}
    <button class="ob-btn ob-btn-primary" onclick="obNext()" ${n===0?'disabled':''}>Continue with ${n} Goal${n!==1?'s':''}</button>
    <button class="ob-btn-back" onclick="obBack()">← Back</button>
  </div>`;
  el.querySelectorAll('.ob-goal-card').forEach(c => {
    c.onclick = () => {
      const id = c.dataset.gid;
      const idx = _obData.goals.indexOf(id);
      if (idx >= 0) _obData.goals.splice(idx, 1); else _obData.goals.push(id);
      _obRenderStep(2, el); haptic('selection');
    };
  });
}

// ── STEP 3: Gym Setup ──
function _obRenderGym(el) {
  const d = _obData;
  const levels = [{v:'beginner',l:'Beginner',s:'< 1 year',c:'#00C896'},{v:'intermediate',l:'Intermediate',s:'1–3 years',c:'#3B82FF'},{v:'advanced',l:'Advanced',s:'3+ years',c:'#A855F7'}];
  const equips = [{v:'full_gym',l:'Full Gym'},{v:'dumbbells_only',l:'Dumbbells'},{v:'home_basic',l:'Home Basic'},{v:'bodyweight',l:'Bodyweight'}];
  const scheds = [{v:'specific_days',l:'Specific Days'},{v:'every_n_days',l:'Every N Days'},{v:'daily',l:'Every Day'}];
  const dayL = ['M','T','W','T','F','S','S'];

  let lvlH = levels.map(l => {
    const s = d.experience_level === l.v;
    return `<button class="ob-level-card" data-lv="${l.v}" style="border-color:${s?l.c:'var(--border)'};background:${s?l.c+'18':'var(--bg-tertiary)'}"><div class="ob-level-dot" style="background:${l.c};box-shadow:${s?'0 0 8px '+l.c:'none'}"></div><span style="font-weight:600;color:${s?'var(--text-primary)':'var(--text-secondary)'};font-size:15px">${l.l}</span><span style="font-size:12px;color:var(--text-tertiary);margin-left:4px">${l.s}</span>${s?ic('check',14,14,l.c):'<span style="margin-left:auto"></span>'}</button>`;
  }).join('');

  let schedH = scheds.map(s => `<button class="ob-sched-btn${d.gym_schedule_type===s.v?' selected':''}" data-sv="${s.v}">${s.l}</button>`).join('');

  let daysH = '';
  if (d.gym_schedule_type === 'specific_days') {
    daysH = '<div style="margin-bottom:18px;animation:ob-fadeIn 0.3s ease"><label class="ob-section-label">Which Days?</label><div style="display:flex;gap:6px">';
    dayL.forEach((dl,i) => {
      const s = d.gym_specific_days.includes(i);
      daysH += `<button class="ob-day-btn${s?' selected':''}" data-di="${i}">${dl}</button>`;
    });
    daysH += '</div></div>';
  }
  let everyH = '';
  if (d.gym_schedule_type === 'every_n_days') {
    everyH = '<div style="margin-bottom:18px;animation:ob-fadeIn 0.3s ease"><label class="ob-section-label">Frequency</label><div style="display:flex;gap:8px">';
    [1,2,3].forEach(n => {
      everyH += `<button class="ob-sched-btn${d.gym_every_n_days===n?' selected':''}" data-en="${n}" style="flex:1">${n===1?'Every Day':'Every '+n+' Days'}</button>`;
    });
    everyH += '</div></div>';
  }

  let equipH = equips.map(e => {
    const s = d.available_equipment === e.v;
    return `<button class="ob-equip-card${s?' selected':''}" data-eq="${e.v}">${e.l}</button>`;
  }).join('');

  el.innerHTML = _obBg('#3B82FF','#00C896','#EAB308') + `<div style="position:relative;z-index:1">
    <div style="margin-bottom:24px"><p class="ob-step-label" style="color:var(--green)">Step 3 of 6</p><h2 class="ob-step-title">Gym Setup</h2><p class="ob-step-subtitle">We'll build a program that fits your reality</p></div>
    <div style="margin-bottom:22px"><label class="ob-section-label">Experience Level</label><div style="display:flex;flex-direction:column;gap:8px" id="obLevels">${lvlH}</div></div>
    <div style="margin-bottom:18px"><label class="ob-section-label">Training Schedule</label><div style="display:flex;gap:8px" id="obScheds">${schedH}</div></div>
    <div id="obDaysWrap">${daysH}</div>
    <div id="obEveryWrap">${everyH}</div>
    <div style="margin-bottom:24px"><label class="ob-section-label">Equipment</label><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px" id="obEquips">${equipH}</div></div>
    <div style="margin-bottom:28px"><label class="ob-section-label">Injuries / Limitations <span style="font-size:10px;font-weight:400;text-transform:none;letter-spacing:0">(optional)</span></label><textarea class="ob-textarea" rows="2" placeholder="e.g. bad knee, shoulder pain" id="obInjuries">${d.injuries}</textarea></div>
    <button class="ob-btn ob-btn-primary" onclick="obNext()">Continue</button>
    <button class="ob-btn-back" onclick="obBack()">← Back</button>
  </div>`;

  // Wire events
  el.querySelectorAll('.ob-level-card').forEach(c => c.onclick = () => { d.experience_level = c.dataset.lv; _obRenderStep(3,el); haptic('selection'); });
  el.querySelectorAll('.ob-sched-btn[data-sv]').forEach(c => c.onclick = () => { d.gym_schedule_type = c.dataset.sv; _obRenderStep(3,el); haptic('selection'); });
  el.querySelectorAll('.ob-day-btn').forEach(c => c.onclick = () => {
    const i = parseInt(c.dataset.di);
    const idx = d.gym_specific_days.indexOf(i);
    if (idx >= 0) d.gym_specific_days.splice(idx,1); else d.gym_specific_days.push(i);
    _obRenderStep(3,el); haptic('selection');
  });
  el.querySelectorAll('[data-en]').forEach(c => c.onclick = () => { d.gym_every_n_days = parseInt(c.dataset.en); _obRenderStep(3,el); haptic('selection'); });
  el.querySelectorAll('.ob-equip-card').forEach(c => c.onclick = () => { d.available_equipment = c.dataset.eq; _obRenderStep(3,el); haptic('selection'); });
  const inj = el.querySelector('#obInjuries');
  if (inj) inj.oninput = () => { d.injuries = inj.value; };
}

// ── Drum Picker (vanilla scroll-snap) ──
const DRUM_H = 48;
function _obDrum(container, label, value, min, max, unit, onChange) {
  const count = max - min + 1;
  let html = `<div class="ob-drum-picker"><label class="ob-section-label">${label}</label><div class="ob-drum-wrap"><div class="ob-drum-fade-top"></div><div class="ob-drum-fade-bottom"></div><div class="ob-drum-band"></div><div class="ob-drum-list">`;
  html += `<div style="height:${DRUM_H}px"></div>`;
  for (let i = 0; i < count; i++) {
    const v = min + i;
    html += `<div class="ob-drum-item" data-v="${v}"><span class="ob-drum-val">${v}</span></div>`;
  }
  html += `<div style="height:${DRUM_H}px"></div></div></div></div>`;
  container.innerHTML = html;

  const list = container.querySelector('.ob-drum-list');
  const idx = Math.max(0, Math.min(count - 1, Number(value) - min));
  // Lock _obData to the initial value immediately — the scroll handler below
  // would otherwise overwrite it with `min` if scrollTop assignment is no-op
  // (which happens while .ob-step is still display:none).
  onChange(String(min + idx));
  list.scrollTop = idx * DRUM_H;

  // Snap on scroll end
  let scrollTimer;
  list.addEventListener('scroll', () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      const nearest = Math.round(list.scrollTop / DRUM_H);
      const clamped = Math.max(0, Math.min(count - 1, nearest));
      list.scrollTo({ top: clamped * DRUM_H, behavior: 'smooth' });
      onChange(String(min + clamped));
      // Update visual styles
      container.querySelectorAll('.ob-drum-item').forEach(item => {
        const v = parseInt(item.dataset.v);
        const dist = Math.abs(v - (min + clamped));
        const valEl = item.querySelector('.ob-drum-val');
        valEl.style.fontSize = dist === 0 ? '26px' : '20px';
        valEl.style.fontWeight = dist === 0 ? '800' : '500';
        valEl.style.color = dist === 0 ? 'var(--text-primary)' : 'var(--text-secondary)';
        valEl.style.opacity = dist === 0 ? '1' : dist === 1 ? '0.5' : '0.2';
        // Show unit only for selected
        const existing = item.querySelector('.ob-drum-unit');
        if (existing) existing.remove();
        if (dist === 0 && unit) {
          const u = document.createElement('span');
          u.className = 'ob-drum-unit';
          u.textContent = unit;
          item.appendChild(u);
        }
      });
    }, 80);
  }, { passive: true });

  // Re-apply scrollTop after the step becomes visible. While .ob-step is
  // display:none, scrollTop assignment is a no-op. Double rAF + a microtask
  // wait ensures layout has run before we set the position.
  const _applyScroll = () => {
    if (list.clientHeight === 0) { requestAnimationFrame(_applyScroll); return; }
    list.scrollTop = idx * DRUM_H;
    list.dispatchEvent(new Event('scroll'));
  };
  requestAnimationFrame(() => requestAnimationFrame(_applyScroll));
}

// Init splash on load
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('obSplash')) _obInitSplash();
});
