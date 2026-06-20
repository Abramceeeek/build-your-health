// ─── DAY SCROLLER ───────────────────────────────
function renderDayScroller() {
  const scroller = document.getElementById('dayScroller');
  scroller.innerHTML = weekData.map(d => {
    const isActive = d.date === selectedDay;
    const isComplete = d.pct >= 100;
    let cls = 'day-pill';
    if (isActive) cls += ' active';
    else if (isComplete) cls += ' complete';
    const typeKey = (d.day_type || '').toLowerCase().split(' ')[0];
    if (typeKey) cls += ' pill-' + typeKey;

    return `<button class="${cls}" onclick="selectDay('${d.date}')">
      <span class="pill-day">${d.day_name}</span>
      <span class="pill-type">${d.day_type || ''}</span>
      <span class="pill-pct">${d.pct || 0}%</span>
    </button>`;
  }).join('');

  setTimeout(() => {
    const active = scroller.querySelector('.day-pill.active');
    if (active) active.scrollIntoView({block:'nearest',inline:'center',behavior:'smooth'});
  }, 50);
}

function selectDay(date) {
  selectedDay = date;
  renderDayScroller();
  loadDayTasks(date);
  haptic('selection');
}

// ─── LOAD DAY TASKS ─────────────────────────────
async function loadDayTasks(date) {
  try {
    const data = await API.getDayTasks(date);
    renderDayContent(data);
  } catch (e) {
    document.getElementById('dayContent').innerHTML =
      '<div style="text-align:center;padding:40px;color:var(--text-tertiary)">Could not load tasks</div>';
  }
}

let currentDayData = null;

