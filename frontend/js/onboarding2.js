// ─── ONBOARDING PART 2: Steps 4-6, Submit, Truth ─────

// ── STEP 4: Muscle Split ──
function _obRenderMuscles(el) {
  const d = _obData;
  const muscles = ['Chest','Back','Legs','Shoulders','Biceps','Triceps','Abs','Neck','Forearms','Rear Delts','Calves'];
  const mColors = {Chest:'#3B82FF',Back:'#00C896',Legs:'#F97316',Shoulders:'#A855F7',Biceps:'#EC4899',Triceps:'#14B8A6',Abs:'#EAB308',Neck:'#FF3B30',Forearms:'#6366F1','Rear Delts':'#8B5CF6',Calves:'#10B981'};
  const dayNames = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const gymDays = d.gym_schedule_type === 'daily' ? [0,1,2,3,4,5,6] : d.gym_schedule_type === 'specific_days' ? d.gym_specific_days : [0,2,4];
  if (!el._activeDay || !gymDays.includes(el._activeDay)) el._activeDay = gymDays[0] || 0;
  const activeDay = el._activeDay;

  const presets = [
    {name:'Push/Pull/Legs',days:{0:['Chest','Shoulders','Triceps'],1:['Back','Biceps','Rear Delts'],2:['Legs','Calves','Abs']}},
    {name:'Upper/Lower',days:{0:['Chest','Back','Shoulders'],1:['Legs','Calves'],2:['Chest','Back','Biceps'],3:['Legs','Abs']}},
    {name:'Full Body',days:{0:['Chest','Back','Legs','Shoulders'],1:['Chest','Back','Legs','Shoulders'],2:['Chest','Back','Legs','Shoulders']}},
  ];

  let tabsH = gymDays.map(day => {
    const dm = d.muscle_schedule[day] || [];
    return `<button class="ob-day-tab${activeDay===day?' active':''}" data-day="${day}">${dayNames[day]}${dm.length>0?`<span class="ob-day-count">${dm.length}</span>`:''}</button>`;
  }).join('');

  let chipsH = muscles.map(m => {
    const s = (d.muscle_schedule[activeDay]||[]).includes(m);
    const c = mColors[m];
    return `<button class="ob-muscle-chip${s?' selected':''}" data-m="${m}" style="border-color:${s?c:'var(--border)'};background:${s?c+'20':'var(--bg-tertiary)'};color:${s?c:'var(--text-secondary)'}">${s?ic('check',10,10,c)+' ':''}${m}</button>`;
  }).join('');

  let summaryH = '';
  const hasSchedule = Object.keys(d.muscle_schedule).length > 0;
  if (hasSchedule) {
    summaryH = '<div style="margin-bottom:20px;animation:ob-fadeIn 0.3s ease"><label class="ob-section-label">Plan Summary</label><div style="display:flex;flex-direction:column;gap:6px">';
    gymDays.forEach(day => {
      const ms = d.muscle_schedule[day] || [];
      if (!ms.length) return;
      summaryH += `<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:10px;background:var(--bg-tertiary);border:1px solid var(--border)"><span style="font-size:12px;font-weight:700;color:var(--purple);min-width:28px">${dayNames[day]}</span><div style="display:flex;gap:4px;flex-wrap:wrap">${ms.map(m=>`<span style="font-size:11px;padding:2px 8px;border-radius:10px;background:${mColors[m]}20;color:${mColors[m]};font-weight:600">${m}</span>`).join('')}</div></div>`;
    });
    summaryH += '</div></div>';
  }

  el.innerHTML = _obBg('#3B82FF','#00C896','#EAB308') + `<div style="position:relative;z-index:1">
    <div style="margin-bottom:24px"><p class="ob-step-label" style="color:var(--purple)">Step 4 of 6</p><h2 class="ob-step-title">Muscle Split</h2><p class="ob-step-subtitle">Assign muscles to each training day</p></div>
    <div style="margin-bottom:20px"><label class="ob-section-label">Quick Presets</label><div style="display:flex;gap:8px;flex-wrap:wrap" id="obPresets">${presets.map(p=>`<button class="ob-split-preset" data-pn="${p.name}">${ic('bolt',10,10,'var(--purple)')} ${p.name}</button>`).join('')}</div></div>
    <div style="margin-bottom:16px"><div style="display:flex;gap:6px;overflow-x:auto;padding-bottom:4px" id="obDayTabs">${tabsH}</div></div>
    <div style="margin-bottom:24px"><label class="ob-section-label">${dayNames[activeDay]} — Select Muscles</label><div style="display:flex;flex-wrap:wrap;gap:8px" id="obMuscleChips">${chipsH}</div></div>
    ${summaryH}
    <button class="ob-btn ob-btn-primary" onclick="obNext()">Continue</button>
    <button class="ob-btn-back" onclick="obBack()">← Back</button>
  </div>`;

  // Wire presets
  el.querySelectorAll('.ob-split-preset').forEach(b => b.onclick = () => {
    const p = presets.find(x => x.name === b.dataset.pn);
    if (!p) return;
    const schedule = {};
    gymDays.forEach((day, i) => {
      const splitDays = Object.values(p.days);
      schedule[day] = splitDays[i % splitDays.length];
    });
    d.muscle_schedule = schedule;
    _obRenderStep(4, el); haptic('selection');
  });
  // Wire tabs
  el.querySelectorAll('.ob-day-tab').forEach(b => b.onclick = () => { el._activeDay = parseInt(b.dataset.day); _obRenderStep(4, el); });
  // Wire chips
  el.querySelectorAll('.ob-muscle-chip').forEach(b => b.onclick = () => {
    const m = b.dataset.m;
    const dayM = d.muscle_schedule[activeDay] || [];
    const idx = dayM.indexOf(m);
    if (idx >= 0) dayM.splice(idx, 1); else dayM.push(m);
    d.muscle_schedule[activeDay] = dayM;
    _obRenderStep(4, el); haptic('selection');
  });
}

