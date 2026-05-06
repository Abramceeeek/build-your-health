/**
 * ExerciseTimer — handles set timers, rest timers, isometric holds, and warmup stopwatches.
 * Also manages the exercise session start/finish API calls.
 */

const ExerciseTimer = (() => {
  // ─── State ─────────────────────────────────────────────────────────────────
  let currentSession = {
    sessionId: null,
    taskId: null,
    exerciseName: "",
    exerciseType: "compound", // compound|isolation|isometric|cardio|stretch
    totalSets: 3,
    restSeconds: 90,           // rest between sets
    targetReps: "10",
    setsLog: [],
    currentSet: 0,
    timerInterval: null,
    timerSeconds: 0,
    timerMode: "idle",          // idle | active | rest | isometric
    startedAt: null,
    totalRestSeconds: 0,
    totalActiveSeconds: 0,
  };

  // ─── DOM Refs ───────────────────────────────────────────────────────────────
  let modal = null;

  // ─── Public API ─────────────────────────────────────────────────────────────

  /**
   * Open the exercise timer modal.
   * @param {Object} opts
   * @param {number|null} opts.taskId
   * @param {string} opts.exerciseName
   * @param {string} opts.exerciseType  — compound|isometric|cardio|stretch
   * @param {number} opts.totalSets
   * @param {number} opts.restSeconds
   * @param {string} opts.targetReps   — e.g. "10", "8-10", "60s"
   * @param {string} opts.date
   */
  async function open(opts) {
    Object.assign(currentSession, {
      taskId: opts.taskId || null,
      exerciseName: opts.exerciseName || "Exercise",
      exerciseType: opts.exerciseType || "compound",
      totalSets: opts.totalSets || 3,
      restSeconds: opts.restSeconds || 90,
      targetReps: opts.targetReps || "10",
      setsLog: [],
      currentSet: 0,
      timerMode: "idle",
      timerSeconds: 0,
      totalRestSeconds: 0,
      totalActiveSeconds: 0,
      startedAt: Date.now(),
    });

    // Start session on backend
    try {
      const date = opts.date || new Date().toISOString().split("T")[0];
      const resp = await apiRequest("POST", "/api/exercise-sessions/start", {
        task_id: currentSession.taskId,
        exercise_name: currentSession.exerciseName,
        date,
      });
      currentSession.sessionId = resp.session_id;
    } catch (e) {
      console.warn("Could not start exercise session on backend:", e);
    }

    _render();
    modal.classList.add("active");
  }

  function close() {
    _stopTimer();
    if (modal) modal.classList.remove("active");
    currentSession.sessionId = null;
  }

  // ─── Rendering ─────────────────────────────────────────────────────────────

  function _render() {
    if (!modal) _createModal();

    const isIsometric = currentSession.exerciseType === "isometric";

    modal.innerHTML = `
      <div class="exercise-timer-modal">
        <div class="timer-header">
          <h2 class="timer-exercise-name">${currentSession.exerciseName}</h2>
          <button class="timer-close-btn" id="timerCloseBtn">✕</button>
        </div>

        ${isIsometric ? _renderIsometric() : _renderStrengthTimer()}

        <div class="sets-log-section">
          <h4>Sets Completed</h4>
          <div class="sets-log-list" id="setsLogList">
            <p class="no-sets-msg">No sets yet — press Start to begin.</p>
          </div>
        </div>

        <div class="timer-finish-row">
          <button class="btn-finish-early" id="timerFinishBtn">Finish & Save</button>
        </div>
      </div>
    `;

    // Attach events
    modal.querySelector("#timerCloseBtn").addEventListener("click", close);
    modal.querySelector("#timerFinishBtn").addEventListener("click", finishSession);

    if (isIsometric) {
      modal.querySelector("#isometricStartBtn")?.addEventListener("click", _startIsometric);
    } else {
      modal.querySelector("#startSetBtn")?.addEventListener("click", _handleSetButton);
    }
  }

  function _renderStrengthTimer() {
    const setsDone = currentSession.setsLog.length;
    const totalSets = currentSession.totalSets;
    const setLabel = setsDone < totalSets
      ? `Set ${setsDone + 1} / ${totalSets}`
      : "All Sets Complete!";

    const mode = currentSession.timerMode;
    let timerDisplay = _formatTime(currentSession.timerSeconds);

    let btnLabel = "▶ Start Set";
    let btnClass = "btn-start-set";
    if (mode === "active") { btnLabel = "🛑 End Set"; btnClass = "btn-end-set"; }
    else if (mode === "rest") { btnLabel = "⏭ Skip Rest"; btnClass = "btn-skip-rest"; }

    const btnDisabled = (mode === "rest" && currentSession.timerSeconds > 10) ? "" : "";

    return `
      <div class="strength-timer">
        <div class="set-label">${setLabel}</div>
        <div class="target-reps">Target: <strong>${currentSession.targetReps} reps</strong> · Rest: ${currentSession.restSeconds}s</div>

        <div class="big-timer ${mode === 'rest' ? 'rest-mode' : mode === 'active' ? 'active-mode' : ''}">
          <div class="timer-display">${timerDisplay}</div>
          <div class="timer-subtitle">${mode === 'active' ? 'Working…' : mode === 'rest' ? '💤 Rest' : 'Ready'}</div>
        </div>

        <div class="set-controls">
          ${setsDone < totalSets || mode === "active"
            ? `<button class="exercise-timer-btn ${btnClass}" id="startSetBtn" ${btnDisabled}>${btnLabel}</button>`
            : ``
          }
        </div>

        ${mode === "active" ? `
          <div class="live-input-row">
            <label>Reps done:</label>
            <input type="number" id="repsInput" class="timer-input" value="${currentSession.targetReps.replace(/\D/g,'') || ''}" min="0" max="100" placeholder="Reps">
            <label>Weight:</label>
            <input type="text" id="weightInput" class="timer-input" value="" placeholder="kg / BW">
          </div>
        ` : ""}
      </div>
    `;
  }

  function _renderIsometric() {
    const holdSeconds = currentSession.restSeconds > 0 ? currentSession.restSeconds : 60;
    const mode = currentSession.timerMode;
    const timeLeft = mode === "isometric"
      ? Math.max(0, holdSeconds - currentSession.timerSeconds)
      : holdSeconds;
    const pct = mode === "isometric" ? (currentSession.timerSeconds / holdSeconds * 100) : 0;

    return `
      <div class="isometric-timer">
        <div class="set-label">Hold for ${holdSeconds}s</div>

        <div class="isometric-ring">
          <svg viewBox="0 0 100 100" class="isometric-svg">
            <circle cx="50" cy="50" r="42" fill="none" stroke="#1a1a2e" stroke-width="8"/>
            <circle cx="50" cy="50" r="42" fill="none" stroke="var(--accent-green)" stroke-width="8"
              stroke-dasharray="263.9" stroke-dashoffset="${263.9 - (263.9 * pct / 100)}"
              stroke-linecap="round" transform="rotate(-90 50 50)" class="timer-ring-progress"
            />
          </svg>
          <div class="isometric-time">${_formatTime(timeLeft)}</div>
        </div>

        ${mode === "idle"
          ? `<button class="exercise-timer-btn btn-start-set" id="isometricStartBtn">▶ Start Hold</button>`
          : mode === "isometric"
          ? `<div class="breathe-cue">Breathe steadily — Don't hold your breath!</div>`
          : `<div class="isometric-done">✅ Hold Complete! Rest and repeat.</div>
             <button class="exercise-timer-btn btn-start-set" id="isometricStartBtn">▶ Next Hold</button>`
        }
      </div>
    `;
  }

  // ─── Timer Logic ────────────────────────────────────────────────────────────

  function _handleSetButton() {
    const mode = currentSession.timerMode;
    if (mode === "idle" || mode === "done_resting") {
      _startSet();
    } else if (mode === "active") {
      _endSet();
    } else if (mode === "rest") {
      _skipRest();
    }
  }

  function _startSet() {
    currentSession.timerMode = "active";
    currentSession.timerSeconds = 0;
    _startTimer(() => {
      currentSession.timerSeconds++;
      currentSession.totalActiveSeconds++;
      _updateTimerDisplay();
    });
    _haptic("impact");
    _render();
  }

  function _endSet() {
    _stopTimer();
    const setNum = currentSession.setsLog.length + 1;
    const duration = currentSession.timerSeconds;

    // Read reps & weight from inputs if visible
    const repsInput = modal.querySelector("#repsInput");
    const weightInput = modal.querySelector("#weightInput");
    const reps = repsInput ? parseInt(repsInput.value) || 0 : 0;
    const weight = weightInput ? weightInput.value.trim() : "";

    currentSession.setsLog.push({
      set_number: setNum,
      reps,
      weight_label: weight || "BW",
      duration_s: duration,
    });

    _haptic("success");

    const allDone = currentSession.setsLog.length >= currentSession.totalSets;
    if (allDone) {
      currentSession.timerMode = "done_resting";
      _render();
      _updateSetsLog();
    } else {
      // Start rest countdown
      _startRest();
    }
  }

  function _startRest() {
    currentSession.timerMode = "rest";
    currentSession.timerSeconds = currentSession.restSeconds;
    _startTimer(() => {
      if (currentSession.timerSeconds <= 0) {
        _restDone();
        return;
      }
      currentSession.timerSeconds--;
      currentSession.totalRestSeconds++;
      _updateTimerDisplay();
    });
    _render();
    _updateSetsLog();
  }

  function _skipRest() {
    _stopTimer();
    currentSession.totalRestSeconds += (currentSession.restSeconds - currentSession.timerSeconds);
    _restDone();
  }

  function _restDone() {
    _stopTimer();
    _haptic("impact");
    currentSession.timerMode = "idle";
    _render();
    _updateSetsLog();
  }

  function _startIsometric() {
    const holdSeconds = currentSession.restSeconds > 0 ? currentSession.restSeconds : 60;
    currentSession.timerMode = "isometric";
    currentSession.timerSeconds = 0;
    _startTimer(() => {
      currentSession.timerSeconds++;
      currentSession.totalActiveSeconds++;
      if (currentSession.timerSeconds >= holdSeconds) {
        _stopTimer();
        currentSession.timerMode = "done_resting";
        currentSession.setsLog.push({
          set_number: currentSession.setsLog.length + 1,
          duration_s: holdSeconds,
          reps: null,
        });
        _haptic("success");
        _render();
        return;
      }
      _updateIsometricRing();
    });
    _haptic("impact");
    _render();
  }

  function _startTimer(tick) {
    _stopTimer();
    currentSession.timerInterval = setInterval(tick, 1000);
  }

  function _stopTimer() {
    if (currentSession.timerInterval) {
      clearInterval(currentSession.timerInterval);
      currentSession.timerInterval = null;
    }
  }

  // ─── Live Update Helpers ────────────────────────────────────────────────────

  function _updateTimerDisplay() {
    const display = modal?.querySelector(".timer-display");
    if (!display) return;

    const subtitle = modal?.querySelector(".timer-subtitle");
    const mode = currentSession.timerMode;

    display.textContent = _formatTime(currentSession.timerSeconds);
    if (subtitle) {
      subtitle.textContent = mode === "active" ? "Working…" : mode === "rest" ? "💤 Rest" : "";
    }

    if (mode === "rest" && currentSession.timerSeconds <= 10) {
      display.style.color = "var(--accent-red, #ff6b6b)";
      if (currentSession.timerSeconds <= 3) _haptic("impact");
    } else {
      display.style.color = "";
    }
  }

  function _updateIsometricRing() {
    const holdSeconds = currentSession.restSeconds > 0 ? currentSession.restSeconds : 60;
    const elapsed = currentSession.timerSeconds;
    const remaining = Math.max(0, holdSeconds - elapsed);
    const pct = (elapsed / holdSeconds) * 100;

    const timeEl = modal?.querySelector(".isometric-time");
    if (timeEl) timeEl.textContent = _formatTime(remaining);

    const ring = modal?.querySelector(".timer-ring-progress");
    if (ring) {
      const circumference = 263.9;
      ring.style.strokeDashoffset = circumference - (circumference * pct / 100);
    }
  }

  function _updateSetsLog() {
    const container = modal?.querySelector("#setsLogList");
    if (!container) return;

    if (currentSession.setsLog.length === 0) {
      container.innerHTML = `<p class="no-sets-msg">No sets yet — press Start to begin.</p>`;
      return;
    }

    container.innerHTML = currentSession.setsLog.map((s) => `
      <div class="set-log-item">
        <span class="set-num">Set ${s.set_number}</span>
        ${s.reps != null ? `<span class="set-reps">${s.reps} reps</span>` : ""}
        ${s.weight_label ? `<span class="set-weight">${s.weight_label}</span>` : ""}
        <span class="set-time">${_formatTime(s.duration_s || 0)}</span>
      </div>
    `).join("");
  }

  // ─── Finish Session ─────────────────────────────────────────────────────────

  async function finishSession() {
    _stopTimer();

    const totalMs = Date.now() - currentSession.startedAt;
    const totalSecs = Math.round(totalMs / 1000);

    if (currentSession.sessionId) {
      try {
        const date = new Date().toISOString().split("T")[0];
        const resp = await apiRequest("POST", `/api/exercise-sessions/${currentSession.sessionId}/finish`, {
          sets_log: currentSession.setsLog,
          total_duration_s: totalSecs,
          rest_seconds_total: currentSession.totalRestSeconds,
        });

        // Show result toast
        const cal = resp.calories_burned || 0;
        const xp = resp.xp_earned || 0;
        showToast(`✅ ${currentSession.exerciseName} done! 🔥 ${cal} kcal burned${xp ? ` · +${xp} XP` : ""}`);

        // Reload tasks if function is available globally
        if (typeof loadTodayTasks === "function") loadTodayTasks();
        if (typeof loadHealthSummary === "function") loadHealthSummary();
      } catch (e) {
        console.error("Failed to finish session:", e);
        showToast("Session saved locally.", "warning");
      }
    }

    close();
  }

  // ─── Utilities ──────────────────────────────────────────────────────────────

  function _formatTime(secs) {
    const s = Math.max(0, Math.round(secs));
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${String(sec).padStart(2, "0")}`;
  }

  function _haptic(type) {
    try {
      if (window.Telegram?.WebApp?.HapticFeedback) {
        if (type === "success") {
          window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
        } else {
          window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
        }
      }
    } catch (_) {}
  }

  function _createModal() {
    modal = document.createElement("div");
    modal.id = "exerciseTimerModal";
    modal.className = "exercise-timer-overlay";
    document.body.appendChild(modal);

    // Add styles
    if (!document.querySelector("#exerciseTimerStyles")) {
      const style = document.createElement("style");
      style.id = "exerciseTimerStyles";
      style.textContent = `
        .exercise-timer-overlay {
          display: none;
          position: fixed;
          inset: 0;
          z-index: 9999;
          background: rgba(0,0,0,0.85);
          backdrop-filter: blur(4px);
          align-items: flex-end;
          justify-content: center;
        }
        .exercise-timer-overlay.active {
          display: flex;
        }
        .exercise-timer-modal {
          background: var(--bg-card, #1a1a2e);
          border-radius: 24px 24px 0 0;
          width: 100%;
          max-width: 480px;
          padding: 20px 20px 32px;
          max-height: 90vh;
          overflow-y: auto;
        }
        .timer-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }
        .timer-exercise-name {
          font-size: 1.2rem;
          font-weight: 700;
          color: var(--text-primary, #fff);
          margin: 0;
        }
        .timer-close-btn {
          background: rgba(255,255,255,0.1);
          border: none;
          color: #fff;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          cursor: pointer;
          font-size: 1rem;
        }
        .set-label {
          text-align: center;
          font-size: 1rem;
          color: var(--text-secondary, #aaa);
          margin-bottom: 4px;
        }
        .target-reps {
          text-align: center;
          font-size: 0.85rem;
          color: var(--text-secondary, #aaa);
          margin-bottom: 16px;
        }
        .big-timer {
          text-align: center;
          padding: 20px;
          background: rgba(255,255,255,0.05);
          border-radius: 20px;
          margin-bottom: 16px;
          border: 2px solid transparent;
          transition: border-color 0.3s;
        }
        .big-timer.active-mode { border-color: var(--accent-green, #00d4aa); }
        .big-timer.rest-mode { border-color: var(--accent-blue, #4facfe); }
        .timer-display {
          font-size: 3.5rem;
          font-weight: 800;
          font-variant-numeric: tabular-nums;
          color: var(--text-primary, #fff);
          transition: color 0.3s;
        }
        .timer-subtitle {
          font-size: 0.85rem;
          color: var(--text-secondary, #aaa);
          margin-top: 4px;
        }
        .set-controls { text-align: center; margin-bottom: 16px; }
        .exercise-timer-btn {
          padding: 14px 40px;
          border: none;
          border-radius: 50px;
          font-size: 1rem;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s;
          letter-spacing: 0.5px;
        }
        .btn-start-set { background: var(--accent-green, #00d4aa); color: #0a0a1a; }
        .btn-end-set { background: var(--accent-red, #ff6b6b); color: #fff; }
        .btn-skip-rest { background: var(--accent-blue, #4facfe); color: #0a0a1a; }
        .exercise-timer-btn:active { transform: scale(0.96); }
        .live-input-row {
          display: grid;
          grid-template-columns: auto 1fr auto 1fr;
          gap: 8px;
          align-items: center;
          margin-top: 12px;
          font-size: 0.9rem;
          color: var(--text-secondary, #aaa);
        }
        .timer-input {
          background: rgba(255,255,255,0.07);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 8px;
          padding: 8px;
          color: #fff;
          font-size: 0.95rem;
          text-align: center;
          width: 100%;
        }
        .sets-log-section { margin-top: 16px; }
        .sets-log-section h4 { font-size: 0.85rem; color: var(--text-secondary, #aaa); margin-bottom: 8px; }
        .set-log-item {
          display: flex;
          gap: 12px;
          align-items: center;
          padding: 8px 12px;
          background: rgba(255,255,255,0.04);
          border-radius: 10px;
          margin-bottom: 6px;
          font-size: 0.9rem;
        }
        .set-num { font-weight: 700; color: var(--accent-green, #00d4aa); min-width: 48px; }
        .set-reps, .set-weight { color: var(--text-primary, #fff); }
        .set-time { color: var(--text-secondary, #aaa); margin-left: auto; }
        .no-sets-msg { color: var(--text-secondary, #aaa); font-size: 0.85rem; text-align: center; }
        .timer-finish-row { text-align: center; margin-top: 20px; }
        .btn-finish-early {
          background: transparent;
          border: 2px solid rgba(255,255,255,0.15);
          color: var(--text-secondary, #aaa);
          padding: 10px 28px;
          border-radius: 50px;
          font-size: 0.9rem;
          cursor: pointer;
          transition: all 0.2s;
        }
        .btn-finish-early:hover { border-color: rgba(255,255,255,0.3); color: #fff; }
        /* Isometric */
        .isometric-timer { text-align: center; }
        .isometric-ring { position: relative; width: 180px; height: 180px; margin: 16px auto; }
        .isometric-svg { width: 100%; height: 100%; }
        .timer-ring-progress { transition: stroke-dashoffset 1s linear; }
        .isometric-time {
          position: absolute;
          top: 50%; left: 50%;
          transform: translate(-50%,-50%);
          font-size: 2.5rem;
          font-weight: 800;
          color: var(--text-primary, #fff);
        }
        .breathe-cue { color: var(--accent-blue, #4facfe); font-size: 0.9rem; margin: 12px 0; }
        .isometric-done { color: var(--accent-green, #00d4aa); font-size: 1rem; margin: 12px 0; }
      `;
      document.head.appendChild(style);
    }
  }

  // ─── Expose ─────────────────────────────────────────────────────────────────
  return { open, close, finishSession };
})();
