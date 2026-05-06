async function apiRequest(method, path, body) {
  const options = { method };
  if (body && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    options.body = JSON.stringify(body);
  }
  return api(path, options);
}

// ─── WEARABLE INTEGRATION ───────────────────────────────────────────────────
// Load wearable data when Today page is shown
document.addEventListener('DOMContentLoaded', () => {
  if (typeof WearableTracker !== 'undefined') {
    WearableTracker.load();
  }
});

// Override the old promptSteps to use wearable panel instead (with fallback)
function promptSteps() {
  if (typeof WearableTracker !== 'undefined' && WearableTracker.openPanel) {
    WearableTracker.openPanel();
  } else {
    const val = prompt('How many steps today?');
    if (val) incrementHealth('steps', parseInt(val) || 0);
  }
}

// ─── SUPPLEMENT TRACKER ─────────────────────────────────────────────────────
// M7 — remember the user's preferred expand state across sessions so daily
// supplement-takers don't have to re-open it every time.
let _suppVisible = (() => {
  try { return localStorage.getItem('supp_expanded') === '1'; } catch (_) { return false; }
})();

async function toggleSuppSection() {
  _suppVisible = !_suppVisible;
  try { localStorage.setItem('supp_expanded', _suppVisible ? '1' : '0'); } catch (_) {}
  const body = document.getElementById('supplementBody');
  const icon = document.getElementById('suppToggleIcon');
  if (body) body.style.display = _suppVisible ? 'block' : 'none';
  if (icon) icon.textContent = _suppVisible ? '▲' : '▾';
  if (_suppVisible) await loadSupplements();
}

// Apply persisted state on first paint after the supplement card is rendered.
document.addEventListener('DOMContentLoaded', () => {
  if (!_suppVisible) return;
  const body = document.getElementById('supplementBody');
  const icon = document.getElementById('suppToggleIcon');
  if (body) body.style.display = 'block';
  if (icon) icon.textContent = '▲';
  loadSupplements().catch(() => {});
});

async function loadSupplements() {
  const grid = document.getElementById('supplementGrid');
  if (!grid) return;
  try {
    const today = new Date().toISOString().split('T')[0];
    const items = await apiRequest('GET', `/api/supplements/daily/${today}`);
    const taken = items.filter(i => i.taken_today).length;
    const countEl = document.getElementById('suppTakenCount');
    if (countEl) countEl.textContent = `${taken}/${items.length}`;

    grid.innerHTML = items.map(item => `
      <div class="supplement-item ${item.taken_today ? 'taken' : ''}" id="suppItem_${item.key}"
           onclick="toggleSupplement('${item.key}', ${item.log_id || 'null'})">
        <span class="supplement-emoji">${item.emoji}</span>
        <div class="supplement-info">
          <div class="supplement-name">${item.name}</div>
          <div class="supplement-dose">${item.default_dose_g >= 1 ? item.default_dose_g + 'g' : (item.default_dose_g * 1000).toFixed(0) + 'mg'} · ${item.when_to_take}</div>
        </div>
        <span class="supplement-check">✓</span>
      </div>
    `).join('');
  } catch (e) {
    if (grid) grid.innerHTML = '<p style="color:#888;font-size:0.85rem;text-align:center">Could not load supplements.</p>';
  }
}

async function toggleSupplement(key, existingLogId) {
  const el = document.getElementById(`suppItem_${key}`);
  if (!el) return;
  const isTaken = el.classList.contains('taken');

  if (isTaken && existingLogId) {
    // Untake
    try {
      await apiRequest('DELETE', `/api/supplements/log/${existingLogId}`);
      el.classList.remove('taken');
      showToast(`Removed ${key} log`);
    } catch (e) { showToast('Could not remove log', 'error'); }
  } else {
    // Take
    try {
      const today = new Date().toISOString().split('T')[0];
      await apiRequest('POST', '/api/supplements/log', { supplement_key: key, date: today });
      el.classList.add('taken');
      haptic('success');
      showToast(`✅ ${key} logged!`);
      await loadSupplements();
    } catch (e) { showToast('Could not log supplement', 'error'); }
  }
}

// ─── COOKED DISH CALCULATOR ─────────────────────────────────────────────────
let _cookedIngredients = [];