// ── STEP 5: AI Split ──
function _obRenderAI(el) {
  const d = _obData;
  const opts = [
    {v:'active',l:'Currently Active',icon:'🔥',sub:'Training regularly'},
    {v:'1_month',l:'1 Month Out',icon:'📅',sub:'Short break'},
    {v:'3_months',l:'3 Months Out',icon:'⏸️',sub:'Moderate deload'},
    {v:'6_months',l:'6 Months Out',icon:'📆',sub:'Significant break'},
    {v:'1_year',l:'1+ Year Out',icon:'🕐',sub:'Major restart'},
    {v:'never',l:'Never Trained',icon:'✨',sub:'Starting fresh'},
  ];
  const loading = el._aiLoading || false;
  const result = el._aiResult || null;

  let optsH = opts.map((o,i) => {
    const s = d.inactivity === o.v;
    return `<button class="ob-ai-option${s?' selected':''}" data-av="${o.v}" style="animation:ob-fadeUp 0.3s ease ${i*0.05}s both">
      <span style="font-size:20px;flex-shrink:0">${o.icon}</span>
      <div style="flex:1"><div style="font-weight:600;font-size:14px;color:${s?'var(--text-primary)':'var(--text-secondary)'}">${o.l}</div><div style="font-size:12px;color:var(--text-tertiary);margin-top:1px">${o.sub}</div></div>
      ${s && !loading ? ic('check',16,16,'var(--blue)') : ''}
      ${s && loading ? '<div class="ob-btn-spinner" style="width:16px;height:16px;border-width:2px"></div>' : ''}
    </button>`;
  }).join('');

  let resultH = '';
  if (loading) {
    resultH = `<div class="ob-ai-loading" style="margin-bottom:24px"><div style="display:flex;align-items:center;gap:10px;margin-bottom:14px"><div class="dot"></div><div class="dot" style="animation-delay:0.2s"></div><div class="dot" style="animation-delay:0.4s"></div><span style="font-size:13px;color:var(--text-secondary);margin-left:4px">AI analyzing your profile...</span></div><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,var(--bg-secondary),var(--text-tertiary),var(--bg-secondary));background-size:200% 100%;animation:shimmer 1.5s infinite;margin-bottom:8px"></div><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,var(--bg-secondary),var(--text-tertiary),var(--bg-secondary));background-size:200% 100%;animation:shimmer 1.5s infinite;width:70%"></div></div>`;
  } else if (result) {
    resultH = `<div class="ob-ai-result" style="margin-bottom:24px"><div style="display:flex;align-items:center;gap:10px;margin-bottom:12px"><div style="width:36px;height:36px;border-radius:10px;background:rgba(59,130,255,0.2);display:flex;align-items:center;justify-content:center;font-size:18px">${result.icon}</div><div><div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:var(--blue);font-family:var(--font-mono)">AI Recommendation</div><div style="font-family:var(--font-display);font-size:20px;font-weight:700">${result.name}</div></div></div><div style="display:flex;align-items:center;gap:6px;margin-bottom:10px">${ic('bolt',12,12,'var(--blue)')}<span style="font-size:13px;font-weight:600;color:var(--blue)">${result.desc}</span></div><p style="font-size:13px;color:var(--text-secondary);line-height:1.5">${result.detail}</p></div>`;
  }

  el.innerHTML = _obBg('#3B82FF','#A855F7','#00C896') + `<div style="position:relative;z-index:1">
    <div style="margin-bottom:24px"><p class="ob-step-label" style="color:var(--blue)">Step 5 of 6</p><h2 class="ob-step-title">AI Split</h2><p class="ob-step-subtitle">How long have you been away from training?</p></div>
    <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:24px" id="obAiOpts">${optsH}</div>
    ${resultH}
    <button class="ob-btn ob-btn-primary" onclick="obNext()" ${!d.inactivity||loading?'disabled':''}>${loading?'Analyzing...':result?'Use This Split':'Continue'}</button>
    <button class="ob-btn-back" onclick="obBack()">← Back</button>
  </div>`;

  el.querySelectorAll('.ob-ai-option').forEach(b => b.onclick = () => _obTriggerAI(b.dataset.av, el));
}

