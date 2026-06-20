// ─── REGISTRATION & TRUTH GATE ──────────────────
function toggleChip(el) {
  el.classList.toggle('selected');
  haptic('selection');
}
function selectSingle(el) {
  el.parentElement.querySelectorAll('.gate-chip').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  haptic('selection');
}

// ─── REGISTRATION WIZARD ────────────────────────────────────────────────────
let _wizardStep = 1;
const WIZARD_TOTAL = 5;

function wizardGoto(step) {
  document.getElementById(`wStep${_wizardStep}`)?.classList.remove('active');
  _wizardStep = step;
  document.getElementById(`wStep${_wizardStep}`)?.classList.add('active');
  const pct = Math.round((step / WIZARD_TOTAL) * 100);
  document.getElementById('wizardProgressBar').style.width = pct + '%';
  document.getElementById('wizardStepLabel').textContent = `Step ${step} of ${WIZARD_TOTAL}`;

  if (step === 4) _setupInactivityChips();
  if (step === 5) _renderWizardSummary();
}

function wizardBack(currentStep) {
  if (currentStep > 1) wizardGoto(currentStep - 1);
}

function wizardNext(currentStep) {
  // Validation per step
  if (currentStep === 1) {
    if (!document.querySelector('#regGender .gate-chip.selected')) {
      return showToast('Please select your gender');
    }
  }
  if (currentStep === 2) {
    if (document.querySelectorAll('#regGoals .gate-chip.selected').length === 0) {
      return showToast('Pick at least one goal');
    }
  }
  if (currentStep === 3) {
    if (!document.querySelector('#regExperience .gate-chip.selected')) {
      return showToast('Select your experience level');
    }
    // Use the *active* schedule type to validate at least one gym day exists.
    // Previous code referenced #regGymDays which doesn't exist in the markup,
    // permanently blocking Continue on this step.
    const count = getActiveGymDaysCount('reg');
    const schedType = document.querySelector('#regGymScheduleType .gate-chip.selected')?.dataset.val;
    if (schedType === 'specific_days' && count === 0) {
      return showToast('Pick at least one gym day');
    }
    if (schedType === 'every_n_days' && !document.querySelector('#regEveryNDays .gate-chip.selected')) {
      return showToast('Pick how often you train');
    }
    if (!document.querySelector('#regEquipment .gate-chip.selected')) {
      return showToast('Pick your available equipment');
    }
  }
  wizardGoto(currentStep + 1);
}

// Wire inactivity chips to trigger AI suggestion
function _setupInactivityChips() {
  document.querySelectorAll('#regInactivity .gate-chip').forEach(chip => {
    chip.addEventListener('click', async () => {
      await _fetchAISplit(parseInt(chip.dataset.val));
    }, { once: false });
  });
}

async function _fetchAISplit(inactivityMonths) {
  const experience = document.querySelector('#regExperience .gate-chip.selected')?.dataset.val || 'beginner';
  const goals = [...document.querySelectorAll('#regGoals .gate-chip.selected')].map(c => c.dataset.val);
  const gymDays = getActiveGymDaysCount('reg');

  const card = document.getElementById('aiSplitCard');
  const loadingEl = document.getElementById('aiSplitLoading');
  const textEl = document.getElementById('aiSplitText');

  if (!card) return;
  card.style.display = 'block';
  loadingEl.textContent = 'Thinking...';
  textEl.textContent = '';

  try {
    const result = await apiRequest('POST', '/api/users/suggest-split', {
      inactivity_months: inactivityMonths === -1 ? 24 : inactivityMonths,
      goals, experience_level: experience, gym_days: gymDays,
    });
    loadingEl.textContent = '';
    // AI-generated text is untrusted. Escape HTML, then convert newlines to <br>.
    const raw = String(result.recommendation || result.split_name || 'Your plan is ready!');
    const safe = raw
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/\n/g, '<br>');
    textEl.innerHTML = safe;
  } catch (e) {
    loadingEl.textContent = '';
    textEl.textContent = 'Could not fetch AI suggestion. Your plan will be built from your selected goals.';
  }
}