function openCookedDishModal() {
  _cookedIngredients = [];
  const overlay = document.getElementById('cookedDishOverlay');
  if (overlay) {
    overlay.style.display = 'block';
    document.getElementById('cookedIngredients').innerHTML = '';
    addCookedIngredient(); // Add first ingredient row
  }
}

function closeCookedDish() {
  const overlay = document.getElementById('cookedDishOverlay');
  if (overlay) overlay.style.display = 'none';
}

function addCookedIngredient() {
  const idx = _cookedIngredients.length;
  _cookedIngredients.push({ food_name: '', grams: 0, nutrients_per_100g: {} });

  const container = document.getElementById('cookedIngredients');
  const row = document.createElement('div');
  row.className = 'gate-section';
  row.id = `cookedRow_${idx}`;
  row.innerHTML = `
    <div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:8px">
      <div style="flex:1">
        <div class="gate-label">Ingredient ${idx + 1}</div>
        <input class="gate-input" id="cookedFood_${idx}" placeholder="Search food..." oninput="searchCookedFood(${idx}, this.value)">
        <div id="cookedSuggest_${idx}" style="display:none;background:#111;border-radius:10px;margin-top:4px;max-height:150px;overflow-y:auto"></div>
      </div>
      <div style="width:80px">
        <div class="gate-label">Grams</div>
        <input class="gate-input" id="cookedGrams_${idx}" type="number" placeholder="100" min="1" value="100">
      </div>
      <button onclick="removeCookedRow(${idx})" style="margin-top:22px;background:none;border:none;color:#888;font-size:1.2rem;cursor:pointer">✕</button>
    </div>
  `;
  container.appendChild(row);
}

function removeCookedRow(idx) {
  document.getElementById(`cookedRow_${idx}`)?.remove();
  _cookedIngredients[idx] = null;
}

let _cookedSearchTimeout = null;
async function searchCookedFood(idx, q) {
  clearTimeout(_cookedSearchTimeout);
  if (q.length < 2) {
    document.getElementById(`cookedSuggest_${idx}`).style.display = 'none';
    return;
  }
  _cookedSearchTimeout = setTimeout(async () => {
    try {
      const results = await apiRequest('GET', `/api/nutrition/search?q=${encodeURIComponent(q)}`);
      const suggest = document.getElementById(`cookedSuggest_${idx}`);
      if (!suggest) return;
      suggest.style.display = results.length ? 'block' : 'none';
      suggest.innerHTML = results.slice(0, 8).map(r => `
        <div onclick="selectCookedFood(${idx}, '${r.name.replace(/'/g,"\\'")}', ${JSON.stringify({calories_per_100g:r.calories_per_100g,protein_per_100g:r.protein_per_100g,carbs_per_100g:r.carbs_per_100g,fat_per_100g:r.fat_per_100g,fibre_per_100g:r.fibre_per_100g}).replace(/"/g,'&quot;')})"
          style="padding:10px 12px;font-size:0.85rem;color:#ddd;border-bottom:1px solid rgba(255,255,255,0.05);cursor:pointer">
          ${r.name} <span style="color:#888;font-size:0.75rem">${r.calories_per_100g} kcal/100g</span>
        </div>
      `).join('');
    } catch(e) {}
  }, 400);
}

function selectCookedFood(idx, name, nutrients) {
  document.getElementById(`cookedFood_${idx}`).value = name;
  document.getElementById(`cookedSuggest_${idx}`).style.display = 'none';
  _cookedIngredients[idx] = { food_name: name, grams: 100, nutrients_per_100g: nutrients };
}

async function submitCookedDish() {
  const name = document.getElementById('cookedDishName')?.value?.trim();
  const method = document.getElementById('cookedMethod')?.value;
  const mealType = document.getElementById('cookedMealType')?.value;
  const servingGrams = parseFloat(document.getElementById('cookedServingGrams')?.value) || null;
  const today = new Date().toISOString().split('T')[0];

  const ingredients = _cookedIngredients.filter(i => i && i.food_name && Object.keys(i.nutrients_per_100g).length > 0).map(i => ({
    food_name: i.food_name,
    grams: parseFloat(document.getElementById(`cookedGrams_${_cookedIngredients.indexOf(i)}`)?.value) || 100,
    nutrients_per_100g: i.nutrients_per_100g,
  }));

  if (!name) return showToast('Please enter a dish name', 'error');
  if (ingredients.length === 0) return showToast('Please add at least one ingredient', 'error');

  try {
    const result = await apiRequest('POST', '/api/nutrition/cooked-dish', {
      dish_name: name,
      cooking_method: method,
      ingredients,
      meal_type: mealType,
      date: today,
      serving_grams: servingGrams,
    });
    showToast(`✅ ${name} logged! ${result.macros_logged.calories} kcal`);
    haptic('success');
    closeCookedDish();
    if (typeof loadNutritionPage === 'function') loadNutritionPage();
  } catch (e) {
    showToast('Failed to log dish: ' + (e.message || 'Unknown error'), 'error');
  }
}