function renderDayContent(data) {
  if (!data) return;
  currentDayData = data;
  _currentDayData = data;   // also expose for timer fallback
  const container = document.getElementById('dayContent');
  const tagClass = {health:'tag-health', fitness:'tag-fitness', sleep:'tag-sleep', face:'tag-face'};

  let html = '';

  for (const sec of data.sections) {
    html += `<div class="section">
      <div class="section-header">
        <div class="section-title">${sec.label}</div>
        <div class="section-line"></div>
      </div>
      <div class="task-list">`;

    for (const t of sec.tasks) {
      const done = t.completed ? ' done' : '';
      const tag = t.category ? `<span class="task-tag ${tagClass[t.category] || 'tag-health'}">${t.category}</span>` : '';
      const dot = t.priority ? '<span class="priority-dot"></span>' : '';
      const pills = (t.exercise_sets || t.exercise_weight) ?
        `<div class="exercise-pills">
          ${t.exercise_sets ? `<span class="ex-pill accent">${t.exercise_sets}</span>` : ''}
          ${t.exercise_weight ? `<span class="ex-pill">${t.exercise_weight}</span>` : ''}
        </div>` : '';

      const isGym = sec.label.toLowerCase().includes('gym');
      const isWarmup = t.task_key === 'gw';

      // Sleep task e9 — show sleep prompt instead of toggle
      let clickAction;
      if (t.task_key === 'e9' && !t.completed) {
        clickAction = `handleSleepTask(${t.id})`;
      } else if (isGym && (t.exercise_sets || t.exercise_weight)) {
        const fw = t.formatted_weight ? t.formatted_weight.replace(/'/g, "\\'") : (t.exercise_weight || '');
        clickAction = `showExerciseDetail(${t.id}, '${t.title.replace(/'/g, "\\'")}', '${t.exercise_sets || ''}', '${fw}', ${t.completed})`;
      } else if (_isWalkTask(t.task_key, t.title) && !t.completed) {
        clickAction = `handleWalkTask(${t.id},'${t.task_key}','${t.title.replace(/'/g, "\\'")}')`;
      } else {
        clickAction = `toggleTask(${t.id})`;
      }

      // ── Timer button for gym exercises (not warmups, not completed) ──
      const timerBtn = isGym && !t.completed && !isWarmup && (t.exercise_sets || t.exercise_weight)
        ? `<button class="task-timer-btn" onclick="event.stopPropagation();startExerciseTimerFor(${t.id})" title="Start timer"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Timer</button>`
        : '';

      // Expandable description for face tasks with long descriptions
      const isFace = t.category === 'face';
      const descFull = t.description || '';
      let descHtml;
      if (isFace && descFull.length > 80) {
        const shortDesc = descFull.slice(0, 60) + '...';
        descHtml = `<div class="task-desc task-desc-short" onclick="event.stopPropagation();this.classList.toggle('expanded')">${shortDesc}<span class="how-to-link"> [How to]</span><div class="task-desc-full">${descFull}</div></div>`;
      } else {
        descHtml = `<div class="task-desc">${descFull}</div>`;
      }

      // ── Intelligence Data ──
      let intelligenceHtml = '';
      if (isGym && !isWarmup) {
        if (t.last_actual_weight) {
          intelligenceHtml += `<div class="task-intelligence">↺ Last: ${t.last_actual_weight}kg × ${t.last_sets_completed || t.exercise_sets || '?'}</div>`;
        }
        if (t.formatted_weight && !t.completed) {
          intelligenceHtml += `<div class="task-intelligence highlight">🎯 Target: ${t.formatted_weight}</div>`;
        }
        if (t.emg_rank) {
          intelligenceHtml += `<div class="task-intelligence">⭐ EMG Rank: #${t.emg_rank}</div>`;
        }
      }

      // Swipe-to-swap data attributes for gym tasks
      const swipeAttrs = isGym && !t.completed && (t.exercise_sets || t.exercise_weight)
        ? ` data-swipable="true" data-task-id="${t.id}"`
        : '';

      html += `<div class="task-item${done}"${swipeAttrs} onclick="${clickAction}">
        <div class="task-check">
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
            <path d="M1 4L3.5 6.5L9 1" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <div class="task-body">
          <div class="task-name">${dot}${t.title}${tag}</div>
          ${pills}
          ${descHtml}
          ${intelligenceHtml}
          ${timerBtn ? `<div class="task-actions-row">${timerBtn}</div>` : ''}
        </div>
        <div class="task-swap-label">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"></path><path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M3 22v-6h6"></path><path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>
        </div>
      </div>`;
    }

    html += '</div></div>';
  }

  container.innerHTML = html;
  initSwipeHandlers();
  _initLongPress();

  const stats = data.stats || {};
  document.getElementById('statDone').textContent = stats.done || 0;
  document.getElementById('statLeft').textContent = (stats.total || 0) - (stats.done || 0);
}

// Handle sleep task e9 — prompt for hours then auto-complete
async function handleSleepTask(taskId) {
  const val = prompt('Hours of sleep last night:', healthData.sleep_hours || '');
  if (val === null) return;
  const hrs = parseFloat(val);
  if (isNaN(hrs) || hrs < 0 || hrs > 24) return;
  healthData.sleep_hours = hrs;
  renderHealthTracker();
  await API.updateHealth({ sleep_hours: hrs });
  await toggleTask(taskId);
}

// Auto-complete task by key
async function autoCompleteTaskByKey(key) {
  if (!currentDayData) return;
  for (const sec of currentDayData.sections) {
    for (const t of sec.tasks) {
      if (t.task_key === key && !t.completed) {
        await toggleTask(t.id);
        return;
      }
    }
  }
}

// ─── SWIPE TO SWAP ──────────────────────────────
function initSwipeHandlers() {
  document.querySelectorAll('[data-swipable="true"]').forEach(el => {
    let startX = 0;
    let currentX = 0;
    let swiping = false;

    el.addEventListener('touchstart', e => {
      startX = e.touches[0].clientX;
      currentX = startX; // Fix: initialize currentX
      swiping = true;
      el.style.transition = 'none';
    }, {passive: true});

    el.addEventListener('touchmove', e => {
      if (!swiping) return;
      currentX = e.touches[0].clientX;
      const deltaX = currentX - startX;
      if (deltaX < -10) { // Slight buffer
        el.style.transform = `translateX(${deltaX}px)`;
        el.classList.add('swiping');
      }
    }, {passive: true});

    el.addEventListener('touchend', e => {
      if (!swiping) return;
      swiping = false;
      const deltaX = currentX - startX;
      el.style.transition = 'transform 0.3s ease';
      
      // Swap threshold is 50% of the element width
      const threshold = -(el.offsetWidth * 0.5);
      
      if (deltaX < threshold) {
        const taskId = el.dataset.taskId;
        el.style.transform = `translateX(-${el.offsetWidth}px)`;
        setTimeout(() => {
          el.style.transform = '';
          el.classList.remove('swiping');
          swapExercise(parseInt(taskId));
        }, 300);
      } else {
        el.style.transform = '';
        el.classList.remove('swiping');
      }
    });
  });
}

// ─── HEALTH TRACKER ─────────────────────────────────────
let healthData = { water_glasses: 0, sleep_hours: 0, steps: 0, mood: 0 };
const MOOD_EMOJIS = ['😫', '😕', '😐', '🙂', '😄'];

async function loadHealthTracker() {
  try {
    const data = await API.getHealthToday();
    healthData = data;
    renderHealthTracker();
    initMoodSwipe();
  } catch (e) {
    console.error('Health tracker load error:', e);
  }
  // Load readiness independently — non-fatal
  loadReadinessCard().catch(() => {});
}

function renderHealthTracker() {
  document.getElementById('healthWater').textContent = `${healthData.water_glasses}/8`;
  document.getElementById('waterBar').style.width = `${Math.min(100, (healthData.water_glasses / 8) * 100)}%`;

  document.getElementById('healthSleep').textContent = healthData.sleep_hours > 0 ? `${healthData.sleep_hours}h` : '--';
  document.getElementById('sleepBar').style.width = `${Math.min(100, (healthData.sleep_hours / 9) * 100)}%`;

  // Sleep score badge
  const badge = document.getElementById('sleepScoreBadge');
  if (badge && healthData.sleep_score != null && healthData.sleep_score > 0) {
    badge.textContent = `${Math.round(healthData.sleep_score)}`;
    badge.style.display = 'inline';
  } else if (badge) {
    badge.style.display = 'none';
  }

  document.getElementById('healthSteps').textContent = healthData.steps > 0 ? healthData.steps.toLocaleString() : '--';
  document.getElementById('stepsBar').style.width = `${Math.min(100, (healthData.steps / 10000) * 100)}%`;
  // Mood emoji
  const moodIdx = Math.max(0, Math.min(4, (healthData.mood || 3) - 1));
  document.getElementById('moodEmoji').textContent = MOOD_EMOJIS[moodIdx];
}

async function incrementWater() {
  const newVal = (healthData.water_glasses || 0) + 1;
  if (newVal > 12) return;
  healthData.water_glasses = newVal;
  renderHealthTracker();
  haptic('light');
  await API.updateHealth({ water_glasses: newVal });

  // Auto-complete water tasks
  if (newVal === 1) {
    autoCompleteTaskByKey('m1');
  }
  if (newVal >= 8) {
    autoCompleteTaskByKey('e4');
  }
}

function promptSleep() {
  const val = prompt('Hours of sleep last night:', healthData.sleep_hours || '');
  if (val === null) return;
  const hrs = parseFloat(val);
  if (isNaN(hrs) || hrs < 0 || hrs > 24) return;
  healthData.sleep_hours = hrs;
  renderHealthTracker();
  API.updateHealth({ sleep_hours: hrs }).then(updated => {
    if (updated) {
      healthData = { ...healthData, ...updated };
      renderHealthTracker();
      loadReadinessCard().catch(() => {});
    }
  });
}

function promptSteps() {
  const val = prompt('Steps today:', healthData.steps || '');
  if (val === null) return;
  const s = parseInt(val);
  if (isNaN(s) || s < 0) return;
  healthData.steps = s;
  renderHealthTracker();
  API.updateHealth({ steps: s });
}

async function setMood(level) {
  healthData.mood = level;
  renderHealthTracker();
  haptic('light');
  await API.updateHealth({ mood: level });
}

// Mood swipe gesture
function initMoodSwipe() {
  const area = document.getElementById('moodSwipeArea');
  if (!area) return;
  let startY = 0;

  area.addEventListener('touchstart', e => {
    startY = e.touches[0].clientY;
    e.stopPropagation();
  }, {passive: true});

  area.addEventListener('touchend', e => {
    const endY = e.changedTouches[0].clientY;
    const deltaY = startY - endY;
    if (Math.abs(deltaY) < 20) return;
    const currentMood = healthData.mood || 3;
    setMood(deltaY > 0 ? Math.min(5, currentMood + 1) : Math.max(1, currentMood - 1));
    e.stopPropagation();
  });

  // Mouse wheel — desktop support
  area.addEventListener('wheel', e => {
    e.preventDefault();
    const currentMood = healthData.mood || 3;
    setMood(e.deltaY < 0 ? Math.min(5, currentMood + 1) : Math.max(1, currentMood - 1));
  }, {passive: false});

  // Inject ↑↓ arrow buttons for desktop/pointer devices
  const hint = area.querySelector('.mood-hint');
  if (hint) {
    hint.innerHTML = `<button class="mood-arrow" onclick="event.stopPropagation();setMood(Math.min(5,(healthData.mood||3)+1))">▲</button><button class="mood-arrow" onclick="event.stopPropagation();setMood(Math.max(1,(healthData.mood||3)-1))">▼</button>`;
  }
}

function toggleHealthTracker() {
  const body = document.getElementById('healthTrackerBody');
  const icon = document.getElementById('healthToggleIcon');
  const collapsed = body.style.display === 'none';
  body.style.display = collapsed ? '' : 'none';
  icon.textContent = collapsed ? '\u25BE' : '\u25B8';
}

// L6 — surface XP gain on the task element so completing feels rewarding.
function _xpPop(taskId, xp) {
  if (!xp || xp <= 0) return;
  const el = document.querySelector(`[data-task-id="${taskId}"]`)
    || document.querySelector(`.task-item[onclick*="toggleTask(${taskId})"]`);
  if (!el) return;
  const pop = document.createElement('span');
  pop.className = 'xp-pop';
  pop.textContent = `+${xp} XP`;
  el.appendChild(pop);
  setTimeout(() => pop.remove(), 900);
}

// ─── TOGGLE TASK ────────────────────────────────
async function toggleTask(taskId, payload) {
  try {
    const res = await API.toggleTask(taskId, payload);
    haptic(res.completed ? 'medium' : 'light');

    if (res.completed) _xpPop(taskId, res.xp_gained || res.xp_reward || 10);

    if (res.day_complete) {
      showToast('Day complete! 🔥');
      haptic('success');
    }

    const dayIdx = weekData.findIndex(d => d.date === selectedDay);
    if (dayIdx >= 0) {
      weekData[dayIdx].pct = res.day_pct;
      weekData[dayIdx].done = res.day_done;
      weekData[dayIdx].total = res.day_total;
    }
    renderDayScroller();

    await loadDayTasks(selectedDay);

    API.updateStreak().then(streakRes => {
      if (streakRes && currentUser) {
        currentUser.streak_days = streakRes.streak_days;
        currentUser.level = streakRes.level;
        currentUser.tier = streakRes.tier;
        currentUser.ovr_rating = streakRes.ovr_rating;
        document.getElementById('statStreak').textContent = streakRes.streak_days;
        updateUserUI();
      }
    }).catch(() => {});

  } catch (e) {
    showToast('Failed to update task');
  }
}

// ─── EXERCISE DETAIL ────────────────────────────
let currentExerciseTaskId = null;
let currentExerciseName = '';
let _selectedRpe = null;   // "easy" | "right" | "brutal" — drives next-session weight

function setRpe(key) {
  _selectedRpe = key;
  ['Easy', 'Right', 'Brutal'].forEach(label => {
    const el = document.getElementById('rpe' + label);
    if (el) el.classList.toggle('active', label.toLowerCase() === key);
  });
}

async function showExerciseDetail(taskId, title, sets, weight, completed) {
  currentExerciseTaskId = taskId;
  currentExerciseName = title;
  _selectedRpe = null;
  ['Easy', 'Right', 'Brutal'].forEach(label => {
    const el = document.getElementById('rpe' + label);
    if (el) el.classList.remove('active');
  });

  document.getElementById('exDetailTitle').textContent = title;
  document.getElementById('exDetailImg').alt = title ? `${title} demonstration` : 'Exercise';
  document.getElementById('exDetailImg').style.display = 'none';
  document.getElementById('exDetailPrescribed').innerHTML = `
    ${sets ? `<span class="ex-pill accent">${sets}</span>` : ''}
    ${weight ? `<span class="ex-pill">${weight}</span>` : ''}
  `;
  document.getElementById('exWeightInput').value = weight || '';
  document.getElementById('exSetsInput').value = sets || '';
  document.getElementById('exCompleteBtn').textContent = completed ? 'Completed' : 'Mark Complete';
  document.getElementById('exCompleteBtn').disabled = completed;

  // Load exercise details from library
  // Muscle-group-aware fallback GIFs (reliable fitnessprogramer.com URLs)
  const fallbackGifs = {
    chest: 'https://fitnessprogramer.com/wp-content/uploads/2021/02/Push-Up.gif',
    back: 'https://fitnessprogramer.com/wp-content/uploads/2021/02/Pull-up.gif',
    shoulder: 'https://fitnessprogramer.com/wp-content/uploads/2021/02/Dumbbell-Lateral-Raise.gif',
    leg: 'https://fitnessprogramer.com/wp-content/uploads/2021/02/Barbell-Squat.gif',
    arm: 'https://fitnessprogramer.com/wp-content/uploads/2021/02/Dumbbell-Curl.gif',
    core: 'https://fitnessprogramer.com/wp-content/uploads/2021/02/Plank.gif',
    default: 'https://fitnessprogramer.com/wp-content/uploads/2021/02/Push-Up.gif',
  };

  function pickFallbackGif(exerciseName) {
    const name = (exerciseName || '').toLowerCase();
    if (name.includes('bench') || name.includes('chest') || name.includes('fly') || name.includes('push-up') || name.includes('push up'))
      return fallbackGifs.chest;
    if (name.includes('pull') || name.includes('row') || name.includes('lat') || name.includes('deadlift') || name.includes('back'))
      return fallbackGifs.back;
    if (name.includes('shoulder') || name.includes('press') || name.includes('lateral') || name.includes('delt') || name.includes('face pull'))
      return fallbackGifs.shoulder;
    if (name.includes('squat') || name.includes('leg') || name.includes('lunge') || name.includes('hip') || name.includes('calf') || name.includes('curl'))
      return fallbackGifs.leg;
    if (name.includes('curl') || name.includes('tricep') || name.includes('bicep') || name.includes('skull'))
      return fallbackGifs.arm;
    if (name.includes('plank') || name.includes('ab') || name.includes('core') || name.includes('crunch') || name.includes('dead bug'))
      return fallbackGifs.core;
    return fallbackGifs.default;
  }

  const fallbackGif = pickFallbackGif(title);
  const imgEl = document.getElementById('exDetailImg');

  try {
    const ex = await API.getExerciseByName(title);
    if (ex) {
      // Show exercise image with fallback
      const finalUrl = (ex.image_url && ex.image_url.length > 5) ? ex.image_url : fallbackGif;
      imgEl.src = "/api/exercises/proxy-image?url=" + encodeURIComponent(finalUrl);
      imgEl.style.display = 'block';
      imgEl.onerror = () => { imgEl.src = fallbackGif; imgEl.onerror = null; };

      const muscles = (ex.muscle_groups || []).map(m =>
        `<span class="ex-muscle-tag">${m}</span>`
      ).join('');
      document.getElementById('exDetailMuscles').innerHTML = muscles;

      const instructions = (ex.instructions || []).map(i => `<li>${i}</li>`).join('');
      document.getElementById('exDetailInstructions').innerHTML = instructions || '<li>No instructions available</li>';

      const mistakes = (ex.common_mistakes || []).map(m => `<li>${m}</li>`).join('');
      document.getElementById('exDetailMistakes').innerHTML = mistakes || '<li>None listed</li>';
    } else {
      // Not in DB — show muscle-group-specific fallback GIF
      imgEl.src = "/api/exercises/proxy-image?url=" + encodeURIComponent(fallbackGif);
      imgEl.style.display = 'block';
      imgEl.onerror = () => { imgEl.style.display = 'none'; };

      document.getElementById('exDetailMuscles').innerHTML = '';
      document.getElementById('exDetailInstructions').innerHTML = '<li>No instructions available</li>';
      document.getElementById('exDetailMistakes').innerHTML = '';
    }
  } catch (e) {
    imgEl.src = "/api/exercises/proxy-image?url=" + encodeURIComponent(fallbackGif);
    imgEl.style.display = 'block';

    document.getElementById('exDetailMuscles').innerHTML = '';
    document.getElementById('exDetailInstructions').innerHTML = '<li>No instructions available</li>';
    document.getElementById('exDetailMistakes').innerHTML = '';
  }

  // Load weight history
  try {
    const history = await API.getWeightHistory(title);
    if (history && history.length > 0) {
      const rows = history.slice(0, 5).map(h =>
        `<div class="ex-history-row">
          <span>${h.date}</span>
          <span>${h.actual_weight || '—'}</span>
          <span>${h.sets_completed || '—'}</span>
        </div>`
      ).join('');
      document.getElementById('exWeightHistory').innerHTML = `
        <div class="ex-detail-label">Recent History</div>
        <div class="ex-history-header">
          <span>Date</span><span>Weight</span><span>Sets</span>
        </div>
        ${rows}
      `;
    } else {
      document.getElementById('exWeightHistory').innerHTML = '';
    }
  } catch (e) {
    document.getElementById('exWeightHistory').innerHTML = '';
  }

  document.getElementById('exerciseDetailOverlay').style.display = 'flex';
}

function closeExerciseDetail() {
  document.getElementById('exerciseDetailOverlay').style.display = 'none';
  currentExerciseTaskId = null;
}

async function completeExercise() {
  if (!currentExerciseTaskId) return;

  const weight = document.getElementById('exWeightInput').value.trim();
  const sets = document.getElementById('exSetsInput').value.trim();

  // Log weight + RPE if provided. RPE ("easy"/"right"/"brutal") is stored as `notes` and
  // drives next session's top set (coach_weight.get_next_top_weight).
  if (weight || sets || _selectedRpe) {
    try {
      await API.logWeight({
        task_id: currentExerciseTaskId,
        exercise_name: currentExerciseName,
        date: getTodayStr(),
        actual_weight: weight,
        sets_completed: sets,
        notes: _selectedRpe || undefined,
      });
    } catch (e) {
      // Weight log is optional, continue to toggle
    }
  }

  // Toggle the task
  await toggleTask(currentExerciseTaskId);
  closeExerciseDetail();
}

async function swapExercise(taskId) {
  try {
    const result = await API.swapExercise(taskId);
    showToast(`Swapped to: ${result.new_title} (${result.swaps_remaining} swaps left)`);
    haptic('success');
    if (selectedDay) {
      const data = await API.getDayTasks(selectedDay);
      renderDayContent(data);
    }
  } catch (e) {
    showToast(e.message);
    haptic('error');
  }
}

// ─── EXERCISE TIMER INTEGRATION ─────────────────────────────────────────────
async function startExerciseTimerFor(taskId) {
  // Show loading state on button
  const btn = document.querySelector(`[onclick*="startExerciseTimerFor(${taskId})"]`);
  if (btn) { btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation: spin 1s linear infinite"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg> Loading...'; btn.disabled = true; }

  try {
    const meta = await apiRequest('GET', `/api/tasks/${taskId}/timer-meta`);
    ExerciseTimer.open({
      taskId,
      exerciseName: meta.exercise_name,
      exerciseType: meta.exercise_type,
      totalSets: meta.total_sets,
      restSeconds: meta.rest_seconds,
      targetReps: meta.target_reps,
      date: selectedDay || new Date().toISOString().split('T')[0],
    });
  } catch (e) {
    showToast('Could not load timer. Using defaults.', 'warning');
    // Fallback — open with defaults
    const task = _currentDayData?.sections?.flatMap(s => s.tasks)?.find(t => t.id === taskId);
    const name = task?.title || 'Exercise';
    const sets = task?.exercise_sets || '3x10';
    const parts = sets.split('x');
    ExerciseTimer.open({
      taskId,
      exerciseName: name,
      exerciseType: 'compound',
      totalSets: parseInt(parts[0]) || 3,
      restSeconds: 90,
      targetReps: parts[1] || '10',
      date: selectedDay || new Date().toISOString().split('T')[0],
    });
  } finally {
    if (btn) { btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Timer'; btn.disabled = false; }
  }
}

// Expose current day data for fallback
let _currentDayData = null;

// ─── EXERCISE ALTERNATIVES PANEL ────────────────────────────────────────────
let _alternativesTaskId = null;

async function showAlternatives(taskId) {
  _alternativesTaskId = taskId;
  _ensureAlternativesPanel();
  const panel = document.getElementById('alternativesPanel');
  const body = document.getElementById('alternativesBody');
  panel.classList.add('active');
  body.innerHTML = '<div style="text-align:center;color:#888;padding:30px">Loading alternatives...</div>';

  try {
    const data = await apiRequest('GET', `/api/tasks/${taskId}/alternatives`);
    const swapsLeft = data.swaps_remaining;

    body.innerHTML = `
      <div style="margin-bottom:12px">
        <div style="color:#fff;font-weight:700;font-size:0.95rem">${data.current_exercise}</div>
        <div style="font-size:0.75rem;color:#888">${swapsLeft} swap${swapsLeft !== 1 ? 's' : ''} remaining</div>
      </div>
      ${swapsLeft === 0 ? '<div style="color:#f66;font-size:0.85rem;margin-bottom:12px">⚠️ No more swaps available for this exercise today.</div>' : ''}
      <div class="alternatives-grid">
        ${data.alternatives.map((alt, i) => `
          <div class="alternative-card" onclick="applyAlternative(${taskId}, ${i})" data-alt-idx="${i}"
               style="animation-delay:${i * 0.08}s">
            <div class="alt-name">${alt.name}</div>
            ${alt.sets ? `<div class="alt-sets">${alt.sets}</div>` : ''}
            <div class="alt-desc">${(alt.description || '').slice(0, 80)}${(alt.description || '').length > 80 ? '…' : ''}</div>
            ${alt.muscle_groups?.length ? `<div class="alt-muscles">${alt.muscle_groups.slice(0,3).join(' · ')}</div>` : ''}
            ${swapsLeft > 0 ? '<div class="alt-swap-cta">Tap to swap →</div>' : ''}
          </div>
        `).join('')}
        ${data.alternatives.length === 0 ? '<div style="color:#888;text-align:center;padding:20px">No alternatives found for this exercise.</div>' : ''}
      </div>
    `;

    // Store alternatives data for apply
    window._altData = data;
  } catch (e) {
    body.innerHTML = '<div style="color:#f66;text-align:center;padding:20px">Could not load alternatives.</div>';
  }
}

async function applyAlternative(taskId, altIdx) {
  const data = window._altData;
  if (!data || data.swaps_remaining === 0) {
    showToast('No more swaps remaining.', 'error');
    return;
  }

  try {
    const result = await API.swapExercise(taskId);
    showToast(`✅ Swapped to: ${result.new_title}`);
    haptic('success');
    closeAlternatives();
    if (selectedDay) {
      const dayData = await API.getDayTasks(selectedDay);
      renderDayContent(dayData);
    }
  } catch (e) {
    showToast(e.message || 'Swap failed', 'error');
  }
}

function closeAlternatives() {
  document.getElementById('alternativesPanel')?.classList.remove('active');
}

function _ensureAlternativesPanel() {
  if (document.getElementById('alternativesPanel')) return;

  const panel = document.createElement('div');
  panel.id = 'alternativesPanel';
  panel.className = 'alternatives-overlay';
  panel.innerHTML = `
    <div class="alternatives-panel">
      <div class="alternatives-header">
        <span style="font-weight:700;color:#fff;font-size:1rem">🔄 Alternatives</span>
        <button onclick="closeAlternatives()" style="background:rgba(255,255,255,0.1);border:none;color:#fff;width:28px;height:28px;border-radius:50%;cursor:pointer">✕</button>
      </div>
      <div id="alternativesBody"></div>
    </div>
  `;
  panel.addEventListener('click', e => { if (e.target === panel) closeAlternatives(); });
  document.body.appendChild(panel);

  const style = document.createElement('style');
  style.textContent = `
    .alternatives-overlay {
      display: none; position: fixed; inset: 0; z-index: 9988;
      background: rgba(0,0,0,0.7); backdrop-filter: blur(4px);
      align-items: flex-end; justify-content: center;
    }
    .alternatives-overlay.active { display: flex; }
    .alternatives-panel {
      background: #13131f; border-radius: 24px 24px 0 0;
      width: 100%; max-width: 480px; padding: 20px 16px 36px;
      max-height: 75vh; overflow-y: auto;
    }
    .alternatives-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .alternatives-grid { display: flex; flex-direction: column; gap: 10px; }
    .alternative-card {
      background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.07);
      border-radius: 14px; padding: 14px; cursor: pointer; transition: all 0.2s;
      animation: slideUpAlt 0.3s ease both;
    }
    .alternative-card:active { transform: scale(0.97); background: rgba(0,122,255,0.1); border-color: rgba(0,122,255,0.3); }
    @keyframes slideUpAlt { from { opacity:0; transform: translateY(12px); } to { opacity:1; transform: translateY(0); } }
    .alt-name { font-weight: 700; color: #fff; font-size: 0.95rem; margin-bottom: 4px; }
    .alt-sets { font-size: 0.78rem; color: var(--accent-green, #34C759); font-weight: 600; margin-bottom: 4px; }
    .alt-desc { font-size: 0.80rem; color: #888; line-height: 1.4; margin-bottom: 6px; }
    .alt-muscles { font-size: 0.72rem; color: #666; }
    .alt-swap-cta { font-size: 0.78rem; color: var(--accent-blue, #007AFF); margin-top: 6px; font-weight: 600; }
    .task-actions-row {
      display: flex; gap: 8px; margin-top: 8px; align-items: center;
    }
    .task-timer-btn {
      background: rgba(52, 199, 89, 0.15);
      color: #34C759; border: none; border-radius: 20px;
      padding: 8px 16px; font-size: 0.9rem; font-weight: 700;
      cursor: pointer; transition: all 0.15s; white-space: nowrap;
      display: flex; align-items: center; gap: 6px;
    }
    .task-timer-btn:active { transform: scale(0.95); opacity: 0.8; }
    .task-timer-btn:disabled { opacity: 0.5; }
  `;
  document.head.appendChild(style);
}

// ─── M4 — LONG-PRESS SKIP ───────────────────────
const SKIP_REASONS = [
  { key: 'no_equipment', label: '🏋️ No equipment' },
  { key: 'injured',      label: '🤕 Injured' },
  { key: 'too_busy',     label: '⏱ Too busy' },
  { key: 'rest_day',     label: '😴 Rest day' },
];

function showSkipSheet(taskId) {
  const existing = document.getElementById('skipSheet');
  if (existing) existing.remove();

  const sheet = document.createElement('div');
  sheet.id = 'skipSheet';
  sheet.style.cssText = `
    position:fixed;bottom:0;left:0;right:0;z-index:9999;
    background:var(--bg-secondary);border-top:1px solid var(--border);
    border-radius:16px 16px 0 0;padding:16px 16px 32px;
    animation:slideUp 0.25s ease-out;
  `;
  sheet.innerHTML = `
    <div style="text-align:center;font-size:13px;color:var(--text-tertiary);margin-bottom:12px">Skip reason</div>
    ${SKIP_REASONS.map(r => `
      <button onclick="skipTask(${taskId},'${r.key}');document.getElementById('skipSheet').remove()"
        style="display:block;width:100%;text-align:left;background:rgba(255,255,255,0.04);border:none;
               border-radius:10px;padding:12px 16px;color:var(--text-primary);font-size:15px;
               margin-bottom:8px;cursor:pointer;">${r.label}</button>
    `).join('')}
    <button onclick="document.getElementById('skipSheet').remove()"
      style="display:block;width:100%;text-align:center;background:none;border:none;
             color:var(--text-tertiary);font-size:14px;padding:8px;cursor:pointer;">Cancel</button>
  `;
  document.body.appendChild(sheet);

  // dismiss on outside tap
  const dismiss = (e) => { if (!sheet.contains(e.target)) { sheet.remove(); document.removeEventListener('pointerdown', dismiss); } };
  setTimeout(() => document.addEventListener('pointerdown', dismiss), 100);
}

async function skipTask(taskId, reason) {
  try {
    await API.toggleTask(taskId, { task_id: taskId, skip_reason: reason });
    haptic('light');
    await loadDayTasks(selectedDay);
  } catch (e) {
    showToast('Could not skip task');
  }
}

// Wire long-press to all task-item elements (called after renderDayContent)
function _initLongPress() {
  document.querySelectorAll('.task-item:not([data-lp])').forEach(el => {
    el.setAttribute('data-lp', '1');
    let timer = null;
    el.addEventListener('pointerdown', e => {
      timer = setTimeout(() => { timer = null; const oc = el.getAttribute('onclick'); const m = oc && oc.match(/toggleTask\((\d+)\)/); if (m) { haptic('medium'); showSkipSheet(parseInt(m[1])); } }, 500);
    });
    el.addEventListener('pointerup',    () => { if (timer) { clearTimeout(timer); timer = null; } });
    el.addEventListener('pointercancel',() => { if (timer) { clearTimeout(timer); timer = null; } });
    el.addEventListener('pointermove',  () => { if (timer) { clearTimeout(timer); timer = null; } });
  });
}

// ─── M14 — WALK DURATION ────────────────────────
function _isWalkTask(taskKey, title) {
  return /walk/i.test(taskKey || '') || /walk/i.test(title || '');
}

async function handleWalkTask(taskId, taskKey, title) {
  const wrap = document.querySelector(`.task-item[onclick="toggleTask(${taskId})"]`);
  if (wrap && wrap.querySelector('.walk-dur-form')) return; // already shown

  const form = document.createElement('div');
  form.className = 'walk-dur-form';
  form.style.cssText = 'margin-top:8px;display:flex;gap:8px;align-items:center;';
  form.innerHTML = `
    <input id="walkMin_${taskId}" type="number" min="1" max="300" placeholder="Minutes"
      style="width:90px;background:rgba(255,255,255,0.08);border:1px solid var(--border);
             border-radius:8px;padding:6px 10px;color:#fff;font-size:14px;"
      onclick="event.stopPropagation()">
    <button onclick="event.stopPropagation();_confirmWalk(${taskId})"
      style="background:var(--green);color:#fff;border:none;border-radius:8px;
             padding:6px 14px;font-size:13px;font-weight:700;cursor:pointer;">Done</button>
    <button onclick="event.stopPropagation();this.closest('.walk-dur-form').remove()"
      style="background:none;border:none;color:var(--text-tertiary);font-size:13px;cursor:pointer;">Skip</button>
  `;
  if (wrap) {
    wrap.querySelector('.task-body').appendChild(form);
    form.querySelector('input').focus();
  } else {
    // fallback — complete without duration
    await toggleTask(taskId);
  }
}

async function _confirmWalk(taskId) {
  const input = document.getElementById(`walkMin_${taskId}`);
  const mins = parseInt(input?.value || '0', 10);
  const payload = mins > 0 ? { task_id: taskId, duration_min: mins } : undefined;
  await toggleTask(taskId, payload);
}

// ─── READINESS CARD ────────────────────────────────────────────────────────

async function loadReadinessCard() {
  const card = document.getElementById('readinessCard');
  if (!card) return;
  const today = new Date().toISOString().slice(0, 10);
  const data = await API.getReadiness(today);
  if (!data || data.score == null) return;

  const score = Math.round(data.score);
  const badge = document.getElementById('readinessBadge');
  const fill  = document.getElementById('readinessBarFill');
  const comps = document.getElementById('readinessComponents');

  // Color by zone
  const color = score >= 70 ? 'var(--green)' : score >= 45 ? 'var(--orange)' : 'var(--red, #FF3B30)';
  const label = score >= 70 ? 'Ready' : score >= 45 ? 'Moderate' : 'Rest day';

  badge.textContent = `${score}/100`;
  badge.style.color = color;
  fill.style.width  = `${score}%`;
  fill.style.background = color;

  // Component chips
  const breakdown = data.breakdown || {};
  const chipData = [
    { key: 'sleep', label: 'Sleep', icon: '🌙' },
    { key: 'hrv',   label: 'HRV',   icon: '💓' },
    { key: 'rhr',   label: 'HR',    icon: '❤️' },
    { key: 'mood',  label: 'Mood',  icon: '😊' },
  ];
  comps.innerHTML = chipData
    .filter(c => breakdown[c.key] != null)
    .map(c => {
      const v = Math.round(breakdown[c.key]);
      const bg = v >= 70 ? '#1a3a1a' : v >= 45 ? '#3a2a00' : '#3a1010';
      const tc = v >= 70 ? 'var(--green)' : v >= 45 ? 'var(--orange)' : '#FF6B6B';
      return `<span style="font-size:10px;padding:2px 6px;border-radius:4px;background:${bg};color:${tc}">${c.icon} ${c.label} ${v}</span>`;
    }).join('');

  card.style.display = 'block';
}

// ─── FOOD PHOTO IDENTIFICATION ─────────────────────────────────────────────

function openFoodPhotoCapture() {
  document.getElementById('foodPhotoInput')?.click();
}

async function handleFoodPhotoChange(input) {
  const file = input.files?.[0];
  if (!file) return;

  showToast('Identifying food…');
  try {
    const result = await API.identifyFoodPhoto(file);
    const foods = result?.foods || [];
    if (!foods.length) { showToast('Could not identify any food'); return; }

    // Pre-fill the food search modal with the best-confidence item,
    // queue remaining items as suggestions in the add-food modal.
    if (typeof openFoodSearch === 'function') openFoodSearch();
    // Short delay so modal opens, then populate the search box
    setTimeout(() => {
      const q = document.getElementById('foodSearchInput');
      if (q && foods[0]) {
        q.value = foods[0].matched_food_name || foods[0].name;
        q.dispatchEvent(new Event('input'));
      }
    }, 300);

    if (foods.length > 1) {
      showToast(`Found ${foods.length} items — showing first`);
    }
  } catch (e) {
    showToast(e.message === 'pro_required' ? 'Pro required for food photos' : 'Photo scan failed');
  }
  input.value = '';
}