function _renderWizardSummary() {
  const gender = document.querySelector('#regGender .gate-chip.selected')?.dataset.val || 'male';
  const goals = [...document.querySelectorAll('#regGoals .gate-chip.selected')].map(c => {
    return c.textContent.trim();
  }).join(', ');
  const exp = document.querySelector('#regExperience .gate-chip.selected')?.dataset.val || 'beginner';
  const gymDays = getActiveGymDaysCount('reg');
  const equip = document.querySelector('#regEquipment .gate-chip.selected')?.textContent.trim() || 'Full gym';
  const height = document.getElementById('regHeight')?.value || '—';
  const weight = document.getElementById('regWeight')?.value || '—';

  const el = document.getElementById('wizardSummary');
  if (el) {
    el.innerHTML = `
      <div>👤 <b>${gender.charAt(0).toUpperCase() + gender.slice(1)}</b> · ${height}cm · ${weight}kg</div>
      <div>🎯 <b>Goals:</b> ${goals || '—'}</div>
      <div>💪 <b>Level:</b> ${exp} · <b>Gym:</b> ${gymDays}×/week</div>
      <div>🏋️ <b>Equipment:</b> ${equip}</div>
    `;
  }
}

async function submitRegistration() {
  const gender = document.querySelector('#regGender .gate-chip.selected')?.dataset.val || 'male';
  const goals = [...document.querySelectorAll('#regGoals .gate-chip.selected')].map(c => c.dataset.val);
  const exp = document.querySelector('#regExperience .gate-chip.selected')?.dataset.val || 'beginner';
  const gymDays = getActiveGymDaysCount('reg');
  const gymScheduleType = document.querySelector('#regGymScheduleType .gate-chip.selected')?.dataset.val || 'specific_days';
  const gymSpecificDays = [...document.querySelectorAll('#regSpecificDays .gate-chip.selected')].map(c => parseInt(c.dataset.val));
  const gymEveryNDays = parseInt(document.querySelector('#regEveryNDays .gate-chip.selected')?.dataset.val || '2');
  const equip = document.querySelector('#regEquipment .gate-chip.selected')?.dataset.val || 'full_gym';
  const injuries = document.getElementById('regInjuries')?.value.trim() || '';
  const height = parseFloat(document.getElementById('regHeight')?.value) || null;
  const weight = parseFloat(document.getElementById('regWeight')?.value) || null;

  if (!document.querySelector('#regGender .gate-chip.selected')) { showToast('Please select your gender'); return; }
  if (goals.length === 0) { showToast('Please select at least one goal'); return; }

  try {
    await API.register({
      gender, goals, experience_level: exp, gym_days_per_week: gymDays,
      available_equipment: [equip], injuries, height_cm: height, weight_kg: weight,
      gym_schedule_type: gymScheduleType,
      gym_specific_days: gymSpecificDays,
      gym_every_n_days: gymEveryNDays,
      muscle_schedule: Object.keys(_currentMuscleSchedule).length > 0 ? _currentMuscleSchedule : null,
    });
    document.getElementById('registrationOverlay').style.display = 'none';
    document.getElementById('truthOverlay').style.display = 'flex';
    haptic('success');
  } catch (e) {
    showToast('Registration failed: ' + e.message);
  }
}

async function confirmTruth() {
  try {
    await API.confirmTruth();
    document.getElementById('truthOverlay').style.display = 'none';
    haptic('success');
    loadDashboard();
  } catch (e) {
    showToast('Failed to confirm');
  }
}

// ─── SETTINGS PAGE ──────────────────────────────
async function loadSettingsPage() {
  try {
    const reg = await API.getRegistration();
    if (!reg || Object.keys(reg).length === 0) return;

    // Pre-select gender
    document.querySelectorAll('#settGender .gate-chip').forEach(c => {
      c.classList.toggle('selected', c.dataset.val === reg.gender);
    });
    // Pre-select goals
    const goals = reg.goals || [];
    document.querySelectorAll('#settGoals .gate-chip').forEach(c => {
      c.classList.toggle('selected', goals.includes(c.dataset.val));
    });
    // Experience
    document.querySelectorAll('#settExperience .gate-chip').forEach(c => {
      c.classList.toggle('selected', c.dataset.val === reg.experience_level);
    });
    // Gym schedule type
    const sType = reg.gym_schedule_type || 'specific_days';
    document.querySelectorAll('#settGymScheduleType .gate-chip').forEach(c => {
      c.classList.toggle('selected', c.dataset.val === sType);
    });
    toggleSettScheduleOpts();
    
    // Specific days
    if (reg.gym_specific_days) {
      document.querySelectorAll('#settSpecificDays .gate-chip').forEach(c => {
        c.classList.toggle('selected', reg.gym_specific_days.includes(parseInt(c.dataset.val)));
      });
    }
    // Every N days
    if (reg.gym_every_n_days) {
      document.querySelectorAll('#settEveryNDays .gate-chip').forEach(c => {
        c.classList.toggle('selected', c.dataset.val === String(reg.gym_every_n_days));
      });
    }
    
    // Muscle schedule
    if (reg.muscle_schedule) {
      _currentMuscleSchedule = reg.muscle_schedule;
    }
    // Equipment
    const equip = (reg.available_equipment || [])[0] || 'full_gym';
    document.querySelectorAll('#settEquipment .gate-chip').forEach(c => {
      c.classList.toggle('selected', c.dataset.val === equip);
    });
    // Injuries
    document.getElementById('settInjuries').value = reg.injuries || '';

    // L10 — sync theme toggle
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) themeToggle.checked = (localStorage.getItem('theme') === 'light');

    // Load reminders (function is optional — the reminders UI may not be wired in)
    if (typeof loadReminders === 'function') loadReminders();
  } catch (e) {
    console.error('Failed to load settings:', e);
    if (typeof loadReminders === 'function') loadReminders();
  }
}