async function _obTriggerAI(val, el) {
  _obData.inactivity = val;
  el._aiLoading = true; el._aiResult = null;
  _obRenderStep(5, el);

  const inactMap = {active:0,'1_month':1,'3_months':3,'6_months':6,'1_year':12,never:24};
  try {
    const result = await apiRequest('POST', '/api/users/suggest-split', {
      inactivity_months: inactMap[val] || 0,
      goals: _obData.goals,
      experience_level: _obData.experience_level || 'beginner',
      gym_days: _obData.gym_specific_days.length || 3,
    });
    const splits = {
      active:{name:'PPL 6-Day',desc:'Push·Pull·Legs × 2/week',detail:'Advanced concurrent training for max volume.',icon:'⚡'},
      '1_month':{name:'Upper/Lower',desc:'4 days/week',detail:'Balanced return from short break.',icon:'💪'},
      '3_months':{name:'Full Body 3x',desc:'3 days/week',detail:'Rebuild your foundation with compounds.',icon:'🏋️'},
      '6_months':{name:'Beginner Push/Pull',desc:'3 days/week',detail:'Conservative restart. Focus on movement patterns.',icon:'📈'},
      '1_year':{name:'Novice Linear',desc:'3 days/week A/B',detail:'Progressive overload over 8–12 weeks.',icon:'🌱'},
      never:{name:'Beginner Foundation',desc:'3 days/week',detail:'Start with fundamentals. Build habit first.',icon:'🚀'},
    };
    el._aiResult = splits[val] || {name:result.split_name||'Custom',desc:'AI Generated',detail:result.recommendation||'Your plan is ready!',icon:'⚡'};
    _obData.ai_split = el._aiResult;
  } catch(e) {
    el._aiResult = {name:'Default Split',desc:'Based on your goals',detail:'Could not fetch AI suggestion. A plan will be built from your goals.',icon:'📋'};
    _obData.ai_split = el._aiResult;
  }
  el._aiLoading = false;
  _obRenderStep(5, el);
}

