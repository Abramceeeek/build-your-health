// ─── PHOTOS & AI PLAN ───────────────────────────
let uploadingType = null;

function uploadPhoto(type) {
  uploadingType = type;
  document.getElementById('photoInput').click();
}

document.getElementById('photoInput').addEventListener('change', async function(e) {
  const file = e.target.files[0];
  if (!file || !uploadingType) return;

  const slotMap = {body_front:'slotFront',body_side:'slotSide',body_back:'slotBack',face:'slotFace'};
  const slot = document.getElementById(slotMap[uploadingType]);

  try {
    showToast('Uploading...');
    await API.uploadPhoto(uploadingType, file);

    const reader = new FileReader();
    reader.onload = (ev) => {
      slot.innerHTML = `<img src="${ev.target.result}">`;
      slot.classList.add('has-photo');
    };
    reader.readAsDataURL(file);

    showToast('Photo uploaded!');
  } catch (err) {
    showToast('Upload failed: ' + err.message);
  }

  e.target.value = '';
  uploadingType = null;
});

async function runPhotoAnalysis() {
  const btn = document.getElementById('btnAnalyzePhotos');
  btn.textContent = 'Analyzing...';
  btn.disabled = true;
  try {
    const res = await API.analyzePhotos();
    if (res?.analysis) {
      renderAnalysis(res.analysis);
      document.getElementById('analysisResult').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      showToast('No analysis returned — upload at least one photo first');
    }
  } catch (e) {
    showToast('Analysis failed: ' + (e.message || 'unknown error'));
  }
  btn.textContent = 'Analyze Photos';
  btn.disabled = false;
}

async function generateAIPlan() {
  const btn = document.getElementById('btnGeneratePlan');
  btn.textContent = 'Generating...';
  btn.disabled = true;

  try {
    // Use registration data if available
    const regData = currentUser?.registration_data_json || {};
    const res = await API.generatePlan({
      goals: regData.goals || ['Build muscle', 'Improve face', 'Better sleep'],
      experience_level: regData.experience || 'intermediate',
      available_equipment: regData.equipment ? [regData.equipment] : ['Full gym'],
      gym_days_per_week: regData.gym_days || 3,
      sleep_target_hours: 8,
      injuries: regData.injuries || '',
    });

    showToast('Plan generated!');

    if (res.analysis) {
      renderAnalysis(res.analysis);
    }

    const week = await API.getWeekTasks().catch(() => null);
    if (week && week.week) {
      weekData = week.week;
      renderDayScroller();
      loadDayTasks(selectedDay);
    }

    loadAssistantStatus();
  } catch (e) {
    const msg = e.message || '';
    if (msg.includes('429')) {
      showToast('Rate limited — try again in a few minutes');
    } else if (msg.includes('403') || msg.includes('subscription')) {
      showToast('Pro required to generate plans');
    } else {
      showToast('Failed: ' + msg);
    }
  }

  btn.textContent = 'Generate Weekly Plan';
  btn.disabled = false;
}

async function loadAssistantStatus() {
  try {
    const dash = await API.getDashboard().catch(() => null);
    const me = currentUser || await API.getMe().catch(() => null);
    const week = weekData.length ? weekData : (await API.getWeekTasks().catch(() => ({}))).week || [];

    // Completion rate
    let totalTasks = 0, doneTasks = 0;
    for (const d of week) {
      totalTasks += d.total || 0;
      doneTasks += d.done || 0;
    }
    const pct = totalTasks > 0 ? Math.round(doneTasks / totalTasks * 100) : 0;
    document.getElementById('assistCompletion').textContent = pct + '%';

    // Streak
    const streak = me?.streak_days || dash?.streak_days || 0;
    document.getElementById('assistStreak').textContent = streak;

    // Days left in week (until Sunday)
    const now = new Date();
    const daysLeft = 7 - now.getDay() || 7;
    document.getElementById('assistDaysLeft').textContent = daysLeft;

    // Status text — focus on progress, not deficit (C4 + L8).
    const statusEl = document.getElementById('assistWeekStatus');
    const dayOfWeek = (new Date().getDay() + 6) % 7; // 0=Mon
    if (totalTasks === 0) {
      statusEl.textContent = 'No plan generated yet. Tap "Generate Weekly Plan" below.';
    } else if (dayOfWeek < 2) {
      statusEl.textContent = 'Week just started — your plan is ready 💪';
    } else if (pct >= 80) {
      statusEl.textContent = `Crushing it! ${pct}% complete this week.`;
    } else if (pct >= 50) {
      statusEl.textContent = `Good progress — ${pct}% done. Keep going!`;
    } else if (pct > 0) {
      statusEl.textContent = `Week in progress — ${pct}% complete. Keep going!`;
    } else {
      statusEl.textContent = 'No tasks completed yet this week. Start now!';
    }

    // Load latest analysis if available
    try {
      const photos = await API.analyzePhotos().catch(() => null);
      if (photos?.analysis) renderAnalysis(photos.analysis);
    } catch (e) { /* no photos yet */ }
  } catch (e) {
    document.getElementById('assistWeekStatus').textContent = 'Could not load status';
  }
}

function renderAnalysis(analysis) {
  if (!analysis || analysis.error) return;
  const el = document.getElementById('analysisResult');

  const posture = analysis.posture || {};
  const body = analysis.body_composition || {};
  const face = analysis.facial_analysis || {};
  const recs = analysis.recommendations || [];

  el.innerHTML = `
    <div class="card">
      <div class="card-title">AI Analysis Results</div>
      <div style="margin-top:12px">
        <div style="font-size:12px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;margin-bottom:6px">Posture</div>
        ${Object.entries(posture).filter(([k]) => k !== 'overall_score').map(([k, v]) =>
          typeof v === 'object' && v.detected !== undefined ?
          `<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:13px;border-bottom:0.5px solid var(--separator)">
            <span>${k.replace(/_/g, ' ')}</span>
            <span style="color:${v.severity === 'none' ? 'var(--green)' : v.severity === 'mild' ? 'var(--orange)' : 'var(--red)'}">${v.severity}</span>
          </div>` : ''
        ).join('')}
      </div>
      <div style="margin-top:12px">
        <div style="font-size:12px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;margin-bottom:6px">Body</div>
        <div style="font-size:13px;color:var(--text-secondary)">BF: ${body.estimated_bf_range || '?'} · Build: ${body.build_type || '?'}</div>
        ${body.priority_areas ? `<div style="font-size:12px;margin-top:4px;color:var(--orange)">Focus: ${body.priority_areas.join(', ')}</div>` : ''}
      </div>
      <div style="margin-top:12px">
        <div style="font-size:12px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;margin-bottom:6px">Recommendations</div>
        ${recs.map(r => `<div style="font-size:13px;color:var(--text-secondary);padding:3px 0;display:flex;gap:6px"><span style="color:var(--blue)">→</span>${r}</div>`).join('')}
      </div>
    </div>
  `;
}