async function saveSettings() {
  const gender = document.querySelector('#settGender .gate-chip.selected')?.dataset.val || 'male';
  const goals = [...document.querySelectorAll('#settGoals .gate-chip.selected')].map(c => c.dataset.val);
  const exp = document.querySelector('#settExperience .gate-chip.selected')?.dataset.val || 'beginner';
  const gymDays = getActiveGymDaysCount('sett');
  const gymScheduleType = document.querySelector('#settGymScheduleType .gate-chip.selected')?.dataset.val || 'specific_days';
  const gymSpecificDays = [...document.querySelectorAll('#settSpecificDays .gate-chip.selected')].map(c => parseInt(c.dataset.val));
  const gymEveryNDays = parseInt(document.querySelector('#settEveryNDays .gate-chip.selected')?.dataset.val || '2');
  const equip = document.querySelector('#settEquipment .gate-chip.selected')?.dataset.val || 'full_gym';
  const injuries = document.getElementById('settInjuries').value.trim();

  if (goals.length === 0) { showToast('Please select at least one goal'); return; }

  try {
    showToast('Saving...');
    await API.updateRegistration({
      gender, goals, experience_level: exp, gym_days_per_week: gymDays,
      available_equipment: [equip], injuries,
      gym_schedule_type: gymScheduleType,
      gym_specific_days: gymSpecificDays,
      gym_every_n_days: gymEveryNDays,
      muscle_schedule: Object.keys(_currentMuscleSchedule).length > 0 ? _currentMuscleSchedule : null
    });
    await API.regenerateWeek();
    showToast('Settings saved! Tasks regenerated.');
    haptic('success');

    // Reload to reflect changes
    const week = await API.getWeekTasks().catch(() => null);
    if (week && week.week) {
      weekData = week.week;
      renderDayScroller();
      loadDayTasks(selectedDay);
    }
  } catch (e) {
    showToast('Failed: ' + e.message);
  }
}


// --- MUSCLE PICKER & CUSTOM SCHEDULE LOGIC ---

let _currentMuscleSchedule = {};
let _musclePickerContext = 'reg'; // 'reg' or 'sett'

const MUSCLES = [
  {id: 'chest', label: 'Chest', tier: 'big', icon: '🫁'},
  {id: 'back', label: 'Back', tier: 'big', icon: '🔙'},
  {id: 'legs', label: 'Legs', tier: 'big', icon: '🦵'},
  {id: 'shoulders', label: 'Shoulders', tier: 'mid', icon: '🏋️'},
  {id: 'biceps', label: 'Biceps', tier: 'mid', icon: '💪'},
  {id: 'triceps', label: 'Triceps', tier: 'mid', icon: '💪'},
  {id: 'abs', label: 'Abs', tier: 'small', icon: '🧱'},
  {id: 'neck', label: 'Neck', tier: 'small', icon: '🦒'},
  {id: 'forearms', label: 'Forearms', tier: 'small', icon: '🤝'},
  {id: 'rear_delts', label: 'Rear Delts', tier: 'small', icon: '🎯'},
  {id: 'calves', label: 'Calves', tier: 'small', icon: '🦶'},
];

function toggleRegScheduleOpts() {
  const type = document.querySelector('#regGymScheduleType .gate-chip.selected')?.dataset.val || 'specific_days';
  document.getElementById('regSpecificWrap').style.display = type === 'specific_days' ? 'block' : 'none';
  document.getElementById('regEveryNWrap').style.display = type === 'every_n_days' ? 'block' : 'none';
}