// ── STEP 6: Summary ──
function _obRenderSummary(el) {
  const d = _obData;
  const goalNames = {build_muscle:'Build Muscle',lose_fat:'Lose Fat',face_improvement:'Face Transform',better_sleep:'Better Sleep',general_health:'General Health',posture_correction:'Fix Posture'};
  const cal = d.weight_kg && d.height_cm && d.age && d.gender ? Math.round((d.gender==='male'?10*d.weight_kg+6.25*d.height_cm-5*d.age+5:10*d.weight_kg+6.25*d.height_cm-5*d.age-161)*1.55) : null;
  const prot = d.weight_kg ? Math.round(d.weight_kg * 2) : null;
  const privChecked = el._privacyChecked || false;

  let nutritionH = '';
  if (cal) {
    const carbs = Math.round(cal*0.45/4), fat = Math.round(cal*0.25/9);
    nutritionH = `<div class="ob-nutrition-preview"><div style="display:flex;align-items:center;gap:6px;margin-bottom:12px">${ic('bolt',12,12,'var(--green)')}<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:var(--green)">AI Nutrition Targets</div></div><div style="display:flex;gap:16px">${[[cal,'kcal','#FF3B30'],[prot,'g protein','#007AFF'],[carbs,'g carbs','#FF9500'],[fat,'g fat','#AF52DE']].map(([v,l,c])=>`<div style="text-align:center"><div style="font-family:var(--font-display);font-size:20px;font-weight:800;color:${c}">${v}</div><div style="font-size:10px;color:var(--text-tertiary)">${l}</div></div>`).join('')}</div></div>`;
  }

  el.innerHTML = _obBg('#00C896','#3B82FF','#A855F7') + `<div style="position:relative;z-index:1">
    <div style="margin-bottom:24px"><p class="ob-step-label" style="color:var(--green)">Step 6 of 6</p><h2 class="ob-step-title">Your Plan</h2><p class="ob-step-subtitle">Review your setup before we generate your first week</p></div>
    <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:24px">
      <div class="ob-summary-card"><div class="ob-card-label">Profile</div><div style="display:flex;gap:20px">${[[d.gender?d.gender.charAt(0).toUpperCase()+d.gender.slice(1):'—','Gender'],[d.age?d.age+'y':'—','Age'],[d.height_cm?d.height_cm+'cm':'—','Height'],[d.weight_kg?d.weight_kg+'kg':'—','Weight']].map(([v,l])=>`<div style="text-align:center"><div style="font-family:var(--font-display);font-size:18px;font-weight:700">${v}</div><div style="font-size:10px;color:var(--text-tertiary);font-weight:600;text-transform:uppercase">${l}</div></div>`).join('')}</div></div>
      <div class="ob-summary-card"><div class="ob-card-label">Goals</div><div style="display:flex;flex-wrap:wrap;gap:6px">${d.goals.map(g=>`<span style="padding:4px 10px;border-radius:20px;background:rgba(59,130,255,0.12);border:1px solid rgba(59,130,255,0.3);font-size:12px;font-weight:600;color:var(--blue)">${goalNames[g]||g}</span>`).join('')}</div></div>
      <div class="ob-summary-card"><div class="ob-card-label">Training</div><div style="display:flex;gap:16px;flex-wrap:wrap"><div><span style="font-size:13px;font-weight:600">${d.experience_level||'—'}</span><div style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase">Level</div></div><div><span style="font-size:13px;font-weight:600">${(d.available_equipment||'—').replace(/_/g,' ')}</span><div style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase">Equipment</div></div>${d.ai_split?`<div><span style="font-size:13px;font-weight:600;color:var(--blue)">${d.ai_split.name}</span><div style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase">AI Split</div></div>`:''}</div></div>
      ${nutritionH}
    </div>
    <button class="ob-privacy-check${privChecked?' checked':''}" id="obPrivacy"><div class="ob-checkbox${privChecked?' checked':''}">${privChecked?ic('check',11,11,'#fff'):''}</div><p style="font-size:12px;color:var(--text-secondary);line-height:1.5">I understand photos are processed in-memory only. I confirm all my information is accurate.</p></button>
    <button class="ob-btn ob-btn-success" id="obSubmitBtn" onclick="obSubmitRegistration()" ${privChecked?'':'disabled'} style="margin-top:20px">${ic('bolt',18,18,'#fff')} Start My Transformation</button>
    <button class="ob-btn-back" onclick="obBack()">← Back</button>
  </div>`;

  el.querySelector('#obPrivacy').onclick = () => { el._privacyChecked = !el._privacyChecked; _obRenderStep(6, el); haptic('selection'); };
}

// ── Submit Registration ──
async function obSubmitRegistration() {
  const d = _obData;
  const btn = document.getElementById('obSubmitBtn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<div class="ob-btn-spinner"></div> Generating Your Plan...'; }
  try {
    const gymDays = d.gym_schedule_type === 'daily' ? 7 : d.gym_schedule_type === 'specific_days' ? d.gym_specific_days.length : Math.floor(7 / d.gym_every_n_days);
    await API.register({
      gender: d.gender, goals: d.goals, experience_level: d.experience_level || 'beginner',
      gym_days_per_week: gymDays, available_equipment: [d.available_equipment || 'full_gym'],
      injuries: d.injuries, height_cm: parseFloat(d.height_cm) || null, weight_kg: parseFloat(d.weight_kg) || null,
      gym_schedule_type: d.gym_schedule_type, gym_specific_days: d.gym_specific_days,
      gym_every_n_days: d.gym_every_n_days,
      muscle_schedule: Object.keys(d.muscle_schedule).length > 0 ? d.muscle_schedule : null,
    });
    document.getElementById('registrationOverlay').style.display = 'none';
    document.getElementById('truthOverlay').style.display = 'flex';
    haptic('success');
  } catch (e) {
    showToast('Registration failed: ' + e.message);
    if (btn) { btn.disabled = false; btn.innerHTML = ic('bolt',18,18,'#fff') + ' Start My Transformation'; }
  }
}

// ── Truth Pledge toggle + confirm ──
function toggleTruthCheck() {
  const cb = document.getElementById('truthCheckbox');
  const btn = document.getElementById('truthConfirmBtn');
  const wrap = document.getElementById('truthPledgeCheck');
  const checked = !cb.classList.contains('checked');
  cb.classList.toggle('checked', checked);
  wrap.classList.toggle('checked', checked);
  cb.innerHTML = checked ? ic('check',13,13,'#fff') : '';
  btn.disabled = !checked;
}

// Override confirmTruth to use new UI
const _origConfirmTruth = window.confirmTruth;
window.confirmTruth = async function() {
  const btn = document.getElementById('truthConfirmBtn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<div class="ob-btn-spinner"></div> Locking In...'; }
  try {
    await API.confirmTruth();
    document.getElementById('truthOverlay').style.display = 'none';
    haptic('success');
    loadDashboard();
  } catch (e) {
    showToast('Failed to confirm');
    if (btn) { btn.disabled = false; btn.textContent = 'Begin Transformation'; }
  }
};
