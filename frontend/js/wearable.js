/**
 * Wearable data entry and calorie burn summary panel.
 * Also handles the daily burn total card combining exercise + wearable.
 */

const WearableTracker = (() => {
  // ─── State ──────────────────────────────────────────────────────────────────
  let todayData = {
    steps: 0,
    active_calories: 0,
    resting_hr: 0,
    floors_climbed: 0,
    wearable_source: "manual",
    exercise_calories: 0,
  };

  let date = new Date().toISOString().split("T")[0];

  // ─── Public API ─────────────────────────────────────────────────────────────

  async function load() {
    date = new Date().toISOString().split("T")[0];
    try {
      const data = await apiRequest("GET", `/api/health/today`);
      todayData = {
        steps: data.steps || 0,
        active_calories: data.active_calories || 0,
        resting_hr: data.resting_hr || 0,
        floors_climbed: data.floors_climbed || 0,
        wearable_source: data.wearable_source || "manual",
        exercise_calories: data.exercise_calories || 0,
      };
    } catch (e) {
      console.warn("Could not load health data:", e);
    }
    _renderSummaryCard();
  }

  function openPanel() {
    _renderPanel();
    document.getElementById("wearablePanel")?.classList.add("active");
  }

  function closePanel() {
    document.getElementById("wearablePanel")?.classList.remove("active");
  }

  async function save() {
    const steps = parseInt(document.getElementById("wearableSteps")?.value) || 0;
    const activeCal = parseInt(document.getElementById("wearableActiveCal")?.value) || 0;
    const hr = parseInt(document.getElementById("wearableHR")?.value) || 0;
    const floors = parseInt(document.getElementById("wearableFloors")?.value) || 0;
    const source = document.getElementById("wearableSource")?.value || "manual";

    try {
      await apiRequest("PATCH", "/api/health/today", {
        steps,
        active_calories: activeCal,
        resting_hr: hr,
        floors_climbed: floors,
        wearable_source: source,
      });

      todayData.steps = steps;
      todayData.active_calories = activeCal;
      todayData.resting_hr = hr;
      todayData.floors_climbed = floors;
      todayData.wearable_source = source;

      _renderSummaryCard();
      closePanel();
      showToast("✅ Activity data saved!");
    } catch (e) {
      showToast("Could not save data. Try again.", "error");
    }
  }

  // ─── Rendering ──────────────────────────────────────────────────────────────

  function _renderSummaryCard() {
    const container = document.getElementById("burnSummaryCard");
    if (!container) return;
    _injectStyles();

    const stepsCal = _stepsToCalories(todayData.steps);
    const totalBurn = (todayData.exercise_calories || 0) + (todayData.active_calories || 0);
    const bmr = _estimateBMR(); // base metabolic rate ~ 1700
    const totalDay = bmr + totalBurn;

    container.innerHTML = `
      <div class="burn-card">
        <div class="burn-card-header">
          <span class="burn-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--orange)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"></path></svg></span>
          <span class="burn-title">Today's Calorie Burn</span>
          <button class="wearable-btn" id="openWearableBtn">Log activity</button>
        </div>
        <div class="burn-stats">
          <div class="burn-stat">
            <div class="burn-stat-val">${todayData.exercise_calories || 0}</div>
            <div class="burn-stat-label">Exercise</div>
          </div>
          <div class="burn-stat">
            <div class="burn-stat-val">${todayData.active_calories || 0}</div>
            <div class="burn-stat-label">Wearable</div>
          </div>
          <div class="burn-stat">
            <div class="burn-stat-val">${stepsCal}</div>
            <div class="burn-stat-label">Steps</div>
          </div>
          <div class="burn-stat burn-stat-total">
            <div class="burn-stat-val">${totalDay}</div>
            <div class="burn-stat-label">Total TDEE</div>
          </div>
        </div>
        ${todayData.steps > 0 ? `<div class="steps-text-inline">${todayData.steps.toLocaleString()} steps</div>` : ""}
        ${todayData.resting_hr > 0 ? `<div class="hr-display"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="color:var(--pink)"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg> Resting HR: ${todayData.resting_hr} bpm</div>` : ""}
        ${todayData.wearable_source && todayData.wearable_source !== "manual" ? `<div class="source-tag">${_sourceLabel(todayData.wearable_source)}</div>` : ""}
      </div>
    `;

    document.getElementById("openWearableBtn")?.addEventListener("click", openPanel);
  }

  function _renderPanel() {
    let panel = document.getElementById("wearablePanel");
    if (!panel) {
      panel = document.createElement("div");
      panel.id = "wearablePanel";
      panel.className = "wearable-slide-panel";
      document.body.appendChild(panel);
      _injectStyles();
    }

    panel.innerHTML = `
      <div class="wearable-panel-inner">
        <div class="wearable-panel-header">
          <h3>Today's Activity</h3>
          <button class="wearable-close" id="wearableCloseBtn"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
        </div>

        <div class="wearable-source-row">
          <label>Device</label>
          <select id="wearableSource" class="wearable-select">
            <option value="manual" ${todayData.wearable_source === "manual" ? "selected" : ""}>Manual Entry</option>
            <option value="apple_watch" ${todayData.wearable_source === "apple_watch" ? "selected" : ""}>Apple Watch</option>
            <option value="fitbit" ${todayData.wearable_source === "fitbit" ? "selected" : ""}>Fitbit</option>
            <option value="samsung" ${todayData.wearable_source === "samsung" ? "selected" : ""}>Samsung Health</option>
            <option value="garmin" ${todayData.wearable_source === "garmin" ? "selected" : ""}>Garmin</option>
            <option value="mi_band" ${todayData.wearable_source === "mi_band" ? "selected" : ""}>Mi Band / Zepp</option>
          </select>
        </div>

        <div class="wearable-fields">
          <div class="wearable-field">
            <label>Steps</label>
            <input type="number" id="wearableSteps" class="wearable-input" value="${todayData.steps || ""}" placeholder="e.g. 8500" min="0" max="100000">
          </div>
          <div class="wearable-field">
            <label>Active Calories (kcal)</label>
            <input type="number" id="wearableActiveCal" class="wearable-input" value="${todayData.active_calories || ""}" placeholder="e.g. 450" min="0">
          </div>
          <div class="wearable-field">
            <label>Resting Heart Rate (bpm)</label>
            <input type="number" id="wearableHR" class="wearable-input" value="${todayData.resting_hr || ""}" placeholder="e.g. 62" min="30" max="200">
          </div>
          <div class="wearable-field">
            <label>Floors Climbed</label>
            <input type="number" id="wearableFloors" class="wearable-input" value="${todayData.floors_climbed || ""}" placeholder="e.g. 5" min="0">
          </div>
        </div>

        <div class="wearable-note">
          Open your health app → Today's summary → copy these values here.
        </div>

        <button class="wearable-save-btn" id="wearableSaveBtn">Save Activity Data</button>
      </div>
    `;

    panel.querySelector("#wearableCloseBtn").addEventListener("click", closePanel);
    panel.querySelector("#wearableSaveBtn").addEventListener("click", save);
  }

  function _injectStyles() {
    if (document.querySelector("#wearableStyles")) return;
    const s = document.createElement("style");
    s.id = "wearableStyles";
    s.textContent = `
      .burn-card {
        background: var(--bg-card-solid);
        border: 1px solid var(--border, rgba(255,255,255,0.07));
        border-radius: var(--card-radius, 12px);
        padding: var(--card-pad, 16px);
        margin: 12px 0;
      }
      .burn-card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 16px;
      }
      .burn-icon { display: flex; align-items: center; }
      .burn-title {
        font-family: var(--font-display, 'Barlow Condensed', system-ui, sans-serif);
        font-weight: 700;
        color: var(--text-primary);
        flex: 1;
        font-size: 17px;
        letter-spacing: -0.2px;
      }
      .wearable-btn {
        background: var(--bg-tertiary);
        border: 1px solid var(--border, rgba(255,255,255,0.07));
        color: var(--blue);
        padding: 7px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
      }
      .burn-stats {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin-bottom: 12px;
      }
      .burn-stat { text-align: left; }
      .burn-stat-val {
        font-family: var(--font-display, 'Barlow Condensed', system-ui, sans-serif);
        font-size: 22px;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.3px;
      }
      .burn-stat-label { font-size: 10px; color: var(--text-secondary); margin-top: 2px; text-transform: uppercase; letter-spacing: 0.4px; }
      .burn-stat-total .burn-stat-val { color: var(--green); }
      .steps-text-inline { font-size: 0.78rem; color: var(--text-secondary); margin-top: 6px; letter-spacing: 0.2px; }
      .hr-display { font-size: 0.82rem; color: var(--pink, #EC4899); margin-top: 8px; }
      .source-tag { font-size: 0.72rem; color: var(--text-tertiary); margin-top: 4px; }

      /* Slide panel */
      .wearable-slide-panel {
        display: none;
        position: fixed;
        inset: 0;
        z-index: 9990;
        background: rgba(0,0,0,0.65);
        backdrop-filter: blur(6px);
        align-items: flex-end;
        justify-content: center;
      }
      .wearable-slide-panel.active { display: flex; }
      .wearable-panel-inner {
        background: var(--bg-secondary);
        border: 1px solid var(--border, rgba(255,255,255,0.07));
        border-bottom: none;
        border-radius: 16px 16px 0 0;
        width: 100%;
        max-width: 480px;
        padding: 24px 20px 40px;
        max-height: 85vh;
        overflow-y: auto;
      }
      .wearable-panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 24px;
      }
      .wearable-panel-header h3 {
        margin: 0;
        color: var(--text-primary);
        font-family: var(--font-display, 'Barlow Condensed', system-ui, sans-serif);
        font-size: 22px;
        font-weight: 700;
        letter-spacing: -0.3px;
      }
      .wearable-close {
        background: var(--bg-tertiary);
        border: 1px solid var(--border, rgba(255,255,255,0.07));
        color: var(--text-secondary);
        width: 30px;
        height: 30px;
        border-radius: 50%;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .wearable-source-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        font-size: 0.88rem;
        color: var(--text-secondary);
      }
      .wearable-select {
        background: var(--bg-tertiary);
        border: 1px solid var(--border, rgba(255,255,255,0.07));
        color: var(--text-primary);
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 14px;
      }
      .wearable-fields { display: flex; flex-direction: column; gap: 12px; }
      .wearable-field label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
      .wearable-input {
        width: 100%;
        background: var(--bg-tertiary);
        border: 1px solid var(--border, rgba(255,255,255,0.07));
        border-radius: 10px;
        padding: 12px 16px;
        color: var(--text-primary);
        font-size: 16px;
        box-sizing: border-box;
        outline: none;
        transition: border-color 0.15s;
      }
      .wearable-input:focus { border-color: var(--blue); }
      .wearable-note {
        margin: 20px 0;
        padding: 12px 16px;
        background: rgba(59,130,255,0.08);
        border: 1px solid rgba(59,130,255,0.18);
        border-radius: 10px;
        font-size: 13px;
        color: var(--blue);
      }
      .wearable-save-btn {
        width: 100%;
        padding: 16px;
        background: var(--blue);
        color: #fff;
        border: none;
        border-radius: 12px;
        font-size: 15px;
        font-weight: 700;
        cursor: pointer;
        margin-top: 10px;
        transition: transform 0.15s, opacity 0.15s;
        letter-spacing: 0.2px;
      }
      .wearable-save-btn:active { transform: scale(0.98); opacity: 0.9; }
    `;
    document.head.appendChild(s);
  }

  // ─── Utilities ──────────────────────────────────────────────────────────────

  function _stepsToCalories(steps) {
    // Standard estimate: 1 step ≈ 0.04 kcal for 75kg person
    return Math.round((steps || 0) * 0.04);
  }

  function _estimateBMR() {
    // Simple average BMR — could be personalised from user profile later
    return 1700;
  }

  function _sourceLabel(source) {
    const labels = {
      apple_watch: "Apple Watch",
      fitbit: "Fitbit",
      samsung: "Samsung Health",
      garmin: "Garmin",
      mi_band: "Mi Band / Zepp",
    };
    return labels[source] || source;
  }

  return { load, openPanel, closePanel };
})();