function toggleSettScheduleOpts() {
  const type = document.querySelector('#settGymScheduleType .gate-chip.selected')?.dataset.val || 'specific_days';
  document.getElementById('settSpecificWrap').style.display = type === 'specific_days' ? 'block' : 'none';
  document.getElementById('settEveryNWrap').style.display = type === 'every_n_days' ? 'block' : 'none';
}

function getActiveGymDaysCount(context) {
  const type = document.querySelector(`#${context}GymScheduleType .gate-chip.selected`)?.dataset.val || 'specific_days';
  if (type === 'daily') return 7;
  if (type === 'specific_days') {
    return document.querySelectorAll(`#${context}SpecificDays .gate-chip.selected`).length || 0;
  }
  if (type === 'every_n_days') {
    const n = parseInt(document.querySelector(`#${context}EveryNDays .gate-chip.selected`)?.dataset.val) || 2;
    return Math.floor(7 / n);
  }
  return 3;
}

// M15 — sensible default splits so each row has a recognisable name
// instead of opening as a blank chip grid.
const DEFAULT_SPLITS = [
  { name: 'Push', muscles: ['chest', 'shoulders', 'triceps'] },
  { name: 'Pull', muscles: ['back', 'biceps', 'rear_delts'] },
  { name: 'Legs', muscles: ['legs', 'calves', 'abs'] },
  { name: 'Upper', muscles: ['chest', 'back', 'shoulders'] },
  { name: 'Lower', muscles: ['legs', 'calves'] },
  { name: 'Arms + Core', muscles: ['biceps', 'triceps', 'abs', 'forearms'] },
  { name: 'Full body', muscles: ['chest', 'back', 'legs'] },
];

function openMusclePicker(context) {
  _musclePickerContext = context;
  const daysCount = getActiveGymDaysCount(context);
  if (daysCount === 0) {
    showToast('Please select at least 1 gym day first.');
    return;
  }

  const listEl = document.getElementById('musclePickerDaysList');
  listEl.innerHTML = '';

  for (let i = 0; i < daysCount; i++) {
    const stored = _currentMuscleSchedule[i.toString()];
    const fallback = DEFAULT_SPLITS[i % DEFAULT_SPLITS.length];
    const selectedMuscles = (stored && stored.length) ? stored : fallback.muscles;
    const sessionLabel = (stored && stored.length) ? `Gym Session ${i + 1}` : `Gym Session ${i + 1} — ${fallback.name}`;

    let html = `<div style="margin-bottom:20px;">
      <div style="font-weight:600;margin-bottom:8px">${sessionLabel}</div>
      <div class="gate-chips" style="gap:6px" id="musclePickerDay_${i}">`;
      
    MUSCLES.forEach(m => {
      const isSelected = selectedMuscles.includes(m.id) ? 'selected' : '';
      html += `<span class="gate-chip ${isSelected}" data-val="${m.id}" onclick="toggleChip(this)" style="font-size:12px;padding:6px 10px;border-color:rgba(255,255,255,0.1)">${m.icon} ${m.label}</span>`;
    });
    
    html += `</div></div>`;
    listEl.innerHTML += html;
  }
  
  // CSS uses `.modal-overlay.active { display: flex; ... }` for layout.
  // Setting `display: block` inline broke the bottom-sheet alignment.
  document.getElementById('musclePickerOverlay').classList.add('active');
}

function closeMusclePicker(e) {
  if (e && e.target !== document.getElementById('musclePickerOverlay') && e.target.tagName !== 'BUTTON') return;
  document.getElementById('musclePickerOverlay').classList.remove('active');
}

function saveMusclePicker() {
  const daysCount = getActiveGymDaysCount(_musclePickerContext);
  _currentMuscleSchedule = {};
  
  for (let i = 0; i < daysCount; i++) {
    const selected = [...document.querySelectorAll(`#musclePickerDay_${i} .gate-chip.selected`)].map(c => c.dataset.val);
    if (selected.length > 0) {
      _currentMuscleSchedule[i.toString()] = selected;
    }
  }
  closeMusclePicker();
  showToast('Muscle split saved temporarily.');
}

// ─── L10 — THEME ────────────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  const toggle = document.getElementById('themeToggle');
  if (toggle) toggle.checked = theme === 'light';
}

// init on load
(function _initTheme() {
  const saved = localStorage.getItem('theme') || 'dark';
  applyTheme(saved);
})();