// ─── BUDGET MEAL SUGGESTIONS ────────────────────────────────────────────────
function openMealSuggestions() {
  const overlay = document.getElementById('mealSuggestOverlay');
  if (overlay) {
    overlay.style.display = 'block';
    document.getElementById('mealSuggestResults').innerHTML = '';
  }
}

function closeMealSuggestions() {
  document.getElementById('mealSuggestOverlay').style.display = 'none';
}

async function fetchMealSuggestions() {
  const btn = document.getElementById('suggestMealsBtn');
  const results = document.getElementById('mealSuggestResults');
  if (!results || !btn) return;

  btn.textContent = '⏳ Getting suggestions...';
  btn.disabled = true;

  try {
    const budget = document.getElementById('mealBudgetLevel')?.value || 'cheap';
    const region = document.getElementById('mealRegion')?.value || 'Central Asia';
    const data = await apiRequest('POST', '/api/nutrition/suggest-meals', { budget_level: budget, region_hint: region });

    results.innerHTML = `
      <div style="margin-bottom:12px;color:#888;font-size:0.85rem">Estimated daily cost: ${data.daily_cost_estimate || 'N/A'}</div>
      ${(data.meals || []).map(meal => `
        <div style="background:rgba(255,255,255,0.04);border-radius:14px;padding:14px;margin-bottom:10px;border:1px solid rgba(255,255,255,0.06)">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span style="font-weight:700;color:#fff">${meal.name}</span>
            <span style="font-size:0.75rem;color:#888;background:rgba(255,255,255,0.05);padding:2px 8px;border-radius:8px">${meal.meal_type}</span>
          </div>
          <div style="font-size:0.8rem;color:#888;margin-bottom:8px">${(meal.ingredients||[]).map(i => `${i.item} ${i.amount}`).join(' · ')}</div>
          <div style="display:flex;gap:12px;font-size:0.8rem">
            <span style="color:#fff">🔥 ${meal.macros?.calories || 0} kcal</span>
            <span style="color:var(--blue)">🥩 ${meal.macros?.protein_g || 0}g</span>
            <span style="color:var(--orange)">🍚 ${meal.macros?.carbs_g || 0}g</span>
            <span style="color:#888">⏱ ${meal.prep_time_min || '?'} min</span>
          </div>
        </div>
      `).join('')}
      ${data.shopping_tips?.length ? `
        <div style="background:rgba(255,193,7,0.1);border-left:3px solid #ffc107;border-radius:8px;padding:12px;margin-top:8px">
          <div style="font-weight:600;color:#ffc107;margin-bottom:6px">💡 Shopping Tips</div>
          ${data.shopping_tips.map(tip => `<div style="color:#ddd;font-size:0.82rem;margin-bottom:4px">• ${tip}</div>`).join('')}
        </div>
      ` : ''}
    `;
  } catch (e) {
    results.innerHTML = '<p style="color:#f66;text-align:center">Could not get suggestions. Check your AI key.</p>';
  }

  btn.textContent = 'Get AI Suggestions';
  btn.disabled = false;
}

// ─── EXERCISE TIMER INTEGRATION ─────────────────────────────────────────────
// Called when user taps a gym task's Start button
function openExerciseTimer(taskId, exerciseName, exerciseType, totalSets, restSeconds, targetReps) {
  const today = new Date().toISOString().split('T')[0];
  ExerciseTimer.open({
    taskId: taskId || null,
    exerciseName: exerciseName || 'Exercise',
    exerciseType: exerciseType || 'compound',
    totalSets: totalSets || 3,
    restSeconds: restSeconds || 90,
    targetReps: targetReps || '10',
    date: today,
  });
}
